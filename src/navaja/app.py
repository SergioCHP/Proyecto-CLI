"""Punto de entrada de la CLI Navaja."""

from __future__ import annotations

import errno
import os
import sys
from datetime import datetime

import typer
from typer.completion import completion_init

from . import __version__, interactivo, logo
from .comandos import (
    ajustes,
    arbol,
    ayuda,
    baja,
    base,
    busca,
    chmod,
    chuleta,
    clave,
    compara,
    comprime,
    convierte,
    copia,
    cuenta,
    doctor,
    duplicados,
    entregas,
    estudia,
    extrae,
    falsos,
    foco,
    fondo,
    genera,
    hoy,
    huella,
    ia,
    imagen,
    listar,
    mis_acciones,
    notas,
    nuevo,
    ocupa,
    ordena,
    pdf,
    puertos,
    qr,
    red,
    renombra,
    sistema,
    sql,
    subred,
)
from .comun import aplicar_tema, cargar_config, console, nombre_para_saludar, preparar_salida

app = typer.Typer(
    name="navaja",
    help=(
        "Caja de herramientas de terminal con utilidades cotidianas.\n\n"
        "Comandos: [bold]listar[/], [bold]ocupa[/], [bold]limpia[/], [bold]arbol[/], "
        "[bold]busca[/], [bold]comprime[/], [bold]extrae[/], [bold]ordena[/], "
        "[bold]renombra[/], [bold]duplicados[/], [bold]copia[/], [bold]notas[/], "
        "[bold]convierte[/], [bold]cuenta[/], [bold]fondo[/], [bold]baja[/], [bold]qr[/], "
        "[bold]pdf[/], [bold]imagen[/], [bold]base[/], "
        "[bold]chmod[/], [bold]red[/], [bold]puertos[/], [bold]sistema[/], [bold]subred[/], [bold]hash[/], [bold]genera[/], "
        "[bold]clave[/], [bold]chuleta[/], [bold]nuevo[/], [bold]hoy[/], [bold]compara[/], [bold]falsos[/], [bold]sql[/], [bold]estudia[/], [bold]foco[/], "
        "[bold]entregas[/], [bold]acciones[/], [bold]doctor[/], [bold]comprobar-ia[/], "
        "[bold]tema[/], [bold]config[/] y [bold]manual[/] (explica todo)."
    ),
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
ayuda.instalar_en_castellano()
completion_init()  # Tab en PowerShell y bash: ver «config autocompletar»


def saludo(hora: int, nombre: str) -> str:
    """Saludo según la hora del día (0-23); sin nombre, solo el saludo."""
    if 6 <= hora < 14:
        momento = "Buenos días"
    elif 14 <= hora < 21:
        momento = "Buenas tardes"
    else:
        momento = "Buenas noches"
    return f"{momento}, {nombre}" if nombre else momento


def resumen_comandos(raiz: typer.Typer) -> list[tuple[str, str]]:
    """Nombre y ayuda corta de cada comando, en el mismo orden que el menú."""
    grupo = typer.main.get_command(raiz)
    return [(nombre, comando.help or "") for nombre, comando in ayuda.subcomandos(grupo)]


def _rotulo_grande() -> bool:
    """¿Cabe el rótulo grande y, debajo, el menú entero? Si la ventana es baja, se usa el
    recuadro sencillo para dejar sitio al menú."""
    if not console.is_terminal:
        return True
    menu = interactivo.alto_menu(typer.main.get_command(app))
    return logo.ALTO_GRANDE + menu + interactivo.MARGEN <= console.height


def _mostrar_cabecera(config: dict[str, str], grande: bool = True) -> None:
    hola = saludo(datetime.now().hour, nombre_para_saludar(config))
    detalle = f"navaja {__version__} · tema {config['tema']}"
    console.print(logo.rotulo(console, hola, detalle, grande))


def _mostrar_bienvenida(config: dict[str, str]) -> None:
    _mostrar_cabecera(config)
    console.print(ayuda.tabla_secciones(typer.main.get_command(app)))
    console.print(
        "\n[pista]Ayuda de un comando: navaja <comando> --help · Todo explicado: navaja manual[/]"
    )


def _mostrar_version(valor: bool) -> None:
    if valor:
        typer.echo(f"navaja {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def principal(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=_mostrar_version,
        is_eager=True,
        help="Muestra la versión y sale.",
    ),
) -> None:
    """Utilidades de terminal en castellano. Sin comando, abre el modo interactivo."""
    config = cargar_config()
    aplicar_tema(config["tema"])
    if ctx.invoked_subcommand is None:
        if interactivo.puede_iniciar():
            if not config["nombre"]:  # la primera vez
                config["nombre"] = ajustes.preguntar_nombre()
            grande = _rotulo_grande()
            _mostrar_cabecera(config, grande)
            reservado = logo.ALTO_GRANDE if grande else logo.ALTO_SENCILLO
            if aviso := entregas.aviso_de_pendientes():
                console.print(aviso)
                reservado += 2
            interactivo.iniciar(app, reservado=reservado)
        else:
            _mostrar_bienvenida(config)


