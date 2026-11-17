import socket
from collections import namedtuple

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import red

runner = CliRunner()

Direccion = namedtuple("Direccion", "family address netmask broadcast ptp")
Estado = namedtuple("Estado", "isup duplex speed mtu")
AF_LINK = -1


def _tarjetas(salida="192.168.1.34", puertas=None):
    direcciones = {
        "Ethernet 2": [Direccion(socket.AF_INET, "169.254.10.3", "255.255.0.0", None, None)],
        "Wi-Fi": [
            Direccion(AF_LINK, "a4-5e-60-11-22-33", None, None, None),
            Direccion(socket.AF_INET, "192.168.1.34", "255.255.255.0", None, None),
            Direccion(socket.AF_INET6, "fe80::1%12", "ffff:ffff:ffff:ffff::", None, None),
        ],
        "vEthernet (WSL)": [Direccion(socket.AF_INET, "172.20.0.1", "255.255.240.0", None, None)],
        "Loopback Pseudo-Interface 1": [
            Direccion(socket.AF_INET, "127.0.0.1", "255.0.0.0", None, None),
            Direccion(AF_LINK, "00:00:00:00:00:00", None, None, None),
        ],
        "Bluetooth": [Direccion(AF_LINK, "11-22-33-44-55-66", None, None, None)],
    }
    estados = {
        "Ethernet 2": Estado(True, 2, 1000, 1500),
        "Wi-Fi": Estado(True, 2, 866, 1500),
        "vEthernet (WSL)": Estado(True, 2, 10000, 1500),
        "Loopback Pseudo-Interface 1": Estado(True, 0, 1073, 1500),
        "Bluetooth": Estado(False, 0, 3, 1500),
    }
    if puertas is None:
        puertas = [red.Puerta("192.168.1.1", ip_local="192.168.1.34")]
    return red.tarjetas_desde(direcciones, estados, salida, puertas, AF_LINK)


@pytest.mark.parametrize(
    ("nombre", "tipo"),
    [
        ("Wi-Fi", "Wi-Fi"), ("wlp2s0", "Wi-Fi"), ("Ethernet", "Cable"), ("eth0", "Cable"),
        ("enp3s0", "Cable"), ("lo", "Loopback"), ("Loopback Pseudo-Interface 1", "Loopback"),
        ("vEthernet (WSL)", "Virtual"), ("docker0", "Virtual"),
        ("VirtualBox Host-Only Network", "Virtual"), ("Conexión de red Bluetooth", "Bluetooth"),
    ],
)
def test_tipo_de_tarjeta(nombre, tipo):
    assert red.tipo_de_tarjeta(nombre) == tipo


def test_mascara_y_prefijo():
    assert red.con_prefijo("192.168.1.34", "255.255.255.0") == "192.168.1.34/24"
    assert red.con_prefijo("fe80::1%eth0", "ffff:ffff:ffff:ffff::") == "fe80::1/64"
    assert red.con_prefijo("10.0.0.5", None) == "10.0.0.5"
    assert red.mascara_de("172.16.5.1/20") == "255.255.240.0"
    assert red.es_apipa("169.254.10.3/16") and not red.es_apipa("192.168.1.34/24")


def test_la_principal_va_primero_con_su_router_y_su_mac():
    tarjetas = _tarjetas()
    wifi = tarjetas[0]
    assert wifi.nombre == "Wi-Fi" and wifi.principal
    assert wifi.ipv4 == ["192.168.1.34/24"] and wifi.puerta == "192.168.1.1"
    assert wifi.mac == "A4-5E-60-11-22-33" and wifi.velocidad == 866
    assert [t.nombre for t in tarjetas][-1] == "Bluetooth"  # apagada: al final
    loopback = next(t for t in tarjetas if t.tipo == "Loopback")
    assert loopback.mac == ""  # 00:00:00:00:00:00 no es una MAC


def test_un_router_sin_saber_de_que_tarjeta_va_a_la_principal():
    tarjetas = _tarjetas(puertas=[red.Puerta("192.168.1.1")])
    assert tarjetas[0].puerta == "192.168.1.1"
    assert not any(t.puerta for t in tarjetas[1:])


def test_sin_red_ninguna_es_principal():
    assert not any(t.principal for t in _tarjetas(salida=""))


def test_visibles_quita_loopback_apagadas_y_sin_ipv4():
    nombres = [t.nombre for t in red.visibles(_tarjetas(), todas=False)]
    assert nombres == ["Wi-Fi", "Ethernet 2", "vEthernet (WSL)"]
    assert len(red.visibles(_tarjetas(), todas=True)) == 5


def test_puertas_linux():
    texto = (
        "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\n"
        "wlp2s0\t00000000\t0101A8C0\t0003\t0\t0\t600\t00000000\n"
        "wlp2s0\t0001A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\n"
    )
    assert red.puertas_linux(texto) == [red.Puerta("192.168.1.1", interfaz="wlp2s0")]


def test_puertas_windows_en_cualquier_idioma():
    texto = """
IPv4 Tabla de enrutamiento
===========================================================================
Rutas activas:
Destino de red        Máscara de red   Puerta de enlace   Interfaz  Métrica
          0.0.0.0          0.0.0.0      192.168.1.1     192.168.1.34     35
          0.0.0.0          0.0.0.0         En vínculo      10.8.0.2       5
===========================================================================
"""
    assert red.puertas_windows(texto) == [red.Puerta("192.168.1.1", ip_local="192.168.1.34")]


def test_puertas_macos():
    texto = "   route to: default\ndestination: default\n    gateway: 192.168.1.1\n  interface: en0\n"
    assert red.puertas_macos(texto) == [red.Puerta("192.168.1.1", interfaz="en0")]
    assert red.puertas_macos("route: writing to routing socket: not in table\n") == []


def test_orden_red(monkeypatch):
    monkeypatch.setattr(red, "recoger", _tarjetas)
    resultado = runner.invoke(app, ["red"])
    assert resultado.exit_code == 0
    assert "Wi-Fi" in resultado.output and "sale a internet" in resultado.output
    assert "255.255.255.0" in resultado.output and "192.168.1.1" in resultado.output
    assert "APIPA" in resultado.output
    assert "navaja subred ver 192.168.1.34/24" in resultado.output
    assert "Loopback" not in resultado.output and "fe80" not in resultado.output

    resultado = runner.invoke(app, ["red", "--todas", "--ipv6"])
    assert "Loopback" in resultado.output and "fe80::1/64" in resultado.output
    assert "apagada" in resultado.output


def test_orden_red_sin_tarjetas(monkeypatch):
    monkeypatch.setattr(red, "recoger", lambda: [])
    resultado = runner.invoke(app, ["red"])
    assert resultado.exit_code == 0 and "No hay ninguna tarjeta" in resultado.output


def test_orden_red_de_verdad():
    """Con las tarjetas de este equipo: no puede fallar, haya red o no."""
    pytest.importorskip("psutil")
    resultado = runner.invoke(app, ["red", "--todas"])
    assert resultado.exit_code == 0, resultado.output
