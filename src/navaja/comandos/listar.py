"""listar: qué hay en una carpeta, en un recuadro como el de ocupa."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.cells import cell_len
from rich.markup import escape
from rich.text import Text

from ..comun import (
    HERRAMIENTAS,
    HUECO,
    MARCO,
    console,
    cuantos,
    error_console,
    es_oculto,
    recuadro,
    resumen,
    tabla_ligera,
    tamano_legible,
)
from ..filtros import sin_tildes


def tipo_de(ruta: Path) -> str:
    """«carpeta», la extensión en minúsculas o «(sin extensión)»."""
    if ruta.is_dir():
        return "carpeta"
    return ruta.suffix.lower() or "(sin extensión)"


def fecha_de(marca: float, formato: str) -> str:
    """La fecha de modificación, o «—» si no se puede escribir: en Windows, una fecha
    de antes de 1970 (algunos zip o cámaras) da error en vez de una fecha."""
    try:
        return datetime.fromtimestamp(marca).strftime(formato)
    except (OSError, ValueError, OverflowError):
        return "—"


def ocultos_en(carpeta: Path) -> int:
    """Cuántas entradas ocultas o de sistema hay (las que «listar» no enseña)."""
    try:
        return sum(es_oculto(e) for e in carpeta.iterdir())
    except OSError:
        return 0


def contenido(carpeta: Path, ocultos: bool = False) -> list[Path]:
    """Entradas de la carpeta: primero las carpetas y luego alfabético (sin mirar
    mayúsculas ni tildes: «Álbum» va con la A)."""
    entradas = [e for e in carpeta.iterdir() if ocultos or not es_oculto(e)]
    return sorted(entradas, key=lambda e: (not e.is_dir(), sin_tildes(e.name).lower()))


def listar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta que quieres ver.", show_default=True
    ),
    ocultos: bool = typer.Option(
        False, "--ocultos", help="Incluir archivos ocultos y de sistema (desktop.ini…)."
    ),
) -> None:
    """Muestra el contenido de una carpeta: nombre, tipo, tamaño y fecha."""
    if not ruta.is_dir():
        error_console.print(
            f"[error]No existe o no es una carpeta:[/] {escape(str(ruta))}", soft_wrap=True
        )
        raise typer.Exit(1)

    try:
        entradas = contenido(ruta, ocultos)
    except OSError as exc:
        error_console.print(f"[error]No se puede leer la carpeta:[/] {escape(str(exc))}", soft_wrap=True)
        raise typer.Exit(1)

    filas = []
    carpetas = archivos = sin_leer = 0
    total = 0
    for entrada in entradas:
        try:
            datos = entrada.stat()
            es_carpeta = entrada.is_dir()
        except OSError:
            sin_leer += 1  # enlace roto o sin permisos
            continue
        if es_carpeta:
            carpetas += 1
            tamano = "—"
        else:
            archivos += 1
            total += datos.st_size
            tamano = tamano_legible(datos.st_size)
        nombre = entrada.name + ("/" if es_carpeta else "")
        filas.append((nombre, es_carpeta, tipo_de(entrada), tamano, datos.st_mtime))

    cabecera = resumen(
        [
            ("Carpeta", f"[bold]{escape(str(ruta.resolve()))}[/]"),
            ("Tiene", f"{cuantos(carpetas, 'carpeta')} y {cuantos(archivos, 'archivo')}"
             + (f" ([titulo]{tamano_legible(total)}[/])" if archivos else "")),
        ]
    )
    if not filas:
        escondidos = 0 if ocultos else ocultos_en(ruta)
        if escondidos:
            aviso = (
                f"No hay nada visible: {cuantos(escondidos, 'oculto')}. "
                "Para verlos: listar --ocultos"
            )
        elif sin_leer:
            aviso = f"No se puede leer nada de lo que hay ({cuantos(sin_leer, 'entrada')})."
        else:
            aviso = "La carpeta está vacía."
        console.print(recuadro("Contenido", cabecera, Text(aviso, style="aviso")))
        return

    con_tipo, ancho_fecha = columnas_que_caben(
        console.width,
        ancho_nombre=max(cell_len(f[0]) for f in filas),
        ancho_tipo=max(len("Tipo"), *(cell_len(f[2]) for f in filas)),
        ancho_tamano=max(len("Tamaño"), *(cell_len(f[3]) for f in filas)),
    )
    tabla = tabla_ligera()
    tabla.add_column("Nombre", overflow="fold")
    if con_tipo:
        tabla.add_column("Tipo", no_wrap=True, style="pista")
    tabla.add_column("Tamaño", justify="right", no_wrap=True)
    if ancho_fecha:
        tabla.add_column("Modificado", no_wrap=True, style="pista")
    formato = "%Y-%m-%d %H:%M" if ancho_fecha == FECHA_LARGA else "%Y-%m-%d"
    for nombre, es_carpeta, tipo, tamano, modificado in filas:
        celdas = [f"[acento]{escape(nombre)}[/]" if es_carpeta else escape(nombre)]
        celdas += [escape(tipo)] if con_tipo else []
        celdas.append(tamano)
        if ancho_fecha:
            celdas.append(fecha_de(modificado, formato))
        tabla.add_row(*celdas)
    console.print(recuadro("Contenido", cabecera, tabla))


NOMBRE_MINIMO = 16
NOMBRE_MAXIMO = 30
"""Lo que se guarda para el nombre antes de dar sitio a las demás columnas: lo que mide
el más largo, entre 16 y 30. Un nombre más largo se parte en líneas."""

FECHA_LARGA = len("2026-11-10 18:27")
FECHA_CORTA = len("2026-11-10")


def columnas_que_caben(
    ancho_consola: int, ancho_nombre: int, ancho_tipo: int, ancho_tamano: int
) -> tuple[bool, int]:
    """Si cabe la columna «Tipo» y cuánto de «Modificado» (con hora, solo fecha o nada).

    Cuenta el recuadro, los huecos entre columnas, el tamaño y el nombre más largo
    (entre ``NOMBRE_MINIMO`` y ``NOMBRE_MAXIMO``). Si falta sitio se quita primero
    «Tipo» (la extensión ya se ve en el nombre) y luego la hora. Antes de quitar también
    la fecha, se prueba dejando al nombre solo ``NOMBRE_MINIMO`` (los largos se parten).
    """
    nombre = max(NOMBRE_MINIMO, min(ancho_nombre, NOMBRE_MAXIMO))
    intentos = (
        (nombre, True, FECHA_LARGA),
        (nombre, False, FECHA_LARGA),
        (nombre, False, FECHA_CORTA),
        (NOMBRE_MINIMO, False, FECHA_CORTA),
    )
    for reservado, con_tipo, fecha in intentos:
        tipo = HUECO + ancho_tipo if con_tipo else 0
        if MARCO + reservado + tipo + HUECO + ancho_tamano + HUECO + fecha <= ancho_consola:
            return con_tipo, fecha
    return False, 0


def registrar(app: typer.Typer) -> None:
    app.command(
        "listar", help="Muestra qué hay en una carpeta.", rich_help_panel=HERRAMIENTAS
    )(listar)
