import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import fondo

Image = pytest.importorskip("PIL.Image")
runner = CliRunner()


class FalsoRembg:
    """Quita «el fondo» haciendo transparente la mitad izquierda, sin descargar el modelo."""

    sesiones: list[str] = []

    @classmethod
    def new_session(cls, modelo):
        cls.sesiones.append(modelo)
        return modelo

    @staticmethod
    def remove(foto, session=None, only_mask=False):
        if only_mask:
            return Image.new("L", foto.size, 255)
        salida = foto.convert("RGBA")
        for x in range(foto.width // 2):
            for y in range(foto.height):
                salida.putpixel((x, y), (0, 0, 0, 0))
        return salida


@pytest.fixture
def falso(monkeypatch):
    FalsoRembg.sesiones = []
    monkeypatch.setattr(fondo, "rembg", lambda: FalsoRembg)
    monkeypatch.setattr(fondo, "_sesion", None)
    return FalsoRembg


def test_png_transparente_y_el_modelo_pequeno(falso, tmp_path):
    Image.new("RGB", (10, 10), "red").save(tmp_path / "a.jpg")
    Image.new("RGB", (10, 10), "red").save(tmp_path / "b.jpg")
    assert runner.invoke(app, ["fondo", str(tmp_path / "*.jpg"), "--si"]).exit_code == 0
    resultado = Image.open(tmp_path / "a-sin-fondo.png")
    assert resultado.mode == "RGBA" and resultado.getpixel((0, 0))[3] == 0 and resultado.getpixel((9, 0))[3] == 255
    assert falso.sesiones == [fondo.MODELO]  # cargado una sola vez para las dos fotos


def test_color_y_mascara(falso, tmp_path):
    Image.new("RGB", (10, 10), "red").save(tmp_path / "carne.jpg")
    assert runner.invoke(app, ["fondo", str(tmp_path / "carne.jpg"), "--color", "azul", "--si"]).exit_code == 0
    assert Image.open(tmp_path / "carne-sin-fondo.jpg").getpixel((0, 0))[2] > 150  # fondo azul
    assert runner.invoke(app, ["fondo", str(tmp_path / "carne.jpg"), "--mascara", "--si"]).exit_code == 0
    assert Image.open(tmp_path / "carne-silueta.png").mode == "L"
    assert runner.invoke(app, ["fondo", str(tmp_path / "carne.jpg"), "--color", "fucsia-raro"]).exit_code == 1
