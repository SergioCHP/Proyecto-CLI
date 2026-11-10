import pytest
from typer.testing import CliRunner

from navaja.app import app

runner = CliRunner()


@pytest.mark.parametrize(
    "argumentos",
    [
        ["listar"],
        ["ocupa"],
        ["ordena", "tipo", "--simular", "-c", "{ruta}"],
        ["renombra", "detras", "_v2", "--simular", "-c", "{ruta}"],
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


class SalidaCerrada:
    """Una salida cuyo lector ya se fue (como «| head -1» en Windows): todo da OSError 22."""

    encoding = "utf-8"

    def write(self, texto):
        raise OSError(22, "Invalid argument")

    def flush(self):
        raise OSError(22, "Invalid argument")


def test_tuberia_cerrada_reconoce_solo_la_salida_rota(monkeypatch):
    import io
    import sys

    from navaja.app import tuberia_cerrada

    assert tuberia_cerrada(BrokenPipeError(32, "Broken pipe"))
    monkeypatch.setattr(sys, "stdout", SalidaCerrada())
    assert tuberia_cerrada(OSError(22, "Invalid argument"))
    assert not tuberia_cerrada(OSError(2, "No such file"))
    # el mismo 22 pero con la salida bien (p. ej. una ruta mala): no es la tubería
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert not tuberia_cerrada(OSError(22, "Invalid argument"))


def test_main_sale_sin_traza_si_la_tuberia_se_cierra(monkeypatch):
    import sys

    from navaja import app as modulo

    def escribe_en_tuberia_cerrada():
        raise OSError(22, "Invalid argument")

    monkeypatch.setattr(sys, "stdout", SalidaCerrada())
    monkeypatch.setattr(modulo, "app", escribe_en_tuberia_cerrada)
    monkeypatch.setattr(modulo, "preparar_salida", lambda flujo: None)
    with pytest.raises(SystemExit) as salida:
        modulo.main()
    assert salida.value.code == 1


def test_main_no_se_traga_otros_errores(monkeypatch):
    from navaja import app as modulo

    def otro_error():
        raise OSError(22, "Invalid argument")  # con la salida bien: es otra cosa

    monkeypatch.setattr(modulo, "app", otro_error)
    monkeypatch.setattr(modulo, "preparar_salida", lambda flujo: None)
    with pytest.raises(OSError):
        modulo.main()
