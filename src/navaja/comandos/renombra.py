"""Renombrado masivo de archivos usando expresiones regulares."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel

from ..comun import (
    cargar_acciones,
    confirmar,
    console,
    crear_tabla,
    error_console,
    guardar_acciones,
    iterar_archivos,
    limpiar_acciones,
    ruta_libre,
)

COLORES_ESTADO = {
    "ok": "green",
    "igual": "dim",
    "conflicto": "red",
    "invalido": "red",
}


def _nombre_valido(nombre: str) -> bool:
    return bool(nombre) and nombre not in {".", ".."} and Path(nombre).name == nombre


def _planificar(
    ruta: Path,
    patron: str,
    reemplazo: str,
    incluir: str,
    recursivo: bool,
    completos: bool,
    ocultos: bool,
) -> list[dict]:
    regex = re.compile(patron)
    movimientos: list[dict] = []
    reservados: set[str] = set()

    for origen in iterar_archivos(ruta, recursivo, ocultos, incluir):
        base = origen.name if completos else origen.stem
        nuevo_base = regex.sub(reemplazo, base)
        nuevo = nuevo_base if completos else nuevo_base + origen.suffix
        destino = origen.parent / nuevo
        entrada = {
            "origen": str(origen),
            "destino": str(destino),
            "estado": "ok",
            "motivo": "",
        }

        if nuevo == origen.name:
            entrada["estado"] = "igual"
            entrada["motivo"] = "sin cambios"
        elif not _nombre_valido(nuevo):
            entrada["estado"] = "invalido"
            entrada["motivo"] = "nombre no válido"
        else:
            clave = str(destino).lower()
            if clave in reservados:
                entrada["estado"] = "conflicto"
                entrada["motivo"] = "nombre repetido"
            elif destino.exists():
                entrada["estado"] = "conflicto"
                entrada["motivo"] = "el destino ya existe"
            else:
                reservados.add(clave)
        movimientos.append(entrada)

    return movimientos


def _mostrar_plan(movimientos: list[dict], limite: int = 200) -> None:
    conteo = Counter(movimiento["estado"] for movimiento in movimientos)
    resumen = "  ·  ".join(
        f"{estado}: [bold]{cantidad}[/]" for estado, cantidad in sorted(conteo.items())
    )
    console.print(
        Panel(
            f"Archivos analizados: [bold]{len(movimientos)}[/]\n{resumen}",
            title="Plan de renombrado",
            border_style="cyan",
        )
    )

    tabla = crear_tabla(["Estado", "Actual", "Nuevo"])
    for movimiento in movimientos[:limite]:
        estado = movimiento["estado"]
        color = COLORES_ESTADO.get(estado, "white")
        actual = Path(movimiento["origen"]).name
        nuevo = Path(movimiento["destino"]).name
        etiqueta = estado if not movimiento["motivo"] else f"{estado}: {movimiento['motivo']}"
        tabla.add_row(f"[{color}]{etiqueta}[/]", escape(actual), escape(nuevo))
    console.print(tabla)

    if len(movimientos) > limite:
        console.print(f"[dim]Mostrando {limite} de {len(movimientos)} archivos.[/]")


def _validar(ruta: Path, patron: str) -> None:
    if not ruta.exists() or not ruta.is_dir():
        error_console.print(f"[red]La carpeta no existe:[/] {escape(str(ruta))}")
        raise typer.Exit(1)
    try:
        re.compile(patron)
    except re.error as exc:
        error_console.print(f"[red]Expresión regular inválida:[/] {escape(str(exc))}")
        raise typer.Exit(2)


def previsualizar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta con los archivos.", show_default=True
    ),
    patron: str = typer.Argument(..., help="Expresión regular a buscar."),
    reemplazo: str = typer.Argument(
        ..., help="Texto de reemplazo. Usa \\1, \\2… para los grupos."
    ),
    incluir: str = typer.Option(
        "*", "--incluir", "-i", help="Patrón glob de archivos.", show_default=True
    ),
    recursivo: bool = typer.Option(
        False, "--recursivo", "-r", help="Incluir subcarpetas."
    ),
    completo: bool = typer.Option(
        False,
        "--completo",
        "-c",
        help="Renombrar el nombre completo (incluida la extensión).",
    ),
    ocultos: bool = typer.Option(
        False, "--ocultos", help="Incluir archivos ocultos."
    ),
) -> None:
    """Muestra cómo quedarían los nombres sin cambiar nada."""
    _validar(ruta, patron)
    movimientos = _planificar(
        ruta, patron, reemplazo, incluir, recursivo, completo, ocultos
    )
    if not movimientos:
        console.print("[green]No se encontraron archivos.[/]")
        return
    _mostrar_plan(movimientos)


def aplicar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta con los archivos.", show_default=True
    ),
    patron: str = typer.Argument(..., help="Expresión regular a buscar."),
    reemplazo: str = typer.Argument(
        ..., help="Texto de reemplazo. Usa \\1, \\2… para los grupos."
    ),
    incluir: str = typer.Option(
        "*", "--incluir", "-i", help="Patrón glob de archivos.", show_default=True
    ),
    recursivo: bool = typer.Option(
        False, "--recursivo", "-r", help="Incluir subcarpetas."
    ),
    completo: bool = typer.Option(
        False,
        "--completo",
        "-c",
        help="Renombrar el nombre completo (incluida la extensión).",
    ),
    ocultos: bool = typer.Option(
        False, "--ocultos", help="Incluir archivos ocultos."
    ),
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación."
    ),
) -> None:
    """Renombra los archivos de verdad (se puede deshacer)."""
    _validar(ruta, patron)
    movimientos = _planificar(
        ruta, patron, reemplazo, incluir, recursivo, completo, ocultos
    )
    if not movimientos:
        console.print("[green]No se encontraron archivos.[/]")
        return

    _mostrar_plan(movimientos)
    aplicables = [m for m in movimientos if m["estado"] == "ok"]
    if not aplicables:
        console.print("[yellow]No hay ningún cambio aplicable.[/]")
        return
    if not confirmar(
        f"¿Renombrar {len(aplicables)} archivos?", saltar=si, por_defecto=False
    ):
        console.print("[yellow]Cancelado.[/]")
        return

    realizados: list[dict] = []
    errores = 0
    for movimiento in aplicables:
        origen = Path(movimiento["origen"])
        destino = Path(movimiento["destino"])
        try:
            origen.rename(destino)
            realizados.append({"origen": str(origen), "destino": str(destino)})
        except OSError as exc:
            errores += 1
            error_console.print(f"[red]No se pudo renombrar[/] {escape(str(origen))}: {escape(str(exc))}")

    if realizados:
        guardar_acciones("renombra", realizados)
    console.print(f"[green]Renombrados {len(realizados)} archivos.[/]")
    if errores:
        console.print(f"[yellow]{errores} archivos no se pudieron renombrar.[/]")
    if realizados:
        console.print("[dim]Puedes revertirlo con: navaja renombra deshacer[/]")


def deshacer(
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación."
    ),
) -> None:
    """Revierte el último renombrado realizado."""
    acciones = cargar_acciones("renombra")
    if not acciones:
        console.print("[yellow]No hay ningún renombrado que deshacer.[/]")
        return

    console.print(f"Se devolverían [bold]{len(acciones)}[/] nombres.")
    if not confirmar("¿Deshacer el último renombrado?", saltar=si, por_defecto=False):
        console.print("[yellow]Cancelado.[/]")
        return

    devueltos = 0
    errores = 0
    for accion in reversed(acciones):
        origen = Path(accion["origen"])
        destino = Path(accion["destino"])
        if not destino.exists():
            continue
        try:
            final = ruta_libre(origen)
            destino.rename(final)
            devueltos += 1
        except OSError as exc:
            errores += 1
            error_console.print(f"[red]No se pudo devolver[/] {escape(str(destino))}: {escape(str(exc))}")

    limpiar_acciones("renombra")
    console.print(f"[green]Restaurados {devueltos} nombres.[/]")
    if errores:
        console.print(f"[yellow]{errores} nombres no se pudieron restaurar.[/]")


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Renombra archivos en masa con expresiones regulares.",
        no_args_is_help=True,
    )
    sub.command("previsualizar", help="Muestra los nombres nuevos sin cambiar nada.")(
        previsualizar
    )
    sub.command("aplicar", help="Renombra los archivos (se puede deshacer).")(aplicar)
    sub.command("deshacer", help="Revierte el último renombrado.")(deshacer)
    app.add_typer(sub, name="renombra")
