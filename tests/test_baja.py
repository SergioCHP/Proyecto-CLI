import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import baja
from navaja.errores import NavajaError

runner = CliRunner()


class FalsoYoutubeDL:
    """Hace como yt-dlp sin internet: apunta lo que se le pide."""

    bajados: list[str] = []
    opciones: list[dict] = []

    def __init__(self, opciones):
        self.opciones.append(opciones)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def extract_info(self, enlace, download=False):
        if "privado" in enlace:
            raise Exception("ERROR: [youtube] abc: Private video")
        return {"title": "Clase de redes", "duration": 3725, "filesize_approx": 5_000_000, "extractor_key": "Youtube"}

    def download(self, enlaces):
        self.bajados.extend(enlaces)


class FalsoModulo:
    YoutubeDL = FalsoYoutubeDL


@pytest.fixture
def falso(monkeypatch):
    FalsoYoutubeDL.bajados = []
    FalsoYoutubeDL.opciones = []
    monkeypatch.setattr(baja, "yt_dlp", lambda: FalsoModulo)
    monkeypatch.setattr(baja, "buscar_programa", lambda *e: "/usr/bin/ffmpeg")
    return FalsoYoutubeDL


def test_leer_enlaces(tmp_path):
    lista = tmp_path / "enlaces.txt"
    lista.write_text("# para clase\nhttps://a.com/1\n\nwww.b.com/2\nhttps://a.com/1\n", encoding="utf-8")
    assert baja.leer_enlaces([str(lista), "https://c.com/3"]) == ["https://a.com/1", "https://www.b.com/2", "https://c.com/3"]
    with pytest.raises(NavajaError):
        baja.leer_enlaces(["hola"])


def test_formato():
    assert baja.formato(True, 720, True)["postprocessors"][0]["preferredcodec"] == "mp3"
    assert "postprocessors" not in baja.formato(True, 720, False)
    assert baja.formato(False, 720, True)["format"].startswith("bestvideo[height<=720]+bestaudio")
    assert "+" not in baja.formato(False, 0, False)["format"]  # sin FFmpeg, lo que ya viene junto


def test_duracion_y_motivo():
    assert baja.duracion_texto(3725) == "1:02:05" and baja.duracion_texto(65) == "1:05" and baja.duracion_texto(None) == "—"
    assert "privado" in baja.motivo(Exception("ERROR: Private video"))
    assert "iniciar sesión" in baja.motivo(Exception("Sign in to confirm your age"))


def test_simular_no_baja(falso, tmp_path):
    salida = runner.invoke(app, ["baja", "https://youtu.be/abc", "--simular", "-d", str(tmp_path)])
    assert salida.exit_code == 0 and "Clase de redes" in salida.output and "1:02:05" in salida.output
    assert falso.bajados == []


def test_baja_los_buenos_y_dice_los_malos(falso, tmp_path):
    salida = runner.invoke(app, ["baja", "https://youtu.be/abc", "https://youtu.be/privado", "--audio", "--si", "-d", str(tmp_path)])
    assert falso.bajados == ["https://youtu.be/abc"]
    assert salida.exit_code == 1 and "privado" in salida.output
    ultima = falso.opciones[-1]
    assert ultima["nooverwrites"] and str(tmp_path) in ultima["outtmpl"]
    assert ultima["postprocessors"][0]["preferredcodec"] == "mp3"


def test_respuesta_no(falso, tmp_path):
    assert runner.invoke(app, ["baja", "https://youtu.be/abc", "-d", str(tmp_path)], input="n\n").exit_code == 0
    assert falso.bajados == []
