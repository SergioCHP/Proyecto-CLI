from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.listar import contenido, tipo_de

runner = CliRunner()


def test_carpetas_primero_y_orden_sin_mayusculas(tmp_path):
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / "A.pdf").write_text("x")
    (tmp_path / "zeta").mkdir()
    (tmp_path / ".oculto").write_text("x")
    assert [e.name for e in contenido(tmp_path)] == ["zeta", "A.pdf", "b.txt"]
    assert ".oculto" in [e.name for e in contenido(tmp_path, ocultos=True)]


def test_tipo(tmp_path):
    (tmp_path / "carpeta").mkdir()
    (tmp_path / "FOTO.JPG").write_text("x")
    (tmp_path / "LEEME").write_text("x")
    assert tipo_de(tmp_path / "carpeta") == "carpeta"
    assert tipo_de(tmp_path / "FOTO.JPG") == ".jpg"
    assert tipo_de(tmp_path / "LEEME") == "(sin extensión)"


def test_listar_muestra_los_archivos(tmp_path):
    (tmp_path / "apuntes de redes.docx").write_text("hola")
    resultado = runner.invoke(app, ["listar", str(tmp_path)])
    assert resultado.exit_code == 0, resultado.output
    assert "apuntes de redes.docx" in resultado.output
    assert "1 archivo" in resultado.output


def test_listar_carpeta_vacia(tmp_path):
    vacia = tmp_path / "vacia"  # tmp_path ya tiene la carpeta de datos del conftest
    vacia.mkdir()
    resultado = runner.invoke(app, ["listar", str(vacia)])
    assert resultado.exit_code == 0
    assert "vacía" in resultado.output


def test_listar_errores_salen_con_1(tmp_path):
    archivo = tmp_path / "contrato.docx"
    archivo.write_text("x")
    assert runner.invoke(app, ["listar", str(tmp_path / "no-existe")]).exit_code == 1
    assert runner.invoke(app, ["listar", str(archivo)]).exit_code == 1
