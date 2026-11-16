import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.errores import NavajaError

pypdf = pytest.importorskip("pypdf")
from navaja.comandos.pdf import leer_paginas, nombre_paginas  # noqa: E402

runner = CliRunner()


def crear(ruta, paginas=5):
    escritor = pypdf.PdfWriter()
    for numero in range(paginas):
        escritor.add_blank_page(width=200 + numero, height=300)  # cada página con su ancho
    with ruta.open("wb") as salida:
        escritor.write(salida)
    return ruta


def anchos(ruta):
    return [round(float(p.mediabox.width)) - 200 for p in pypdf.PdfReader(str(ruta)).pages]


@pytest.mark.parametrize(
    "texto, esperado",
    [("1-3,7", [0, 1, 2, 6]), ("8-", [7, 8, 9]), ("-2", [0, 1]), ("3,1,3", [2, 0]), ("ultima", [9]), (" 2 - 3 ", [1, 2])],
)
def test_leer_paginas(texto, esperado):
    assert leer_paginas(texto, 10) == esperado


@pytest.mark.parametrize("texto", ["0", "11", "5-3", "uno", ","])
def test_paginas_malas(texto):
    with pytest.raises(NavajaError):
        leer_paginas(texto, 10)


def test_nombre_paginas():
    assert nombre_paginas([0, 1, 2, 6]) == "p1-3,7"
    assert nombre_paginas([4]) == "p5"


def test_saca_quita_separa_une(tmp_path):
    original = crear(tmp_path / "apuntes.pdf")
    assert runner.invoke(app, ["pdf", "saca", str(original), "2,4-5", "--si"]).exit_code == 0
    assert anchos(tmp_path / "apuntes-p2,4-5.pdf") == [1, 3, 4]
    assert runner.invoke(app, ["pdf", "quita", str(original), "1", "--si"]).exit_code == 0
    assert anchos(tmp_path / "apuntes-sin-p1.pdf") == [1, 2, 3, 4]
    assert runner.invoke(app, ["pdf", "separa", str(original), "1-2,3-", "--si"]).exit_code == 0
    assert anchos(tmp_path / "apuntes-p3-5.pdf") == [2, 3, 4]
    assert runner.invoke(app, ["pdf", "une", str(tmp_path / "apuntes-p3-5.pdf"), str(original), "--si", "-n", "todo"]).exit_code == 0
    assert anchos(tmp_path / "todo.pdf") == [2, 3, 4, 0, 1, 2, 3, 4]
    assert anchos(original) == [0, 1, 2, 3, 4]  # el original, igual


def test_gira_comprime_y_simular(tmp_path):
    original = crear(tmp_path / "a.pdf", 2)
    assert runner.invoke(app, ["pdf", "gira", str(original), "-p", "2", "-g", "180", "--si"]).exit_code == 0
    assert [p.rotation for p in pypdf.PdfReader(str(tmp_path / "a-girado.pdf")).pages] == [0, 180]
    assert runner.invoke(app, ["pdf", "comprime", str(original), "--si"]).exit_code == 0
    assert (tmp_path / "a-comprimido.pdf").exists()
    assert runner.invoke(app, ["pdf", "quita", str(original), "1", "--simular"]).exit_code == 0
    assert not (tmp_path / "a-sin-p1.pdf").exists()
    assert runner.invoke(app, ["pdf", "gira", str(original), "-g", "45"]).exit_code == 1


def test_contrasena_poner_y_quitar(tmp_path):
    pytest.importorskip("cryptography")
    original = crear(tmp_path / "a.pdf", 1)
    assert runner.invoke(app, ["pdf", "protege", str(original), "--si"], input="abc\nabc\n").exit_code == 0
    cerrado = tmp_path / "a-con-clave.pdf"
    assert pypdf.PdfReader(str(cerrado)).is_encrypted
    assert "sí" in runner.invoke(app, ["pdf", "info", str(cerrado)]).output
    assert runner.invoke(app, ["pdf", "desprotege", str(cerrado), "--si"], input="mal\n").exit_code == 1
    assert runner.invoke(app, ["pdf", "desprotege", str(cerrado), "--si"], input="abc\n").exit_code == 0
    assert not pypdf.PdfReader(str(tmp_path / "a-con-clave-sin-clave.pdf")).is_encrypted
    assert runner.invoke(app, ["pdf", "protege", str(original), "--si"], input="abc\nxyz\n").exit_code == 1


def test_no_es_un_pdf(tmp_path):
    (tmp_path / "x.txt").write_text("hola")
    assert runner.invoke(app, ["pdf", "info", str(tmp_path / "x.txt")]).exit_code == 1
