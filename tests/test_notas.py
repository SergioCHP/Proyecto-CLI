from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.notas import _normalizar_etiquetas

runner = CliRunner()


def test_normalizar_etiquetas():
    assert _normalizar_etiquetas(["Python", "#Docs, python", "  "]) == [
        "python",
        "docs",
    ]


def test_normalizar_etiquetas_vacias():
    assert _normalizar_etiquetas([]) == []
    assert _normalizar_etiquetas(["", ",", "#"]) == []


def test_agregar_un_enlace_sin_opciones_y_buscar_sin_tildes():
    assert runner.invoke(app, ["notas", "agregar", "Mi web", "www.ejemplo.com", "-e", "clase"]).exit_code == 0
    assert runner.invoke(app, ["notas", "agregar", "Apunte", "Hola árbol"]).exit_code == 0
    listado = runner.invoke(app, ["notas", "listar"]).output
    assert "enlace" in listado and "https://www.ejemplo.com" in listado
    encontrado = runner.invoke(app, ["notas", "buscar", "ARBOL"]).output
    assert "Apunte" in encontrado and "Mi web" not in encontrado
    assert "Ninguna nota lleva «xyz»" in runner.invoke(app, ["notas", "buscar", "xyz"]).output


def test_abrir_una_nota_que_no_existe_dice_donde_mirar():
    resultado = runner.invoke(app, ["notas", "abrir", "99"])
    assert resultado.exit_code == 1
    assert "No hay ninguna nota con el número 99" in resultado.output
    assert "notas listar" in resultado.output
