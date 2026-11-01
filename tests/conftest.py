import pytest


@pytest.fixture(autouse=True)
def datos_aislados(tmp_path, monkeypatch):
    """Ningún test lee ni escribe en el directorio de datos real."""
    monkeypatch.setenv("NAVAJA_DATOS", str(tmp_path / "datos_navaja"))


@pytest.fixture(autouse=True)
def ancho_fijo(monkeypatch):
    """Las tablas se pintan siempre con el mismo ancho, sea cual sea la terminal.

    Sin esto, el resultado dependía del equipo: en Windows, Rich usa una columna
    menos (79 en vez de 80) y partía líneas que los tests buscan enteras.
    """
    monkeypatch.setenv("COLUMNS", "120")
