"""Punto de entrada de la CLI Navaja."""

from __future__ import annotations

from datetime import datetime

import typer
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .comandos import ajustes, duplicados, notas, ocupa, ordena, renombra
from .comun import aplicar_tema, cargar_config, console

app = typer.Typer(
    name="navaja",
    help=(
        "Caja de herramientas de terminal con utilidades cotidianas.\n\n"
        "Comandos: [bold]ocupa[/], [bold]limpia[/], [bold]ordena[/], "
        "[bold]renombra[/], [bold]duplicados[/], [bold]notas[/], "
        "[bold]tema[/] y [bold]config[/]."
    ),
    add_completion=False,
    rich_markup_mode="rich",
)


def saludo(hora: int, nombre: str) -> str:
    """Saludo según la hora del día (0-23)."""
    if 6 <= hora < 14:
        momento = "Buenos días"
    elif 14 <= hora < 21:
        momento = "Buenas tardes"
    else:
        momento = "Buenas noches"
    return f"{momento}, {nombre}"


def resumen_comandos(raiz: typer.Typer) -> list[tuple[str, str]]:
    """Nombre y ayuda corta de cada comando registrado, en orden."""
    filas = [(c.name or "", c.help or "") for c in raiz.registered_commands]
    filas += [
        (g.name or "", g.typer_instance.info.help or "") for g in raiz.registered_groups
    ]
    return filas


def _mostrar_bienvenida(config: dict[str, str]) -> None:
    texto = (
        f"[titulo]{escape(saludo(datetime.now().hour, config['nombre']))}[/]\n"
        f"[pista]navaja {__version__} · tema {config['tema']}[/]"
    )
    console.print(Panel(texto, title="navaja", border_style="marco", expand=False))

    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", no_wrap=True)
    tabla.add_column()
    for nombre, ayuda in resumen_comandos(app):
        tabla.add_row(nombre, ayuda)
    console.print(tabla)
    console.print("\n[pista]navaja <comando> --help para más detalles[/]")


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
    """Utilidades de terminal en castellano."""
    config = cargar_config()
    aplicar_tema(config["tema"])
    if ctx.invoked_subcommand is None:
        _mostrar_bienvenida(config)


for modulo in (ocupa, ordena, renombra, duplicados, notas, ajustes):
    modulo.registrar(app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
