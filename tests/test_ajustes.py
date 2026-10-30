import json

from typer.testing import CliRunner

from navaja.app import app, resumen_comandos, saludo
from navaja.comun import CONFIG_POR_DEFECTO, TEMAS, cargar_config, guardar_config

runner = CliRunner()


def test_saludo_segun_hora():
    assert saludo(8, "Ana") == "Buenos días, Ana"
    assert saludo(14, "Ana") == "Buenas tardes, Ana"
    assert saludo(21, "Ana") == "Buenas noches, Ana"
    assert saludo(3, "Ana") == "Buenas noches, Ana"


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
    for esperado in ("ocupa", "limpia", "ordena", "duplicados", "notas", "tema", "config"):
        assert esperado in nombres


def test_sin_argumentos_muestra_bienvenida():
    resultado = runner.invoke(app, [])
    assert resultado.exit_code == 0, resultado.output
    assert CONFIG_POR_DEFECTO["nombre"] in resultado.output
    assert "duplicados" in resultado.output


def test_fijar_tema_y_nombre_desde_la_cli():
    assert runner.invoke(app, ["tema", "fijar", "Morado"]).exit_code == 0
    assert runner.invoke(app, ["config", "nombre", "[Sergio]"]).exit_code == 0
    assert cargar_config() == {"nombre": "[Sergio]", "tema": "morado"}

    resultado = runner.invoke(app, [])
    assert "[Sergio]" in resultado.output

    assert runner.invoke(app, ["tema", "fijar", "inventado"]).exit_code == 1
