import os
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.ordena import (
    Agrupar,
    carpeta_por_fecha,
    carpeta_por_letra,
    carpeta_por_tipo,
    planificar,
)
from navaja.filtros import tipo_de

runner = CliRunner()


def crear(carpeta: Path, nombre: str, fecha: datetime | None = None) -> Path:
    archivo = carpeta / nombre
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("x")
    if fecha:
        marca = fecha.timestamp()
        os.utime(archivo, (marca, marca))
    return archivo


def ordena(*argumentos: str, entrada: str = "s\n"):
    return runner.invoke(app, ["ordena", *argumentos], input=entrada)


def relativos(carpeta: Path) -> set[str]:
    return {p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()}


@pytest.fixture
def descargas(tmp_path):
    carpeta = tmp_path / "Descargas"
    crear(carpeta, "foto.jpg", datetime(2026, 9, 10, 12))
    crear(carpeta, "informe.pdf", datetime(2026, 10, 5, 12))
    crear(carpeta, "cancion.mp3", datetime(2025, 3, 1, 12))
    crear(carpeta, "desktop.ini")  # archivo de sistema: no se toca
    return carpeta


def test_tipo_de():
    assert tipo_de("foto.JPG") == "imagenes"
    assert tipo_de("documento.pdf") == "documentos"
    assert tipo_de("desconocido.xyz") == "otros"


def test_por_tipo(descargas):
    resultado = ordena("tipo", "-c", str(descargas))
    assert resultado.exit_code == 0, resultado.output
    assert relativos(descargas) == {
        "Imagenes/foto.jpg", "Documentos/informe.pdf", "Audio/cancion.mp3", "desktop.ini",
    }


@pytest.mark.parametrize(
    "por, esperado",
    [
        ("mes", "2026/09 septiembre/foto.jpg"),
        ("año", "2026/foto.jpg"),
        ("día", "2026-09-10/foto.jpg"),
    ],
)
def test_por_fecha(descargas, por, esperado):
    resultado = ordena("fecha", "--por", por, "-c", str(descargas), "--solo", "jpg")
    assert resultado.exit_code == 0, resultado.output
    assert esperado in relativos(descargas)


def test_tramo_de_una_fecha_a_otra(descargas):
    resultado = ordena("tramo", "1/9/2026", "30/9/2026", "-c", str(descargas))
    assert resultado.exit_code == 0, resultado.output
    assert relativos(descargas) == {
        "del 2026-09-01 al 2026-09-30/foto.jpg", "informe.pdf", "cancion.mp3", "desktop.ini",
    }


def test_tramo_con_meses_y_nombre_propio(descargas):
    ordena("tramo", "septiembre 2026", "octubre 2026", "--nombre", "Curso", "-c", str(descargas))
    assert {"Curso/foto.jpg", "Curso/informe.pdf"} <= relativos(descargas)


def test_tramo_con_una_fecha_que_no_se_entiende(descargas):
    resultado = ordena("tramo", "mañana", "-c", str(descargas))
    assert resultado.exit_code == 2
    assert "No entiendo la fecha «mañana»" in resultado.output


def test_filtros_de_fecha_y_tipo(descargas):
    resultado = ordena("tipo", "-c", str(descargas), "--desde", "2026", "--solo", "documentos")
    assert resultado.exit_code == 0, resultado.output
    assert relativos(descargas) == {
        "Documentos/informe.pdf", "foto.jpg", "cancion.mp3", "desktop.ini",
    }


def test_sin_nada_que_ordenar_lo_dice(descargas):
    resultado = ordena("tipo", "-c", str(descargas), "--contiene", "zzz")
    assert "No hay nada que ordenar" in resultado.output


def test_simular_y_contestar_que_no_no_mueven_nada(descargas):
    antes = relativos(descargas)
    assert "Simulación" in ordena("tipo", "-c", str(descargas), "--simular").output
    resultado = ordena("tipo", "-c", str(descargas), entrada="n\n")
    assert "¿Mover 3 archivos a 3 carpetas?" in resultado.output
    assert relativos(descargas) == antes


def test_fuera_del_modo_interactivo_volver_no_vale(descargas):
    antes = relativos(descargas)
    resultado = ordena("tipo", "-c", str(descargas), entrada="volver\nn\n")
    assert "[s/n]" in resultado.output and "volver]" not in resultado.output
    assert "Responde s o n." in resultado.output
    assert relativos(descargas) == antes


