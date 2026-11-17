"""navaja compara: diferencias entre dos archivos o dos carpetas, con colores.

Dos archivos de texto: las líneas quitadas en rojo y las añadidas en verde, con unas
líneas de contexto alrededor (como ``git diff``). Dos carpetas: qué está solo en una,
solo en la otra y qué ha cambiado (con ``--detalle``, también las líneas de cada uno).
No cambia nada: solo mira.
"""

from __future__ import annotations

import difflib
import filecmp
from dataclasses import dataclass, field
from pathlib import Path

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, PROGRAMACION, bonita, console, tamano_legible
from ..errores import NavajaError
from ..lotes import fallar

NO_ENTRAR = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
MAXIMO_TEXTO = 5 * 1024 * 1024
"""Un archivo más grande que esto solo se compara entero (iguales o no), sin las líneas."""

MAXIMO_LINEAS = 400
"""Cuántas líneas de diferencias se enseñan como mucho por archivo."""


def leer_texto(ruta: Path) -> list[str] | None:
    """Las líneas del archivo, o None si es binario, no es UTF-8 ni Latin-1 legible o es enorme."""
    try:
        if ruta.stat().st_size > MAXIMO_TEXTO:
            return None
        datos = ruta.read_bytes()
    except OSError as error:
        raise NavajaError(f"No se pudo leer {bonita(ruta)}: {error.strerror or error}") from error
    if b"\0" in datos[:8192]:
        return None
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion).splitlines()
        except UnicodeDecodeError:
            continue
    return None


def diferencias(a: list[str], b: list[str], nombre_a: str, nombre_b: str, contexto: int, sin_espacios: bool) -> list[str]:
    if sin_espacios:
        a = [" ".join(linea.split()) for linea in a]
        b = [" ".join(linea.split()) for linea in b]
    return list(difflib.unified_diff(a, b, nombre_a, nombre_b, n=contexto, lineterm=""))


def pintar_diff(lineas: list[str]) -> None:
    for linea in lineas[:MAXIMO_LINEAS]:
        if linea.startswith(("---", "+++")):
            estilo = "pista"
        elif linea.startswith("@@"):
            estilo = "acento"
        elif linea.startswith("+"):
            estilo = "ok"
        elif linea.startswith("-"):
            estilo = "error"
        else:
            estilo = ""
        console.print(Text(linea, style=estilo), soft_wrap=True)
    if len(lineas) > MAXIMO_LINEAS:
        console.print(f"[pista]… y {len(lineas) - MAXIMO_LINEAS} líneas más.[/]")


def comparar_archivos(a: Path, b: Path, contexto: int, sin_espacios: bool, nombre_a: str, nombre_b: str) -> bool:
    """Enseña las diferencias de dos archivos. Devuelve True si son iguales."""
    if filecmp.cmp(a, b, shallow=False):
        return True
    texto_a, texto_b = leer_texto(a), leer_texto(b)
    if texto_a is None or texto_b is None:
        console.print(
            f"[aviso]Son distintos[/] [pista](binario o muy grande: no se ven las líneas; "
            f"{tamano_legible(a.stat().st_size)} y {tamano_legible(b.stat().st_size)}).[/]"
        )
        return False
    lineas = diferencias(texto_a, texto_b, nombre_a, nombre_b, contexto, sin_espacios)
    if not lineas:
        motivo = "los espacios" if sin_espacios else "los finales de línea (Windows ↔ Linux) o la codificación"
        console.print(f"[aviso]Solo cambian {motivo}[/]: las líneas son iguales.")
        return False
    pintar_diff(lineas)
    quitadas = sum(1 for l in lineas if l.startswith("-") and not l.startswith("---"))
    puestas = sum(1 for l in lineas if l.startswith("+") and not l.startswith("+++"))
    console.print(f"[error]-{quitadas}[/] [ok]+{puestas}[/] [pista]líneas[/]")
    return False


def archivos_de(carpeta: Path) -> set[str]:
    """Rutas relativas (con /) de todos los archivos, sin entrar en .git, .venv…"""
    encontrados: set[str] = set()
    pendientes = [carpeta]
    while pendientes:
        actual = pendientes.pop()
        try:
            hijos = list(actual.iterdir())
        except OSError:
            continue
        for hijo in hijos:
            if hijo.is_dir() and not hijo.is_symlink():
                if hijo.name not in NO_ENTRAR:
                    pendientes.append(hijo)
            elif hijo.is_file():
                encontrados.add(hijo.relative_to(carpeta).as_posix())
    return encontrados


