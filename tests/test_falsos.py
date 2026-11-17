import csv
import io
import json
import sqlite3
import sys

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import falsos
from navaja.errores import NavajaError

pytest.importorskip("faker")
runner = CliRunner()


def test_letra_del_dni():
    assert falsos.letra_dni(12345678) == "Z"
    assert falsos.letra_dni(0) == "T"
    assert falsos.dni_valido("12345678Z") and not falsos.dni_valido("12345678A")


def test_los_dni_y_emails_son_validos_y_no_se_repiten():
    filas = falsos.generar(300, ["nombre", "apellidos", "email", "dni"], semilla=1)
    assert all(falsos.dni_valido(f["dni"]) for f in filas)
    assert len({f["dni"] for f in filas}) == 300
    emails = [f["email"] for f in filas]
    assert len(set(emails)) == 300
    assert all(e.isascii() and e.count("@") == 1 and " " not in e for e in emails)


def test_misma_semilla_mismos_datos():
    campos = ["nombre", "dni", "ciudad"]
    assert falsos.generar(5, campos, 7) == falsos.generar(5, campos, 7)
    assert falsos.generar(5, campos, 7) != falsos.generar(5, campos, 8)


def test_campos_y_errores():
    assert falsos.leer_campos(None) == falsos.POR_DEFECTO
    assert falsos.leer_campos("Nombre, email,nombre,teléfono") == ["nombre", "email", "telefono"]
    with pytest.raises(NavajaError, match="No hay campo «edad»"):
        falsos.leer_campos("nombre,edad")
    with pytest.raises(NavajaError):
        falsos.leer_campos(" , ")


def test_tabla_por_defecto():
    resultado = runner.invoke(app, ["falsos", "-n", "3", "--semilla", "1"])
    assert resultado.exit_code == 0, resultado.output
    assert "dni" in resultado.output and "email" in resultado.output


def test_csv_json_y_sql_por_la_salida():
    salida = runner.invoke(app, ["falsos", "-n", "4", "-f", "csv", "-c", "id,nombre,dni"]).output
    filas = list(csv.DictReader(io.StringIO(salida), delimiter=";"))
    assert [f["id"] for f in filas] == ["1", "2", "3", "4"]

    datos = json.loads(runner.invoke(app, ["falsos", "-n", "2", "-f", "json", "-c", "id,activo,sueldo"]).output)
    assert datos[0]["id"] == 1 and isinstance(datos[0]["sueldo"], int)

    texto = runner.invoke(app, ["falsos", "-n", "3", "-f", "sql", "-t", "clientes"]).output
    conexion = sqlite3.connect(":memory:")
    conexion.executescript(texto)
    assert conexion.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 3


def test_un_apostrofe_no_rompe_el_sql():
    texto = falsos.a_sql([{"id": 1, "nombre": "D'Angelo"}], ["id", "nombre"], "personas")
    conexion = sqlite3.connect(":memory:")
    conexion.executescript(texto)
    assert conexion.execute("SELECT nombre FROM personas").fetchone()[0] == "D'Angelo"


def test_guardar_elige_el_formato_por_la_extension_y_no_pisa(tmp_path):
    destino = tmp_path / "clientes.json"
    destino.write_text("mío", encoding="utf-8")
    resultado = runner.invoke(app, ["falsos", "-n", "2", "-g", str(destino)])
    assert resultado.exit_code == 0, resultado.output
    assert destino.read_text(encoding="utf-8") == "mío"
    nuevo = tmp_path / "clientes (1).json"
    assert len(json.loads(nuevo.read_text(encoding="utf-8"))) == 2

    csv_ = tmp_path / "datos.csv"
    runner.invoke(app, ["falsos", "-n", "2", "-g", str(csv_)])
    assert csv_.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM: Excel lee bien las tildes


def test_guardar_sql_sugiere_meterlo_en_una_base(tmp_path):
    resultado = runner.invoke(app, ["falsos", "-g", str(tmp_path / "datos.sql")])
    assert "navaja sql" in resultado.output and "--crear" in resultado.output


def test_simular_no_guarda(tmp_path):
    resultado = runner.invoke(app, ["falsos", "-g", str(tmp_path / "x.csv"), "--simular"])
    assert resultado.exit_code == 0 and "Simulado" in resultado.output
    assert not (tmp_path / "x.csv").exists()


def test_lista_de_campos():
    resultado = runner.invoke(app, ["falsos", "--lista"])
    assert "nacimiento" in resultado.output and "por defecto" in resultado.output


@pytest.mark.parametrize(
    "opciones, mensaje",
    [
        (["-c", "nombre,edad"], "No hay campo"),
        (["-f", "sql", "-t", "1mala tabla"], "no vale como nombre de tabla"),
        (["-f", "csv", "--separador", ";;"], "un solo carácter"),
        (["-g", "/no/existe/x.csv"], "No existe la carpeta"),
    ],
)
def test_errores_sin_traza(opciones, mensaje):
    resultado = runner.invoke(app, ["falsos", *opciones])
    assert resultado.exit_code == 1, resultado.output
    assert mensaje in resultado.output and "Traceback" not in resultado.output


def test_sin_faker_dice_como_instalarlo(monkeypatch):
    monkeypatch.setitem(sys.modules, "faker", None)  # import faker → ImportError
    resultado = runner.invoke(app, ["falsos"])
    assert resultado.exit_code == 1
    assert "Faker" in resultado.output and "uv tool install" in resultado.output
    assert "Traceback" not in resultado.output
