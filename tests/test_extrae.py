import io
import tarfile
import zipfile
from pathlib import PurePosixPath

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.extrae import carpeta_comun, leer_contenido, planificar, ruta_segura, sin_extension
from navaja.errores import NavajaError

runner = CliRunner()


def crear_zip(ruta, contenido):
    with zipfile.ZipFile(ruta, "w") as z:
        for nombre, texto in contenido.items():
            z.writestr(nombre, texto)
    return ruta


@pytest.mark.parametrize(
    "nombre, esperada",
    [
        ("a/b.txt", "a/b.txt"),
        ("./a//b.txt", "a/b.txt"),
        ("a\\b.txt", "a/b.txt"),
        ("../fuera.txt", None),
        ("a/../../fuera.txt", None),
        ("/etc/passwd", None),
        ("C:/Windows/x", None),
        ("C:x", None),
        ("", None),
    ],
)
def test_ruta_segura(nombre, esperada):
    resultado = ruta_segura(nombre)
    assert (str(resultado) if resultado else None) == esperada


def test_sin_extension():
    assert sin_extension("practica.tar.gz") == "practica"
    assert sin_extension("Practica.ZIP") == "Practica"


def test_carpeta_comun_y_plan(tmp_path):
    archivo = crear_zip(tmp_path / "entrega.zip", {"practica/a.txt": "1", "practica/src/b.py": "2"})
    _, entradas = leer_contenido(archivo)
    assert carpeta_comun(entradas) == "practica"
    plan = planificar(archivo, entradas, None)
    assert plan.raiz == tmp_path / "practica" and plan.quitar == "practica"
    sueltos = crear_zip(tmp_path / "fotos.zip", {"a.jpg": "1", "b.jpg": "2"})
    assert planificar(sueltos, leer_contenido(sueltos)[1], None).raiz == tmp_path / "fotos"


def test_extrae_sin_repetir_la_carpeta_y_sin_pisar(tmp_path):
    archivo = crear_zip(tmp_path / "entrega.zip", {"practica/a.txt": "uno", "practica/src/b.py": "dos"})
    (tmp_path / "practica").mkdir()  # ya hay una: va a «practica (1)»
    salida = runner.invoke(app, ["extrae", str(archivo), "--si"])
    assert salida.exit_code == 0
    assert (tmp_path / "practica (1)" / "src" / "b.py").read_text() == "dos"
    assert list((tmp_path / "practica").iterdir()) == []


def test_lo_peligroso_se_salta(tmp_path):
    archivo = crear_zip(tmp_path / "malo.zip", {"../fuera.txt": "x", "/abs.txt": "x", "bien.txt": "hola"})
    salida = runner.invoke(app, ["extrae", str(archivo), "--si"])
    assert salida.exit_code == 0 and "no son seguras" in salida.output
    assert (tmp_path / "malo" / "bien.txt").read_text() == "hola"
    assert not (tmp_path / "fuera.txt").exists() and not (tmp_path.parent / "fuera.txt").exists()


def test_tar_sin_enlaces(tmp_path):
    archivo = tmp_path / "copia.tar.gz"
    with tarfile.open(archivo, "w:gz") as tar:
        datos = b"hola"
        info = tarfile.TarInfo("copia/hola.txt")
        info.size = len(datos)
        tar.addfile(info, io.BytesIO(datos))
        enlace = tarfile.TarInfo("copia/enlace")
        enlace.type = tarfile.SYMTYPE
        enlace.linkname = "/etc/passwd"
        tar.addfile(enlace)
    tipo, entradas = leer_contenido(archivo)
    assert tipo == "tar" and [e.motivo for e in entradas if e.ruta is None] == ["es un enlace o un dispositivo"]
    salida = runner.invoke(app, ["extrae", str(archivo), "--si", "-d", str(tmp_path / "aqui")])
    assert salida.exit_code == 0
    assert (tmp_path / "aqui" / "copia" / "hola.txt").read_text() == "hola"
    assert not (tmp_path / "aqui" / "copia" / "enlace").exists()


def test_simular_y_no(tmp_path):
    archivo = crear_zip(tmp_path / "a.zip", {"x.txt": "1"})
    assert runner.invoke(app, ["extrae", str(archivo), "--simular"]).exit_code == 0
    assert runner.invoke(app, ["extrae", str(archivo)], input="n\n").exit_code == 0
    assert not (tmp_path / "a").exists()


def test_formatos_que_no(tmp_path):
    (tmp_path / "x.rar").write_bytes(b"Rar!")
    with pytest.raises(NavajaError, match="7-Zip"):
        leer_contenido(tmp_path / "x.rar")
    (tmp_path / "x.zip").write_bytes(b"no soy un zip")
    with pytest.raises(NavajaError, match="no es un .zip"):
        leer_contenido(tmp_path / "x.zip")
