import pytest
from rich.cells import cell_len
from typer.testing import CliRunner

from navaja import comun
from navaja.app import app
from navaja.comandos.listar import (
    FECHA_CORTA,
    FECHA_LARGA,
    columnas_que_caben,
    contenido,
    tipo_de,
)

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


def test_listar_ordena_sin_mirar_tildes(tmp_path):
    carpeta = tmp_path / "fotos"
    carpeta.mkdir()
    for nombre in ("zeta.jpg", "Álbum.jpg", "boda.jpg"):
        (carpeta / nombre).write_text("x")
    salida = runner.invoke(app, ["listar", str(carpeta)]).output
    assert salida.index("Álbum.jpg") < salida.index("boda.jpg") < salida.index("zeta.jpg")


def test_columnas_que_caben_segun_el_ancho():
    assert columnas_que_caben(120, 20, 7, 6) == (True, FECHA_LARGA)
    assert columnas_que_caben(60, 20, 7, 6) == (False, FECHA_LARGA)  # sin «Tipo»
    assert columnas_que_caben(50, 20, 7, 6) == (False, FECHA_CORTA)  # sin la hora
    assert columnas_que_caben(44, 30, 7, 6) == (False, FECHA_CORTA)  # el nombre se parte
    assert columnas_que_caben(30, 20, 7, 6) == (False, 0)  # solo nombre y tamaño


@pytest.mark.parametrize("ancho", [34, 44, 60, 80, 120])
def test_listar_cabe_en_la_ventana(tmp_path, monkeypatch, ancho):
    (tmp_path / "Apuntes").mkdir()
    (tmp_path / "horario.pdf").write_text("x" * 50, encoding="utf-8")
    monkeypatch.setattr(comun.console, "_width", ancho)
    resultado = runner.invoke(app, ["listar", str(tmp_path)])
    assert resultado.exit_code == 0, resultado.output
    lineas = resultado.output.splitlines()
    assert all(cell_len(linea) <= ancho for linea in lineas)
    assert sum(linea.startswith(("┌", "╭")) for linea in lineas) == 1  # un solo recuadro
    assert "Apuntes/" in resultado.output and "horario.pdf" in resultado.output
    assert "50 B" in resultado.output
    cabeceras = next(linea for linea in lineas if "Nombre" in linea)
    assert ("Tipo" in cabeceras) == (ancho >= 60)  # nombres cortos: cabe pronto


def test_listar_extension_con_corchetes_y_fecha_imposible(tmp_path, monkeypatch):
    archivo = tmp_path / "informe.[b]"
    archivo.write_text("x", encoding="utf-8")
    monkeypatch.setattr(comun.console, "_width", 120)
    monkeypatch.setattr("navaja.comandos.listar.datetime", FechaRota)
    resultado = runner.invoke(app, ["listar", str(tmp_path)])
    assert resultado.exit_code == 0, resultado.output
    assert ".[b]" in resultado.output  # la extensión no se toma por formato
    assert "Traceback" not in resultado.output


class FechaRota:
    """Como en Windows con un archivo de antes de 1970: fromtimestamp falla."""

    @staticmethod
    def fromtimestamp(_marca):
        raise OSError(22, "Invalid argument")


def test_listar_carpeta_con_solo_ocultos(tmp_path, monkeypatch):
    carpeta = tmp_path / "solo-ocultos"
    carpeta.mkdir()
    (carpeta / ".git").mkdir()
    monkeypatch.setattr(comun.console, "_width", 100)
    resultado = runner.invoke(app, ["listar", str(carpeta)])
    assert "No hay nada visible: 1 oculto" in resultado.output
    assert "--ocultos" in resultado.output
    assert ".git/" in runner.invoke(app, ["listar", str(carpeta), "--ocultos"]).output