def test_deshacer_devuelve_y_quita_las_carpetas_vacias(descargas):
    antes = relativos(descargas)
    ordena("fecha", "-c", str(descargas))
    assert relativos(descargas) != antes
    resultado = ordena("deshacer", "--si")
    assert resultado.exit_code == 0, resultado.output
    assert relativos(descargas) == antes
    assert not [p for p in descargas.iterdir() if p.is_dir()]


def test_nunca_sobrescribe(tmp_path):
    crear(tmp_path, "foto.jpg")
    crear(tmp_path, "Imagenes/foto.jpg")
    movimientos = planificar([tmp_path / "foto.jpg"], tmp_path, carpeta_por_tipo)
    assert Path(movimientos[0]["destino"]).name == "foto (1).jpg"


def test_destino_distinto(tmp_path):
    origen, destino = tmp_path / "origen", tmp_path / "destino"
    crear(origen, "foto.jpg")
    ordena("tipo", "-c", str(origen), "-d", str(destino))
    assert (destino / "Imagenes" / "foto.jpg").exists()


def test_carpeta_por_fecha_por_mes(tmp_path):
    archivo = crear(tmp_path, "nota.txt", datetime(2020, 5, 15, 12))
    assert carpeta_por_fecha(Agrupar.mes)(archivo) == str(Path("2020") / "05 mayo")


@pytest.fixture
def vacia(tmp_path):
    carpeta = tmp_path / "Carpeta"  # tmp_path ya tiene la carpeta de datos del conftest
    carpeta.mkdir()
    return carpeta


def test_por_nombre_junta_los_que_llevan_el_texto(vacia):
    for nombre in ("factura_enero.pdf", "Factura luz octubre.pdf", "foto.jpg"):
        crear(vacia, nombre)
    resultado = ordena("nombre", "factura", "-c", str(vacia))
    assert resultado.exit_code == 0, resultado.output
    assert relativos(vacia) == {
        "factura/factura_enero.pdf", "factura/Factura luz octubre.pdf", "foto.jpg",
    }


def test_por_nombre_con_carpeta_propia_y_filtro_de_tipo(vacia):
    for nombre in ("Gemini_1.png", "Gemini_2.png", "gemini notas.txt"):
        crear(vacia, nombre)
    ordena("nombre", "gemini", "--nombre", "Imagenes IA", "--solo", "imagenes", "-c", str(vacia))
    assert relativos(vacia) == {
        "Imagenes IA/Gemini_1.png", "Imagenes IA/Gemini_2.png", "gemini notas.txt",
    }


@pytest.mark.parametrize("texto, extra", [("a/b", []), ("factura", ["--nombre", "mal?"]), ("  ", [])])
def test_por_nombre_con_una_carpeta_que_no_vale(vacia, texto, extra):
    crear(vacia, "factura.pdf")
    resultado = ordena("nombre", texto, *extra, "-c", str(vacia))
    assert resultado.exit_code == 2
    assert relativos(vacia) == {"factura.pdf"}


@pytest.mark.parametrize(
    "nombre, carpeta",
    [
        ("Activitat.pdf", "A"),
        ("boletin.pdf", "B"),
        ("Álbum.jpg", "A"),
        ("ñandú.jpg", "Ñ"),
        ("2024 notas.txt", "0-9"),
        ("_borrador.docx", "B"),
        ("(1) foto.png", "0-9"),
        ("___.txt", "Otros"),
        (".gitignore", "G"),
        ("—.~", "Otros"),
    ],
)
def test_carpeta_por_letra(nombre, carpeta):
    assert carpeta_por_letra(Path(nombre)) == carpeta


def test_por_letra(vacia):
    for nombre in ("Activitat.pdf", "apuntes.txt", "Boletin.pdf", "0465983.pdf"):
        crear(vacia, nombre)
    resultado = ordena("letra", "-c", str(vacia))
    assert resultado.exit_code == 0, resultado.output
    assert relativos(vacia) == {
        "A/Activitat.pdf", "A/apuntes.txt", "B/Boletin.pdf", "0-9/0465983.pdf",
    }
    ordena("deshacer", "--si")
    assert relativos(vacia) == {"Activitat.pdf", "apuntes.txt", "Boletin.pdf", "0465983.pdf"}
