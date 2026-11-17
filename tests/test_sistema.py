import sys
from collections import namedtuple

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import sistema

runner = CliRunner()

Particion = namedtuple("Particion", "device mountpoint fstype opts")


def test_barra_y_colores():
    assert sistema.barra(0, ancho=10) == "[ok][/][pista]░░░░░░░░░░[/]   0 %"
    assert sistema.barra(50, ancho=10).startswith("[ok]█████[/]")
    assert sistema.barra(75, ancho=4).startswith("[aviso]")
    assert sistema.barra(95, ancho=4).startswith("[error]")
    assert sistema.barra(150, ancho=4) == "[error]████[/][pista][/] 100 %"
    assert sistema.barra(30, ancho=10, utf8=False).startswith("[ok]###[/][pista]-------")
    assert sistema.nivel(15, invertido=True) == "aviso" and sistema.nivel(5, invertido=True) == "error"


@pytest.mark.parametrize(
    ("segundos", "texto"),
    [(30, "menos de 1 min"), (60, "1 min"), (3600, "1 h"), (3660, "1 h 1 min"),
     (90061, "1 día 1 h 1 min"), (2 * 86400, "2 días")],
)
def test_tiempo_encendido(segundos, texto):
    assert sistema.tiempo_encendido(segundos) == texto


def test_juntar_programas_suma_y_reparte_la_cpu():
    procesos = [("chrome.exe", 40.0, 100), ("Chrome.exe", 40.0, 200), ("code.exe", 8.0, 50), ("raro", None, None)]
    programas = {p.nombre.lower(): p for p in sistema.juntar_programas(procesos, nucleos=8)}
    chrome = programas["chrome.exe"]
    assert chrome.procesos == 2 and chrome.cpu == pytest.approx(10.0) and chrome.memoria == 300
    assert programas["raro"].cpu == 0 and programas["raro"].memoria == 0


def test_los_que_mas():
    programas = [
        sistema.Programa("a", 1, 5.0, 10), sistema.Programa("b", 1, 1.0, 900), sistema.Programa("c", 1, 9.0, 1),
    ]
    assert [p.nombre for p in sistema.los_que_mas(programas, sistema.Orden.cpu, 2)] == ["c", "a"]
    assert [p.nombre for p in sistema.los_que_mas(programas, sistema.Orden.memoria, 1)] == ["b"]


@pytest.mark.parametrize(
    ("particion", "si"),
    [
        (Particion("C:\\", "C:\\", "NTFS", "rw,fixed"), True),
        (Particion("D:\\", "D:\\", "", "cdrom"), False),
        (Particion("/dev/loop3", "/snap/core/1", "squashfs", "ro"), False),
        (Particion("/dev/sda1", "/", "ext4", "rw"), True),
        (Particion("tmpfs", "/run", "tmpfs", "rw"), False),
    ],
)
def test_es_disco(particion, si):
    assert sistema.es_disco(particion) is si


def test_texto_de_la_bateria():
    assert sistema.texto_bateria(100, True, None) == "enchufado"
    assert sistema.texto_bateria(60, True, None) == "cargando"
    assert sistema.texto_bateria(45, False, 7800) == "quedan 2 h 10 min"
    assert sistema.texto_bateria(45, False, None) == "con batería"


def test_orden_sistema_una_vez():
    pytest.importorskip("psutil")
    resultado = runner.invoke(app, ["sistema", "--una-vez", "-n", "3"])
    assert resultado.exit_code == 0, resultado.output
    for texto in ("CPU", "Memoria", "Encendido", "Lo que más CPU gasta", "Programa"):
        assert texto in resultado.output
    resultado = runner.invoke(app, ["sistema", "--una-vez", "--orden", "memoria"])
    assert "Lo que más memoria gasta" in resultado.output


def test_sin_terminal_lo_enseña_una_vez():
    """En una tubería («navaja sistema > a.txt») no se queda esperando a Ctrl+C."""
    pytest.importorskip("psutil")
    resultado = runner.invoke(app, ["sistema"])
    assert resultado.exit_code == 0 and resultado.output.count("navaja · sistema") == 1
    assert "Ctrl+C" not in resultado.output


def test_en_vivo_se_actualiza_hasta_ctrl_c(monkeypatch):
    pytest.importorskip("psutil")
    monkeypatch.setattr(type(sistema.console), "is_terminal", property(lambda self: True))
    vueltas = []

    def dormir(segundos):
        vueltas.append(segundos)
        if len(vueltas) >= 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(sistema.time, "sleep", dormir)
    resultado = runner.invoke(app, ["sistema", "--cada", "1"])
    assert resultado.exit_code == 0, resultado.output
    assert vueltas == [sistema.ESPERA_PRIMERA, 1, 1]
    assert "Hasta luego" in resultado.output


def test_sin_psutil_dice_como_instalarlo(monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)  # import psutil → ImportError
    for orden in (["sistema", "--una-vez"], ["red"], ["puertos"]):
        resultado = runner.invoke(app, orden)
        assert resultado.exit_code == 1, orden
        assert "psutil" in resultado.output and "uv tool install" in resultado.output
