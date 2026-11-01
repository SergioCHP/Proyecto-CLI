import os
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.renombra import (
    extensiones,
    formatear_plantilla,
    nombre_arreglado,
    planificar,
    seleccionar,
)

runner = CliRunner()


def crear(carpeta: Path, *nombres: str) -> None:
    for nombre in nombres:
        (carpeta / nombre).write_text("x")


def nombres(carpeta: Path) -> set[str]:
    return {p.name for p in carpeta.iterdir() if p.is_file()}


def renombra(*argumentos: str, entrada: str = "s\n"):
    return runner.invoke(app, ["renombra", *argumentos], input=entrada)


@pytest.fixture
def fotos(tmp_path):
    carpeta = tmp_path / "fotos"
    carpeta.mkdir()
    crear(carpeta, "IMG_1234.jpg", "IMG_1235.jpg", "notas.txt")
    return carpeta


# ── Cada opción ────────────────────────────────────────────────────────────


def test_cambiar_texto_sin_regex(fotos):
    resultado = renombra("cambiar", "IMG_", "foto_", "-c", str(fotos))
    assert resultado.exit_code == 0, resultado.output
    assert nombres(fotos) == {"foto_1234.jpg", "foto_1235.jpg", "notas.txt"}


def test_cambiar_trata_los_simbolos_como_texto(tmp_path):
    crear(tmp_path, "a.b(1).txt")
    renombra("cambiar", "(1)", "", "-c", str(tmp_path))
    assert "a.b.txt" in nombres(tmp_path)


def test_delante_y_detras(fotos):
    renombra("delante", "2026_", "-c", str(fotos), "--solo", "txt")
    renombra("detras", "_v2", "-c", str(fotos), "--solo", "txt")
    assert "2026_notas_v2.txt" in nombres(fotos)


def test_numerar_por_carpeta_y_con_cifras(fotos):
    resultado = renombra("numerar", "playa", "-c", str(fotos), "--solo", "jpg", "--empieza", "8", "--cifras", "2")
    assert resultado.exit_code == 0, resultado.output
    assert nombres(fotos) == {"playa_08.jpg", "playa_09.jpg", "notas.txt"}


def test_numerar_por_fecha(tmp_path):
    (tmp_path / "a.jpg").write_text("a")
    (tmp_path / "b.jpg").write_text("b")
    antes = time.time() - 1000
    os.utime(tmp_path / "b.jpg", (antes, antes))  # b es la más antigua
    renombra("numerar", "foto", "-c", str(tmp_path), "--orden", "fecha")
    assert (tmp_path / "foto_001.jpg").read_text() == "b"
    assert (tmp_path / "foto_002.jpg").read_text() == "a"


def test_fecha_delante_y_no_se_repite(fotos):
    os.utime(fotos / "notas.txt", (1793000000, 1793000000))  # 2026-10-26 o 27 según la zona
    dia = time.strftime("%Y-%m-%d", time.localtime(1793000000))
    renombra("fecha", "-c", str(fotos), "--solo", "txt")
    assert f"{dia}_notas.txt" in nombres(fotos)

    resultado = renombra("fecha", "-c", str(fotos), "--solo", "txt")
    assert "Ningún nombre cambia" in resultado.output


def test_arreglar_nombres():
    assert nombre_arreglado("Foto Año.JPG") == "foto-ano.jpg"
    assert nombre_arreglado("Mi  Archivo (1).PDF") == "mi-archivo-1.pdf"
    assert nombre_arreglado("Canción_Ñandú.mp3", "_") == "cancion_nandu.mp3"
    assert nombre_arreglado("¿¿??.txt") == "archivo.txt"


def test_arreglar_solo_mayusculas_se_puede(tmp_path):
    crear(tmp_path, "FOTO.JPG")
    resultado = renombra("arreglar", "-c", str(tmp_path))
    assert resultado.exit_code == 0, resultado.output
    assert nombres(tmp_path) == {"foto.jpg"}


def test_plantilla_con_los_huecos_de_acciones_json(tmp_path):
    crear(tmp_path, "IMG_1.JPG")
    archivo = tmp_path / "IMG_1.JPG"
    os.utime(archivo, (1793000000, 1793000000))
    dia = time.strftime("%Y-%m-%d", time.localtime(1793000000))
    assert formatear_plantilla("{fecha:%Y-%m-%d}_{n:03}{ext}", archivo, 7) == f"{dia}_007.jpg"
    assert formatear_plantilla("{nombre}-copia{ext}", archivo, 1) == "IMG_1-copia.jpg"


