from pathlib import Path

from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.ocupa import _buscar_basura, _recolectar, _tamano_ruta

runner = CliRunner()


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


def test_limpia_no_toca_carpetas_tuyas_que_se_llaman_como_las_de_programar(tmp_path):
    for carpeta in ("build", "Seguro/coverage", "dist", "target"):
        (tmp_path / carpeta).mkdir(parents=True)
        (tmp_path / carpeta / "importante.pdf").write_text("x")
    (tmp_path / "desktop.ini").write_text("x")
    assert _buscar_basura(tmp_path) == []


def test_limpia_si_borra_lo_compilado_dentro_de_un_proyecto(tmp_path):
    proyecto = tmp_path / "web"
    (proyecto / "dist").mkdir(parents=True)
    (proyecto / "dist" / "app.js").write_text("x")
    (proyecto / "package.json").write_text("{}")
    (tmp_path / "notas.txt~").write_text("x")
    nombres = {Path(item[0]).name: item[2] for item in _buscar_basura(tmp_path)}
    assert set(nombres) == {"dist", "notas.txt~"}
    assert "compilado" in nombres["dist"]


def test_limpia_simular_no_borra(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text("x")
    resultado = runner.invoke(app, ["limpia", str(tmp_path), "--simular"])
    assert resultado.exit_code == 0, resultado.output
    assert "caché de Python" in resultado.output and "Simulación" in resultado.output
    assert (tmp_path / "__pycache__" / "x.pyc").exists()
