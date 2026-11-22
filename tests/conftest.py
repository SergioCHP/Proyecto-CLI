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


@pytest.fixture(autouse=True)
def sin_ia_real(monkeypatch):
    """Ningún test habla con Gemini de verdad ni lee tu .env (con tu clave): sin clave y sin
    archivos .env. Los tests de la IA ponen un proveedor falso o su propio .env."""
    from navaja import proveedor_ia

    for variable in (proveedor_ia.ENV_CLAVE, proveedor_ia.ENV_MODELO, proveedor_ia.ENV_SIN_IA,
                     proveedor_ia.ENV_URL, proveedor_ia.ENV_CLAVE_SERVIDOR):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(proveedor_ia, "archivos_env", lambda: [])
