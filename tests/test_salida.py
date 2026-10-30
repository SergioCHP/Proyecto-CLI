import pytest
from typer.testing import CliRunner

from navaja.app import app

runner = CliRunner()


@pytest.mark.parametrize(
    "argumentos",
    [
        ["ocupa"],
        ["ordena", "previsualizar"],
        ["renombra", "previsualizar", "{ruta}", "zzz", "y"],
    ],
)
def test_nombres_con_corchetes_se_ven_enteros(tmp_path, argumentos):
    (tmp_path / "[borrador].pdf").write_text("x")
    (tmp_path / "[red]aviso.txt").write_text("x")

    if "{ruta}" in argumentos:
        argumentos = [str(tmp_path) if a == "{ruta}" else a for a in argumentos]
    else:
        argumentos = [*argumentos, str(tmp_path)]

    resultado = runner.invoke(app, argumentos)
    assert resultado.exit_code == 0, resultado.output
    assert "[borrador].pdf" in resultado.output
    assert "[red]aviso.txt" in resultado.output
