"""Analizador de disco y limpieza de archivos temporales."""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path

import typer
from rich.cells import cell_len
from rich.markup import escape
from rich.text import Text

from ..comun import (
    HERRAMIENTAS,
    HUECO,
    MARCO,
    confirmar,
    console,
    crear_tabla,
    cuantos,
    error_console,
    recuadro,
    resumen,
    tabla_ligera,
    tamano_legible,
)

BASURA_DIRS = {
    "__pycache__": "caché de Python",
    ".pytest_cache": "caché de Python",
    ".mypy_cache": "caché de Python",
    ".ruff_cache": "caché de Python",
    ".tox": "entornos de prueba de Python",
    ".nox": "entornos de prueba de Python",
    "node_modules": "paquetes de Node (se reinstalan con npm install)",
    ".next": "caché de Next.js",
    ".parcel-cache": "caché de Parcel",
    ".turbo": "caché de Turbo",
    "htmlcov": "informe de cobertura de tests",
    ".cache": "caché",
    ".gradle": "caché de Gradle",
}
"""Carpetas que siempre son caché: se vuelven a crear solas."""

BASURA_EN_PROYECTOS = {
    "dist": "programa compilado (se vuelve a generar)",
    "build": "programa compilado (se vuelve a generar)",
    "target": "programa compilado (se vuelve a generar)",
    "coverage": "informe de cobertura de tests",
}
"""Solo son basura dentro de un proyecto de programación (junto a un archivo de
MARCAS_DE_PROYECTO). En otro sitio pueden ser tuyas: «build» con planos,
«coverage» con la póliza del seguro…"""

MARCAS_DE_PROYECTO = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml", "pom.xml",
    "build.gradle", "build.gradle.kts", "CMakeLists.txt", "Makefile", "go.mod",
    "composer.json",
}

BASURA_ARCHIVOS = {".DS_Store": "archivo de macOS", "Thumbs.db": "miniaturas de Windows"}

BASURA_PATRONES = {
    "*.pyc": "caché de Python",
    "*.pyo": "caché de Python",
    "*.tmp": "temporal",
    "*.swp": "temporal de Vim",
    "*.swo": "temporal de Vim",
    "*~": "copia de seguridad de un editor",
}

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
    """Cada archivo y carpeta hasta ``profundidad`` niveles, con su tamaño y archivos."""
    return _medir(ruta, profundidad, nivel)[0]


def _medir(ruta: Path, profundidad: int, nivel: int) -> tuple[list[tuple], int, int]:
    """Lo de ``_recolectar`` más el total de la carpeta, recorriéndola una sola vez.

    Las subcarpetas que se enseñan se miden por dentro y su tamaño es la suma de lo
    suyo; así ``-p 3`` no vuelve a recorrer tres veces lo mismo.
    """
    resultado: list[tuple] = []
    total = num_total = 0
    try:
        with os.scandir(ruta) as entradas:
            ordenadas = sorted(entradas, key=lambda e: e.name.lower())
    except OSError as exc:
        error_console.print(f"[aviso]No se pudo leer {escape(str(ruta))}: {escape(str(exc))}[/]")
        return resultado, 0, 0

    for entrada in ordenadas:
        ruta_entrada = Path(entrada.path)
        try:
            if entrada.is_dir(follow_symlinks=False):
                if nivel + 1 < profundidad:
                    dentro, tam, num = _medir(ruta_entrada, profundidad, nivel + 1)
                else:
                    dentro, (tam, num) = [], _tamano_ruta(ruta_entrada)
                resultado.append((ruta_entrada, tam, num, nivel, True))
                resultado.extend(dentro)
            elif entrada.is_file(follow_symlinks=False):
                tam, num = entrada.stat(follow_symlinks=False).st_size, 1
                resultado.append((ruta_entrada, tam, 1, nivel, False))
            else:
                continue
        except OSError:
            continue
        total += tam
        num_total += num
    return resultado, total, num_total


BARRA_MAXIMA = 18
"""Lo más larga que se hace la barra de «Uso»; en una ventana estrecha se acorta."""


def _barra(porcentaje: float, ancho: int = BARRA_MAXIMA) -> str:
    """La barra de uso con el porcentaje detrás (sin barra si ``ancho`` es 0)."""
    numero = f"{porcentaje:5.1f}%"
    if ancho <= 0:
        return numero
    llenos = round(max(0.0, min(100.0, porcentaje)) / 100 * ancho)
    estilo = "ok" if porcentaje < 60 else "aviso" if porcentaje < 85 else "error"
    # con la salida a un archivo en Windows (cp1252) «━» saldría «?»: allí, # y -
    lleno, vacio = ("#", "-") if console.options.ascii_only else ("━", "━")
    return f"[{estilo}]{lleno * llenos}[/][borde]{vacio * (ancho - llenos)}[/] {numero}"


