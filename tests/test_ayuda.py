import pytest
import typer
from typer.testing import CliRunner

from navaja import interactivo
from navaja.app import app
from navaja.comun import HERRAMIENTAS, NAVAJA, PALABRAS_VOLVER, REPITES, SECCIONES
from navaja.comandos.ayuda import (
    argumentos,
    opciones_visibles,
    por_secciones,
    subcomandos,
    todos,
)

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
    for cosa in ("NAVAJA_DATOS", "[s/n]", "--version", "notas.db", "papelera", "código 2"):
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


# ── Secciones del menú principal ───────────────────────────────────────────


def test_cada_comando_tiene_su_seccion_y_no_se_reordena():
    secciones = por_secciones(RAIZ)
    assert [s for s, _ in secciones] == [HERRAMIENTAS, REPITES, NAVAJA]
    assert all(s in SECCIONES for s, _ in secciones)
    # Juntas, en el mismo orden que subcomandos: los números del menú no cambian
    assert [n for _, cs in secciones for n, _ in cs] == [n for n, _ in subcomandos(RAIZ)]
    assert [n for n, _ in secciones[1][1]] == ["acciones"]


def test_un_submenu_no_tiene_secciones():
    assert [s for s, _ in por_secciones(RAIZ.commands["acciones"])] == [""]


def test_help_y_menu_ensenan_las_secciones(capsys):
    texto = plano(runner.invoke(app, ["--help"]).output)
    for seccion, explicacion in SECCIONES.items():
        assert f"{seccion} — {explicacion}" in texto
    assert texto.index("notas") < texto.index(REPITES) < texto.index("acciones")

    interactivo.mostrar_menu(RAIZ, [])
    menu = plano(capsys.readouterr().out)
    numero = {n: i for i, (n, _) in enumerate(subcomandos(RAIZ), start=1)}
    ultima = por_secciones(RAIZ)[0][1][-1][0]  # la última herramienta
    filas = [f"{numero[n]} {n}" for n in (ultima, "acciones", "manual")]
    assert all(fila in menu for fila in filas)
    assert menu.index(filas[0]) < menu.index(REPITES) < menu.index(filas[1])


# ── --help y errores en castellano ─────────────────────────────────────────


def plano(texto):
    """Sin los saltos de línea que pone Rich al ajustar al ancho."""
    return " ".join(texto.split())


@pytest.mark.parametrize("pedido", [["ocupa", "--help"], ["ocupa", "-h"]])
def test_help_de_un_comando_en_castellano(pedido):
    resultado = runner.invoke(app, pedido)
    assert resultado.exit_code == 0
    texto = plano(resultado.output)
    assert "Uso: navaja ocupa [RUTA] [opciones]" in texto
    assert "--mayores" in texto and "por defecto: 15" in texto
    for ingles in ("Usage", "Options", "Show this message"):
        assert ingles not in texto


def test_help_de_un_grupo_y_de_navaja():
    texto = plano(runner.invoke(app, ["ordena", "--help"]).output)
    assert "Uso: navaja ordena <subcomando>" in texto
    assert "tramo" in texto and "letra" in texto
    assert "Commands" not in texto

    texto = plano(runner.invoke(app, ["--help"]).output)
    assert "navaja manual" in texto and "duplicados" in texto
    assert "Usage" not in texto


@pytest.mark.parametrize(
    "pedido, esperado",
    [
        (["ocupa", "-n", "abc"], "--mayores: «abc» no es un número entero."),
        (["ocupa", "-n", "0"], "--mayores: 0 no vale: tiene que ser 1 o más."),
        (["ordena", "tipo", "--xyz"], "No existe la opción --xyz."),
        (["renombra", "cambiar"], "Falta BUSCAR: Qué texto del nombre quieres cambiar"),
        (["ordena", "tipo", "sobra"], "Sobra «sobra»."),
        (["ordena", "fecha", "--por", "semana"], "«semana» no vale; elige mes, año o día."),
        (["ordna"], "No existe «ordna». ¿Querías decir ordena?"),
    ],
)
def test_errores_de_uso_en_castellano(pedido, esperado):
    resultado = runner.invoke(app, pedido)
    assert resultado.exit_code == 2
    texto = plano(resultado.output)
    assert esperado in texto
    assert "Uso: navaja" in texto and "--help" in texto
    for ingles in ("Usage", "Invalid value", "Missing", "No such", "Error"):
        assert ingles not in texto
