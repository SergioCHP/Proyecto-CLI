"""Punto de entrada de la CLI Navaja."""

from __future__ import annotations

import typer

from . import __version__
from .comandos import notas, ocupa, ordena, renombra

app = typer.Typer(
    name="navaja",
    help=(
        "Caja de herramientas de terminal con utilidades cotidianas.\n\n"
        "Comandos: [bold]ocupa[/], [bold]limpia[/], [bold]ordena[/], "
        "[bold]renombra[/] y [bold]notas[/]."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _mostrar_version(valor: bool) -> None:
    if valor:
        typer.echo(f"navaja {__version__}")
        raise typer.Exit()


@app.callback()
def principal(
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


for modulo in (ocupa, ordena, renombra, notas):
    modulo.registrar(app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
