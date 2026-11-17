from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import entregas
from navaja.errores import NavajaError

runner = CliRunner()
HOY = date(2026, 11, 17)


def fecha_en(dias: int) -> str:
    return (date.today() + timedelta(days=dias)).strftime("%d/%m/%Y")


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("2026-12-15", date(2026, 12, 15)),
        ("15/12/2026", date(2026, 12, 15)),
        ("15-12-2026", date(2026, 12, 15)),
        ("hoy", HOY),
        ("Mañana", HOY + timedelta(days=1)),
        ("manana", HOY + timedelta(days=1)),
        ("+3", HOY + timedelta(days=3)),
        ("20/11", date(2026, 11, 20)),
        ("10/11", date(2027, 11, 10)),  # ya pasó este año: la próxima
        ("17/11", HOY),  # hoy cuenta
        ("29/02", date(2028, 2, 29)),  # la próxima que existe
    ],
)
def test_formas_de_escribir_la_fecha(texto, esperado):
    assert entregas.leer_fecha(texto, HOY) == esperado


@pytest.mark.parametrize("texto", ["", "pasado", "31/02/2026", "2026-13-01", "32/01", "1/2/3/4"])
def test_fechas_que_no_valen(texto):
    with pytest.raises(NavajaError):
        entregas.leer_fecha(texto, HOY)


@pytest.mark.parametrize(
    "dias, estilo, texto",
    [
        (-3, "error", "vencida hace 3 días"),
        (-1, "error", "vencida hace 1 día"),
        (0, "error", "¡hoy!"),
        (1, "error", "mañana"),
        (2, "aviso", "en 2 días"),
        (6, "aviso", "en 6 días"),
        (7, "ok", "en 7 días"),
        (30, "ok", "en 30 días"),
    ],
)
def test_colores_de_la_cuenta_atras(dias, estilo, texto):
    plazo = entregas.plazo_de(HOY + timedelta(days=dias), HOY)
    assert (plazo.estilo, plazo.texto) == (estilo, texto)


def test_agregar_y_listar():
    resultado = runner.invoke(app, ["entregas", "agregar", "Práctica CLI", "+3", "-a", "programación"])
    assert resultado.exit_code == 0, resultado.output
    assert "Práctica CLI" in resultado.output
    resultado = runner.invoke(app, ["entregas", "agregar", "Examen de redes", "+10", "--examen", "-a", "redes"])
    assert resultado.exit_code == 0, resultado.output
    assert "Apuntado" in resultado.output

    lista = runner.invoke(app, ["entregas", "listar"]).output
    assert lista.index("Práctica CLI") < lista.index("Examen de redes")  # lo más cercano primero
    assert "en 3 días" in lista and "Examen" in lista

    solo_redes = runner.invoke(app, ["entregas", "listar", "-a", "REDES"]).output
    assert "Examen de redes" in solo_redes and "Práctica CLI" not in solo_redes


def test_hecha_la_quita_de_lo_pendiente_y_todas_la_enseña():
    runner.invoke(app, ["entregas", "agregar", "Informe", "+2"])
    resultado = runner.invoke(app, ["entregas", "hecha", "1"])
    assert resultado.exit_code == 0, resultado.output
    assert "Hecha" in resultado.output
    assert "No tienes nada pendiente" in runner.invoke(app, ["entregas", "listar"]).output
    assert "hecha" in runner.invoke(app, ["entregas", "listar", "--todas"]).output
    assert "ya estaba hecha" in runner.invoke(app, ["entregas", "hecha", "1"]).output


def test_borrar_pregunta_y_con_si_no():
    runner.invoke(app, ["entregas", "agregar", "Informe", "+2"])
    cancelado = runner.invoke(app, ["entregas", "borrar", "1"], input="n\n")
    assert "Cancelado" in cancelado.output
    assert "Informe" in runner.invoke(app, ["entregas", "listar"]).output
    borrado = runner.invoke(app, ["entregas", "borrar", "1", "--si"])
    assert borrado.exit_code == 0, borrado.output
    assert "No tienes nada pendiente" in runner.invoke(app, ["entregas", "listar"]).output


def test_simular_no_cambia_nada():
    simulado = runner.invoke(app, ["entregas", "agregar", "Informe", "+2", "--simular"])
    assert simulado.exit_code == 0, simulado.output
    assert "Simulado" in simulado.output
    assert "Todavía no has apuntado nada" not in simulado.output
    assert "No tienes nada pendiente" in runner.invoke(app, ["entregas", "listar"]).output

    runner.invoke(app, ["entregas", "agregar", "Informe", "+2"])
    assert "Simulado" in runner.invoke(app, ["entregas", "hecha", "1", "--simular"]).output
    assert "Simulado" in runner.invoke(app, ["entregas", "borrar", "1", "--simular"]).output
    lista = runner.invoke(app, ["entregas", "listar"]).output
    assert "Informe" in lista and "hecha ✔" not in lista


def test_fecha_mala_y_numero_que_no_existe_sin_traza():
    mala = runner.invoke(app, ["entregas", "agregar", "Informe", "cuando sea"])
    assert mala.exit_code == 1
    assert "No entiendo la fecha" in mala.output and "Traceback" not in mala.output
    for orden in ("hecha", "borrar"):
        sin = runner.invoke(app, ["entregas", orden, "99"])
        assert sin.exit_code == 1
        assert "No hay ninguna entrega con el número 99" in sin.output


def test_el_titulo_con_corchetes_no_rompe_el_markup():
    runner.invoke(app, ["entregas", "agregar", "[bold]Ejercicio[/] 3", "+4"])
    assert "[bold]Ejercicio[/] 3" in runner.invoke(app, ["entregas", "listar"]).output


def test_aviso_del_saludo():
    assert entregas.aviso_de_pendientes() is None  # sin nada apuntado
    runner.invoke(app, ["entregas", "agregar", "Lejana", "+30"])
    assert entregas.aviso_de_pendientes() is None  # no vence pronto
    runner.invoke(app, ["entregas", "agregar", "Práctica CLI", "+1"])
    runner.invoke(app, ["entregas", "agregar", "Otra", "+4"])
    aviso = entregas.aviso_de_pendientes()
    assert "Práctica CLI" in aviso and "mañana" in aviso and "(y 1 más)" in aviso
    runner.invoke(app, ["entregas", "hecha", "2"])
    runner.invoke(app, ["entregas", "hecha", "3"])
    assert entregas.aviso_de_pendientes() is None  # lo hecho no avisa