RUTA_MINIMA = 12
RUTA_MAXIMA = 30
"""Lo que se guarda para la ruta antes de dar sitio a la barra o a «Archivos»: lo que
mide la más larga, entre 12 y 30 columnas. Una ruta más larga se parte en líneas."""


def columnas_que_caben(
    ancho_consola: int, ancho_tamano: int, ancho_archivos: int, ancho_ruta: int = 0
) -> tuple[int, bool]:
    """Cuánta barra cabe y si cabe la columna «Archivos», sin que la tabla parta nada.

    Cuenta el recuadro (``MARCO``), los huecos entre columnas (``HUECO``), el tamaño,
    « 56.6%» y la ruta más larga (entre ``RUTA_MINIMA`` y ``RUTA_MAXIMA``). Primero se
    quita la barra (si quedan menos de 6) y, si aun así no cabe, «Archivos»: el total ya
    sale arriba.
    """
    ruta = max(RUTA_MINIMA, min(ancho_ruta, RUTA_MAXIMA))
    fijo = MARCO + ancho_tamano + HUECO + 6 + HUECO + ruta
    con_archivos = ancho_consola >= fijo + HUECO + ancho_archivos
    if con_archivos:
        fijo += HUECO + ancho_archivos
    sitio = ancho_consola - fijo - 1  # el espacio entre la barra y el porcentaje
    return (min(BARRA_MAXIMA, sitio) if sitio >= 6 else 0), con_archivos


def ocupa(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta que se quiere analizar.", show_default=True
    ),
    mayores: int = typer.Option(
        15, "--mayores", "-n", min=1, help="Cuántas entradas enseñar (las que más ocupan)."
    ),
    profundidad: int = typer.Option(
        1,
        "--profundidad",
        "-p",
        min=1,
        help="Cuántos niveles de subcarpetas enseñar (1 = solo lo de esta carpeta).",
    ),
) -> None:
    """Muestra qué archivos y carpetas ocupan más espacio."""
    if not ruta.exists():
        error_console.print(f"[error]La ruta no existe:[/] {escape(str(ruta))}", soft_wrap=True)
        raise typer.Exit(1)

    if ruta.is_file():
        tam = ruta.stat().st_size
        console.print(f"{escape(ruta.name)}: [bold]{tamano_legible(tam)}[/]")
        return

    # En una carpeta grande (tu carpeta personal, C:\) tarda: que se vea que trabaja.
    with console.status("[pista]Midiendo… (Ctrl+C para cancelar)[/]"):
        entradas, total, num_archivos = _medir(ruta, profundidad, 0)
    libre = shutil.disk_usage(ruta).free

    datos = resumen(
        [
            ("Carpeta", f"[bold]{escape(str(ruta.resolve()))}[/]"),
            ("Ocupa", f"[titulo]{tamano_legible(total)}[/] en {cuantos(num_archivos, 'archivo')}"),
            ("Libre", f"[logro]{tamano_legible(libre)}[/] en el disco"),
        ]
    )

    entradas.sort(key=lambda item: item[1], reverse=True)
    visibles = entradas[:mayores]
    if visibles:
        filas = []
        for ruta_entrada, tam, num, _nivel, es_dir in visibles:
            porcentaje = (tam / total * 100) if total else 0.0
            # la ruta desde la carpeta, sin sangría: si no cabe y sigue en la línea de
            # abajo, se lee igual (con sangría, la segunda línea perdería el escalón)
            nombre = os.path.relpath(ruta_entrada, ruta)
            etiqueta = f"{nombre}{'/' if es_dir else ''}"
            filas.append((tamano_legible(tam), porcentaje, f"{num:,}", etiqueta))
        ancho_tamano = max(len("Tamaño"), *(cell_len(f[0]) for f in filas))
        ancho_archivos = max(len("Archivos"), *(cell_len(f[2]) for f in filas))
        ancho_ruta = max(cell_len(f[3]) for f in filas)
        barra, con_archivos = columnas_que_caben(
            console.width, ancho_tamano, ancho_archivos, ancho_ruta
        )

        tabla = tabla_ligera()
        tabla.add_column("Tamaño", justify="right", no_wrap=True)
        tabla.add_column("Uso", no_wrap=True)
        if con_archivos:
            tabla.add_column("Archivos", justify="right", no_wrap=True)
        tabla.add_column("Ruta", overflow="fold")
        for tam_texto, porcentaje, num_texto, etiqueta in filas:
            celdas = [tam_texto, _barra(porcentaje, barra)]
            celdas += [num_texto] if con_archivos else []
            tabla.add_row(*celdas, escape(etiqueta))
        console.print(recuadro("Uso de disco", datos, tabla))
    else:
        console.print(recuadro("Uso de disco", datos, Text("La carpeta está vacía.", style="aviso")))

    if len(entradas) > len(visibles):
        console.print(
            f"[pista]Mostrando {len(visibles)} de {len(entradas)}. "
            "Para ver más: --mayores 50[/]"
        )


