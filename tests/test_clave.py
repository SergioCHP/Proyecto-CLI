import string

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.clave import (
    PALABRAS,
    SIMBOLOS,
    bits_de_frase,
    frase,
    largo_util,
    medir,
    nueva,
    tiempo_para,
)

runner = CliRunner()


@pytest.mark.parametrize("largo", [4, 8, 16, 64])
def test_nueva_lleva_de_todo(largo):
    for _ in range(50):
        clave = nueva(largo)
        assert len(clave) == largo
        assert any(c.islower() for c in clave) and any(c.isupper() for c in clave)
        assert any(c.isdigit() for c in clave) and any(c in SIMBOLOS for c in clave)


def test_nueva_sin_simbolos():
    clave = nueva(20, simbolos=False)
    assert all(c in string.ascii_letters + string.digits for c in clave)


def test_frase():
    partes = frase(5, "-").split("-")
    assert len(partes) == 6 and all(p in PALABRAS for p in partes[:5]) and partes[5].isdigit()
    assert bits_de_frase(5) > 40


def test_la_lista_de_palabras_es_facil_de_escribir():
    assert len(PALABRAS) >= 300
    assert all(p.isascii() and p.isalpha() and p.islower() for p in PALABRAS)


def test_largo_util_no_cuenta_patrones_ni_palabras():
    assert largo_util("aaaaaaaa")[0] == 1
    assert largo_util("12345678")[0] == 1
    assert "patron" in largo_util("qwerty")[1]
    utiles, vistos = largo_util("casa")
    assert utiles == 1 and "palabra" in vistos
    assert largo_util("Tq9#vL2!")[0] == 8


@pytest.mark.parametrize(
    "clave, nivel",
    [
        ("123456", "muy débil"),
        ("Barcelona2026", "muy débil"),  # de las más usadas con números detrás
        ("aaaaaaaaaaaaaaaa", "muy débil"),
        ("Tq9#vL2!pX7@mR4z", "muy fuerte"),
    ],
)
def test_medir(clave, nivel):
    assert medir(clave).nivel == nivel


def test_medir_da_consejos():
    consejos = " ".join(medir("gato").consejos)
    assert "12 caracteres" in consejos and "mayúsculas" in consejos


def test_tiempo_para():
    assert tiempo_para(10) == "al momento"
    assert tiempo_para(40) == "55 segundos"
    assert tiempo_para(200) == "más de mil millones de años"


def test_ordenes():
    salida = runner.invoke(app, ["clave", "nueva", "-l", "12", "-n", "3"])
    lineas = salida.output.split()
    assert salida.exit_code == 0 and len(lineas) == 3 and all(len(c) == 12 for c in lineas)
    salida = runner.invoke(app, ["clave", "fuerza"], input="123456\n")
    assert salida.exit_code == 0 and "muy débil" in salida.output and "123456" not in salida.output
    assert runner.invoke(app, ["clave", "frase", "-p", "4"]).output.count("-") == 4
