import os
from pathlib import Path

import pytest
from rich.cells import cell_len
from typer.testing import CliRunner

from navaja import comun
from navaja.app import app
from navaja.comandos.ocupa import (
    BARRA_MAXIMA,
    _buscar_basura,
    _recolectar,
    _tamano_ruta,
    columnas_que_caben,
)

runner = CliRunner()


def test_tamano_ruta(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_bytes(b"1234")
    (tmp_path / "sub" / "b.txt").write_bytes(b"123456")

    tam, archivos = _tamano_ruta(tmp_path)
    assert tam == 10
    assert archivos == 2


def test_recolectar_respeta_profundidad(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "archivo.txt").write_bytes(b"1234")

    nivel_uno = _recolectar(tmp_path, 1)
    assert [Path(item[0]).name for item in nivel_uno] == ["sub"]

    nivel_dos = _recolectar(tmp_path, 2)
    assert [Path(item[0]).name for item in nivel_dos] == ["sub", "archivo.txt"]


def test_buscar_basura(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"123")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_bytes(b"12345")
    (tmp_path / "normal.txt").write_bytes(b"hola")

    candidatos = _buscar_basura(tmp_path)
    nombres = {Path(item[0]).name for item in candidatos}
    assert nombres == {"__pycache__", "node_modules"}


def test_limpia_no_toca_carpetas_tuyas_que_se_llaman_como_las_de_programar(tmp_path):
    for carpeta in ("build", "Seguro/coverage", "dist", "target"):
        (tmp_path / carpeta).mkdir(parents=True)
        (tmp_path / carpeta / "importante.pdf").write_text("x")
    (tmp_path / "desktop.ini").write_text("x")
    assert _buscar_basura(tmp_path) == []


def test_limpia_si_borra_lo_compilado_dentro_de_un_proyecto(tmp_path):
    proyecto = tmp_path / "web"
    (proyecto / "dist").mkdir(parents=True)
    (proyecto / "dist" / "app.js").write_text("x")
    (proyecto / "package.json").write_text("{}")
    (tmp_path / "notas.txt~").write_text("x")
    nombres = {Path(item[0]).name: item[2] for item in _buscar_basura(tmp_path)}
    assert set(nombres) == {"dist", "notas.txt~"}
    assert "compilado" in nombres["dist"]


def test_limpia_simular_no_borra(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text("x")
    resultado = runner.invoke(app, ["limpia", str(tmp_path), "--simular"])
    assert resultado.exit_code == 0, resultado.output
    assert "caché de Python" in resultado.output and "Simulación" in resultado.output
    assert (tmp_path / "__pycache__" / "x.pyc").exists()


def test_columnas_que_caben_segun_el_ancho():
    assert columnas_que_caben(200, 6, 8) == (BARRA_MAXIMA, True)
    barra, con_archivos = columnas_que_caben(60, 6, 8)
    assert 6 <= barra < BARRA_MAXIMA and con_archivos  # barra más corta
    assert columnas_que_caben(48, 6, 8) == (0, True)  # sin barra, solo el porcentaje
    assert columnas_que_caben(36, 6, 8) == (0, False)  # y sin «Archivos»
    # la ruta larga se queda con el sitio de la barra antes que partirse
    assert columnas_que_caben(80, 6, 8, 30)[0] < columnas_que_caben(80, 6, 8, 10)[0]


@pytest.mark.parametrize("ancho", [36, 44, 60, 80, 120])
def test_ocupa_cabe_en_la_ventana_sin_cortar_nada(tmp_path, monkeypatch, ancho):
    (tmp_path / "Apuntes" / "Tema1").mkdir(parents=True)
    (tmp_path / "Apuntes" / "Tema1" / "a.txt").write_text("x" * 300, encoding="utf-8")
    (tmp_path / "foto.jpg").write_text("y" * 100, encoding="utf-8")
    monkeypatch.setattr(comun.console, "_width", ancho)
    resultado = runner.invoke(app, ["ocupa", str(tmp_path), "-p", "2"])
    assert resultado.exit_code == 0, resultado.output
    lineas = resultado.output.splitlines()
    assert all(cell_len(linea) <= ancho for linea in lineas)
    assert sum(linea.startswith("┌") or linea.startswith("╭") for linea in lineas) == 1  # un recuadro
    # en una ventana estrecha una ruta puede seguir en la línea de abajo, pero entera
    seguido = "".join(resultado.output.replace("│", "").split())
    for ruta in ("Apuntes/", f"Apuntes{os.sep}Tema1/", "foto.jpg"):
        assert ruta in seguido
    if ancho >= 60:  # con sitio, cada ruta en su fila, sin partir
        assert f"Apuntes{os.sep}Tema1/" in resultado.output


def test_ocupa_carpeta_vacia(tmp_path, monkeypatch):
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    monkeypatch.setattr(comun.console, "_width", 80)
    resultado = runner.invoke(app, ["ocupa", str(vacia)])
    assert resultado.exit_code == 0, resultado.output
    assert "Uso de disco" in resultado.output and "vacía" in resultado.output
