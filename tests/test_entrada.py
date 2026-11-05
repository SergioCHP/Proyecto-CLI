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
