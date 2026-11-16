"""Lo que comparten las órdenes que crean archivos nuevos a partir de otros (convierte,
imagen, pdf, fondo…): leer los archivos de entrada (con comodines), el nombre del archivo
nuevo al lado del original sin pisar nada, enseñar el plan y preguntar, hacerlo en
paralelo y decir qué ha fallado, y avisar bien cuando falta una librería o un programa.
"""

from __future__ import annotations

import glob
import importlib
import os
import shutil
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import NoReturn

import typer
from rich.markup import escape
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from .comun import bonita, confirmar, console, cuantos, error_console, ruta_libre, tabla_ligera
from .errores import NavajaError

WINDOWS = sys.platform == "win32"
def como_instalar(extra: str = "todo") -> str:
    """El comando para tener las librerías opcionales en el navaja de la terminal.

    Siempre con ``todo`` (y ``fondo`` si hace falta): ``uv tool install`` deja solo los
    extras que se le dicen, así que instalar «.[qr]» quitaría los que ya tenías.
    """
    extras = "todo,fondo" if extra == "fondo" else "todo"
    return f'uv tool install --editable ".[{extras}]"'


class FaltaAlgo(NavajaError):
    """Falta una librería opcional o un programa de fuera: el mensaje dice cómo instalarlo."""


def libreria(modulo: str, paquete: str, extra: str, para: str) -> ModuleType:
    """Importa una librería opcional o lanza ``FaltaAlgo`` con el comando para instalarla."""
    try:
        return importlib.import_module(modulo)
    except ImportError:
        raise FaltaAlgo(
            f"Para {para} hace falta {paquete}. Desde la carpeta de navaja: {como_instalar(extra)}"
        ) from None


RUTAS_WINDOWS = {
    "soffice": [r"C:\Program Files\LibreOffice\program\soffice.exe"],
    "7z": [r"C:\Program Files\7-Zip\7z.exe"],
}

COMO_INSTALAR = {
    "ffmpeg": ("winget install Gyan.FFmpeg", "sudo apt install ffmpeg"),
    "soffice": ("winget install TheDocumentFoundation.LibreOffice", "sudo apt install libreoffice"),
    "pandoc": ("winget install JohnMacFarlane.Pandoc", "sudo apt install pandoc"),
}
NOMBRE_PROGRAMA = {"ffmpeg": "FFmpeg", "soffice": "LibreOffice", "pandoc": "Pandoc"}


def buscar_programa(*ejecutables: str) -> str | None:
    """Dónde está un programa: en el PATH o, en Windows, donde se instala normalmente."""
    for ejecutable in ejecutables:
        ruta = shutil.which(ejecutable)
        if ruta:
            return ruta
        if WINDOWS:
            for candidata in RUTAS_WINDOWS.get(ejecutable, []):
                if Path(candidata).is_file():
                    return candidata
    return None


def programa(ejecutable: str, para: str, *otros: str) -> str:
    """La ruta del programa o ``FaltaAlgo`` con cómo instalarlo."""
    ruta = buscar_programa(ejecutable, *otros)
    if ruta:
        return ruta
    windows, linux = COMO_INSTALAR.get(ejecutable, ("", ""))
    como = windows if WINDOWS else linux
    nombre = NOMBRE_PROGRAMA.get(ejecutable, ejecutable)
    raise FaltaAlgo(
        f"Para {para} hace falta {nombre}." + (f" Instálalo con: {como} y abre otra terminal." if como else "")
    )


def pedir_secreto(texto: str) -> str:
    """Una contraseña sin que se vea. Si no hay terminal («… | navaja …»), la primera línea."""
    if sys.stdin.isatty():
        return console.input(f"[pista]{texto}:[/] ", password=True)
    return sys.stdin.readline().rstrip("\r\n")


# ── Archivos de entrada ────────────────────────────────────────────────────


def expandir(patrones: list[str]) -> list[Path]:
    """Los archivos de lo escrito: rutas tal cual o comodines (``*.heic``, ``fotos/*.jpg``).

    En Windows la terminal no expande los comodines (lo hace navaja aquí). Sin repetir y en
    el orden en que se escribieron. ``NavajaError`` si alguno no existe o no encaja con nada.
    """
    archivos: list[Path] = []
    for patron in patrones:
        ruta = Path(patron).expanduser()
        if any(c in patron for c in "*?["):
            encontrados = sorted(Path(p) for p in glob.glob(str(ruta)) if Path(p).is_file())
            if not encontrados and not ruta.is_file():
                raise NavajaError(f"Ningún archivo encaja con {patron}.")
            archivos += encontrados or [ruta]
        elif ruta.is_file():
            archivos.append(ruta)
        elif ruta.is_dir():
            raise NavajaError(f"{patron} es una carpeta: escribe los archivos ({patron}/*.jpg).")
        else:
            raise NavajaError(f"No existe el archivo {patron}.")
    vistos: set[str] = set()
    unicos = []
    for archivo in archivos:
        clave = os.path.normcase(str(archivo.resolve()))
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(archivo)
    return unicos


