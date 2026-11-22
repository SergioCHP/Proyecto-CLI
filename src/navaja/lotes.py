"""Lo que comparten las órdenes que crean archivos nuevos a partir de otros (convierte,
imagen, pdf, fondo…): leer los archivos de entrada (con comodines), el nombre del archivo
nuevo al lado del original sin pisar nada, enseñar el plan y preguntar, hacerlo en
paralelo y decir qué ha fallado, y avisar bien cuando falta una librería o un programa.
"""

from __future__ import annotations

import contextlib
import functools
import importlib
import importlib.metadata
import json
import os
import shutil
import signal
import sys
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import NoReturn

import typer
from rich.markup import escape
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from .comun import (
    bonita, buscar_con_comodin, confirmar, console, cuantos, error_console, ruta_libre, tabla_ligera, tiene_comodin,
)
from . import __version__
from .errores import NavajaError

WINDOWS = sys.platform == "win32"
REPO = "https://github.com/SergioCHP/Proyecto-CLI"
"""De donde se instala navaja si no se sabe de dónde vino (la orden del README)."""


@functools.cache
def origen_instalacion() -> dict:
    """Cómo se instaló navaja, según el ``direct_url.json`` que deja uv (o pip):
    ``{"dir_info": {"editable": true}}`` desde una carpeta con --editable, o
    ``{"url": "https://github.com/…", "vcs_info": {…}}`` desde GitHub con git, o
    ``{"url": "…/v1.2.0.zip", "archive_info": {…}}`` desde el .zip de una versión (lo que
    hace el instalador, ``instalar.ps1`` / ``instalar.sh``). Vacío si no se sabe."""
    try:
        texto = importlib.metadata.distribution("navaja").read_text("direct_url.json")
        datos = json.loads(texto) if texto else {}
    except (importlib.metadata.PackageNotFoundError, ValueError, OSError):
        return {}
    return datos if isinstance(datos, dict) else {}


def instalada_editable() -> bool:
    """¿Usa navaja el código de una carpeta (``uv tool install --editable`` o ``uv run``)?"""
    return bool((origen_instalacion().get("dir_info") or {}).get("editable"))


def como_instalar(extra: str = "todo") -> str:
    """El comando para tener las librerías opcionales en el navaja de la terminal, según
    cómo se instaló: desde la carpeta del proyecto (``--editable``) o desde GitHub (la
    misma dirección y la misma versión, con ``--force`` para cambiar la que hay).

    Siempre con ``todo`` (y ``fondo`` si hace falta): ``uv tool install`` deja solo los
    extras que se le dicen, así que instalar «.[qr]» quitaría los que ya tenías.
    """
    extras = "todo,fondo" if extra == "fondo" else "todo"
    if instalada_editable():
        return f'uv tool install --editable ".[{extras}]"'
    origen = origen_instalacion()
    url = origen.get("url")
    vcs = origen.get("vcs_info") or {}
    if url and vcs.get("vcs") == "git":
        version = vcs.get("requested_revision")
        return f'uv tool install --force "navaja[{extras}] @ git+{url}{"@" + version if version else ""}"'
    if not (url and "archive_info" in origen):  # no se sabe: el .zip de esta versión (sin git)
        url = zip_de_version()
    return f'uv tool install --force "navaja[{extras}] @ {url}"'


def zip_de_version(version: str = __version__) -> str:
    """El .zip de una versión en GitHub: se instala sin tener git (es lo que usa el instalador)."""
    return f"{REPO}/archive/refs/tags/v{version}.zip"


def donde_instalar() -> str:
    """Lo que va delante del comando: con --editable hay que estar en la carpeta de navaja."""
    return "Desde la carpeta de navaja" if instalada_editable() else "Instálalo con"


class FaltaAlgo(NavajaError):
    """Falta una librería opcional o un programa de fuera: el mensaje dice cómo instalarlo."""


