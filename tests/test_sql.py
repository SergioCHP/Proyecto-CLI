import sqlite3

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import sql

runner = CliRunner()


@pytest.fixture
def base(tmp_path):
    ruta = tmp_path / "clase.db"
    with sqlite3.connect(ruta) as conexion:
        conexion.executescript(
            """
            CREATE TABLE alumnos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, nota REAL);
            INSERT INTO alumnos (nombre, nota) VALUES ('Ana', 8.5), ('Luis', 4), ('[bold]Eva', NULL);
            CREATE VIEW aprobados AS SELECT * FROM alumnos WHERE nota >= 5;
            """
        )
    conexion.close()
    return ruta


def filas(ruta, consulta="SELECT nombre FROM alumnos ORDER BY id"):
    with sqlite3.connect(ruta) as conexion:
        resultado = conexion.execute(consulta).fetchall()
    conexion.close()
    return resultado


def test_partir_respeta_los_puntos_y_coma_entre_comillas():
    texto = "-- comentario\nSELECT 'a;b';\nINSERT INTO t VALUES (1);\n\n;  \nSELECT 2"
    assert sql.partir(texto) == ["SELECT 'a;b';", "INSERT INTO t VALUES (1);", "SELECT 2"]


def test_solo_lee():
    assert sql.solo_lee(["select * from t", "  WITH x AS (SELECT 1) SELECT * FROM x"])
    assert not sql.solo_lee(["SELECT 1", "DELETE FROM t"])


def test_sin_consulta_enseña_las_tablas(base):
    resultado = runner.invoke(app, ["sql", str(base)])
    assert resultado.exit_code == 0, resultado.output
    texto = " ".join(resultado.output.split())
    assert "alumnos · tabla · 3 filas" in texto
    assert "aprobados · vista · 1 fila" in texto
    assert "clave" in texto and "obligatoria" in texto


def test_select_en_tabla_con_null_y_corchetes(base):
    resultado = runner.invoke(app, ["sql", str(base), "SELECT nombre, nota FROM alumnos ORDER BY id"])
    assert resultado.exit_code == 0, resultado.output
    assert "Ana" in resultado.output and "8.5" in resultado.output
    assert "NULL" in resultado.output and "[bold]Eva" in resultado.output
    assert "3 filas" in resultado.output


def test_limite(base):
    resultado = runner.invoke(app, ["sql", str(base), "SELECT * FROM alumnos", "-n", "2"])
    assert "Solo las 2 primeras" in resultado.output and "Eva" not in resultado.output


def test_csv_guarda_todo_y_no_pisa(base, tmp_path):
    destino = tmp_path / "notas.csv"
    destino.write_text("mío", encoding="utf-8")
    resultado = runner.invoke(app, ["sql", str(base), "SELECT * FROM alumnos", "--csv", str(destino)])
    assert resultado.exit_code == 0, resultado.output
    assert destino.read_text(encoding="utf-8") == "mío"
    texto = (tmp_path / "notas (1).csv").read_text(encoding="utf-8-sig")
    assert texto.splitlines()[0] == "id;nombre;nota" and len(texto.splitlines()) == 4


def test_un_cambio_pregunta_y_con_no_no_hace_nada(base):
    resultado = runner.invoke(app, ["sql", str(base), "DELETE FROM alumnos WHERE nota < 5"], input="n\n")
    assert "DELETE FROM alumnos" in resultado.output and "Cancelado" in resultado.output
    assert len(filas(base)) == 3


