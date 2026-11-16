import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.errores import NavajaError

Image = pytest.importorskip("PIL.Image")
from navaja.comandos import imagen  # noqa: E402

runner = CliRunner()


def foto(ruta, tamano=(800, 600), gps=False, modo="RGB"):
    im = Image.new(modo, tamano, "red" if modo == "RGB" else (255, 0, 0, 0))
    exif = Image.Exif()
    exif[0x010F] = "Movil"
    if gps:
        exif[0x8825] = {1: "N", 2: (40.0, 25.0, 0.0)}
    im.save(ruta, exif=exif) if ruta.suffix == ".jpg" else im.save(ruta)
    return ruta


def test_color_y_proporcion():
    assert imagen.color("Blanco") == (255, 255, 255)
    assert imagen.color("#ff8800") == (255, 136, 0) and imagen.color("1,2,3") == (1, 2, 3)
    assert imagen.proporcion("16:9") == pytest.approx(16 / 9)
    for malo in ("morado-chillon", "300,0,0"):
        with pytest.raises(NavajaError):
            imagen.color(malo)
    with pytest.raises(NavajaError):
        imagen.proporcion("ancha")


def test_recortar_y_reducir():
    im = Image.new("RGB", (1600, 900))
    assert imagen.recortar_centro(im, 1.0).size == (900, 900)
    assert imagen.recortar_centro(im, 9 / 16).size == (506, 900)
    assert imagen.reducir(im, 400).size == (400, 225)
    assert imagen.reducir(Image.new("RGB", (100, 50)), 400).size == (100, 50)  # nunca agranda


def test_guardar_quita_gps_y_transparencia_a_jpg(tmp_path):
    original = foto(tmp_path / "a.jpg", gps=True)
    assert imagen.gps_de(original)
    imagen.guardar(imagen.abrir(original), tmp_path / "b.jpg")
    assert not imagen.gps_de(tmp_path / "b.jpg")
    trans = foto(tmp_path / "t.png", modo="RGBA")
    imagen.guardar(imagen.abrir(trans), tmp_path / "t.jpg")
    assert Image.open(tmp_path / "t.jpg").getpixel((0, 0)) == (255, 255, 255)  # fondo blanco


def test_ordenes(tmp_path):
    foto(tmp_path / "a.jpg", gps=True)
    foto(tmp_path / "b.jpg")
    salida = runner.invoke(app, ["imagen", "info", str(tmp_path / "a.jpg")])
    assert "lleva dónde se hizo" in salida.output and "Movil" in salida.output
    assert runner.invoke(app, ["imagen", "reduce", str(tmp_path / "*.jpg"), "-l", "100", "--si"]).exit_code == 0
    assert Image.open(tmp_path / "b-reducida.jpg").size == (100, 75)
    assert runner.invoke(app, ["imagen", "limpia", str(tmp_path / "a.jpg"), "--si"]).exit_code == 0
    assert not imagen.gps_de(tmp_path / "a-limpia.jpg") and imagen.gps_de(tmp_path / "a.jpg")
    assert runner.invoke(app, ["imagen", "recorta", str(tmp_path / "a.jpg"), "-p", "1:1", "--si"]).exit_code == 0
    assert Image.open(tmp_path / "a-1x1.jpg").size == (600, 600)
    assert runner.invoke(app, ["imagen", "grises", str(tmp_path / "a.jpg"), "--si"]).exit_code == 0
    assert Image.open(tmp_path / "a-grises.jpg").mode == "L"
    assert runner.invoke(app, ["imagen", "icono", str(tmp_path / "a.jpg"), "--si"]).exit_code == 0
    assert Image.open(tmp_path / "a-icono.ico").format == "ICO"
    assert runner.invoke(app, ["imagen", "comprime", str(tmp_path / "a.jpg"), "--simular"]).exit_code == 0
    assert not (tmp_path / "a-comprimida.jpg").exists()


def test_heic(tmp_path):
    heif = pytest.importorskip("pillow_heif")
    heif.register_heif_opener()
    Image.new("RGB", (40, 30), "orange").save(tmp_path / "movil.heic")
    assert runner.invoke(app, ["imagen", "reduce", str(tmp_path / "movil.heic"), "-l", "20", "--si"]).exit_code == 0
    assert Image.open(tmp_path / "movil-reducida.jpg").size == (20, 15)  # la HEIC sale en JPG
