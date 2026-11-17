import json
import shutil
import subprocess
from pathlib import Path

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


@pytest.mark.parametrize(
    "valor, esperado",
    [("12", 12), ("-3", -3), ("7,5", 7.5), ("7.5", 7.5), ("0", 0), ("0,5", 0.5), ("08001", "08001"),
     ("1234567890123456", "1234567890123456"), ("inf", "inf"), ("nan", "nan"), ("1_000", "1_000"),
     ("1.234,56", "1.234,56"), ("1.500", "1.500"), ("2,250", "2,250"), ("0,125", 0.125), ("-0", 0),
     ("+5", "+5"), ("１２", "１２"), ("1,00000000000000001", "1,00000000000000001"), ("", ""), (None, None)],
)
def test_numero_o_texto(valor, esperado):
    resultado = c.numero_o_texto(valor)
    assert resultado == esperado and type(resultado) is type(esperado)


def test_csv_con_columnas_de_mas(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    (tmp_path / "a.csv").write_text("a,b\n1,2\n3,4,5\n", encoding="utf-8")
    c.csv_a_xlsx(tmp_path / "a.csv", tmp_path / "a.xlsx")
    filas = list(openpyxl.load_workbook(tmp_path / "a.xlsx").active.iter_rows(values_only=True))
    assert filas == [("a", "b", None), (1, 2, None), (3, 4, 5)]


def test_libreoffice_perfil_fijo_y_archivo_soltado_tarde(tmp_path, monkeypatch):
    """Lo que pasó de verdad en Windows: LibreOffice convierte bien pero suelta un archivo un
    instante tarde; borrar la carpeta temporal fallaba y el PDF bueno se tiraba."""
    abiertos, ordenes, carpetas = [], [], []

    def soffice_falso(orden, **_):
        ordenes.append(orden)
        salida = Path(orden[orden.index("--outdir") + 1])
        carpetas.append(salida)
        (salida / "trabajo.pdf").write_bytes(b"%PDF")
        abiertos.append((salida / "update.log").open("w"))  # sigue abierto: en Windows no se puede borrar
        return subprocess.CompletedProcess(orden, 0, "", "")

    monkeypatch.setattr(c, "programa", lambda *_: "soffice")
    monkeypatch.setattr(c.subprocess, "run", soffice_falso)
    (tmp_path / "trabajo.docx").write_bytes(b"x")
    try:
        c.con_libreoffice(tmp_path / "trabajo.docx", tmp_path / "trabajo.pdf")
    finally:
        for archivo in abiertos:
            archivo.close()
        for carpeta in carpetas:
            shutil.rmtree(carpeta, ignore_errors=True)
    assert (tmp_path / "trabajo.pdf").read_bytes() == b"%PDF"
    perfil = next(a for a in ordenes[0] if a.startswith("-env:UserInstallation="))
    assert perfil.endswith("/libreoffice") and "navaja-" not in perfil  # en la carpeta de datos


def test_libreoffice_reintenta_si_sale_bien_sin_convertir(tmp_path, monkeypatch):
    """Lo de Windows: una llamada sí y otra no sale con código 0 sin hacer nada."""
    llamadas = []

    def soffice_que_alterna(orden, **_):
        llamadas.append(orden)
        if len(llamadas) % 2 == 0:
            (Path(orden[orden.index("--outdir") + 1]) / "trabajo.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(orden, 0, "", "")

    monkeypatch.setattr(c, "programa", lambda *_: "soffice")
    monkeypatch.setattr(c.subprocess, "run", soffice_que_alterna)
    (tmp_path / "trabajo.docx").write_bytes(b"x")
    c.con_libreoffice(tmp_path / "trabajo.docx", tmp_path / "trabajo.pdf")
    assert (tmp_path / "trabajo.pdf").read_bytes() == b"%PDF" and len(llamadas) == 2


def test_libreoffice_con_error_de_verdad_no_reintenta(tmp_path, monkeypatch):
    llamadas = []

    def soffice_que_falla(orden, **_):
        llamadas.append(orden)
        return subprocess.CompletedProcess(orden, 1, "", "Error: source file could not be loaded")

    monkeypatch.setattr(c, "programa", lambda *_: "soffice")
    monkeypatch.setattr(c.subprocess, "run", soffice_que_falla)
    (tmp_path / "roto.docx").write_bytes(b"x")
    with pytest.raises(NavajaError, match="could not be loaded"):
        c.con_libreoffice(tmp_path / "roto.docx", tmp_path / "roto.pdf")
    assert len(llamadas) == 1


def test_word_sin_la_barra_en_ingles_de_docx2pdf(tmp_path, monkeypatch, capfd):
    import sys
    import types

    def convert(origen, destino):
        sys.stderr.write("100%|##########| 1/1 [00:04<00:00,  4.95s/it]\n")  # lo que pinta tqdm
        Path(destino).write_bytes(b"%PDF")

    convert(None, tmp_path / "prueba.pdf")
    assert "100%" in capfd.readouterr().err  # sin callarla, la barra sí se vería
    monkeypatch.setitem(sys.modules, "docx2pdf", types.SimpleNamespace(convert=convert))
    c.con_word(tmp_path / "a.docx", tmp_path / "a.pdf")
    assert (tmp_path / "a.pdf").exists() and "100%" not in capfd.readouterr().err


def test_word_que_no_crea_el_pdf(tmp_path, monkeypatch):
    import sys
    import types

    monkeypatch.setitem(sys.modules, "docx2pdf", types.SimpleNamespace(convert=lambda *_: None))
    with pytest.raises(NavajaError, match="Word no ha podido"):
        c.con_word(tmp_path / "a.docx", tmp_path / "a.pdf")


@pytest.fixture(autouse=True)
def sin_pausa_entre_intentos(monkeypatch):
    monkeypatch.setattr(c, "PAUSA_LIBREOFFICE", 0)


def soffice_falso(monkeypatch, responder):
    """Cambia LibreOffice por ``responder(orden, carpeta_de_salida, perfil)`` y apunta las llamadas."""
    llamadas = []

    def run(orden, **_):
        llamadas.append(orden)
        perfil = next(a for a in orden if a.startswith("-env:UserInstallation=")).split("=", 1)[1]
        return responder(orden, Path(orden[orden.index("--outdir") + 1]), perfil)

    monkeypatch.setattr(c, "programa", lambda *_: "soffice")
    monkeypatch.setattr(c.subprocess, "run", run)
    return llamadas


def test_libreoffice_plan_b_con_perfil_nuevo(tmp_path, monkeypatch):
    """El perfil fijo en uso por otro navaja (otra terminal) o estropeado: sale «bien» sin nada."""
    def responder(orden, salida, perfil):
        if perfil != c.carpeta_perfil_libreoffice().as_uri():
            (salida / "trabajo.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(orden, 0, "", "")

    llamadas = soffice_falso(monkeypatch, responder)
    (tmp_path / "trabajo.docx").write_bytes(b"x")
    c.con_libreoffice(tmp_path / "trabajo.docx", tmp_path / "trabajo.pdf")
    assert (tmp_path / "trabajo.pdf").exists() and len(llamadas) == c.INTENTOS_LIBREOFFICE + 1


def test_libreoffice_sin_decir_nada_explica_que_hacer(tmp_path, monkeypatch):
    llamadas = soffice_falso(monkeypatch, lambda orden, *_: subprocess.CompletedProcess(orden, 0, "convert ... -> ...", ""))
    (tmp_path / "trabajo.docx").write_bytes(b"x")
    with pytest.raises(NavajaError, match="no dice por qué") as error:
        c.con_libreoffice(tmp_path / "trabajo.docx", tmp_path / "trabajo.pdf")
    assert str(c.carpeta_perfil_libreoffice()) in str(error.value) and "->" not in str(error.value)  # ni su stdout
    assert len(llamadas) == 2 * c.INTENTOS_LIBREOFFICE  # perfil fijo y plan B


def test_libreoffice_colgado(tmp_path, monkeypatch):
    def colgado(orden, *_):
        raise subprocess.TimeoutExpired(orden, c.TIEMPO_LIBREOFFICE)

    soffice_falso(monkeypatch, colgado)
    (tmp_path / "trabajo.docx").write_bytes(b"x")
    with pytest.raises(NavajaError, match="minutos sin acabar"):
        c.con_libreoffice(tmp_path / "trabajo.docx", tmp_path / "trabajo.pdf")


def test_un_hilo_si_cualquier_archivo_es_de_ofimatica(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    from PIL import Image

    Image.new("RGB", (4, 4)).save(tmp_path / "a.jpg")
    (tmp_path / "b.docx").write_bytes(b"x")
    monkeypatch.setattr(lotes, "buscar_programa", lambda *_: "soffice")
    hilos = []
    monkeypatch.setattr(c, "ejecutar", lambda tareas, titulo, simular, si, h: hilos.append(h))
    salida = runner.invoke(app, ["convierte", str(tmp_path / "a.jpg"), str(tmp_path / "b.docx"), "a", "pdf", "--simular"])
    assert salida.exit_code == 0 and hilos == [1]  # el primero es una foto, pero hay un .docx


def test_libreoffice_que_windows_no_deja_arrancar(tmp_path, monkeypatch):
    def bloqueado(orden, *_):
        raise PermissionError(32, "El proceso no tiene acceso al archivo")

    soffice_falso(monkeypatch, bloqueado)
    (tmp_path / "trabajo.docx").write_bytes(b"x")
    with pytest.raises(NavajaError, match="no deja arrancar LibreOffice"):
        c.con_libreoffice(tmp_path / "trabajo.docx", tmp_path / "trabajo.pdf")


def test_perfil_sin_actualizaciones_automaticas(tmp_path):
    """Lo que de verdad pasaba en Windows: LibreOffice usaba una llamada sí y otra no para
    instalarse una versión nueva desde el perfil de navaja."""
    perfil = tmp_path / "perfil"
    (perfil / "updates" / "0").mkdir(parents=True)
    (perfil / "updates" / "0" / "update.mar").write_bytes(b"x")
    assert c.preparar_perfil(perfil) == perfil.as_uri()
    ajustes = perfil / "user" / "registrymodifications.xcu"
    assert not (perfil / "updates").exists()
    assert '<prop oor:name="Enabled" oor:op="fuse"><value>false</value>' in ajustes.read_text(encoding="utf-8")
    # como lo deja LibreOffice al salir: con sus ajustes y nuestro valor reescrito
    ajustes.write_text(
        c.XCU_VACIO.replace("</oor:items>",
            '<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="X" oor:op="fuse"><value>1</value></prop></item>\n'
            '<item oor:path="/org.openoffice.Office.Update/Update"><prop oor:name="Enabled" oor:op="fuse" oor:type="xs:boolean">'
            "<value>true</value></prop></item>\n</oor:items>"),
        encoding="utf-8",
    )
    c.preparar_perfil(perfil)
    texto = ajustes.read_text(encoding="utf-8")
    assert texto.count('oor:name="Enabled"') == 1 and "<value>true</value>" not in texto
    assert 'oor:name="X"' in texto  # lo demás de LibreOffice se queda
    ajustes.write_text("roto", encoding="utf-8")
    c.preparar_perfil(perfil)
    assert "<value>false</value>" in ajustes.read_text(encoding="utf-8")


def test_perfil_xml_valido_sin_reescribir_y_respetando_lo_demas(tmp_path):
    import xml.etree.ElementTree as ET

    perfil = tmp_path / "perfil"
    ajustes = perfil / "user" / "registrymodifications.xcu"
    ajustes.parent.mkdir(parents=True)
    canal = '<item oor:path="/org.openoffice.Office.Update/Update"><prop oor:name="UpdateChannel" oor:op="fuse"><value>x</value></prop></item>\n'
    ajustes.write_text(c.XCU_VACIO.replace("</oor:items>", canal + "</oor:items>"), encoding="utf-8")
    c.preparar_perfil(perfil)
    primero = ajustes.read_bytes()
    ET.fromstring(primero)  # XML válido
    assert b"UpdateChannel" in primero and b"\r\n" not in primero  # lo demás se queda; «\n» como LibreOffice
    antes = ajustes.stat().st_mtime_ns
    c.preparar_perfil(perfil)  # otra vez: ya está bien, no se toca
    assert ajustes.read_bytes() == primero and ajustes.stat().st_mtime_ns == antes
    assert primero.count(b'oor:name="Enabled"') == 1
    assert not ajustes.with_name(ajustes.name + ".navaja").exists()


def test_si_el_perfil_fijo_no_se_puede_preparar_va_al_plan_b(tmp_path, monkeypatch):
    preparar = c.preparar_perfil

    def preparar_bloqueado(carpeta):
        if carpeta == c.carpeta_perfil_libreoffice():
            raise PermissionError(32, "en uso por otro proceso")  # otro navaja en otra terminal
        return preparar(carpeta)

    def responder(orden, salida, perfil):
        (salida / "trabajo.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(orden, 0, "", "")

    monkeypatch.setattr(c, "preparar_perfil", preparar_bloqueado)
    llamadas = soffice_falso(monkeypatch, responder)
    (tmp_path / "trabajo.docx").write_bytes(b"x")
    c.con_libreoffice(tmp_path / "trabajo.docx", tmp_path / "trabajo.pdf")
    assert (tmp_path / "trabajo.pdf").exists() and len(llamadas) == 1
    assert c.carpeta_perfil_libreoffice().as_uri() not in " ".join(llamadas[0])
