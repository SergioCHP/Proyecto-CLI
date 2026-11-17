import re
import sqlite3
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import estudia
from navaja.comun import directorio_datos

runner = CliRunner()
HOY = date(2026, 11, 17)


def plano(texto):
    """Sin los bordes de las tablas ni los saltos de línea: «redes 2 1 h 15 min»."""
    return " ".join(re.sub(r"[│┃┏┓┡┩└┘┌┐├┤┼╇╈━─┳┻┬┴┠┨┯┷]", " ", texto).split())

APUNTE = """# Redes

P: ¿Qué es una máscara de subred?
R: Separa los bits de red de los de host.

- P: ¿Cuántos hosts útiles tiene una /24?
- R: 254
  (256 menos red y broadcast)

P: Pregunta que ocupa
   dos líneas
R: Respuesta de
varias líneas

P: Esta no tiene respuesta
"""


@pytest.fixture(autouse=True)
def fecha_fija(monkeypatch):
    monkeypatch.setattr(estudia, "hoy", lambda: HOY)


def importar(tmp_path, texto=APUNTE, nombre="redes.md", *extra):
    archivo = tmp_path / nombre
    archivo.write_text(texto, encoding="utf-8")
    return runner.invoke(app, ["estudia", "importa", str(archivo), *extra])


def filas(sql="SELECT * FROM tarjetas ORDER BY id"):
    with sqlite3.connect(directorio_datos() / "estudia.db") as conexion:
        conexion.row_factory = sqlite3.Row
        return conexion.execute(sql).fetchall()


# ── Leer tarjetas ──────────────────────────────────────────────────────────


def test_lee_las_tarjetas_con_viñetas_y_varias_lineas():
    assert estudia.leer_tarjetas(APUNTE) == [
        ("¿Qué es una máscara de subred?", "Separa los bits de red de los de host."),
        ("¿Cuántos hosts útiles tiene una /24?", "254\n(256 menos red y broadcast)"),
        ("Pregunta que ocupa dos líneas", "Respuesta de\nvarias líneas"),
    ]  # la que no tiene respuesta se ignora


def test_p_y_r_valen_en_minuscula_y_sin_espacio():
    assert estudia.leer_tarjetas("p:uno\nr:dos") == [("uno", "dos")]


def test_texto_normal_no_son_tarjetas():
    assert estudia.leer_tarjetas("# Título\n\nUn apunte cualquiera.\nPero: no.\n") == []
    assert estudia.leer_tarjetas("R: respuesta suelta\n") == []


# ── SM-2 ───────────────────────────────────────────────────────────────────


def test_sm2_intervalos_1_6_y_luego_por_la_facilidad():
    estado = (2.5, 0, 0)
    intervalos = []
    for _ in range(4):
        estado = estudia.siguiente(*estado, 4)  # «bien»
        intervalos.append(estado[2])
    assert intervalos == [1, 6, 15, 38]  # 6 × 2,5 = 15; 15 × 2,5 = 37,5 → 38
    assert estado[0] == pytest.approx(2.5)  # «bien» no cambia la facilidad


def test_sm2_facil_sube_y_difícil_baja_la_facilidad():
    assert estudia.siguiente(2.5, 2, 6, 5)[0] == pytest.approx(2.6)
    assert estudia.siguiente(2.5, 2, 6, 3)[0] == pytest.approx(2.36)
    assert estudia.siguiente(1.3, 2, 6, 3)[0] == 1.3  # nunca por debajo de 1,3


def test_sm2_fallar_vuelve_a_empezar_sin_tocar_la_facilidad():
    assert estudia.siguiente(2.2, 5, 40, 1) == (2.2, 0, 1)


# ── importa ────────────────────────────────────────────────────────────────


def test_importa_guarda_las_nuevas_y_no_repite(tmp_path):
    resultado = importar(tmp_path, APUNTE, "redes.md", "-a", "redes")
    assert resultado.exit_code == 0, resultado.output
    assert "3 nuevas" in resultado.output
    assert [f["asignatura"] for f in filas()] == ["redes"] * 3
    assert all(f["proxima"] == HOY.isoformat() for f in filas())

    otra_vez = importar(tmp_path, APUNTE, "redes.md", "-a", "redes")
    assert "0 nuevas" in otra_vez.output and "3 que ya estaban" in otra_vez.output
    assert len(filas()) == 3


