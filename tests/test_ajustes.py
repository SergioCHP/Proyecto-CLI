import json

from typer.testing import CliRunner

import pytest

from navaja.app import app, resumen_comandos, saludo
from navaja.comandos.ajustes import preguntar_nombre
from navaja.comun import (
    CONFIG_POR_DEFECTO,
    TEMAS,
    cargar_config,
    guardar_config,
    usuario_del_sistema,
)

runner = CliRunner()


def test_saludo_segun_hora():
    assert saludo(8, "Ana") == "Buenos días, Ana"
    assert saludo(14, "Ana") == "Buenas tardes, Ana"
    assert saludo(21, "Ana") == "Buenas noches, Ana"
    assert saludo(3, "Ana") == "Buenas noches, Ana"
    assert saludo(8, "") == "Buenos días"


def test_config_por_defecto_si_no_existe(tmp_path):
    assert cargar_config(tmp_path / "config.json") == CONFIG_POR_DEFECTO


def test_config_ignora_valores_invalidos(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps({"nombre": "  ", "tema": "inventado", "otra": 1}))
    assert cargar_config(ruta) == CONFIG_POR_DEFECTO

    ruta.write_text("esto no es json")
    assert cargar_config(ruta) == CONFIG_POR_DEFECTO


def test_config_se_guarda_y_se_lee(tmp_path):
    ruta = tmp_path / "config.json"
    guardar_config({"nombre": "Lucía", "tema": "pastel"}, ruta)
    assert cargar_config(ruta) == {"nombre": "Lucía", "tema": "pastel"}


def test_todos_los_temas_definen_los_mismos_estilos():
    estilos = set(TEMAS["clasico"])
    for nombre, tema in TEMAS.items():
        assert set(tema) == estilos, nombre


def test_resumen_incluye_todos_los_comandos():
    nombres = [nombre for nombre, _ in resumen_comandos(app)]
    for esperado in ("listar", "ocupa", "limpia", "ordena", "duplicados", "notas", "tema", "config"):
        assert esperado in nombres


def test_sin_argumentos_muestra_bienvenida(monkeypatch):
    monkeypatch.setattr("getpass.getuser", lambda: "lucia")
    resultado = runner.invoke(app, [])
    assert resultado.exit_code == 0, resultado.output
    assert "Lucia" in resultado.output  # sin nombre guardado, el usuario del sistema
    assert "duplicados" in resultado.output


def test_elegir_tema_y_nombre_desde_la_cli():
    assert runner.invoke(app, ["tema", "elegir", "Morado"]).exit_code == 0
    assert runner.invoke(app, ["config", "nombre", "[Sergio]"]).exit_code == 0
    assert cargar_config() == {"nombre": "[Sergio]", "tema": "morado"}

    resultado = runner.invoke(app, [])
    assert "[Sergio]" in resultado.output

    assert runner.invoke(app, ["tema", "elegir", "inventado"]).exit_code == 1


def lector(*lineas):
    pendientes = iter(lineas)

    def leer(_prompt):
        try:
            return next(pendientes)
        except StopIteration:
            raise EOFError from None

    return leer


def test_usuario_del_sistema_con_mayuscula(monkeypatch):
    monkeypatch.setattr("getpass.getuser", lambda: "sergi")
    assert usuario_del_sistema() == "Sergi"


@pytest.mark.parametrize("respuesta, guardado", [("", "Sergi"), ("  Sergio ", "Sergio")])
def test_la_primera_vez_pregunta_como_llamarte_y_lo_guarda(monkeypatch, respuesta, guardado):
    monkeypatch.setattr("getpass.getuser", lambda: "sergi")
    assert cargar_config()["nombre"] == ""  # todavía no hay nombre: es la primera vez
    assert preguntar_nombre(lector(respuesta)) == guardado
    assert cargar_config()["nombre"] == guardado


def test_si_se_cancela_la_primera_pregunta_no_se_guarda(monkeypatch):
    monkeypatch.setattr("getpass.getuser", lambda: "sergi")
    assert preguntar_nombre(lector()) == "Sergi"  # Ctrl+D: usa el usuario
    assert cargar_config()["nombre"] == ""  # y la próxima vez lo vuelve a preguntar


def test_config_ver_dice_si_es_tu_usuario(monkeypatch):
    monkeypatch.setattr("getpass.getuser", lambda: "sergi")
    texto = " ".join(runner.invoke(app, ["config", "ver"]).output.split())
    assert "Nombre: Sergi (tu usuario del sistema" in texto
    runner.invoke(app, ["config", "nombre", "Sergio"])
    texto = runner.invoke(app, ["config", "ver"]).output
    assert "Nombre: Sergio" in texto and "tu usuario" not in texto
