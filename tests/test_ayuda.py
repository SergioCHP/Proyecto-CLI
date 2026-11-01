import typer
from typer.testing import CliRunner

from navaja import interactivo
from navaja.app import app
from navaja.comun import PALABRAS_VOLVER
from navaja.comandos.ayuda import argumentos, opciones_visibles, subcomandos, todos

runner = CliRunner()
RAIZ = typer.main.get_command(app)


def manual():
    resultado = runner.invoke(app, ["manual"])
    assert resultado.exit_code == 0, resultado.output
    return resultado.output


def test_el_manual_explica_todos_los_comandos_y_opciones():
    texto = manual()
    for nombres, comando in todos(RAIZ):
        assert " ".join(nombres) in texto
        for param in argumentos(comando):
            assert param.name.upper() in texto
        for opcion in opciones_visibles(comando):
            for nombre in opcion.opts:
                assert nombre in texto, (nombres, nombre)


def test_todas_las_opciones_tienen_explicacion():
    for nombres, comando in todos(RAIZ):
        assert (comando.help or "").strip(), nombres
        for param in argumentos(comando) + opciones_visibles(comando):
            assert (getattr(param, "help", None) or "").strip(), (nombres, param.name)


def test_el_manual_explica_el_modo_interactivo_y_los_alias():
    texto = manual()
    palabras = (
        interactivo.SALIR
        | interactivo.MENU
        | interactivo.AYUDA_SOLA
        | interactivo.LIMPIAR_PANTALLA
        | interactivo.PREFIJOS
        | set(interactivo.ALIAS)
        | PALABRAS_VOLVER
        | {"cd", "pwd", "volver", "Ctrl+C", "nav", "manual", "ocupa ?"}
    )
    for palabra in palabras:
        assert palabra in texto, palabra
    for cosa in ("NAVAJA_DATOS", "[s/n]", "[s/n/volver]", "--version", "notas.db", "papelera", "código 2"):
        assert cosa in texto, cosa


def test_manual_de_un_comando_solo_muestra_ese():
    resultado = runner.invoke(app, ["manual", "ocupa"])
    assert resultado.exit_code == 0
    assert "--mayores" in resultado.output
    assert "--conservar" not in resultado.output
    assert "Manual de navaja" not in resultado.output


def test_manual_de_un_grupo_explica_sus_subcomandos():
    resultado = runner.invoke(app, ["manual", "ordena"])
    for sub in ("tipo", "fecha", "tramo", "nombre", "letra", "tipos", "deshacer"):
        assert f"ordena {sub}" in resultado.output
    assert "Otros" in resultado.output  # nota de las categorías


def test_manual_de_algo_que_no_existe():
    resultado = runner.invoke(app, ["manual", "ordena", "tram"])
    assert resultado.exit_code == 1
    assert "No hay ningún comando «ordena tram»" in resultado.output
    assert "ordena tramo" in resultado.output


def test_manual_va_el_ultimo_del_menu():
    assert subcomandos(RAIZ)[-1][0] == "manual"
