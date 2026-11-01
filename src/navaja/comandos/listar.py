"""listar: qué hay en una carpeta, en una tabla."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.markup import escape

from ..comun import console, crear_tabla, error_console, es_oculto, tamano_legible


def tipo_de(ruta: Path) -> str:
    """«carpeta», la extensión en minúsculas o «(sin extensión)»."""
    if ruta.is_dir():
        return "carpeta"
    return ruta.suffix.lower() or "(sin extensión)"


def contenido(carpeta: Path, ocultos: bool = False) -> list[Path]:
    """Entradas de la carpeta: primero las carpetas y luego alfabético sin mayúsculas."""
    entradas = [e for e in carpeta.iterdir() if ocultos or not es_oculto(e)]
    return sorted(entradas, key=lambda e: (not e.is_dir(), e.name.lower()))


def listar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta que quieres ver.", show_default=True
    ),
    ocultos: bool = typer.Option(
        False, "--ocultos", help="Incluir archivos ocultos."
    ),
) -> None:
    """Muestra el contenido de una carpeta: nombre, tipo, tamaño y fecha."""
    if not ruta.is_dir():
        error_console.print(
            f"[error]No existe o no es una carpeta:[/] {escape(str(ruta))}"
        )
        raise typer.Exit(1)

    try:
        entradas = contenido(ruta, ocultos)
    except OSError as exc:
        error_console.print(f"[error]No se puede leer la carpeta:[/] {escape(str(exc))}")
        raise typer.Exit(1)

    if not entradas:
        console.print(f"[aviso]La carpeta está vacía:[/] {escape(str(ruta.resolve()))}")
        return

    tabla = crear_tabla(
        ["Nombre", "Tipo", "Tamaño", "Modificado"], titulo=escape(str(ruta.resolve()))
    )
    tabla.columns[2].justify = "right"
    carpetas = archivos = 0
    for entrada in entradas:
        try:
            datos = entrada.stat()
            es_carpeta = entrada.is_dir()
        except OSError:
            continue  # enlace roto o sin permisos
        fecha = datetime.fromtimestamp(datos.st_mtime).strftime("%Y-%m-%d %H:%M")
        if es_carpeta:
            carpetas += 1
            nombre = f"[acento]{escape(entrada.name)}/[/]"
            tamano = "—"
        else:
            archivos += 1
            nombre = escape(entrada.name)
            tamano = tamano_legible(datos.st_size)
        tabla.add_row(nombre, tipo_de(entrada), tamano, fecha)

    console.print(tabla)
    console.print(
        f"[pista]{carpetas} carpeta{'' if carpetas == 1 else 's'} · "
        f"{archivos} archivo{'' if archivos == 1 else 's'}[/]"
    )


def registrar(app: typer.Typer) -> None:
    app.command("listar", help="Muestra qué hay en una carpeta.")(listar)
