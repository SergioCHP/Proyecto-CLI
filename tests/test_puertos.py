import os
import socket
import subprocess
import sys
import time
from collections import namedtuple

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import puertos
from navaja.errores import NavajaError

runner = CliRunner()

Dir = namedtuple("Dir", "ip port")
Conexion = namedtuple("Conexion", "fd family type laddr raddr status pid")
TCP, UDP = socket.SOCK_STREAM, socket.SOCK_DGRAM


def _conexiones():
    return [
        Conexion(-1, socket.AF_INET, TCP, Dir("0.0.0.0", 8000), (), "LISTEN", 500),
        Conexion(-1, socket.AF_INET6, TCP, Dir("::", 8000), (), "LISTEN", 500),
        Conexion(-1, socket.AF_INET, TCP, Dir("127.0.0.1", 5432), (), "LISTEN", 77),
        Conexion(-1, socket.AF_INET, TCP, Dir("192.168.1.34", 51000), Dir("1.1.1.1", 443), "ESTABLISHED", 900),
        Conexion(-1, socket.AF_INET, UDP, Dir("0.0.0.0", 5353), (), "NONE", 300),
        Conexion(-1, socket.AF_INET, TCP, Dir("0.0.0.0", 135), (), "LISTEN", None),
    ]


def test_escuchas_junta_ipv4_e_ipv6_y_se_salta_las_conexiones():
    lista = puertos.escuchas(_conexiones())
    assert [(e.puerto, e.protocolo) for e in lista] == [(135, "TCP"), (5432, "TCP"), (8000, "TCP")]
    ocho_mil = lista[-1]
    assert ocho_mil.direcciones == {"0.0.0.0", "::"} and ocho_mil.pid == 500


def test_escuchas_udp_y_un_puerto():
    assert (5353, "UDP") in [(e.puerto, e.protocolo) for e in puertos.escuchas(_conexiones(), udp=True)]
    assert [e.protocolo for e in puertos.escuchas(_conexiones(), puerto=5353)] == ["UDP"]  # con puerto, también UDP
    assert puertos.escuchas(_conexiones(), puerto=9999) == []


def test_desde_donde_y_para_que():
    assert puertos.Escucha(80, "TCP", 1, {"0.0.0.0"}).desde == "toda la red"
    assert puertos.Escucha(80, "TCP", 1, {"127.0.0.1", "::1"}).desde == "solo este PC"
    assert puertos.Escucha(80, "TCP", 1, {"192.168.1.34"}).desde == "192.168.1.34"
    assert puertos.Escucha(3306, "TCP", 1).para_que == "MySQL / MariaDB"
    assert puertos.Escucha(12345, "TCP", 1).para_que == ""


@pytest.mark.parametrize(
    ("escucha", "motivo"),
    [
        (puertos.Escucha(135, "TCP", None), "administrador"),
        (puertos.Escucha(445, "TCP", 4, programa="System"), "sistema"),
        (puertos.Escucha(135, "TCP", 900, programa="svchost.exe"), "sistema"),
        (puertos.Escucha(1, "TCP", os.getpid(), programa="python"), "navaja misma"),
    ],
)
def test_no_cierra_lo_que_no_debe(escucha, motivo):
    with pytest.raises(NavajaError, match=motivo):
        puertos.comprobar_que_se_puede_cerrar(escucha)


def test_se_puede_cerrar_un_programa_normal():
    puertos.comprobar_que_se_puede_cerrar(puertos.Escucha(8000, "TCP", 500, programa="python.exe"))


def _falsas(udp, puerto):
    lista = puertos.escuchas(_conexiones(), udp, puerto)
    nombres = {500: "python.exe", 77: "postgres.exe", 300: "mdnsresponder.exe"}
    for escucha in lista:
        escucha.programa = nombres.get(escucha.pid, "")
    return lista


