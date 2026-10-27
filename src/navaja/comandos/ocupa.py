"""Analizador de disco y limpieza de archivos temporales."""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path

import typer
from rich.panel import Panel

from ..comun import (
    confirmar,
    console,
    crear_tabla,
    error_console,
    tamano_legible,
)

BASURA_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "node_modules",
    ".next",
    ".parcel-cache",
    ".turbo",
    "dist",
    "build",
    "target",
    "htmlcov",
    ".cache",
    ".gradle",
    "coverage",
}

BASURA_ARCHIVOS = {".DS_Store", "Thumbs.db", "desktop.ini"}

BASURA_PATRONES = {"*.pyc", "*.pyo", "*.tmp", "*.swp", "*.swo", "*.~"}

DIRS_IGNORADOS = {".git", ".hg", ".svn", "venv", ".venv"}


def _tamano_ruta(ruta: Path) -> tuple[int, int]:
    """Calcula tamaño total y número de archivos de una carpeta."""
    total = 0
    archivos = 0
    pila = [ruta]
    while pila:
        actual = pila.pop()
        try:
            with os.scandir(actual) as entradas:
                for entrada in entradas:
                    try:
                        if entrada.is_dir(follow_symlinks=False):
                            pila.append(Path(entrada.path))
                        elif entrada.is_file(follow_symlinks=False):
                            total += entrada.stat(follow_symlinks=False).st_size
                            archivos += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, archivos


def _recolectar(ruta: Path, profundidad: int, nivel: int = 0) -> list[tuple]:
    resultado: list[tuple] = []
    try:
        with os.scandir(ruta) as entradas:
            ordenadas = sorted(entradas, key=lambda e: e.name.lower())
    except OSError as exc:
        error_console.print(f"[yellow]No se pudo leer {ruta}: {exc}[/]")
        return resultado

    for entrada in ordenadas:
        ruta_entrada = Path(entrada.path)
        try:
            if entrada.is_dir(follow_symlinks=False):
                tam, num = _tamano_ruta(ruta_entrada)
                resultado.append((ruta_entrada, tam, num, nivel, True))
                if nivel + 1 < profundidad:
                    resultado.extend(
                        _recolectar(ruta_entrada, profundidad, nivel + 1)
                    )
            elif entrada.is_file(follow_symlinks=False):
                tam = entrada.stat(follow_symlinks=False).st_size
                resultado.append((ruta_entrada, tam, 1, nivel, False))
        except OSError:
            continue
    return resultado


def _barra(porcentaje: float, ancho: int = 18) -> str:
    llenos = round(max(0.0, min(100.0, porcentaje)) / 100 * ancho)
    color = "green" if porcentaje < 60 else "yellow" if porcentaje < 85 else "red"
    return f"[{color}]{'█' * llenos}[/][dim]{'░' * (ancho - llenos)}[/]"


def ocupa(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta que se quiere analizar.", show_default=True
    ),
    mayores: int = typer.Option(
        15, "--mayores", "-n", help="Número de entradas a mostrar.", show_default=True
    ),
    profundidad: int = typer.Option(
        1,
        "--profundidad",
        "-p",
        help="Niveles de carpetas que se muestran.",
        show_default=True,
    ),
) -> None:
    """Muestra qué archivos y carpetas ocupan más espacio."""
    if profundidad < 1:
        raise typer.BadParameter("La profundidad debe ser como mínimo 1.")
    if not ruta.exists():
        error_console.print(f"[red]La ruta no existe:[/] {ruta}")
        raise typer.Exit(1)

    if ruta.is_file():
        tam = ruta.stat().st_size
        console.print(f"{ruta.name}: [bold]{tamano_legible(tam)}[/]")
        return

    entradas = _recolectar(ruta, profundidad)
    total = sum(tam for _, tam, _, nivel, _ in entradas if nivel == 0)
    num_archivos = sum(num for _, _, num, nivel, _ in entradas if nivel == 0)
    libre = shutil.disk_usage(ruta).free

    resumen = (
        f"[bold]{ruta.resolve()}[/]\n"
        f"Tamaño: [bold cyan]{tamano_legible(total)}[/]  ·  "
        f"Archivos: [bold]{num_archivos:,}[/]  ·  "
        f"Libre en el disco: [bold green]{tamano_legible(libre)}[/]"
    )
    console.print(Panel(resumen, title="Uso de disco", border_style="cyan"))

    if not entradas:
        console.print("[yellow]La carpeta está vacía.[/]")
        return

    entradas.sort(key=lambda item: item[1], reverse=True)
    visibles = entradas[:mayores]

    tabla = crear_tabla(["Tamaño", "%", "Uso", "Archivos", "Ruta"])
    for ruta_entrada, tam, num, nivel, es_dir in visibles:
        porcentaje = (tam / total * 100) if total else 0.0
        nombre = os.path.relpath(ruta_entrada, ruta)
        sangria = "  " * nivel
        etiqueta = f"{sangria}{nombre}{'/' if es_dir else ''}"
        tabla.add_row(
            tamano_legible(tam),
            f"{porcentaje:5.1f}%",
            _barra(porcentaje),
            f"{num:,}",
            etiqueta,
        )
    console.print(tabla)

    if len(entradas) > len(visibles):
        console.print(
            f"[dim]Mostrando {len(visibles)} de {len(entradas)} entradas. "
            "Usa --mayores para ver más.[/]"
        )


