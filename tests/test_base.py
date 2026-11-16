import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.base import (
    agrupado,
    divisiones,
    en_base,
    ip_en_binario,
    leer_numero,
    potencias,
)
from navaja.errores import NavajaError

runner = CliRunner()


@pytest.mark.parametrize(
    "texto, base, valor, leida",
    [
        ("200", None, 200, 10),
        ("0b11001000", None, 200, 2),
        ("0o310", None, 200, 8),
        ("0xC8", None, 200, 16),
        ("0xc8", None, 200, 16),
        ("C8h", None, 200, 16),
        ("c8", None, 200, 16),  # con letras: hexadecimal
        ("1100 1000", None, 11001000, 10),  # sin --de, unos y ceros son decimal
        ("1100 1000", 2, 200, 2),
        ("310", 8, 200, 8),
        ("1_000", None, 1000, 10),
    ],
)
def test_leer_numero(texto, base, valor, leida):
    numero = leer_numero(texto, base)
    assert (numero.valor, numero.base) == (valor, leida)


def test_con_letras_avisa_de_que_es_hexadecimal():
    assert "hexadecimal" in leer_numero("FF").nota
    assert leer_numero("0xFF").nota == ""


@pytest.mark.parametrize("texto, base", [("1012", 2), ("9", 8), ("G1", 16), ("hola", None), ("-5", None), ("", None), ("0x", None)])
def test_leer_numero_malo(texto, base):
    with pytest.raises(NavajaError):
        leer_numero(texto, base)


@pytest.mark.parametrize("numero, base, texto", [(0, 2, "0"), (200, 2, "11001000"), (200, 8, "310"), (200, 16, "C8"), (255, 16, "FF"), (10, 10, "10")])
def test_en_base(numero, base, texto):
    assert en_base(numero, base) == texto


def test_agrupado():
    assert agrupado("11001000") == "1100 1000"
    assert agrupado("10100") == "1 0100"
    assert agrupado("10100", rellenar=True) == "0001 0100"
    assert agrupado("11001000", 3, rellenar=True) == "011 001 000"


def test_divisiones_sucesivas():
    pasos = divisiones(13, 2)
    assert pasos == [(13, 6, 1), (6, 3, 0), (3, 1, 1), (1, 0, 1)]
    assert "".join(str(r) for _, _, r in reversed(pasos)) == "1101"
    assert divisiones(0, 2) == [(0, 0, 0)]


def test_potencias():
    assert potencias("C8", 16) == [("C", 1, 192), ("8", 0, 8)]
    assert sum(v for _, _, v in potencias("11001000", 2)) == 200


def test_ip_en_binario():
    assert ip_en_binario("192.168.1.10") == [
        (192, "11000000"), (168, "10101000"), (1, "00000001"), (10, "00001010")
    ]
    assert ip_en_binario("200") is None


def test_orden_base_ensena_las_cuatro_y_los_pasos():
    salida = runner.invoke(app, ["base", "200"])
    assert salida.exit_code == 0
    for texto in ("1100 1000", "310", "C8", "200 ÷ 2", "11001000"):
        assert texto in salida.output


def test_orden_base_a_decimal_y_atajo():
    salida = runner.invoke(app, ["base", "0xC8"])
    assert "12·16^1 + 8·16^0" in salida.output and "192 + 8 = 200" in salida.output
    salida = runner.invoke(app, ["base", "0xC8", "--a", "2"])
    assert "1100 → C" in salida.output


def test_orden_base_errores():
    salida = runner.invoke(app, ["base", "1012", "--de", "2"])
    assert salida.exit_code == 1 and "solo valen las cifras 0 y 1" in salida.output
    salida = runner.invoke(app, ["base", "10", "--de", "3"])
    assert salida.exit_code == 2


def test_orden_base_con_una_ip():
    salida = runner.invoke(app, ["base", "192.168.1.10"])
    assert salida.exit_code == 0 and "11000000.10101000.00000001.00001010" in salida.output