def es_proyecto(carpeta: Path) -> bool:
    """Tiene un archivo de proyecto de programación (package.json, pyproject.toml…)."""
    return any((carpeta / marca).is_file() for marca in MARCAS_DE_PROYECTO)


def que_basura(nombre: str) -> str | None:
    """Qué es un archivo de basura («temporal»…), o None si no lo es."""
    if nombre in BASURA_ARCHIVOS:
        return BASURA_ARCHIVOS[nombre]
    for patron, que in BASURA_PATRONES.items():
        if fnmatch.fnmatch(nombre, patron):
            return que
    return None


def _buscar_basura(raiz: Path) -> list[tuple[Path, int, str, bool]]:
    """(ruta, tamaño, qué es, es carpeta) de lo que se puede borrar sin perder nada."""
    candidatos: list[tuple[Path, int, str, bool]] = []
    for actual, dirs, archivos in os.walk(raiz):
        actual_path = Path(actual)
        proyecto = None  # se mira solo si hace falta

        for nombre in list(dirs):
            ruta_dir = actual_path / nombre
            if nombre in DIRS_IGNORADOS:
                dirs.remove(nombre)
                continue
            que = BASURA_DIRS.get(nombre)
            if que is None and nombre in BASURA_EN_PROYECTOS:
                if proyecto is None:
                    proyecto = es_proyecto(actual_path)
                if proyecto:
                    que = BASURA_EN_PROYECTOS[nombre]
            if que is not None:
                tam, _ = _tamano_ruta(ruta_dir)
                candidatos.append((ruta_dir, tam, que, True))
                dirs.remove(nombre)

        for nombre in archivos:
            que = que_basura(nombre)
            if que is None:
                continue
            ruta_archivo = actual_path / nombre
            try:
                tam = ruta_archivo.stat().st_size
            except OSError:
                continue
            candidatos.append((ruta_archivo, tam, que, False))
    return candidatos


def limpia(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta donde buscar archivos temporales.", show_default=True
    ),
    simular: bool = typer.Option(
        False, "--simular", help="Solo enseña lo que borraría, sin borrar nada."
    ),
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación antes de borrar."
    ),
) -> None:
    """Busca y borra cachés y archivos temporales (node_modules, __pycache__…)."""
    if not ruta.is_dir():
        error_console.print(f"[error]La carpeta no existe:[/] {escape(str(ruta))}", soft_wrap=True)
        raise typer.Exit(1)

    candidatos = _buscar_basura(ruta)
    if not candidatos:
        console.print(f"[ok]No hay nada que limpiar en[/] {escape(str(ruta.resolve()))}", soft_wrap=True)
        return

    candidatos.sort(key=lambda item: item[1], reverse=True)
    total = sum(tam for _, tam, _, _ in candidatos)

    console.print(f"[pista]En[/] {escape(str(ruta.resolve()))}", soft_wrap=True)
    tabla = crear_tabla(["Tamaño", "Qué es", "Se borraría"])
    for ruta_candidata, tam, que, es_carpeta in candidatos:
        relativa = os.path.relpath(ruta_candidata, ruta) + ("/" if es_carpeta else "")
        tabla.add_row(tamano_legible(tam), que, escape(relativa))
    console.print(tabla)
    console.print(
        f"Se liberarían [logro]{tamano_legible(total)}[/] "
        f"({cuantos(len(candidatos), 'cosa')}). Son cachés y temporales: lo que haga falta, "
        "los programas lo vuelven a crear."
    )

    if simular:
        console.print("[pista]Simulación: no se ha borrado nada. Sin --simular, lo hace.[/]")
        return

    if not confirmar("¿Borrar todo lo de la lista? No va a la papelera.", saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return

    liberado = 0
    errores = 0
    for ruta_candidata, tam, _, es_carpeta in candidatos:
        try:
            if es_carpeta:
                shutil.rmtree(ruta_candidata)
            else:
                ruta_candidata.unlink()
            liberado += tam
        except OSError as exc:
            errores += 1
            error_console.print(
                f"[error]No se pudo borrar[/] {escape(str(ruta_candidata))}: {escape(str(exc))}",
                soft_wrap=True,
            )

    console.print(f"[ok]Liberados {tamano_legible(liberado)}.[/]")
    if errores:
        console.print(f"[aviso]No se pudo borrar: {cuantos(errores, 'cosa')}.[/]")


def registrar(app: typer.Typer) -> None:
    app.command(
        "ocupa", help="Muestra qué ocupa espacio en disco.", rich_help_panel=HERRAMIENTAS
    )(ocupa)
    app.command(
        "limpia", help="Borra cachés y archivos temporales.", rich_help_panel=HERRAMIENTAS
    )(limpia)
