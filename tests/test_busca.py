import zipfile

import pytest
from typer.testing import CliRunner

from ayudantes import pdf_con_texto
from navaja.app import app
from navaja.comandos.busca import Linea, buscar, patron, recortar, sin_tildes_igual_largo
from navaja.errores import NavajaError

runner = CliRunner()
DOCX = (
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    "<w:p><w:r><w:t>La Función de transferencia</w:t></w:r></w:p></w:body></w:document>"
)


def apuntes(tmp_path):
    (tmp_path / "tema2.md").write_text("# Tema 2\n\nUna funcion recursiva.\nOtra línea.\n", encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "tema1.docx", "w") as z:
        z.writestr("word/document.xml", DOCX)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "x.py").write_text("funcion escondida")
    (tmp_path / "foto.bin").write_bytes(b"\0funcion")
    return tmp_path


def test_sin_tildes_igual_largo():
    assert sin_tildes_igual_largo("Función ÑANDÚ") == "funcion nandu"
    assert len(sin_tildes_igual_largo("ﬁ ß İ")) == len("ﬁ ß İ")


def test_busca_sin_mayusculas_ni_tildes_y_dentro_de_word(tmp_path):
    resultados, mirados = buscar(apuntes(tmp_path), "FUNCIÓN")
    assert sorted(r.archivo.name for r in resultados) == ["tema1.docx", "tema2.md"]
    assert mirados == 3  # .venv no se mira
    md = next(r for r in resultados if r.archivo.name == "tema2.md")
    linea = md.lineas[0]
    assert linea.numero == 3 and linea.texto[slice(*linea.trozos[0])] == "funcion"


def test_exacto_regex_y_solo(tmp_path):
    apuntes(tmp_path)
    assert [r.archivo.name for r in buscar(tmp_path, "Función", exacto=True)[0]] == ["tema1.docx"]
    assert len(buscar(tmp_path, r"func\w+ (de|rec)", regex=True)[0]) == 2
    assert [r.archivo.name for r in buscar(tmp_path, "funcion", solo="md")[0]] == ["tema2.md"]
    assert len(buscar(tmp_path, "escondida", todo=True)[0]) == 1
    with pytest.raises(NavajaError, match="regular"):
        patron("(sin cerrar", regex=True)


def test_dentro_de_pdf_por_pagina(tmp_path):
    pytest.importorskip("pypdf")
    (tmp_path / "apuntes.pdf").write_bytes(pdf_con_texto(["Nada aqui", "La subred y la mascara"]))
    resultados, _ = buscar(tmp_path, "mascara")
    assert resultados[0].por_pagina and resultados[0].lineas[0].numero == 2


def test_recortar_linea_larga():
    texto = "x" * 300 + "AQUI" + "y" * 300
    corte, trozos = recortar(Linea(1, texto, [(300, 304)]), ancho=60)
    assert corte.startswith("…") and corte.endswith("…") and corte[slice(*trozos[0])] == "AQUI"
    corte, trozos = recortar(Linea(1, "    sangria AQUI", [(12, 16)]))
    assert corte == "sangria AQUI" and corte[slice(*trozos[0])] == "AQUI"


def test_orden(tmp_path):
    apuntes(tmp_path)
    salida = runner.invoke(app, ["busca", "funcion", str(tmp_path)])
    assert salida.exit_code == 0 and "tema1.docx" in salida.output and "2 líneas en 2 archivos" in salida.output
    salida = runner.invoke(app, ["busca", "nada de nada", str(tmp_path)])
    assert salida.exit_code == 1 and "No aparece" in salida.output


def test_pdf_con_contrasena_o_roto_se_salta(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    pytest.importorskip("cryptography")  # para cifrar con AES-256
    escritor = pypdf.PdfWriter()
    escritor.add_blank_page(100, 100)
    escritor.encrypt("x", algorithm="AES-256")
    escritor.write(tmp_path / "cifrado.pdf")
    (tmp_path / "roto.pdf").write_bytes(b"%PDF-1.4 basura")
    (tmp_path / "notas.txt").write_text("hola", encoding="utf-8")
    salida = runner.invoke(app, ["busca", "hola", str(tmp_path)])
    assert salida.exit_code == 0 and "notas.txt" in salida.output
