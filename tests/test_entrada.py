"""Tab y ↑/↓ en el modo interactivo (entrada.py)."""

from __future__ import annotations

import threading

import pytest
import typer
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from navaja.app import app
from navaja.entrada import crear_lector, historial, sugerencias

RAIZ = typer.main.get_command(app)


def posibles(camino, antes, palabra=""):
    nombres, rutas = sugerencias(RAIZ, camino, antes, palabra)
    return [n for n in nombres if n.lower().startswith(palabra.lower())], rutas


def test_primera_palabra_comandos_y_atajos():
    nombres, _ = posibles([], [], "")
    for esperado in ("listar", "ordena", "acciones", "manual", "cd", "salir"):
        assert esperado in nombres
    assert posibles([], [], "or") == (["ordena"], "")
    assert "version" not in nombres  # las órdenes ocultas no se sugieren


def test_subcomandos_y_opciones():
    assert "tipo" in posibles([], ["ordena"])[0]
    assert posibles([], ["nav", "acciones"])[0][:2] == ["ver", "ejecutar"]
    assert posibles([], ["ordena", "tipo"], "--si")[0] == ["--simular", "--si"]


def test_en_un_submenu_tambien_el_menu_principal():
    nombres, _ = posibles(["acciones"], [])
    assert {"ejecutar", "listar", "volver"} <= set(nombres)
    assert posibles(["acciones"], ["ejecutar"], "--c")[0] == ["--config"]


@pytest.mark.parametrize(
    ("antes", "rutas"),
    [
        (["cd"], "carpetas"),
        (["listar"], "rutas"),
        (["ordena", "tipo", "-c"], "rutas"),
        (["ordena", "tipo", "--solo"], ""),
        (["ordena", "tipo"], ""),
    ],
)
def test_cuando_se_completan_rutas(antes, rutas):
    assert posibles([], antes)[1] == rutas


def test_ayuda_y_manual_completan_comandos():
    assert posibles([], ["ayuda"], "ren")[0] == ["renombra"]
    assert "fecha" in posibles([], ["manual", "ordena"])[0]


def test_tab_completa_y_el_historial_se_guarda():
    with create_pipe_input() as entrada, create_app_session(input=entrada, output=DummyOutput()):
        lector = crear_lector(RAIZ)
        assert lector is not None
        entrada.send_text("ord\t")
        # Intro un poco después, como una persona: Tab calcula las sugerencias aparte.
        threading.Timer(0.5, entrada.send_text, args=("\r",)).start()
        assert lector.orden("> ", []).strip() == "ordena"
    # Lo escrito queda en historial.txt, y un lector nuevo (otra vez que abres navaja)
    # lo tiene para ↑. La flecha en sí no se prueba aquí: en Windows la entrada falsa
    # no entiende las teclas de cursor; se prueba a mano.
    assert "ordena" in historial().read_text(encoding="utf-8")
    with create_pipe_input() as entrada, create_app_session(input=entrada, output=DummyOutput()):
        otro = crear_lector(RAIZ)
        assert "ordena" in list(otro.menu.history.load_history_strings())


@pytest.fixture
def mis_acciones(tmp_path, monkeypatch):
    """Un acciones.json en una carpeta temporal, que pasa a ser la actual."""
    import json

    (tmp_path / "acciones.json").write_text(json.dumps({"version": 1, "acciones": [
        {"nombre": "usb-a-pc", "descripcion": "Trae al PC lo nuevo del USB de clase, con "
         "sus subcarpetas, y lo que ya está no lo copia otra vez", "tipo": "copiar", "destino": "x"},
        {"nombre": "pc-a-usb", "descripcion": "Lleva al USB", "tipo": "copiar", "destino": "y"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_tab_completa_los_nombres_de_las_acciones(mis_acciones):
    assert posibles([], ["acciones", "ejecutar"], "us") == (["usb-a-pc"], "")
    nombres, rutas = posibles(["acciones"], ["ejecutar"])
    assert {"usb-a-pc", "pc-a-usb"} <= set(nombres) and rutas == ""
    # después del nombre va la carpeta: ahí vuelven las rutas
    assert posibles([], ["acciones", "ejecutar", "usb-a-pc"])[1] == "rutas"


def test_tab_usa_el_config_que_ya_se_ha_escrito(mis_acciones, tmp_path_factory):
    import json

    otra = tmp_path_factory.mktemp("otra") / "otras.json"
    otra.write_text(json.dumps({"version": 1, "acciones": [
        {"nombre": "limpiar-usb", "descripcion": "x", "tipo": "borrar", "filtro": {"solo": "pdf"}},
    ]}), encoding="utf-8")
    assert posibles([], ["acciones", "ejecutar", "--config", str(otra)], "")[0][0] == "limpiar-usb"


def test_tab_con_un_acciones_json_roto_no_sugiere_nada(mis_acciones):
    (mis_acciones / "acciones.json").write_text("{ roto", encoding="utf-8")
    assert posibles([], ["acciones", "ejecutar"], "u") == ([], "rutas")


def test_el_tab_de_powershell_da_nombres_con_descripcion_corta(mis_acciones):
    from navaja.comandos.mis_acciones import nombres_para_tab

    ctx = typer.Context(RAIZ.commands["acciones"].commands["ejecutar"])
    nombres = nombres_para_tab(ctx, "U")  # sin mirar mayúsculas
    assert [n for n, _ in nombres] == ["usb-a-pc"]
    descripcion = nombres[0][1]
    assert len(descripcion) <= 45 and descripcion.endswith("…") and "\n" not in descripcion