def al_lado(original: Path, sufijo: str = "", extension: str | None = None, reservados: set[str] | None = None) -> Path:
    """El archivo nuevo junto al original: «foto.heic» → «foto.jpg», «foto-sin-fondo.png»…

    Nunca uno que ya exista ni uno ya repartido en el mismo plan (``reservados``): «(1)».
    """
    extension = original.suffix if extension is None else extension
    destino = original.with_name(f"{original.stem}{sufijo}{extension}")
    reservados = reservados if reservados is not None else set()
    candidato = ruta_libre(destino)
    indice = 1
    while os.path.normcase(str(candidato)) in reservados:
        candidato = ruta_libre(destino.with_name(f"{destino.stem} ({indice}){destino.suffix}"))
        indice += 1
    reservados.add(os.path.normcase(str(candidato)))
    return candidato


# ── Plan, confirmación y trabajo en paralelo ───────────────────────────────


@dataclass
class Tarea:
    origen: Path
    destino: Path
    hacer: Callable[[], object]
    etiqueta: str = ""  # lo que se enseña en el plan si no es solo el nombre del destino


@dataclass
class Fallo:
    origen: Path
    motivo: str


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def ensenar_plan(tareas: list[Tarea], titulo: str, maximo: int = 15) -> None:
    tabla = tabla_ligera()
    tabla.add_column("De")
    tabla.add_column("")
    tabla.add_column("A (nuevo)")
    for tarea in tareas[:maximo]:
        tabla.add_row(escape(tarea.origen.name), "[pista]→[/]", f"[acento]{escape(tarea.etiqueta or tarea.destino.name)}[/]")
    console.print(f"[titulo]{escape(titulo)}[/]")
    console.print(tabla)
    if len(tareas) > maximo:
        console.print(f"[pista]… y {len(tareas) - maximo} más[/]")


def hacer_todo(tareas: list[Tarea], hilos: int = 4) -> list[Fallo]:
    """Hace las tareas en paralelo con una barra; si una falla, las demás siguen."""
    fallos: list[Fallo] = []
    progreso = Progress(
        SpinnerColumn(style="acento"), TextColumn("[pista]{task.completed} de {task.total}[/]"),
        BarColumn(style="borde", complete_style="acento"), console=console, transient=True,
        disable=not console.is_terminal,
    )
    with progreso:
        barra = progreso.add_task("", total=len(tareas))
        with ThreadPoolExecutor(max_workers=max(1, min(hilos, len(tareas)))) as hilos_:
            futuros = {hilos_.submit(t.hacer): t for t in tareas}
            for futuro in as_completed(futuros):
                tarea = futuros[futuro]
                try:
                    futuro.result()
                except NavajaError as error:
                    fallos.append(Fallo(tarea.origen, str(error)))
                    tarea.destino.unlink(missing_ok=True)
                except Exception as error:  # una foto rota no debe parar las demás
                    fallos.append(Fallo(tarea.origen, f"{type(error).__name__}: {error}"))
                    tarea.destino.unlink(missing_ok=True)
                progreso.advance(barra)
    return fallos


def ejecutar(tareas: list[Tarea], titulo: str, simular: bool, si: bool, hilos: int = 4) -> None:
    """Enseña el plan, pregunta [s/n], lo hace y dice qué ha salido y qué no."""
    if not tareas:
        console.print("[aviso]No hay nada que hacer.[/]")
        return
    ensenar_plan(tareas, titulo)
    if simular:
        console.print("[pista]Simulación: no se ha creado nada.[/]")
        return
    if not confirmar(f"¿{'Lo creo' if len(tareas) == 1 else 'Los creo'}?", si):
        console.print("[pista]No se ha creado nada.[/]")
        return
    fallos = hacer_todo(tareas, hilos)
    bien = len(tareas) - len(fallos)
    if bien:
        donde = bonita(tareas[0].destino.parent)
        console.print(f"[ok]✔ {cuantos(bien, 'archivo nuevo', 'archivos nuevos')}[/] [pista]en {escape(donde)}[/]", soft_wrap=True)
    for fallo in fallos:
        error_console.print(f"[error]✘ {escape(fallo.origen.name)}:[/] {escape(fallo.motivo)}", soft_wrap=True)
    if fallos:
        raise typer.Exit(1)
