import hashlib

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.huella import (
    TROZO,
    algoritmo_de,
    coincide,
    huellas_de_archivo,
    huellas_de_bytes,
)
from navaja.errores import NavajaError

runner = CliRunner()


def test_huellas_de_un_archivo_grande_por_trozos(tmp_path):
    datos = b"navaja" * (TROZO // 3)  # más de un trozo
    ruta = tmp_path / "grande.bin"
    ruta.write_bytes(datos)
    leidos = []
    huellas = huellas_de_archivo(ruta, leidos.append)
    assert huellas == {
        "md5": hashlib.md5(datos).hexdigest(),
        "sha1": hashlib.sha1(datos).hexdigest(),
        "sha256": hashlib.sha256(datos).hexdigest(),
    }
    assert sum(leidos) == len(datos) and len(leidos) == 2


def test_algoritmo_por_largo():
    assert algoritmo_de("a" * 32) == "md5"
    assert algoritmo_de("A" * 40) == "sha1"
    assert algoritmo_de(" " + "0" * 64 + " ") == "sha256"
    for mala in ("xyz", "g" * 32, "a" * 33):
        with pytest.raises(NavajaError):
            algoritmo_de(mala)


def test_coincide_sin_mirar_mayusculas():
    huellas = huellas_de_bytes(b"hola")
    assert coincide(huellas, huellas["sha256"].upper()) == ("sha256", True)
    assert coincide(huellas, "0" * 32) == ("md5", False)


def test_orden_archivo_y_compara(tmp_path):
    ruta = tmp_path / "descarga.iso"
    ruta.write_bytes(b"contenido")
    buena = hashlib.sha256(b"contenido").hexdigest()
    salida = runner.invoke(app, ["hash", "archivo", str(ruta), "--compara", buena])
    assert salida.exit_code == 0 and "Coincide" in salida.output
    salida = runner.invoke(app, ["hash", "archivo", str(ruta), "-c", "0" * 64])
    assert salida.exit_code == 1 and "No coincide" in salida.output


def test_orden_texto_y_errores(tmp_path):
    salida = runner.invoke(app, ["hash", "texto", "hola"])
    assert salida.exit_code == 0 and hashlib.md5(b"hola").hexdigest() in salida.output
    salida = runner.invoke(app, ["hash", "archivo", str(tmp_path / "no.iso")])
    assert salida.exit_code == 1 and "No existe" in salida.output