def test_orden_puertos(monkeypatch):
    monkeypatch.setattr(puertos, "recoger", _falsas)
    resultado = runner.invoke(app, ["puertos"])
    assert resultado.exit_code == 0
    assert "3 abiertos" in resultado.output
    assert "python.exe" in resultado.output and "Servidor de Python" in resultado.output
    assert "toda la red" in resultado.output and "solo este PC" in resultado.output
    assert "(sin permiso)" in resultado.output and "5353" not in resultado.output
    assert "5353" in runner.invoke(app, ["puertos", "--udp"]).output


def test_quien_usa_un_puerto_y_libre(monkeypatch):
    monkeypatch.setattr(puertos, "recoger", _falsas)
    resultado = runner.invoke(app, ["puertos", "8000"])
    assert resultado.exit_code == 0
    assert "python.exe" in resultado.output and "navaja puertos 8000 --cerrar" in resultado.output
    resultado = runner.invoke(app, ["puertos", "8001"])
    assert resultado.exit_code == 0 and "está libre" in resultado.output


def test_cerrar_necesita_un_puerto_valido():
    resultado = runner.invoke(app, ["puertos", "--cerrar"])
    assert resultado.exit_code == 2 and "di qué puerto" in resultado.output
    assert runner.invoke(app, ["puertos", "70000"]).exit_code == 2


def test_cerrar_simulado_y_cancelado_no_tocan_nada(monkeypatch):
    monkeypatch.setattr(puertos, "recoger", _falsas)
    cerrados = []
    monkeypatch.setattr(puertos, "cerrar", lambda psutil, escucha: cerrados.append(escucha.pid))
    pytest.importorskip("psutil")

    resultado = runner.invoke(app, ["puertos", "8000", "--cerrar", "--simular"])
    assert resultado.exit_code == 0 and "Simulación" in resultado.output
    resultado = runner.invoke(app, ["puertos", "8000", "--cerrar"], input="n\n")
    assert resultado.exit_code == 1 and "Cancelado" in resultado.output
    assert cerrados == []

    resultado = runner.invoke(app, ["puertos", "8000", "--cerrar"], input="s\n")
    assert resultado.exit_code == 0 and "queda libre" in resultado.output
    assert cerrados == [500]  # IPv4 e IPv6 son el mismo programa: se cierra una vez


def test_cerrar_un_programa_del_sistema_falla(monkeypatch):
    monkeypatch.setattr(puertos, "recoger", _falsas)
    pytest.importorskip("psutil")
    resultado = runner.invoke(app, ["puertos", "135", "--cerrar", "--si"])
    assert resultado.exit_code == 1 and "administrador" in resultado.output


def test_de_verdad_ve_y_cierra_un_servidor(tmp_path):
    """Un servidor de Python de verdad en un puerto libre: lo encuentra y lo cierra."""
    pytest.importorskip("psutil")
    with socket.socket() as hueco:
        hueco.bind(("127.0.0.1", 0))
        numero = hueco.getsockname()[1]
    servidor = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(numero), "--bind", "127.0.0.1"],
        cwd=tmp_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # En Windows, el python.exe de un .venv es un lanzador: el que escucha es su hijo
        psutil = pytest.importorskip("psutil")
        nuestros = {servidor.pid}
        escucha = None
        for _ in range(50):
            try:
                nuestros |= {h.pid for h in psutil.Process(servidor.pid).children(recursive=True)}
            except psutil.NoSuchProcess:
                pass
            escucha = next((e for e in puertos.recoger(False, numero) if e.pid in nuestros), None)
            if escucha:
                break
            time.sleep(0.1)
        assert escucha, f"nadie de los nuestros escucha en el {numero}"
        resultado = runner.invoke(app, ["puertos", str(numero)])
        assert str(escucha.pid) in resultado.output, resultado.output
        resultado = runner.invoke(app, ["puertos", str(numero), "--cerrar", "--si"])
        assert resultado.exit_code == 0, resultado.output
        assert servidor.wait(timeout=10) is not None  # cerrado el hijo, el lanzador también acaba
        assert "está libre" in runner.invoke(app, ["puertos", str(numero)]).output
    finally:
        if servidor.poll() is None:
            servidor.kill()
