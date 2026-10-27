from pathlib import Path

from navaja.comandos.ocupa import _buscar_basura, _recolectar, _tamano_ruta


def test_tamano_ruta(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_bytes(b"1234")
    (tmp_path / "sub" / "b.txt").write_bytes(b"123456")

    tam, archivos = _tamano_ruta(tmp_path)
    assert tam == 10
    assert archivos == 2


def test_recolectar_respeta_profundidad(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "archivo.txt").write_bytes(b"1234")

    nivel_uno = _recolectar(tmp_path, 1)
    assert [Path(item[0]).name for item in nivel_uno] == ["sub"]

    nivel_dos = _recolectar(tmp_path, 2)
    assert [Path(item[0]).name for item in nivel_dos] == ["sub", "archivo.txt"]


def test_buscar_basura(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"123")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_bytes(b"12345")
    (tmp_path / "normal.txt").write_bytes(b"hola")

    candidatos = _buscar_basura(tmp_path)
    nombres = {Path(item[0]).name for item in candidatos}
    assert nombres == {"__pycache__", "node_modules"}
