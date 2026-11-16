import ipaddress
import random

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.subred import (
    Nivel,
    Peticion,
    bloque_para,
    calcular,
    clase,
    con_puntos,
    corregir,
    dividir,
    ejercicio,
    leer_ip,
    leer_mascara,
    leer_peticiones,
    leer_red,
    misma_red,
    nombre_por_posicion,
    pasos,
    tipo,
    vlsm,
)
from navaja.errores import NavajaError

runner = CliRunner()


# ── Leer la IP ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texto, mascara, esperado",
    [
        ("192.168.10.200/26", "", "192.168.10.200/26"),
        ("192.168.10.200/255.255.255.192", "", "192.168.10.200/26"),
        ("192.168.10.200", "255.255.255.192", "192.168.10.200/26"),
        ("192.168.10.200", "/26", "192.168.10.200/26"),
        ("192.168.10.200 255.255.255.192", "", "192.168.10.200/26"),  # entre comillas
        ("10.0.0.5", "", "10.0.0.5/8"),  # clase A
        ("172.16.3.4", "", "172.16.3.4/16"),  # clase B
        ("192.168.1.9", "", "192.168.1.9/24"),  # clase C
        ("2001:db8::1", "", "2001:db8::1/64"),
    ],
)
def test_leer_ip(texto, mascara, esperado):
    assert leer_ip(texto, mascara) == ipaddress.ip_interface(esperado)


@pytest.mark.parametrize(
    "texto, mascara",
    [
        ("300.1.1.1", ""),
        ("hola", ""),
        ("192.168.1.1/33", ""),
        ("192.168.1.1", "255.0.255.0"),  # los unos no van seguidos
        ("192.168.1.1/24", "/24"),  # la máscara dos veces
        ("224.0.0.1", ""),  # clase D: sin máscara de clase
    ],
)
def test_leer_ip_mala_dice_por_que(texto, mascara):
    with pytest.raises(NavajaError):
        leer_ip(texto, mascara)


def test_leer_mascara():
    assert leer_mascara("255.255.248.0", 4) == 21
    assert leer_mascara("/0", 4) == 0
    assert leer_mascara("64", 6) == 64


def test_leer_red_avisa_si_se_escribe_un_equipo():
    assert leer_red("192.168.1.0/24") == (ipaddress.ip_network("192.168.1.0/24"), False)
    assert leer_red("192.168.1.77/24") == (ipaddress.ip_network("192.168.1.0/24"), True)


# ── Qué es cada IP ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ip, letra",
    [("10.1.1.1", "A"), ("127.0.0.1", "A"), ("128.0.0.1", "B"), ("191.255.0.1", "B"),
     ("192.0.0.1", "C"), ("223.1.1.1", "C"), ("224.0.0.1", "D"), ("240.0.0.1", "E"), ("::1", "—")],
)
def test_clase(ip, letra):
    assert clase(ipaddress.ip_address(ip)) == letra


@pytest.mark.parametrize(
    "ip, empieza",
    [
        ("192.168.1.1", "privada"),
        ("172.31.255.1", "privada"),
        ("172.32.0.1", "pública"),
        ("8.8.8.8", "pública"),
        ("127.0.0.1", "loopback"),
        ("169.254.10.20", "APIPA"),
        ("100.64.0.1", "compartida"),
        ("239.1.1.1", "multicast"),
        ("255.255.255.255", "difusión limitada"),
        ("fe80::1", "de enlace local"),
        ("fd00::1", "privada"),
        ("2a00:1450::1", "pública"),
    ],
)
def test_tipo(ip, empieza):
    assert tipo(ipaddress.ip_address(ip)).startswith(empieza)


def test_con_puntos():
    assert con_puntos(16777214) == "16.777.214"
    assert con_puntos(62) == "62"


# ── Calcular ───────────────────────────────────────────────────────────────