def test_si_cambia_la_respuesta_se_actualiza_sin_perder_lo_aprendido(tmp_path):
    importar(tmp_path, "P: ¿Puerto de SSH?\nR: 21\n")
    runner.invoke(app, ["estudia", "repasa"], input="\n3\n")
    antes = filas()[0]
    assert antes["repeticiones"] == 1
    resultado = importar(tmp_path, "P: ¿Puerto de SSH?\nR: 22\n")
    assert "1 con la respuesta cambiada" in resultado.output
    despues = filas()[0]
    assert despues["respuesta"] == "22"
    assert (despues["repeticiones"], despues["proxima"]) == (antes["repeticiones"], antes["proxima"])


def test_importa_una_carpeta_entera(tmp_path):
    carpeta = tmp_path / "apuntes"
    (carpeta / "sub").mkdir(parents=True)
    (carpeta / "a.md").write_text("P: uno\nR: 1\n", encoding="utf-8")
    (carpeta / "sub" / "b.md").write_text("P: dos\nR: 2\n", encoding="utf-8")
    (carpeta / "sin.md").write_text("# nada\n", encoding="utf-8")
    (carpeta / "c.txt").write_text("P: no\nR: no\n", encoding="utf-8")
    resultado = runner.invoke(app, ["estudia", "importa", str(carpeta)])
    assert resultado.exit_code == 0, resultado.output
    assert "2 nuevas" in resultado.output and "1 archivo(s) sin tarjetas" in resultado.output


def test_importa_simular_no_guarda(tmp_path):
    resultado = importar(tmp_path, APUNTE, "redes.md", "--simular")
    assert resultado.exit_code == 0, resultado.output
    assert "Simulado" in resultado.output and "3 nuevas" in resultado.output
    assert not (directorio_datos() / "estudia.db").exists() or filas() == []


def test_importa_errores_sin_traza(tmp_path):
    no_existe = runner.invoke(app, ["estudia", "importa", str(tmp_path / "nada.md")])
    assert no_existe.exit_code == 1 and "No existe" in no_existe.output
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    sin_md = runner.invoke(app, ["estudia", "importa", str(vacia)])
    assert sin_md.exit_code == 1 and "No hay archivos .md" in sin_md.output
    assert "Traceback" not in no_existe.output + sin_md.output
    sin_tarjetas = importar(tmp_path, "# solo texto\n", "texto.md")
    assert sin_tarjetas.exit_code == 0 and "No encontré ninguna tarjeta" in sin_tarjetas.output


def test_un_archivo_que_no_es_utf8_se_salta(tmp_path):
    carpeta = tmp_path / "apuntes"
    carpeta.mkdir()
    (carpeta / "mal.md").write_bytes(b"P: \xff\xfe\nR: x\n")
    (carpeta / "bien.md").write_text("P: uno\nR: 1\n", encoding="utf-8")
    resultado = runner.invoke(app, ["estudia", "importa", str(carpeta)])
    assert resultado.exit_code == 0, resultado.output
    assert "se salta" in resultado.output and "1 nuevas" in resultado.output


# ── repasa ─────────────────────────────────────────────────────────────────


def test_sin_tarjetas_explica_como_empezar():
    resultado = runner.invoke(app, ["estudia"])
    assert resultado.exit_code == 0, resultado.output
    assert "Todavía no tienes tarjetas" in resultado.output


def test_repaso_reprograma_cada_tarjeta(tmp_path):
    importar(tmp_path, "P: uno\nR: 1\n\nP: dos\nR: 2\n\nP: tres\nR: 3\n")
    # Intro + nota: uno «bien» (3), dos «fácil» (4), tres «difícil» (2)
    resultado = runner.invoke(app, ["estudia"], input="\n3\n\n4\n\n2\n")
    assert resultado.exit_code == 0, resultado.output
    assert "Repasadas 3" in resultado.output
    por_pregunta = {f["pregunta"]: f for f in filas()}
    assert por_pregunta["uno"]["intervalo"] == 1 and por_pregunta["uno"]["proxima"] == "2026-11-18"
    assert por_pregunta["dos"]["facilidad"] == pytest.approx(2.6)
    assert por_pregunta["tres"]["facilidad"] == pytest.approx(2.36)
    assert len(filas("SELECT * FROM repasos")) == 3

    de_nuevo = runner.invoke(app, ["estudia"])
    assert "No te toca repasar nada hoy" in de_nuevo.output