def test_un_cambio_con_si_hace_copia_antes(base):
    resultado = runner.invoke(app, ["sql", str(base), "UPDATE alumnos SET nota = 5 WHERE nombre = 'Luis'", "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert "1 fila cambiada" in resultado.output and "Copia de antes" in resultado.output
    assert filas(base, "SELECT nota FROM alumnos WHERE nombre = 'Luis'") == [(5.0,)]
    copias = list(sql.carpeta_copias().glob("clase-*.db"))
    assert len(copias) == 1
    assert filas(copias[0], "SELECT nota FROM alumnos WHERE nombre = 'Luis'") == [(4.0,)]


def test_solo_se_guardan_las_ultimas_copias(base, monkeypatch):
    for numero in range(sql.COPIAS + 2):
        runner.invoke(app, ["sql", str(base), f"INSERT INTO alumnos (nombre) VALUES ('n{numero}')", "--si"])
    assert len(list(sql.carpeta_copias().glob("clase-*"))) == sql.COPIAS


def test_simular_prueba_y_deshace(base):
    resultado = runner.invoke(app, ["sql", str(base), "DELETE FROM alumnos", "--simular"])
    assert resultado.exit_code == 0, resultado.output
    assert "cambiaría 3 filas" in resultado.output
    assert len(filas(base)) == 3
    assert not sql.carpeta_copias().exists()


def test_si_una_sentencia_falla_no_se_hace_ninguna(base):
    script = "INSERT INTO alumnos (nombre) VALUES ('Nuevo'); INSERT INTO no_existe VALUES (1);"
    resultado = runner.invoke(app, ["sql", str(base), script, "--si"])
    assert resultado.exit_code == 1
    assert "Error de SQL" in resultado.output and "no_existe" in resultado.output
    assert ("Nuevo",) not in filas(base)


def test_archivo_y_crear_una_base_nueva(tmp_path):
    script = tmp_path / "datos.sql"
    script.write_text(
        "CREATE TABLE t (id INTEGER, texto TEXT);\nINSERT INTO t VALUES (1, 'uno; dos');\n", encoding="utf-8"
    )
    nueva = tmp_path / "nueva.db"
    sin_crear = runner.invoke(app, ["sql", str(nueva), "-a", str(script), "--si"])
    assert sin_crear.exit_code == 1 and "--crear" in sin_crear.output
    assert not nueva.exists()
    resultado = runner.invoke(app, ["sql", str(nueva), "-a", str(script), "--crear", "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert filas(nueva, "SELECT texto FROM t") == [("uno; dos",)]


def test_falsos_y_sql_juntos(tmp_path):
    pytest.importorskip("faker")
    datos = tmp_path / "personas.sql"
    assert runner.invoke(app, ["falsos", "-n", "25", "-f", "sql", "-g", str(datos)]).exit_code == 0
    base = tmp_path / "clase.db"
    assert runner.invoke(app, ["sql", str(base), "-a", str(datos), "--crear", "--si"]).exit_code == 0
    assert filas(base, "SELECT COUNT(*) FROM personas") == [(25,)]


@pytest.mark.parametrize(
    "argumentos, mensaje",
    [
        (["nada.db"], "No existe"),
        (["texto.txt"], "no es una base SQLite"),
        (["clase.db", "SELEC * FROM alumnos"], "Error de SQL"),
        (["clase.db", "  ;  "], "está vacía"),
        (["clase.db", "DELETE FROM alumnos", "--csv", "x.csv"], "--csv es para"),
        (["clase.db", "SELECT 1", "-a", "datos.sql"], "no las dos"),
    ],
)
def test_errores_sin_traza(base, tmp_path, argumentos, mensaje):
    (tmp_path / "texto.txt").write_text("hola, no soy una base de datos" * 50, encoding="utf-8")
    argumentos = [str(tmp_path / a) if a.endswith((".db", ".txt", ".sql", ".csv")) else a for a in argumentos]
    resultado = runner.invoke(app, ["sql", *argumentos])
    assert resultado.exit_code == 1, resultado.output
    assert mensaje in resultado.output and "Traceback" not in resultado.output


def test_una_consulta_de_lectura_no_puede_cambiar_nada(base):
    # Empieza por WITH (parece lectura), pero borra: se abre en solo lectura y falla
    resultado = runner.invoke(app, ["sql", str(base), "WITH x AS (SELECT 1) DELETE FROM alumnos"])
    assert resultado.exit_code == 1
    assert "intenta cambiar la base" in resultado.output
    assert len(filas(base)) == 3


def test_no_crea_la_base_por_mirar(tmp_path):
    runner.invoke(app, ["sql", str(tmp_path / "nueva.db"), "SELECT 1"])
    assert not (tmp_path / "nueva.db").exists()
