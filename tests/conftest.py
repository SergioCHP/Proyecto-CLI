import pytest


@pytest.fixture(autouse=True)
def datos_aislados(tmp_path, monkeypatch):
    """Ningún test lee ni escribe en el directorio de datos real."""
    monkeypatch.setenv("NAVAJA_DATOS", str(tmp_path / "datos_navaja"))