def _buscar_basura(raiz: Path) -> list[tuple[Path, int, int, str]]:
    candidatos: list[tuple[Path, int, int, str]] = []
    for actual, dirs, archivos in os.walk(raiz):
        actual_path = Path(actual)

        for nombre in list(dirs):
            ruta_dir = actual_path / nombre
            if nombre in DIRS_IGNORADOS:
                dirs.remove(nombre)
                continue
            if nombre in BASURA_DIRS:
                tam, num = _tamano_ruta(ruta_dir)
                candidatos.append((ruta_dir, tam, num, "carpeta"))
                dirs.remove(nombre)

        for nombre in archivos:
            coincide = nombre in BASURA_ARCHIVOS or any(
                fnmatch.fnmatch(nombre, patron) for patron in BASURA_PATRONES
            )
            if not coincide:
                continue
            ruta_archivo = actual_path / nombre
            try:
                tam = ruta_archivo.stat().st_size
            except OSError:
                continue
            candidatos.append((ruta_archivo, tam, 1, "archivo"))
    return candidatos


def limpia(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta donde buscar archivos temporales.", show_default=True
    ),
    seco: bool = typer.Option(
        False, "--seco", help="Solo muestra lo que se borraría, sin borrar nada."
    ),
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación antes de borrar."
    ),
) -> None:
    """Busca y elimina cachés y archivos temporales (node_modules, __pycache__…)."""
    if not ruta.exists() or not ruta.is_dir():
        error_console.print(f"[red]La carpeta no existe:[/] {ruta}")
        raise typer.Exit(1)

    candidatos = _buscar_basura(ruta)
    if not candidatos:
        console.print("[green]No se encontró basura.[/]")
        return

    candidatos.sort(key=lambda item: item[1], reverse=True)
    total = sum(tam for _, tam, _, _ in candidatos)

    tabla = crear_tabla(["Tamaño", "Tipo", "Ruta"], titulo="Candidatos a borrar")
    for ruta_candidata, tam, _, tipo in candidatos:
        tabla.add_row(
            tamano_legible(tam),
            tipo,
            str(ruta_candidata),
        )
    console.print(tabla)
    console.print(
        f"Se liberarían [bold green]{tamano_legible(total)}[/] "
        f"en {len(candidatos)} entradas."
    )

    if seco:
        console.print("[yellow]Modo seco: no se borró nada.[/]")
        return

    if not confirmar("¿Borrar todo lo anterior?", saltar=si, por_defecto=False):
        console.print("[yellow]Cancelado.[/]")
        return

    liberado = 0
    errores = 0
    for ruta_candidata, tam, _, tipo in candidatos:
        try:
            if tipo == "carpeta":
                shutil.rmtree(ruta_candidata)
            else:
                ruta_candidata.unlink()
            liberado += tam
        except OSError as exc:
            errores += 1
            error_console.print(f"[red]No se pudo borrar[/] {ruta_candidata}: {exc}")

    console.print(f"[green]Liberados {tamano_legible(liberado)}.[/]")
    if errores:
        console.print(f"[yellow]{errores} entradas no se pudieron borrar.[/]")


def registrar(app: typer.Typer) -> None:
    app.command("ocupa", help="Muestra qué ocupa espacio en disco.")(ocupa)
    app.command("limpia", help="Borra cachés y archivos temporales.")(limpia)
