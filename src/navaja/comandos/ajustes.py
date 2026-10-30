"""tema y config: colores y datos personales de navaja."""

from __future__ import annotations

import typer
from rich.markup import escape
from rich.theme import Theme

from ..comun import (
    TEMAS,
    aplicar_tema,
    cargar_config,
    console,
    directorio_datos,
    error_console,
    guardar_config,
)


def muestra_tema(nombre: str, actual: bool = False) -> str:
    """Línea de ejemplo con todos los estilos del tema."""
    marca = "[ok]✔[/]" if actual else " "
    return (
        f"{marca} [titulo]{nombre:<9}[/] [ok]hecho[/]  [aviso]ojo[/]  "
        f"[error]fallo[/]  [acento]acento[/]  [logro]1.2 GB[/]  [pista]pista[/]"
    )


def listar() -> None:
    """Muestra los temas disponibles con una muestra de sus colores."""
    actual = cargar_config()["tema"]
    for nombre, estilos in TEMAS.items():
        with console.use_theme(Theme(estilos)):
            console.print(muestra_tema(nombre, nombre == actual))
    console.print("\n[pista]Cambiar: navaja tema fijar <nombre>[/]")


def fijar(
    nombre: str = typer.Argument(..., help="Nombre del tema (ver: navaja tema listar)."),
) -> None:
    """Guarda el tema elegido."""
    nombre = nombre.strip().lower()
    if nombre not in TEMAS:
        error_console.print(
            f"[error]No existe el tema[/] {escape(nombre)}. "
            f"Disponibles: {', '.join(TEMAS)}."
        )
        raise typer.Exit(1)
    config = cargar_config()
    config["tema"] = nombre
    guardar_config(config)
    aplicar_tema(nombre)
    console.print(muestra_tema(nombre, actual=True))
    console.print(f"[ok]Tema cambiado a[/] [titulo]{nombre}[/].")


def ver() -> None:
    """Muestra la configuración actual."""
    config = cargar_config()
    console.print(f"Nombre: [acento]{escape(config['nombre'])}[/]")
    console.print(f"Tema:   [acento]{config['tema']}[/]")
    console.print(f"[pista]Guardada en {escape(str(directorio_datos() / 'config.json'))}[/]")


def nombre(
    nuevo: str = typer.Argument(..., help="Cómo quieres que te salude navaja."),
) -> None:
    """Cambia el nombre del saludo."""
    nuevo = nuevo.strip()
    if not nuevo:
        error_console.print("[error]El nombre no puede estar vacío.[/]")
        raise typer.Exit(1)
    config = cargar_config()
    config["nombre"] = nuevo
    guardar_config(config)
    console.print(f"[ok]A partir de ahora te saludo como[/] [acento]{escape(nuevo)}[/].")


def registrar(app: typer.Typer) -> None:
    tema = typer.Typer(help="Elige los colores de navaja.", no_args_is_help=True)
    tema.command("listar", help="Muestra los temas con una muestra de colores.")(listar)
    tema.command("fijar", help="Guarda el tema elegido.")(fijar)
    app.add_typer(tema, name="tema")

    config = typer.Typer(help="Ajustes personales: nombre y tema.", no_args_is_help=True)
    config.command("ver", help="Muestra la configuración actual.")(ver)
    config.command("nombre", help="Cambia el nombre del saludo.")(nombre)
    app.add_typer(config, name="config")