def test_calcular_el_ejemplo_de_clase():
    datos = calcular(leer_ip("192.168.10.200/26"))
    assert str(datos.red) == "192.168.10.192/26"
    assert str(datos.mascara) == "255.255.255.192"
    assert str(datos.wildcard) == "0.0.0.63"
    assert str(datos.broadcast) == "192.168.10.255"
    assert (str(datos.primero), str(datos.ultimo)) == ("192.168.10.193", "192.168.10.254")
    assert datos.hosts == 62
    assert datos.clase == "C" and datos.tipo == "privada"
    assert not datos.avisos


def test_calcular_avisa_si_la_ip_es_la_red_o_el_broadcast():
    assert "dirección de la red" in calcular(leer_ip("192.168.1.0/24")).avisos[0]
    assert "broadcast" in calcular(leer_ip("192.168.1.255/24")).avisos[0]


def test_calcular_31_y_32():
    enlace = calcular(leer_ip("10.0.0.1/31"))
    assert enlace.hosts == 2 and enlace.broadcast is None and enlace.avisos
    solo = calcular(leer_ip("10.0.0.1/32"))
    assert solo.hosts == 1 and str(solo.primero) == str(solo.ultimo) == "10.0.0.1"


def test_calcular_ipv6_sin_broadcast():
    datos = calcular(leer_ip("2001:db8::1/126"))
    assert datos.broadcast is None and datos.hosts == 4 and datos.clase == "—"


# ── Dividir y VLSM ─────────────────────────────────────────────────────────


def test_dividir_en_partes_iguales():
    subredes = dividir(ipaddress.ip_network("192.168.1.0/24"), 4)
    assert [str(s) for s in subredes] == [
        "192.168.1.0/26", "192.168.1.64/26", "192.168.1.128/26", "192.168.1.192/26"
    ]


def test_dividir_sube_a_la_siguiente_potencia_de_2():
    assert len(dividir(ipaddress.ip_network("10.0.0.0/8"), 5)) == 8


def test_dividir_imposible():
    with pytest.raises(NavajaError, match="sin equipos"):
        dividir(ipaddress.ip_network("192.168.1.0/29"), 4)  # serían /31
    with pytest.raises(NavajaError):
        dividir(ipaddress.ip_network("192.168.1.0/24"), 1)


@pytest.mark.parametrize("hosts, bloque", [(1, 4), (2, 4), (3, 8), (6, 8), (14, 16), (50, 64), (62, 64), (63, 128)])
def test_bloque_para(hosts, bloque):
    assert bloque_para(hosts) == bloque


def test_vlsm_de_mayor_a_menor_y_lo_que_queda_libre():
    repartos, libre = vlsm(ipaddress.ip_network("192.168.1.0/24"), leer_peticiones(["10", "50", "2", "20"]))
    assert [(r.peticion.nombre, str(r.red)) for r in repartos] == [
        ("B", "192.168.1.0/26"),
        ("D", "192.168.1.64/27"),
        ("A", "192.168.1.96/28"),
        ("C", "192.168.1.112/30"),
    ]
    assert [r.sobran for r in repartos] == [12, 10, 4, 0]
    assert [str(r) for r in libre] == ["192.168.1.116/30", "192.168.1.120/29", "192.168.1.128/25"]


def test_vlsm_justo_sin_libre():
    repartos, libre = vlsm(ipaddress.ip_network("192.168.1.0/24"), [Peticion("a", 126), Peticion("b", 126)])
    assert [str(r.red) for r in repartos] == ["192.168.1.0/25", "192.168.1.128/25"] and libre == []


def test_vlsm_no_cabe_y_dice_cuanto_falta():
    with pytest.raises(NavajaError, match="384 direcciones"):
        vlsm(ipaddress.ip_network("192.168.1.0/24"), [Peticion("a", 200), Peticion("b", 100)])


def test_peticiones_con_nombre():
    assert leer_peticiones(["ventas:50", "aula=20", "7"]) == [
        Peticion("ventas", 50), Peticion("aula", 20), Peticion("C", 7)
    ]
    with pytest.raises(NavajaError):
        leer_peticiones(["muchos"])
    with pytest.raises(NavajaError):
        leer_peticiones(["0"])


