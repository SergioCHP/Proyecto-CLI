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
    resultados, mirados, _ = buscar(apuntes(tmp_path), "FUNCIÓN")
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
    resultados, _, _ = buscar(tmp_path, "mascara")
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


def cifrar(origen_bytes, destino, usuario, propietario="dueño"):
    """Un PDF con contraseña: ``usuario`` para abrirlo («» = se abre, solo protegido contra copia)."""
    pypdf = pytest.importorskip("pypdf")
    pytest.importorskip("cryptography")  # para cifrar con AES-256
    destino.write_bytes(origen_bytes)
    escritor = pypdf.PdfWriter(clone_from=str(destino))
    escritor.encrypt(usuario, propietario, algorithm="AES-256")
    escritor.write(destino)


def test_pdf_con_contrasena_o_roto_se_salta_y_se_avisa(tmp_path):
    cifrar(pdf_con_texto(["hola escondido"]), tmp_path / "cifrado.pdf", "x")
    (tmp_path / "roto.pdf").write_bytes(b"%PDF-1.4 basura")
    (tmp_path / "notas.txt").write_text("hola", encoding="utf-8")
    resultados, mirados, no_leidos = buscar(tmp_path, "hola")
    assert [r.archivo.name for r in resultados] == ["notas.txt"] and mirados == 1
    assert sorted((n.archivo.name, n.motivo) for n in no_leidos) == [("cifrado.pdf", "con contraseña"), ("roto.pdf", "dañado")]
    salida = runner.invoke(app, ["busca", "hola", str(tmp_path)])
    assert salida.exit_code == 0 and "notas.txt" in salida.output
    assert "No se han podido leer 2 archivos" in salida.output and "cifrado.pdf (con contraseña)" in salida.output


def test_si_no_se_lee_ninguno_no_dice_solo_que_no_aparece(tmp_path):
    cifrar(pdf_con_texto(["hola"]), tmp_path / "cifrado.pdf", "x")
    salida = runner.invoke(app, ["busca", "hola", str(tmp_path)])
    assert salida.exit_code == 1 and "en 0 archivos" in salida.output
    assert "No se ha podido leer 1 archivo" in salida.output


def test_pdf_protegido_solo_contra_copia_se_lee(tmp_path):
    cifrar(pdf_con_texto(["La subred y la mascara"]), tmp_path / "apuntes.pdf", "")
    resultados, _, no_leidos = buscar(tmp_path, "mascara")
    assert [r.archivo.name for r in resultados] == ["apuntes.pdf"] and no_leidos == []


def test_aviso_con_corchetes_mas_de_cinco_docx_roto_y_sin_permiso(tmp_path, monkeypatch):
    from navaja.comandos import busca as modulo

    for numero in range(5):
        (tmp_path / f"[tema {numero}].pdf").write_bytes(b"%PDF-1.4 basura")
    (tmp_path / "roto.docx").write_bytes(b"no es un zip")
    (tmp_path / "bloqueado.txt").write_text("hola", encoding="utf-8")
    original = modulo.leer_texto_plano

    def sin_permiso(ruta):
        if ruta.name == "bloqueado.txt":
            raise PermissionError(13, "Permission denied")  # abierto en otro programa
        return original(ruta)

    monkeypatch.setattr(modulo, "leer_texto_plano", sin_permiso)
    _, mirados, no_leidos = buscar(tmp_path, "hola")
    motivos = {n.archivo.name: n.motivo for n in no_leidos}
    assert mirados == 0 and motivos["roto.docx"] == "dañado" and motivos["bloqueado.txt"] == "no se puede abrir"
    salida = runner.invoke(app, ["busca", "hola", str(tmp_path)])
    assert "No se han podido leer 7 archivos" in salida.output
    assert "[tema 0].pdf (dañado)" in salida.output and "… y 2 más" in salida.output
