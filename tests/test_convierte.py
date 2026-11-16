import json
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from navaja import lotes
from navaja.app import app
from navaja.comandos import convierte as c
from navaja.errores import NavajaError
from navaja.lotes import FaltaAlgo

runner = CliRunner()


def test_separar_formato_y_sinonimos():
    assert c.separar_formato(["a.heic", "b.heic", "a", "JPEG"]) == (["a.heic", "b.heic"], ".jpg")
    assert c.separar_formato(["x.pdf", "en", "Word"]) == (["x.pdf"], ".docx")
    with pytest.raises(NavajaError):
        c.separar_formato(["x.pdf", "docx"])


@pytest.mark.parametrize(
    "entrada, salida, tipo",
    [
        (".heic", ".jpg", "imagen"), (".png", ".pdf", "imagenes-pdf"), (".pdf", ".png", "pdf-imagenes"),
        (".pdf", ".docx", "pdf-docx"), (".docx", ".pdf", "ofimatica-pdf"), (".xlsx", ".pdf", "ofimatica-pdf"),
        (".md", ".docx", "pandoc"), (".csv", ".json", "csv-json"), (".xlsx", ".csv", "xlsx-csv"),
        (".mp4", ".mp3", "ffmpeg"), (".mov", ".mp4", "ffmpeg"), (".mp4", ".mp4", "ffmpeg"),
        (".jpg", ".jpg", None), (".mp3", ".gif", None), (".jpg", ".mp3", None), (".pdf", ".xlsx", None),
    ],
)
def test_que_conversion_es(entrada, salida, tipo):
    assert c.conversion(entrada, salida) == tipo


def test_csv_json_ida_y_vuelta(tmp_path):
    (tmp_path / "datos.csv").write_text("nombre;edad\nAna;20\nLuis;31\n", encoding="utf-8")
    c.csv_a_json(tmp_path / "datos.csv", tmp_path / "datos.json")
    assert json.loads((tmp_path / "datos.json").read_text(encoding="utf-8")) == [
        {"nombre": "Ana", "edad": "20"}, {"nombre": "Luis", "edad": "31"}
    ]
    (tmp_path / "otro.json").write_text('{"alumnos": [{"a": 1}, {"a": 2, "b": [1]}]}', encoding="utf-8")
    c.json_a_csv(tmp_path / "otro.json", tmp_path / "otro.csv")
    assert (tmp_path / "otro.csv").read_text(encoding="utf-8-sig").splitlines() == ["a;b", "1;", "2;[1]"]
    (tmp_path / "malo.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(NavajaError):
        c.json_a_csv(tmp_path / "malo.json", tmp_path / "malo.csv")


def test_excel(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    (tmp_path / "notas.csv").write_text("alumno,nota\nAna,7.5\nLuis,9\n", encoding="utf-8")
    c.csv_a_xlsx(tmp_path / "notas.csv", tmp_path / "notas.xlsx")
    filas = list(openpyxl.load_workbook(tmp_path / "notas.xlsx").active.iter_rows(values_only=True))
    assert filas == [("alumno", "nota"), ("Ana", 7.5), ("Luis", 9)]
    c.xlsx_a_csv(tmp_path / "notas.xlsx", tmp_path / "vuelta.csv")
    assert (tmp_path / "vuelta.csv").read_text(encoding="utf-8-sig").splitlines()[1] == "Ana;7.5"


def test_imagenes(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    carpeta = tmp_path / "pizarra"
    carpeta.mkdir()
    for nombre in ("1.png", "2.png"):
        Image.new("RGBA", (30, 20), (0, 0, 255, 0)).save(carpeta / nombre)
    assert runner.invoke(app, ["convierte", str(carpeta / "*.png"), "a", "jpg", "--si"]).exit_code == 0
    assert Image.open(carpeta / "1.jpg").getpixel((0, 0)) == (255, 255, 255)
    salida = runner.invoke(app, ["convierte", str(carpeta / "*.png"), "a", "pdf", "--si"])
    assert salida.exit_code == 0 and (carpeta / "pizarra.pdf").exists()  # todas en uno, con el nombre de la carpeta
    assert runner.invoke(app, ["convierte", str(carpeta / "1.png"), str(carpeta / "2.png"), "a", "pdf", "--separados", "--si"]).exit_code == 0
    assert (carpeta / "1.pdf").exists() and (carpeta / "2.pdf").exists()


def test_pdf_a_imagenes(tmp_path):
    pytest.importorskip("pymupdf")
    pypdf = pytest.importorskip("pypdf")
    escritor = pypdf.PdfWriter()
    for _ in range(2):
        escritor.add_blank_page(width=100, height=100)
    with (tmp_path / "doc.pdf").open("wb") as salida:
        escritor.write(salida)
    assert runner.invoke(app, ["convierte", str(tmp_path / "doc.pdf"), "a", "png", "--dpi", "72", "--si"]).exit_code == 0
    assert (tmp_path / "doc-p1.png").exists() and (tmp_path / "doc-p2.png").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="sin FFmpeg")
def test_video_a_mp3(tmp_path):
    video = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x48:rate=5",
         "-f", "lavfi", "-i", "sine=duration=1", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(video)],
        check=True,
    )
    assert runner.invoke(app, ["convierte", str(video), "a", "mp3", "--si"]).exit_code == 0
    assert (tmp_path / "clip.mp3").stat().st_size > 0
    assert runner.invoke(app, ["convierte", str(video), "a", "mp4", "--comprime", "--si"]).exit_code == 0
    assert (tmp_path / "clip-comprimido.mp4").exists()


def test_falta_el_programa_antes_de_preguntar(tmp_path, monkeypatch):
    (tmp_path / "clip.mp4").write_bytes(b"x")
    monkeypatch.setattr(lotes, "buscar_programa", lambda *e: None)
    salida = runner.invoke(app, ["convierte", str(tmp_path / "clip.mp4"), "a", "mp3"])
    assert salida.exit_code == 1 and "FFmpeg" in salida.output and "¿Lo creo?" not in salida.output
    with pytest.raises(FaltaAlgo):
        c.programa("pandoc", "probar")


def test_lo_que_no_se_sabe(tmp_path):
    (tmp_path / "foto.jpg").write_bytes(b"x")
    salida = runner.invoke(app, ["convierte", str(tmp_path / "foto.jpg"), "a", "mp3"])
    assert salida.exit_code == 1 and "No sé pasar .jpg a .mp3" in salida.output
