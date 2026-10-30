"""Organizador de carpetas por tipo de archivo o fecha."""

from __future__ import annotations

import shutil
from collections import Counter
from datetime import datetime
from enum import Enum
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

CATEGORIAS: dict[str, set[str]] = {
    "imagenes": {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
        ".tif", ".tiff", ".heic", ".raw", ".cr2", ".nef", ".ico",
    },
    "videos": {
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".mpg", ".mpeg", ".3gp",
    },
    "audio": {
        ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus",
    },
    "documentos": {
        ".pdf", ".doc", ".docx", ".txt", ".md", ".odt", ".rtf",
        ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".csv", ".epub",
    },
    "comprimidos": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".iso",
    },
    "codigo": {
        ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp",
        ".h", ".hpp", ".go", ".rs", ".rb", ".php", ".sh", ".html", ".css",
        ".scss", ".json", ".yaml", ".yml", ".toml", ".xml", ".sql", ".lua",
    },
    "ejecutables": {
        ".exe", ".msi", ".deb", ".rpm", ".appimage", ".dmg", ".apk", ".bat",
    },
}

NOMBRES = {
    "imagenes": "Imagenes",
    "videos": "Videos",
    "audio": "Audio",
    "documentos": "Documentos",
    "comprimidos": "Comprimidos",
    "codigo": "Codigo",
    "ejecutables": "Ejecutables",
    "otros": "Otros",
}


class ModoOrden(str, Enum):
    extension = "extension"
    fecha = "fecha"


def _categoria(nombre: str) -> str:
    extension = Path(nombre).suffix.lower()
    for categoria, extensiones in CATEGORIAS.items():
        if extension in extensiones:
            return categoria
    return "otros"


def _destino_libre(destino: Path, reservados: set[str]) -> Path:
    candidato = destino
    base = destino.stem
    sufijo = destino.suffix
    indice = 1
    while candidato.exists() or str(candidato).lower() in reservados:
        candidato = destino.with_name(f"{base} ({indice}){sufijo}")
        indice += 1
    reservados.add(str(candidato).lower())
    return candidato


def _planificar(
    ruta: Path,
    modo: ModoOrden,
    destino: Path,
    recursivo: bool,
    incluir_ocultos: bool,
) -> list[dict]:
    movimientos: list[dict] = []
    reservados: set[str] = set()

    destino_resuelto = destino.resolve()
    ruta_resuelta = ruta.resolve()

    for origen in iterar_archivos(ruta, recursivo, incluir_ocultos):
        if (
            recursivo
            and destino_resuelto != ruta_resuelta
            and origen.resolve().is_relative_to(destino_resuelto)
        ):
            continue

        categoria = _categoria(origen.name)
        if modo is ModoOrden.fecha:
            marca = datetime.fromtimestamp(origen.stat().st_mtime)
            subcarpeta = Path(f"{marca.year:04d}") / f"{marca.month:02d}"
        else:
            subcarpeta = Path(NOMBRES[categoria])

        deseado = destino / subcarpeta / origen.name
        if deseado == origen:
            continue
        final = _destino_libre(deseado, reservados)
        movimientos.append(
            {
                "origen": str(origen),
                "destino": str(final),
                "categoria": categoria,
            }
        )
    return movimientos


def _mostrar_plan(movimientos: list[dict], ruta: Path, limite: int = 100) -> None:
    conteo = Counter(movimiento["categoria"] for movimiento in movimientos)
    resumen = "  ·  ".join(
        f"{NOMBRES[categoria]}: [bold]{cantidad}[/]"
        for categoria, cantidad in sorted(conteo.items())
    )
    console.print(
        Panel(
            f"Se moverían [bold]{len(movimientos)}[/] archivos.\n{resumen}",
            title="Plan de organización",
            border_style="cyan",
        )
    )

    tabla = crear_tabla(["Categoría", "Origen", "Destino"])
    for movimiento in movimientos[:limite]:
        origen = Path(movimiento["origen"])
        destino = Path(movimiento["destino"])
        try:
            origen_texto = str(origen.relative_to(ruta))
        except ValueError:
            origen_texto = str(origen)
        try:
            destino_texto = str(destino.relative_to(ruta))
        except ValueError:
            destino_texto = str(destino)
        tabla.add_row(
            NOMBRES[movimiento["categoria"]],
            escape(origen_texto),
            escape(destino_texto),
        )
    console.print(tabla)

    if len(movimientos) > limite:
        console.print(
            f"[dim]Mostrando {limite} de {len(movimientos)} movimientos.[/]"
        )


def _validar(ruta: Path) -> None:
    if not ruta.exists() or not ruta.is_dir():
        error_console.print(f"[red]La carpeta no existe:[/] {escape(str(ruta))}")
        raise typer.Exit(1)


