import zipfile

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.cuenta import contar, limpiar_html, limpiar_markdown, minutos, paginas_texto, texto_de
from navaja.errores import NavajaError

runner = CliRunner()

DOCX = (
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    "<w:p><w:r><w:t>Hola</w:t></w:r><w:r><w:t xml:space=\"preserve\"> mundo</w:t></w:r></w:p>"
    "<w:p><w:r><w:t>Segundo</w:t><w:tab/><w:t>párrafo</w:t></w:r></w:p>"
    "</w:body></w:document>"
)
ODT = (
    '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text>'
    "<text:h>Título</text:h><text:p>Uno dos <text:span>tres</text:span></text:p>"
    "</office:text></office:body></office:document-content>"
)


def test_contar():
    cuenta = contar("Hola, mundo. Esto es bien-estar\n\ny l'aigua 2026.")
    assert cuenta.palabras == 8
    assert cuenta.parrafos == 2


def test_minutos_y_paginas():
    assert minutos(100, 230) == "menos de 1 min"
    assert minutos(2300, 230) == "10 min"
    assert minutos(230 * 65, 230) == "1 h 5 min"
    assert paginas_texto(0.2) == "menos de media" and paginas_texto(1) == "una" and paginas_texto(4.4) == "unas 4"


def test_markdown_y_html_sin_simbolos():
    assert contar(limpiar_markdown("# Título\n\n- **uno**\n- [dos](http://x.com)\n\n```\ncodigo no cuenta\n```\n")).palabras == 3
    assert contar(limpiar_html("<p>Hola <b>mundo</b></p><script>var x = 1;</script>")).palabras == 2


def test_docx_y_odt_sin_librerias(tmp_path):
    docx = tmp_path / "trabajo.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", DOCX)
    assert texto_de(docx) == "Hola mundo\nSegundo párrafo"
    odt = tmp_path / "trabajo.odt"
    with zipfile.ZipFile(odt, "w") as z:
        z.writestr("content.xml", ODT)
    assert contar(texto_de(odt)).palabras == 4


def test_pdf(tmp_path):
    pytest.importorskip("pypdf")
    contenido = b"BT /F1 12 Tf 72 720 Td (Hola mundo desde un PDF) Tj ET"
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    datos = b"%PDF-1.4\n"
    posiciones = []
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(datos))
        datos += b"%d 0 obj\n" % numero + objeto + b"\nendobj\n"
    xref = len(datos)
    datos += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    datos += b"".join(b"%010d 00000 n \n" % p for p in posiciones)
    datos += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, xref)
    pdf = tmp_path / "apuntes.pdf"
    pdf.write_bytes(datos)
    assert contar(texto_de(pdf)).palabras == 5


def test_formatos_que_no_sabe(tmp_path):
    for nombre in ("viejo.doc", "foto.jpg"):
        (tmp_path / nombre).write_bytes(b"x")
        with pytest.raises(NavajaError):
            texto_de(tmp_path / nombre)
    roto = tmp_path / "roto.docx"
    roto.write_bytes(b"no es un zip")
    with pytest.raises(NavajaError, match="dañado"):
        texto_de(roto)


def test_orden_con_minimo_y_varios(tmp_path):
    (tmp_path / "a.txt").write_text("uno dos tres", encoding="utf-8")
    (tmp_path / "b.txt").write_text("cuatro cinco", encoding="utf-8")
    salida = runner.invoke(app, ["cuenta", str(tmp_path / "a.txt"), "--minimo", "10"])
    assert salida.exit_code == 0 and "Te faltan 7 palabras" in salida.output
    salida = runner.invoke(app, ["cuenta", str(tmp_path / "a.txt"), str(tmp_path / "b.txt"), "-m", "5"])
    assert "2 archivos" in salida.output and "Llegas" in salida.output
    assert runner.invoke(app, ["cuenta", str(tmp_path / "no.txt")]).exit_code == 1


def test_pdf_protegido_solo_contra_copia_se_cuenta_y_con_contrasena_no(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    pytest.importorskip("cryptography")
    from ayudantes import pdf_con_texto

    for nombre, usuario in (("copia.pdf", ""), ("clave.pdf", "x")):
        (tmp_path / nombre).write_bytes(pdf_con_texto(["Hola mundo desde un PDF"]))
        escritor = pypdf.PdfWriter(clone_from=str(tmp_path / nombre))
        escritor.encrypt(usuario, "dueño", algorithm="AES-256")
        escritor.write(tmp_path / nombre)
    assert contar(texto_de(tmp_path / "copia.pdf")).palabras == 5
    with pytest.raises(NavajaError, match="contraseña"):
        texto_de(tmp_path / "clave.pdf")


def test_pdf_que_rompe_pypdf_de_otra_forma_no_da_traza(tmp_path, monkeypatch):
    pypdf = pytest.importorskip("pypdf")

    def roto(*_):
        raise KeyError("/Root")

    monkeypatch.setattr(pypdf, "PdfReader", roto)
    (tmp_path / "raro.pdf").write_bytes(b"%PDF-1.4")
    with pytest.raises(NavajaError, match="dañado"):
        texto_de(tmp_path / "raro.pdf")
