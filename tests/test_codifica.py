import base64
import json
from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.codifica import (
    a_base64,
    a_html,
    a_url,
    de_base64,
    de_html,
    de_url,
    fechas_jwt,
    leer_jwt,
)
from navaja.errores import NavajaError

runner = CliRunner()


def jwt(cabecera, datos):
    parte = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{parte(cabecera)}.{parte(datos)}.firma"


@pytest.mark.parametrize("texto", ["hola", "año 2026 ñ €", "", "a" * 100])
def test_base64_ida_y_vuelta(texto):
    assert de_base64(a_base64(texto)) == texto


def test_base64_de_url_y_sin_relleno():
    assert de_base64("YcOxbw") == "año"  # sin «=»
    assert de_base64(base64.urlsafe_b64encode("¿?>>".encode()).decode()) == "¿?>>"


def test_base64_malo_o_sin_texto():
    with pytest.raises(NavajaError, match="no es Base64"):
        de_base64("%%%")
    with pytest.raises(NavajaError, match="no hay texto"):
        de_base64(base64.b64encode(b"\xff\xfe\x00").decode())


def test_url_y_html():
    assert a_url("año 2026 & más") == "a%C3%B1o%202026%20%26%20m%C3%A1s"
    assert de_url("a%C3%B1o+2026") == "año 2026"
    assert a_html('<a href="x">&') == "&lt;a href=&quot;x&quot;&gt;&amp;"
    assert de_html("&lt;b&gt; &aacute;") == "<b> á"


def test_leer_jwt():
    cabecera, datos = leer_jwt(jwt({"alg": "HS256"}, {"sub": "sergio", "exp": 0}))
    assert cabecera == {"alg": "HS256"} and datos["sub"] == "sergio"
    for malo in ("abc", "a.b", "e30.%%%.x"):
        with pytest.raises(NavajaError):
            leer_jwt(malo)


def test_fechas_jwt():
    ahora = datetime(2026, 11, 16, tzinfo=timezone.utc)
    caducado = dict(fechas_jwt({"exp": 1_000_000_000}, ahora))
    assert "ya ha caducado" in caducado["Caduca"]
    vale = dict(fechas_jwt({"exp": 2_000_000_000, "iat": 1_000_000_000}, ahora))
    assert "aún vale" in vale["Caduca"] and "Creado" in vale
    assert fechas_jwt({"exp": "mañana"}, ahora) == []


def test_ordenes():
    assert runner.invoke(app, ["codifica", "base64", "hola"]).output.strip() == "aG9sYQ=="
    assert runner.invoke(app, ["codifica", "base64", "-d", "aG9sYQ=="]).output.strip() == "hola"
    assert runner.invoke(app, ["codifica", "url", "a b"]).output.strip() == "a%20b"
    assert runner.invoke(app, ["codifica", "html", "-d", "&lt;"]).output.strip() == "<"
    salida = runner.invoke(app, ["codifica", "jwt", jwt({"alg": "none"}, {"name": "Sergio"})])
    assert salida.exit_code == 0 and "Sergio" in salida.output and "firma no se comprueba" in salida.output
    salida = runner.invoke(app, ["codifica", "base64", "-d", "%%%"])
    assert salida.exit_code == 1 and "Traceback" not in salida.output
