from pathlib import Path

from navaja.comandos.renombra import _planificar


def _crear(ruta: Path, nombre: str) -> Path:
    archivo = ruta / nombre
    archivo.write_text("x")
    return archivo


def test_planificar_basico(tmp_path):
    _crear(tmp_path, "IMG_001.jpg")
    _crear(tmp_path, "IMG_002.jpg")

    movimientos = _planificar(
        tmp_path, r"IMG_(\d+)", r"foto_\1", "*.jpg", False, False, False
    )
    destinos = {Path(m["destino"]).name for m in movimientos}
    assert destinos == {"foto_001.jpg", "foto_002.jpg"}
    assert all(m["estado"] == "ok" for m in movimientos)


def test_planificar_marca_conflictos(tmp_path):
    _crear(tmp_path, "a.txt")
    _crear(tmp_path, "b.txt")

    movimientos = _planificar(
        tmp_path, r"[ab]", "c", "*.txt", False, False, False
    )
    estados = [m["estado"] for m in movimientos]
    assert estados.count("ok") == 1
    assert "conflicto" in estados


def test_planificar_marca_invalidos(tmp_path):
    _crear(tmp_path, "nota.txt")

    movimientos = _planificar(
        tmp_path, r"nota", "sub/nota", "*.txt", False, False, False
    )
    assert movimientos[0]["estado"] == "invalido"


def test_renombrar_nombre_completo(tmp_path):
    _crear(tmp_path, "archivo.txt")

    movimientos = _planificar(
        tmp_path, r"\.txt$", ".md", "*", False, True, False
    )
    assert Path(movimientos[0]["destino"]).name == "archivo.md"


def test_respeta_incluir_y_ocultos(tmp_path):
    _crear(tmp_path, "visible.py")
    _crear(tmp_path, "oculto.py")
    (tmp_path / "oculto.py").rename(tmp_path / ".oculto.py")

    movimientos = _planificar(
        tmp_path, r"oculto", "secreto", "*.py", False, False, False
    )
    nombres = {Path(m["origen"]).name for m in movimientos}
    assert nombres == {"visible.py"}

    movimientos = _planificar(
        tmp_path, r"oculto", "secreto", "*.py", False, False, True
    )
    nombres = {Path(m["origen"]).name for m in movimientos}
    assert nombres == {"visible.py", ".oculto.py"}
