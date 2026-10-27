import os
from datetime import datetime
from pathlib import Path

from navaja.comandos.ordena import ModoOrden, _categoria, _planificar


def _crear(ruta: Path, nombre: str, contenido: bytes = b"x") -> Path:
    archivo = ruta / nombre
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_bytes(contenido)
    return archivo


def test_categoria():
    assert _categoria("foto.JPG") == "imagenes"
    assert _categoria("documento.pdf") == "documentos"
    assert _categoria("cancion.mp3") == "audio"
    assert _categoria("desconocido.xyz") == "otros"


def test_planificar_por_extension(tmp_path):
    _crear(tmp_path, "foto.jpg")
    _crear(tmp_path, "nota.txt")
    _crear(tmp_path, ".oculta.jpg")

    movimientos = _planificar(tmp_path, ModoOrden.extension, tmp_path, False, False)
    destinos = {Path(m["destino"]).relative_to(tmp_path).as_posix() for m in movimientos}
    assert destinos == {"Imagenes/foto.jpg", "Documentos/nota.txt"}

    con_ocultos = _planificar(tmp_path, ModoOrden.extension, tmp_path, False, True)
    assert len(con_ocultos) == 3


def test_planificar_evita_colisiones(tmp_path):
    _crear(tmp_path, "foto.jpg")
    _crear(tmp_path, "Imagenes/foto.jpg")

    movimientos = _planificar(tmp_path, ModoOrden.extension, tmp_path, False, False)
    destinos = [Path(m["destino"]).name for m in movimientos]
    assert "foto (1).jpg" in destinos


def test_planificar_por_fecha(tmp_path):
    archivo = _crear(tmp_path, "nota.txt")
    marca = datetime(2020, 5, 15, 12, 0).timestamp()
    os.utime(archivo, (marca, marca))

    movimientos = _planificar(tmp_path, ModoOrden.fecha, tmp_path, False, False)
    destino = Path(movimientos[0]["destino"]).relative_to(tmp_path).as_posix()
    assert destino == "2020/05/nota.txt"


def test_destino_distinto(tmp_path):
    origen = tmp_path / "origen"
    destino = tmp_path / "destino"
    origen.mkdir()
    destino.mkdir()
    _crear(origen, "foto.jpg")

    movimientos = _planificar(origen, ModoOrden.extension, destino, False, False)
    assert movimientos[0]["destino"] == str(destino / "Imagenes" / "foto.jpg")