def previsualizar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta a organizar.", show_default=True
    ),
    por: ModoOrden = typer.Option(
        ModoOrden.extension,
        "--por",
        help="Criterio: extensión del archivo o fecha de modificación.",
    ),
    destino: Path | None = typer.Option(
        None, "--destino", "-d", help="Carpeta base donde organizar."
    ),
    recursivo: bool = typer.Option(
        False, "--recursivo", "-r", help="Incluir subcarpetas."
    ),
    ocultos: bool = typer.Option(
        False, "--ocultos", help="Incluir archivos ocultos."
    ),
) -> None:
    """Muestra qué se movería sin tocar ningún archivo."""
    _validar(ruta)
    base = destino or ruta
    movimientos = _planificar(ruta, por, base, recursivo, ocultos)
    if not movimientos:
        console.print("[green]No hay nada que organizar.[/]")
        return
    _mostrar_plan(movimientos, ruta)


def aplicar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta a organizar.", show_default=True
    ),
    por: ModoOrden = typer.Option(
        ModoOrden.extension,
        "--por",
        help="Criterio: extensión del archivo o fecha de modificación.",
    ),
    destino: Path | None = typer.Option(
        None, "--destino", "-d", help="Carpeta base donde organizar."
    ),
    recursivo: bool = typer.Option(
        False, "--recursivo", "-r", help="Incluir subcarpetas."
    ),
    ocultos: bool = typer.Option(
        False, "--ocultos", help="Incluir archivos ocultos."
    ),
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación."
    ),
) -> None:
    """Organiza los archivos de verdad (se puede deshacer)."""
    _validar(ruta)
    base = destino or ruta
    movimientos = _planificar(ruta, por, base, recursivo, ocultos)
    if not movimientos:
        console.print("[green]No hay nada que organizar.[/]")
        return

    _mostrar_plan(movimientos, ruta)
    if not confirmar("¿Mover los archivos?", saltar=si, por_defecto=False):
        console.print("[yellow]Cancelado.[/]")
        return

    realizados: list[dict] = []
    errores = 0
    for movimiento in movimientos:
        origen = Path(movimiento["origen"])
        destino_final = Path(movimiento["destino"])
        try:
            destino_final.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origen), str(destino_final))
            realizados.append(
                {"origen": str(origen), "destino": str(destino_final)}
            )
        except OSError as exc:
            errores += 1
            error_console.print(f"[red]No se pudo mover[/] {escape(str(origen))}: {escape(str(exc))}")

    if realizados:
        guardar_acciones("ordena", realizados)
    console.print(f"[green]Movidos {len(realizados)} archivos.[/]")
    if errores:
        console.print(f"[yellow]{errores} archivos no se pudieron mover.[/]")
    if realizados:
        console.print("[dim]Puedes revertirlo con: navaja ordena deshacer[/]")


def deshacer(
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación."
    ),
) -> None:
    """Revierte la última organización realizada."""
    acciones = cargar_acciones("ordena")
    if not acciones:
        console.print("[yellow]No hay ninguna organización que deshacer.[/]")
        return

    console.print(f"Se devolverían [bold]{len(acciones)}[/] archivos a su sitio.")
    if not confirmar("¿Deshacer la última organización?", saltar=si, por_defecto=False):
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
            origen.parent.mkdir(parents=True, exist_ok=True)
            final = ruta_libre(origen)
            shutil.move(str(destino), str(final))
            devueltos += 1
        except OSError as exc:
            errores += 1
            error_console.print(f"[red]No se pudo devolver[/] {escape(str(destino))}: {escape(str(exc))}")

    limpiar_acciones("ordena")
    console.print(f"[green]Devueltos {devueltos} archivos.[/]")
    if errores:
        console.print(f"[yellow]{errores} archivos no se pudieron devolver.[/]")


def categorias() -> None:
    """Lista las categorías y extensiones que reconoce el organizador."""
    tabla = crear_tabla(["Categoría", "Carpeta", "Extensiones"])
    for categoria, extensiones in CATEGORIAS.items():
        tabla.add_row(
            categoria,
            NOMBRES[categoria],
            " ".join(sorted(extensiones)),
        )
    tabla.add_row("otros", NOMBRES["otros"], "(cualquier otra extensión)")
    console.print(tabla)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Organiza archivos por extensión o fecha, con opción de deshacer.",
        no_args_is_help=True,
    )
    sub.command("previsualizar", help="Muestra el plan sin mover nada.")(previsualizar)
    sub.command("aplicar", help="Mueve los archivos (se puede deshacer).")(aplicar)
    sub.command("deshacer", help="Revierte la última organización.")(deshacer)
    sub.command("categorias", help="Lista las categorías y extensiones.")(categorias)
    app.add_typer(sub, name="ordena")