@dataclass
class Resumen:
    solo_a: list[str] = field(default_factory=list)
    solo_b: list[str] = field(default_factory=list)
    cambiados: list[str] = field(default_factory=list)
    iguales: int = 0


def resumen_carpetas(a: Path, b: Path) -> Resumen:
    en_a, en_b = archivos_de(a), archivos_de(b)
    resumen = Resumen(sorted(en_a - en_b), sorted(en_b - en_a))
    for ruta in sorted(en_a & en_b):
        try:
            iguales = filecmp.cmp(a / ruta, b / ruta, shallow=False)
        except OSError:
            iguales = False
        if iguales:
            resumen.iguales += 1
        else:
            resumen.cambiados.append(ruta)
    return resumen


def compara(
    a: Path = typer.Argument(..., help="El primer archivo o carpeta (el de antes)."),
    b: Path = typer.Argument(..., help="El segundo archivo o carpeta (el de después)."),
    contexto: int = typer.Option(
        3, "--contexto", "-n", min=0, max=50, help="Líneas iguales que se enseñan alrededor de cada cambio.",
        rich_help_panel=AJUSTE,
    ),
    sin_espacios: bool = typer.Option(
        False, "--sin-espacios", "-w", help="No cuenta los cambios de espacios ni tabuladores.",
        rich_help_panel=AJUSTE,
    ),
    detalle: bool = typer.Option(
        False, "--detalle", help="Con carpetas: enseña también las líneas cambiadas de cada archivo.",
        rich_help_panel=AJUSTE,
    ),
) -> None:
    """Diferencias entre dos archivos o dos carpetas, con colores. No cambia nada."""
    try:
        a, b = a.expanduser(), b.expanduser()
        for ruta in (a, b):
            if not ruta.exists():
                raise NavajaError(f"No existe {bonita(ruta)}.")
        if a.is_dir() != b.is_dir():
            raise NavajaError("Compara dos archivos o dos carpetas, no un archivo con una carpeta.")

        if a.is_file():
            if comparar_archivos(a, b, contexto, sin_espacios, a.name, b.name if b.name != a.name else bonita(b)):
                console.print(f"[ok]✔ Son iguales[/] [pista]({tamano_legible(a.stat().st_size)}).[/]")
            return

        resumen = resumen_carpetas(a, b)
        console.print(f"[titulo]{escape(bonita(a))}[/] [pista]↔[/] [titulo]{escape(bonita(b))}[/]", soft_wrap=True)
        for ruta in resumen.solo_a:
            console.print(Text.assemble(("  - ", "error"), (ruta, "error"), ("  (solo en la primera)", "pista")))
        for ruta in resumen.solo_b:
            console.print(Text.assemble(("  + ", "ok"), (ruta, "ok"), ("  (solo en la segunda)", "pista")))
        for ruta in resumen.cambiados:
            console.print(Text.assemble(("  ~ ", "aviso"), (ruta, "aviso"), ("  (cambiado)", "pista")))
            if detalle:
                comparar_archivos(a / ruta, b / ruta, contexto, sin_espacios, f"a/{ruta}", f"b/{ruta}")
                console.print()
        if not (resumen.solo_a or resumen.solo_b or resumen.cambiados):
            console.print(f"[ok]✔ Son iguales[/] [pista]({resumen.iguales} archivos).[/]")
            return
        console.print(
            f"\n[error]{len(resumen.solo_a)} solo en la primera[/] · [ok]{len(resumen.solo_b)} solo en la segunda[/] · "
            f"[aviso]{len(resumen.cambiados)} cambiados[/] · [pista]{resumen.iguales} iguales[/]"
            + ("" if detalle or not resumen.cambiados else "\n[pista]Para ver las líneas: --detalle[/]")
        )
    except NavajaError as error:
        fallar(error)


def registrar(app: typer.Typer) -> None:
    app.command(
        "compara", help="Diferencias entre dos archivos o carpetas, con colores.",
        rich_help_panel=PROGRAMACION,
    )(compara)