def libreria(modulo: str, paquete: str, extra: str, para: str) -> ModuleType:
    """Importa una librería opcional o lanza ``FaltaAlgo`` con el comando para instalarla."""
    try:
        return importlib.import_module(modulo)
    except ImportError:
        raise FaltaAlgo(
            f"Para {para} hace falta {paquete}. {donde_instalar()}: {como_instalar(extra)}"
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
        if tiene_comodin(patron):  # solo * y ? (los corchetes van tal cual): buscar_con_comodin
            encontrados = buscar_con_comodin(ruta)
            if not encontrados:
                raise NavajaError(f"Ningún archivo encaja con {patron}.")
            archivos += encontrados
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
    mas_destinos: list[Path] = field(default_factory=list)  # PDF a imágenes: una por página

    def borrar_lo_hecho(self) -> list[Path]:
        """Quita lo que dejó a medias (si falló o se cortó). Devuelve lo que no se ha podido
        borrar (en Windows, abierto por el antivirus, OneDrive o un visor), para decirlo."""
        quedan = []
        for destino in [self.destino, *self.mas_destinos]:
            try:
                destino.unlink(missing_ok=True)
            except OSError:
                quedan.append(destino)
        return quedan


@dataclass
class Fallo:
    origen: Path
    motivo: str
    a_medias: list[Path] = field(default_factory=list)  # lo que no se ha podido borrar


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


def motivo(error: BaseException) -> str:
    if isinstance(error, NavajaError):
        return str(error)
    return f"{type(error).__name__}: {error}"  # una foto rota no debe parar las demás


def fallo_de(tarea: Tarea, error: BaseException) -> Fallo:
    """El fallo de una tarea, con lo que dejó a medias ya borrado (o apuntado si no se pudo)."""
    return Fallo(tarea.origen, motivo(error), tarea.borrar_lo_hecho())


def avisar_fallos(fallos: list[Fallo]) -> None:
    for fallo in fallos:
        quedan = ""
        if fallo.a_medias:
            nombres = ", ".join(p.name for p in fallo.a_medias)
            quedan = f" [aviso](no se ha podido borrar lo que quedó a medias, bórralo tú: {escape(nombres)})[/]"
        error_console.print(f"[error]✘ {escape(fallo.origen.name)}:[/] {escape(fallo.motivo)}{quedan}", soft_wrap=True)


ESPERA = 0.2
"""Cada cuánto se mira si ha acabado alguna tarea (segundos)."""


def hacer_todo(tareas: list[Tarea], hilos: int = 4) -> list[Fallo]:
    """Hace las tareas en paralelo con una barra; si una falla, las demás siguen.

    Con Ctrl+C se para: ver ``cortar``.
    """
    fallos: list[Fallo] = []
    progreso = Progress(
        SpinnerColumn(style="acento"), TextColumn("[pista]{task.completed} de {task.total}[/]"),
        BarColumn(style="borde", complete_style="acento"), console=console, transient=True,
        disable=not console.is_terminal,
    )
    ejecutor = ThreadPoolExecutor(max_workers=max(1, min(hilos, len(tareas))))
    futuros: dict[Future[object], Tarea] = {}
    vistos: set[Future[object]] = set()
    try:
        with progreso:
            barra = progreso.add_task("", total=len(tareas))
            for tarea in tareas:
                futuros[ejecutor.submit(tarea.hacer)] = tarea
            pendientes = set(futuros)
            while pendientes:
                # Esperas cortas y no as_completed: en Windows (hasta Python 3.14) una espera sin
                # límite no deja pasar el Ctrl+C hasta que acaba alguna tarea.
                listos, pendientes = wait(pendientes, timeout=ESPERA, return_when=FIRST_COMPLETED)
                for futuro in listos:
                    error = futuro.exception()
                    if error is not None:
                        fallos.append(fallo_de(futuros[futuro], error))
                    vistos.add(futuro)  # después: con un Ctrl+C justo antes, cortar lo recoge
                    progreso.advance(barra)
    except KeyboardInterrupt:
        cortar(ejecutor, futuros, vistos, fallos, len(tareas))
    ejecutor.shutdown()
    return fallos


@contextlib.contextmanager
def sin_ctrl_c() -> Iterator[None]:
    """Mientras se recoge tras un Ctrl+C, otro Ctrl+C no corta navaja: dejaría archivos a
    medias y una traza. (Los programas que ya están en marcha, como FFmpeg, sí lo reciben y
    paran; su tarea falla y se limpia igual.) Solo se puede tocar desde el hilo principal."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    anterior = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, anterior)


def cortar(
    ejecutor: ThreadPoolExecutor, futuros: dict[Future[object], Tarea], vistos: set[Future[object]],
    fallos: list[Fallo], total: int,
) -> NoReturn:
    """Ctrl+C: lo de la cola ya no empieza y se espera a lo que estaba en marcha (un hilo no se
    puede matar; FFmpeg, LibreOffice y Pandoc sí reciben el Ctrl+C y paran). Lo que falla o
    queda a medias se borra; lo que acabó bien se queda. Se dicen todos los fallos, también
    los de antes del corte. Sale con 130, como cualquier Ctrl+C."""
    with sin_ctrl_c():
        for futuro in futuros:
            futuro.cancel()  # solo cancela lo que no ha empezado
        error_console.print("[aviso]Cortando: no se empieza nada más; espera a que acabe lo que estaba en marcha…[/]")
        ejecutor.shutdown(wait=True)
        hechos = 0
        for futuro, tarea in futuros.items():
            if futuro.cancelled():
                continue
            error = futuro.exception()
            if error is None:
                hechos += 1
            elif futuro not in vistos:
                fallos.append(fallo_de(tarea, error))
        avisar_fallos(fallos)
        limpio = not any(f.a_medias for f in fallos)
        error_console.print(
            f"[aviso]Cortado: {cuantos(hechos, 'archivo nuevo', 'archivos nuevos')} de {total}.[/]"  # total: aunque no se llegara a enviar todo
            + (" [pista]No queda nada a medias.[/]" if limpio else "")
        )
    raise typer.Exit(130)


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
    avisar_fallos(fallos)
    if fallos:
        raise typer.Exit(1)