def test_nombre_por_posicion():
    assert [nombre_por_posicion(i) for i in (0, 1, 25, 26, 27)] == ["A", "B", "Z", "AA", "AB"]


# ── Misma red ──────────────────────────────────────────────────────────────


def test_misma_red_usa_la_mascara_de_la_primera():
    assert misma_red("192.168.1.10/24", "192.168.1.200").misma
    assert not misma_red("192.168.1.10/24", "192.168.2.5").misma
    assert misma_red("192.168.1.10/16", "192.168.2.5").misma


def test_misma_red_con_mascaras_distintas_es_a_medias():
    comparacion = misma_red("192.168.1.10/16", "192.168.2.5/24")
    assert comparacion.a_ve_a_b and not comparacion.b_ve_a_a and not comparacion.misma


def test_misma_red_ipv4_con_ipv6():
    with pytest.raises(NavajaError):
        misma_red("192.168.1.10/24", "::1/64")


# ── Práctica ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("nivel", list(Nivel))
def test_ejercicio_nunca_es_la_red_ni_el_broadcast(nivel):
    rng = random.Random(1)
    for _ in range(200):
        interfaz = ejercicio(rng, nivel)
        red = interfaz.network
        assert interfaz.ip not in (red.network_address, red.broadcast_address)
        assert interfaz.ip.is_private
        if nivel is Nivel.facil:
            assert red.prefixlen >= 25


def test_corregir():
    interfaz = ipaddress.IPv4Interface("172.16.45.130/21")
    bien = corregir(interfaz, {"mascara": "255.255.248.0", "red": "172.16.40.0", "broadcast": " 172.16.47.255", "hosts": "2.046"})
    assert all(c.bien for c in bien)
    mal = corregir(interfaz, {"mascara": "255.255.248.0", "red": "172.16.45.0", "broadcast": "nose", "hosts": ""})
    assert [c.bien for c in mal] == [True, False, False, False]
    assert mal[1].buena == "172.16.40.0" and mal[3].tuya == "—"


def test_pasos_con_el_numero_magico():
    texto = " ".join(pasos(ipaddress.IPv4Interface("172.16.45.130/21")))
    assert "255.255.248.0" in texto and "256 − 248 = 8" in texto
    assert "172.16.40.0" in texto and "172.16.47.255" in texto and "2.046" in texto


# ── Órdenes ────────────────────────────────────────────────────────────────


def test_orden_ver():
    salida = runner.invoke(app, ["subred", "ver", "192.168.10.200/26"])
    assert salida.exit_code == 0
    assert "192.168.10.192/26" in salida.output and "11000000.10101000" in salida.output


def test_orden_ver_ip_mala_sin_traza():
    salida = runner.invoke(app, ["subred", "ver", "300.1.1.1"])
    assert salida.exit_code == 1 and "no es una IP" in salida.output
    assert "Traceback" not in salida.output


def test_orden_dividir_y_vlsm():
    salida = runner.invoke(app, ["subred", "dividir", "192.168.1.0/24", "3"])
    assert salida.exit_code == 0 and "Pediste 3: salen 4" in salida.output
    salida = runner.invoke(app, ["subred", "vlsm", "192.168.1.0/24", "50", "20"])
    assert salida.exit_code == 0 and "192.168.1.64/27" in salida.output


def test_orden_misma():
    salida = runner.invoke(app, ["subred", "misma", "192.168.1.10/24", "192.168.2.5"])
    assert salida.exit_code == 0 and "redes distintas" in salida.output


def test_orden_practica_se_puede_dejar_a_medias():
    salida = runner.invoke(app, ["subred", "practica", "-n", "2"], input="255.255.255.0\n1.1.1.1\n1.1.1.1\n1\nsalir\n")
    assert salida.exit_code == 0
    assert "Ejercicio 1 de 2" in salida.output and "0 de 1 ejercicio sin fallos" in salida.output