def test_plantilla_con_un_hueco_que_no_existe(tmp_path):
    crear(tmp_path, "a.txt")
    resultado = renombra("plantilla", "{numero}{ext}", "-c", str(tmp_path))
    assert resultado.exit_code == 2
    assert "{numero}" in resultado.output and "{nombre}" in resultado.output


def test_avanzado_con_regex(fotos):
    resultado = renombra("avanzado", r"IMG_(\d+)", r"foto_\1", "-c", str(fotos))
    assert resultado.exit_code == 0, resultado.output
    assert "foto_1234.jpg" in nombres(fotos)
    assert renombra("avanzado", "[", "x", "-c", str(fotos)).exit_code == 2


# ── El camino común ────────────────────────────────────────────────────────


def test_simular_no_toca_nada(fotos):
    resultado = renombra("cambiar", "IMG_", "foto_", "-c", str(fotos), "--simular")
    assert resultado.exit_code == 0
    assert "foto_1234.jpg" in resultado.output
    assert "Simulación" in resultado.output
    assert nombres(fotos) == {"IMG_1234.jpg", "IMG_1235.jpg", "notas.txt"}


def test_contestar_que_no_no_toca_nada(fotos):
    resultado = renombra("cambiar", "IMG_", "foto_", "-c", str(fotos), entrada="n\n")
    assert "[s/n]" in resultado.output
    assert "Cancelado" in resultado.output
    assert "IMG_1234.jpg" in nombres(fotos)


def test_deshacer(fotos):
    renombra("numerar", "x", "-c", str(fotos))
    assert "IMG_1234.jpg" not in nombres(fotos)
    resultado = renombra("deshacer", "--si")
    assert resultado.exit_code == 0, resultado.output
    assert nombres(fotos) == {"IMG_1234.jpg", "IMG_1235.jpg", "notas.txt"}


def test_conflictos_no_se_tocan(tmp_path):
    crear(tmp_path, "a.txt", "b.txt", "ya.txt")
    movimientos = planificar(
        seleccionar(tmp_path, "", False, False), lambda a, n: "c.txt" if a.stem in "ab" else "ya.txt"
    )
    estados = {Path(m["origen"]).name: m["estado"] for m in movimientos}
    assert estados == {"a.txt": "ok", "b.txt": "conflicto", "ya.txt": "igual"}


def test_nombres_que_no_valen_en_windows(tmp_path):
    crear(tmp_path, "a.txt")
    resultado = renombra("delante", "12:30 ", "-c", str(tmp_path), "--si")
    assert "nombre no válido" in resultado.output
    assert nombres(tmp_path) == {"a.txt"}


def test_contiene_solo_coge_esos_archivos(tmp_path):
    crear(
        tmp_path,
        "Gemini_Generated_Image_4ll5w74ll5w74ll5.png",
        "Gemini_Generated_Image_jx2wlfjx2wlfjx2w.png",
        "Gemini_Generated_Image_yz08iryz08iryz08.png",
        "captura.png",
    )
    resultado = renombra(
        "numerar", "gemini", "--separador", " ", "--cifras", "1",
        "--contiene", "gemini", "-c", str(tmp_path),
    )
    assert resultado.exit_code == 0, resultado.output
    assert nombres(tmp_path) == {"gemini 1.png", "gemini 2.png", "gemini 3.png", "captura.png"}

    resultado = renombra("delante", "x", "--contiene", "nada", "-c", str(tmp_path))
    assert "No hay archivos (con «nada» en el nombre)" in resultado.output


def test_solo_acepta_extensiones_de_varias_formas():
    assert extensiones("jpg, .PNG,*.gif") == {".jpg", ".png", ".gif"}
    assert extensiones("") == set()


def test_carpeta_que_no_existe(tmp_path):
    resultado = renombra("cambiar", "a", "b", "-c", str(tmp_path / "no"))
    assert resultado.exit_code == 1


def test_sin_archivos_con_esas_extensiones(fotos):
    resultado = renombra("delante", "x", "-c", str(fotos), "--solo", "pdf")
    assert "No hay archivos (tipo pdf)" in resultado.output