def test_una_tarjeta_fallada_vuelve_en_la_misma_sesion(tmp_path):
    importar(tmp_path, "P: uno\nR: 1\n")
    resultado = runner.invoke(app, ["estudia"], input="\n1\n\n3\n")  # falla, y luego «bien»
    assert resultado.exit_code == 0, resultado.output
    assert "Repasadas 2" in resultado.output and "1 bien, 1 por repetir" in resultado.output
    tarjeta = filas()[0]
    assert (tarjeta["repeticiones"], tarjeta["intervalo"]) == (1, 1)


def test_salir_deja_las_demas_para_otro_dia(tmp_path):
    importar(tmp_path, "P: uno\nR: 1\n\nP: dos\nR: 2\n")
    resultado = runner.invoke(app, ["estudia"], input="\n3\n\ns\n")
    assert "Repasadas 1" in resultado.output
    assert [f["proxima"] for f in filas()] == ["2026-11-18", "2026-11-17"]


def test_si_se_acaba_la_entrada_no_falla(tmp_path):
    importar(tmp_path, "P: uno\nR: 1\n")
    resultado = runner.invoke(app, ["estudia", "repasa"], input="")
    assert resultado.exit_code == 0, resultado.output
    assert "Repasadas 0" in resultado.output and "Traceback" not in resultado.output


def test_limite_y_asignatura(tmp_path):
    importar(tmp_path, "P: uno\nR: 1\n\nP: dos\nR: 2\n", "redes.md", "-a", "redes")
    importar(tmp_path, "P: tres\nR: 3\n", "bd.md", "-a", "bd")
    uno = runner.invoke(app, ["estudia", "repasa", "-n", "1"], input="s\n\n")
    assert "1 tarjeta." in uno.output
    solo_bd = runner.invoke(app, ["estudia", "repasa", "-a", "BD"], input="\ns\n")
    assert "tres" in solo_bd.output and "uno" not in solo_bd.output


def test_el_texto_de_una_tarjeta_con_corchetes_no_rompe_el_markup(tmp_path):
    importar(tmp_path, "P: ¿Qué hace [bold]?\nR: [/] nada\n")
    resultado = runner.invoke(app, ["estudia"], input="\ns\n")
    assert resultado.exit_code == 0, resultado.output
    assert "[bold]" in resultado.output and "nada" in resultado.output


# ── estadísticas ───────────────────────────────────────────────────────────


def test_estadisticas_sin_tarjetas():
    assert "Todavía no tienes tarjetas" in runner.invoke(app, ["estudia", "estadisticas"]).output


def test_estadisticas_cuenta_pendientes_y_racha(tmp_path):
    importar(tmp_path, "P: uno\nR: 1\n\nP: dos\nR: 2\n", "redes.md", "-a", "redes")
    runner.invoke(app, ["estudia"], input="\n3\ns\n")
    texto = plano(runner.invoke(app, ["estudia", "estadisticas"]).output)
    assert "Tarjetas 2" in texto and "Te tocan hoy 1" in texto
    assert "Sin estudiar aún 1" in texto and "Repasadas hoy 1" in texto
    assert "Racha 1 día seguido" in texto
    assert "redes 2 1" in texto


def test_racha_cuenta_dias_seguidos():
    ayer = (HOY - timedelta(days=1)).isoformat()
    anteayer = (HOY - timedelta(days=2)).isoformat()
    hace_cinco = (HOY - timedelta(days=5)).isoformat()
    assert estudia._racha([]) == 0
    assert estudia._racha([HOY.isoformat(), ayer, anteayer, hace_cinco]) == 3
    assert estudia._racha([ayer, anteayer]) == 2  # hoy aún no repasaste: no se pierde
    assert estudia._racha([anteayer]) == 0  # se cortó
