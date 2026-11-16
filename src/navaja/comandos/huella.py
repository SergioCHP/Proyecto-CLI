"""navaja hash: la huella (MD5, SHA-1 y SHA-256) de un archivo o de un texto.

Sirve para comprobar que una descarga ha llegado entera: la web da la huella y, si la
del archivo coincide, es el mismo archivo. Se lee una sola vez y por trozos, así que vale
para una ISO de varios GB sin llenar la memoria.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, NoReturn

import typer
from rich.markup import escape
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn
from rich.text import Text

from ..comun import AJUSTE, PROGRAMACION, console, error_console, recuadro, resumen
from ..errores import NavajaError

ALGORITMOS = ("md5", "sha1", "sha256")
NOMBRES = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256"}
POR_LARGO = {32: "md5", 40: "sha1", 64: "sha256"}
TROZO = 1024 * 1024


def huellas_de_bytes(datos: bytes) -> dict[str, str]:
    return {nombre: hashlib.new(nombre, datos).hexdigest() for nombre in ALGORITMOS}


def huellas_de_archivo(
    ruta: Path, avance: Callable[[int], None] | None = None
) -> dict[str, str]:
    """Las tres huellas leyendo el archivo una sola vez. ``avance`` recibe los bytes de
    cada trozo leído (para la barra)."""
    calculos = {nombre: hashlib.new(nombre) for nombre in ALGORITMOS}
    with ruta.open("rb") as archivo:
        while trozo := archivo.read(TROZO):
            for calculo in calculos.values():
                calculo.update(trozo)
            if avance:
                avance(len(trozo))
    return {nombre: calculo.hexdigest() for nombre, calculo in calculos.items()}


def algoritmo_de(esperada: str) -> str:
    """Qué algoritmo es una huella por su largo (32 → MD5, 40 → SHA-1, 64 → SHA-256)."""
    limpia = esperada.strip().lower()
    if not all(c in "0123456789abcdef" for c in limpia) or len(limpia) not in POR_LARGO:
        raise NavajaError(
            f"«{esperada}» no parece una huella: tiene que tener 32 (MD5), 40 (SHA-1) o "
            "64 (SHA-256) cifras hexadecimales."
        )
    return POR_LARGO[len(limpia)]


def coincide(huellas: dict[str, str], esperada: str) -> tuple[str, bool]:
    """(algoritmo, si coincide), sin mirar mayúsculas ni espacios."""
    algoritmo = algoritmo_de(esperada)
    return algoritmo, huellas[algoritmo] == esperada.strip().lower()


# ── Orden ──────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def calcular(ruta: Path) -> dict[str, str]:
    """Con barra de progreso si el archivo es grande (más de 50 MB)."""
    tamano = ruta.stat().st_size
    if tamano < 50 * TROZO or not console.is_terminal:
        return huellas_de_archivo(ruta)
    with Progress(
        TextColumn("[pista]Leyendo[/]"), BarColumn(), DownloadColumn(), console=console, transient=True
    ) as barra:
        tarea = barra.add_task("", total=tamano)
        return huellas_de_archivo(ruta, lambda n: barra.advance(tarea, n))


OPCION_COMPARA = typer.Option(
    "", "--compara", "-c", help="La huella que te dan en la web, para ver si coincide.",
    rich_help_panel=AJUSTE, show_default=False,
)


def archivo_orden(
    archivo: Path = typer.Argument(..., help="El archivo (una ISO, un instalador…)."),
    compara: str = OPCION_COMPARA,
) -> None:
    """La huella MD5, SHA-1 y SHA-256 de un archivo y, con --compara, si coincide."""
    ruta = archivo.expanduser()
    if not ruta.is_file():
        fallar(NavajaError(f"No existe el archivo {archivo}."))
    try:
        huellas = calcular(ruta)
    except OSError as error:
        fallar(NavajaError(f"No se puede leer {archivo}: {error.strerror or error}"))
    mostrar(f"Huellas de {ruta.name}", huellas, compara)


def texto_orden(
    texto: str = typer.Argument(..., help="El texto."),
    compara: str = OPCION_COMPARA,
) -> None:
    """La huella MD5, SHA-1 y SHA-256 de un texto (en UTF-8)."""
    mostrar("Huellas del texto", huellas_de_bytes(texto.encode("utf-8")), compara)


def mostrar(titulo: str, huellas: dict[str, str], compara: str) -> None:
    """Las tres huellas y, si hay una para comparar, si coincide (si no, sale con 1)."""
    elegido = ""
    bien = True
    if compara:
        try:
            elegido, bien = coincide(huellas, compara)
        except NavajaError as error:
            fallar(error)
    filas = []
    for nombre in ALGORITMOS:
        valor = escape(huellas[nombre])
        if nombre == elegido:
            valor = f"[{'ok' if bien else 'error'}]{valor}[/]"
        filas.append((NOMBRES[nombre], valor))
    partes: list = [resumen(filas)]
    if compara:
        if bien:
            partes.append(Text.from_markup(f"[ok]✔ Coincide con la {NOMBRES[elegido]} que te dieron: es lo mismo, sin un byte cambiado.[/]"))
        else:
            partes.append(
                Text.from_markup(
                    f"[error]✘ No coincide con la {NOMBRES[elegido]} que te dieron "
                    f"({escape(compara.strip().lower())}).[/] [pista]La descarga está a medias o "
                    "estropeada, o no es el mismo archivo: vuelve a bajarlo.[/]"
                )
            )
    partes.append(
        Text.from_markup(
            "[pista]MD5 y SHA-1 valen para ver si una descarga está bien, no para seguridad: "
            "para eso, SHA-256.[/]"
        )
    )
    console.print(recuadro(titulo, *partes))
    if not bien:
        raise typer.Exit(1)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Huella MD5, SHA-1 y SHA-256: comprueba que una descarga está bien.",
        no_args_is_help=True,
    )
    sub.command("archivo", help="La huella de un archivo y si coincide con la de la web.")(archivo_orden)
    sub.command("texto", help="La huella de un texto.")(texto_orden)
    app.add_typer(sub, name="hash", rich_help_panel=PROGRAMACION)
