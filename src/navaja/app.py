"""Punto de entrada de la CLI Navaja."""

from __future__ import annotations

from datetime import datetime

import typer
from rich.markup import escape
from typer.completion import completion_init
from rich.panel import Panel
from rich.table import Table

from . import __version__, interactivo
from .comandos import (
    ajustes,
    ayuda,
    duplicados,
    listar,
    mis_acciones,
    notas,
    ocupa,
    ordena,
    renombra,
)
from .comun import aplicar_tema, cargar_config, console, nombre_para_saludar

app = typer.Typer(
    name="navaja",
    help=(
        "Caja de herramientas de terminal con utilidades cotidianas.\n\n"
        "Comandos: [bold]listar[/], [bold]ocupa[/], [bold]limpia[/], [bold]ordena[/], "
        "[bold]renombra[/], [bold]duplicados[/], [bold]notas[/], [bold]acciones[/], "
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


def _mostrar_cabecera(config: dict[str, str]) -> None:
    texto = (
        f"[titulo]{escape(saludo(datetime.now().hour, nombre_para_saludar(config)))}[/]\n"
        f"[pista]navaja {__version__} · tema {config['tema']}[/]"
    )
    console.print(Panel(texto, title="navaja", border_style="marco", expand=False))


def _mostrar_bienvenida(config: dict[str, str]) -> None:
    _mostrar_cabecera(config)
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", no_wrap=True)
    tabla.add_column()
    for nombre, texto in resumen_comandos(app):
        tabla.add_row(nombre, texto)
    console.print(tabla)
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
            _mostrar_cabecera(config)
            interactivo.iniciar(app)
        else:
            _mostrar_bienvenida(config)


@app.command("version", hidden=True)
def version_orden() -> None:
    """Muestra la versión (lo mismo que navaja --version)."""
    typer.echo(f"navaja {__version__}")


for modulo in (listar, ocupa, ordena, renombra, duplicados, notas, mis_acciones, ajustes, ayuda):
    modulo.registrar(app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
