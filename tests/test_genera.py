import random
import uuid

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.genera import lorem, numeros, uuids
from navaja.errores import NavajaError

runner = CliRunner()


def test_uuids_validos_y_distintos():
    lista = uuids(50)
    assert len(set(lista)) == 50
    assert all(uuid.UUID(u).version == 4 for u in lista)


def test_lorem():
    parrafos = lorem(30, 3, random.Random(1))
    assert len(parrafos) == 3
    assert parrafos[0].startswith("Lorem ipsum")
    assert all(len(p.split()) == 30 and p.endswith(".") for p in parrafos)


def test_numeros():
    rng = random.Random(1)
    lista = numeros(1, 6, 100, False, rng)
    assert len(lista) == 100 and set(lista) <= set(range(1, 7))
    sorteo = numeros(10, 1, 10, True, rng)  # al revés también vale
    assert sorted(sorteo) == list(range(1, 11))
    with pytest.raises(NavajaError):
        numeros(1, 3, 5, True, rng)


def test_ordenes():
    assert len(runner.invoke(app, ["genera", "uuid", "-n", "3"]).output.split()) == 3
    salida = runner.invoke(app, ["genera", "numero", "5", "5", "-n", "2"])
    assert salida.output.strip() == "5 5"
    assert runner.invoke(app, ["genera", "lorem", "-p", "5"]).output.startswith("Lorem ipsum")
    salida = runner.invoke(app, ["genera", "numero", "1", "2", "-n", "3", "--sin-repetir"])
    assert salida.exit_code == 1
