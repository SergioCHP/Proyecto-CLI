import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.qr import dibujar, texto_wifi

runner = CliRunner()


def test_dibujar_dos_filas_por_linea():
    assert dibujar([[False, True], [False, False]]) == ["█▄"]  # blanco = bloque; negro = fondo
    assert dibujar([[True, True], [True, False], [False, True]]) == [" ▄", "▀ "]  # la última fila, sola


def test_wifi_protege_los_caracteres_especiales():
    assert texto_wifi("Casa;5G", 'a:b"c') == r'WIFI:T:WPA;S:Casa\;5G;P:a\:b\"c;;'
    assert texto_wifi("Abierta", "") == "WIFI:T:nopass;S:Abierta;P:;;"


def test_orden(tmp_path):
    pytest.importorskip("qrcode")
    salida = runner.invoke(app, ["qr", "https://example.com"])
    assert salida.exit_code == 0 and "█" in salida.output and "example.com" in salida.output
    pytest.importorskip("PIL")
    salida = runner.invoke(app, ["qr", "hola", "--guardar", str(tmp_path / "codigo")])
    assert salida.exit_code == 0 and (tmp_path / "codigo.png").exists()
    salida = runner.invoke(app, ["qr", "MiCasa", "--wifi"], input="secreta\n")
    assert salida.exit_code == 0 and "la wifi «MiCasa»" in salida.output
    assert runner.invoke(app, ["qr"]).exit_code == 1
