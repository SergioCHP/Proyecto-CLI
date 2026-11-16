import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.chmod import Permisos, avisos, leer_permisos, que_puede
from navaja.errores import NavajaError

runner = CliRunner()


@pytest.mark.parametrize(
    "texto, octal, letras",
    [
        ("755", "755", "rwxr-xr-x"),
        ("644", "644", "rw-r--r--"),
        ("600", "600", "rw-------"),
        ("0755", "755", "rwxr-xr-x"),
        ("4755", "4755", "rwsr-xr-x"),
        ("2750", "2750", "rwxr-s---"),
        ("1777", "1777", "rwxrwxrwt"),
        ("1776", "1776", "rwxrwxrwT"),
        ("rwxr-xr-x", "755", "rwxr-xr-x"),
        ("-rw-r--r--", "644", "rw-r--r--"),  # como sale en ls -l
        ("drwxrwxrwt", "1777", "rwxrwxrwt"),
        ("rwSr--r--", "4644", "rwSr--r--"),
    ],
)
def test_ida_y_vuelta(texto, octal, letras):
    permisos = leer_permisos(texto)
    assert permisos.octal == octal and permisos.letras == letras


@pytest.mark.parametrize("texto", ["8", "75", "789", "rwxrwx", "rwxr-xr-y", "hola"])
def test_permisos_malos(texto):
    with pytest.raises(NavajaError):
        leer_permisos(texto)


def test_que_puede():
    assert que_puede(7) == "leer, escribir y ejecutar"
    assert que_puede(5) == "leer y ejecutar"
    assert que_puede(4) == "leer"
    assert que_puede(0) == "nada"
    assert que_puede(5, carpeta=True) == "ver y entrar"


def test_avisos():
    assert any("Cualquiera" in a for a in avisos(Permisos((7, 7, 7))))
    assert any("más que el dueño" in a for a in avisos(Permisos((4, 7, 0))))
    assert avisos(Permisos((7, 5, 5))) == []


def test_orden_chmod():
    salida = runner.invoke(app, ["chmod", "755"])
    assert salida.exit_code == 0 and "rwxr-xr-x" in salida.output and "chmod 755 archivo" in salida.output
    salida = runner.invoke(app, ["chmod", "rwsr-xr-x"])
    assert "4755" in salida.output and "setuid" in salida.output
    salida = runner.invoke(app, ["chmod", "9"])
    assert salida.exit_code == 1 and "no son permisos" in salida.output