@app.command("version", hidden=True)
def version_orden() -> None:
    """Muestra la versión (lo mismo que navaja --version)."""
    typer.echo(f"navaja {__version__}")


for modulo in (
    listar, ocupa, arbol, busca, comprime, extrae, ordena, renombra, duplicados, copia, notas,
    convierte, cuenta, fondo, baja, qr, pdf, imagen,
    base, chmod, red, puertos, sistema, subred,
    estudia, foco, entregas,
    huella, genera, clave, chuleta, nuevo, hoy, compara, falsos, sql,
    mis_acciones, doctor, ia, ajustes, ayuda,
):
    modulo.registrar(app)


def tuberia_cerrada(error: OSError) -> bool:
    """¿El error es que quien leía la salida ya se fue («navaja … | head -1»)?

    En Linux y macOS es ``BrokenPipeError``; en Windows, un ``OSError`` 22 (Invalid
    argument). Ese mismo número sale también con una ruta mala, así que se comprueba que
    lo roto sea de verdad la salida: si se puede vaciar, el error era de otra cosa.
    """
    if isinstance(error, BrokenPipeError):
        return True
    if error.errno != errno.EINVAL:
        return False
    try:
        sys.stdout.flush()
    except OSError:
        return True
    return False


def silenciar_salida() -> None:
    """Lo que quede por escribir va a la nada: si no, Python lo intenta otra vez al cerrar
    y suelta «Exception ignored … OSError»."""
    try:
        nulo = os.open(os.devnull, os.O_WRONLY)
        os.dup2(nulo, sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):  # sin descriptor de verdad (p. ej. tests)
        pass


def argumentos_de_windows(argumentos: list[str], windows: bool = os.name == "nt") -> list[str] | None:
    """En Windows, ``~`` y ``%VARIABLES%`` de cada argumento, como hace Click, pero sin
    expandir ``*``: Click lo haría en la carpeta actual (no en la de ``-c``) y estropearía
    patrones como ``IMG_*`` de renombra; quien necesita un comodín lo expande él.

    cmd y Windows PowerShell no convierten ``~`` al llamar a un programa: sin esto,
    ``navaja ordena tipo -c ~\\Descargas`` diría que la carpeta no existe. En Linux y
    macOS lo hace el shell, y se devuelve None (Click lee los argumentos como siempre).
    """
    if not windows:
        return None
    return [os.path.expandvars(os.path.expanduser(argumento)) for argumento in argumentos]


def main() -> None:
    preparar_salida(sys.stdout)  # Git Bash / salida redirigida: ✔ y → sin trazas
    preparar_salida(sys.stderr)
    try:
        app(args=argumentos_de_windows(sys.argv[1:]), windows_expand_args=False)
    except OSError as error:
        if not tuberia_cerrada(error):
            raise
        silenciar_salida()  # «| head -1» y similares: quien leía ya tiene lo que quería
        sys.exit(1)


if __name__ == "__main__":
    main()
