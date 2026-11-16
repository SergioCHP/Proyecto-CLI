"""navaja extrae: descomprimir un .zip o .tar(.gz) enseñando antes qué lleva.

Seguro: nada sale de la carpeta de destino (un zip con «../» o «C:\\» delante, el truco
de los zip maliciosos, se salta), no se crean enlaces ni dispositivos de un .tar y nunca
se pisa nada: si hay que extraer en una carpeta que ya tiene ese archivo, sale «(1)».
Si el zip ya trae su propia carpeta dentro, no se mete en otra con el mismo nombre.
"""

from __future__ import annotations

import os
import shutil
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, NoReturn

import typer
from rich.markup import escape
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn
from rich.text import Text

from ..comun import (
    ARCHIVOS,
    bonita,
    confirmar,
    console,
    cuantos,
    error_console,
    recuadro,
    resumen,
    ruta_libre,
    tabla_ligera,
    tamano_legible,
)
from ..errores import NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR

SIN_SOPORTE = {".rar": "RAR", ".7z": "7-Zip"}
EXTENSIONES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz", ".tar", ".zip")
ENSENAR = 15
"""Cuántos archivos se enseñan antes de preguntar; del resto, solo cuántos son."""


@dataclass
class Entrada:
    """Un archivo o carpeta de dentro del comprimido."""

    nombre: str  # tal cual viene
    ruta: PurePosixPath | None  # la ruta segura relativa, o None si no se puede extraer
    tamano: int
    carpeta: bool
    fecha: float | None = None
    motivo: str = ""  # por qué no se extrae


def ruta_segura(nombre: str) -> PurePosixPath | None:
    """La ruta relativa si no se sale de la carpeta de destino; si no, None.

    Se rechazan las absolutas («/etc/…», «C:\\…», «\\\\servidor\\…») y las que llevan «..».
    """
    limpio = nombre.replace("\\", "/")
    if not limpio or limpio.startswith("/") or (len(limpio) > 1 and limpio[1] == ":"):
        return None
    partes = [p for p in limpio.split("/") if p not in ("", ".")]
    if not partes or ".." in partes:
        return None
    return PurePosixPath(*partes)


def leer_contenido(archivo: Path) -> tuple[str, list[Entrada]]:
    """Qué hay dentro: ("zip" o "tar", las entradas). ``NavajaError`` si no se puede abrir."""
    sufijo = archivo.suffix.lower()
    if sufijo in SIN_SOPORTE:
        raise NavajaError(
            f"Los {SIN_SOPORTE[sufijo]} aún no se pueden abrir con navaja: hace falta 7-Zip "
            "(winget install 7zip.7zip). navaja doctor dice si lo tienes."
        )
    if zipfile.is_zipfile(archivo):
        with zipfile.ZipFile(archivo) as zipeado:
            entradas = []
            for info in zipeado.infolist():
                if info.flag_bits & 0x1:
                    raise NavajaError(f"{archivo.name} tiene contraseña: aún no se puede abrir con navaja.")
                ruta = ruta_segura(info.filename)
                fecha = time.mktime(info.date_time + (0, 0, -1)) if info.date_time[0] >= 1980 else None
                entradas.append(
                    Entrada(info.filename, ruta, info.file_size, info.is_dir(), fecha,
                            "" if ruta else "se saldría de la carpeta")
                )
            return "zip", entradas
    try:
        with tarfile.open(archivo) as tar:
            entradas = []
            for miembro in tar.getmembers():
                ruta = ruta_segura(miembro.name)
                motivo = "" if ruta else "se saldría de la carpeta"
                if ruta and not (miembro.isfile() or miembro.isdir()):
                    ruta, motivo = None, "es un enlace o un dispositivo"
                entradas.append(Entrada(miembro.name, ruta, miembro.size, miembro.isdir(), miembro.mtime, motivo))
            return "tar", entradas
    except (tarfile.TarError, OSError):
        pass
    raise NavajaError(f"{archivo.name} no es un .zip ni un .tar (o está dañado).")


def sin_extension(nombre: str) -> str:
    bajo = nombre.lower()
    for extension in EXTENSIONES:
        if bajo.endswith(extension):
            return nombre[: -len(extension)] or nombre
    return Path(nombre).stem


def carpeta_comun(entradas: list[Entrada]) -> str | None:
    """Si todo va dentro de una sola carpeta («practica/…»), su nombre."""
    primeras = {e.ruta.parts[0] for e in entradas if e.ruta}
    if len(primeras) != 1:
        return None
    unica = primeras.pop()
    if any(e.ruta and len(e.ruta.parts) == 1 and not e.carpeta for e in entradas):
        return None  # hay un archivo suelto con ese nombre, no una carpeta
    return unica


@dataclass
class Plan:
    raiz: Path  # dónde va todo
    quitar: str | None  # la carpeta común que ya es la raíz (no se repite)
    nueva: bool  # la raíz se crea ahora (y se puede quitar si se cancela)


def planificar(archivo: Path, entradas: list[Entrada], destino: Path | None) -> Plan:
    """Sin --destino: al lado del archivo, en una carpeta nueva con su nombre, o con el de
    la carpeta que ya trae dentro (sin repetirla). Con --destino: dentro de esa carpeta."""
    if destino is not None:
        return Plan(destino, None, not destino.exists())
    comun = carpeta_comun(entradas)
    nombre = comun or sin_extension(archivo.name)
    return Plan(ruta_libre(archivo.parent / nombre), comun, True)


def destino_de(plan: Plan, ruta: PurePosixPath) -> Path:
    partes = ruta.parts[1:] if plan.quitar else ruta.parts
    return plan.raiz.joinpath(*partes)


def extraer(archivo: Path, tipo: str, entradas: list[Entrada], plan: Plan, avance=None) -> list[Path]:
    """Extrae las entradas seguras. Lo que ya existe no se pisa: se le pone «(1)»."""
    creados: list[Path] = []
    plan.raiz.mkdir(parents=True, exist_ok=True)

    def copiar(origen: IO[bytes], entrada: Entrada) -> None:
        assert entrada.ruta is not None
        final = ruta_libre(destino_de(plan, entrada.ruta))
        final.parent.mkdir(parents=True, exist_ok=True)
        with open(final, "wb") as salida:
            while trozo := origen.read(1024 * 1024):
                salida.write(trozo)
                if avance:
                    avance(len(trozo))
        if entrada.fecha:
            try:
                os.utime(final, (entrada.fecha, entrada.fecha))
            except (OSError, OverflowError, ValueError):
                pass
        creados.append(final)

    seguras = [e for e in entradas if e.ruta is not None]
    if tipo == "zip":
        with zipfile.ZipFile(archivo) as zipeado:
            for entrada in seguras:
                if entrada.carpeta:
                    destino_de(plan, entrada.ruta).mkdir(parents=True, exist_ok=True)
                    continue
                with zipeado.open(entrada.nombre) as origen:
                    copiar(origen, entrada)
    else:
        with tarfile.open(archivo) as tar:
            for entrada in seguras:
                if entrada.carpeta:
                    destino_de(plan, entrada.ruta).mkdir(parents=True, exist_ok=True)
                    continue
                origen = tar.extractfile(entrada.nombre)
                if origen is not None:
                    with origen:
                        copiar(origen, entrada)
    return creados


# ── Orden ──────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def extrae(
    archivo: Path = typer.Argument(..., help="El .zip, .tar o .tar.gz."),
    destino: Path = typer.Option(
        None, "--destino", "-d", help="En qué carpeta (por defecto, una nueva al lado del archivo).",
        show_default=False,
    ),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Descomprime un .zip o .tar(.gz): enseña antes lo que hay y no pisa nada."""
    ruta = archivo.expanduser()
    if not ruta.is_file():
        fallar(NavajaError(f"No existe el archivo {archivo}."))
    try:
        tipo, entradas = leer_contenido(ruta)
    except NavajaError as error:
        fallar(error)
    except OSError as error:
        fallar(NavajaError(f"No se puede leer {archivo}: {error.strerror or error}"))
    archivos = [e for e in entradas if e.ruta and not e.carpeta]
    malas = [e for e in entradas if e.ruta is None]
    if not archivos:
        fallar(NavajaError(f"{ruta.name} no tiene nada que se pueda extraer."))
    plan = planificar(ruta, entradas, destino.expanduser() if destino else None)
    peso = sum(e.tamano for e in archivos)
    try:
        libre = shutil.disk_usage(plan.raiz if plan.raiz.exists() else plan.raiz.parent).free
    except OSError:
        libre = None
    tabla = tabla_ligera()
    tabla.add_column("Dentro")
    tabla.add_column("Tamaño", justify="right", no_wrap=True)
    for entrada in archivos[:ENSENAR]:
        tabla.add_row(escape(str(entrada.ruta)), tamano_legible(entrada.tamano))
    filas = [
        ("Archivo", escape(bonita(ruta))),
        ("Lleva", f"{cuantos(len(archivos), 'archivo')} · {tamano_legible(peso)} al sacarlos"),
        ("Se sacan en", f"[acento]{escape(bonita(plan.raiz))}[/]" + ("" if plan.nueva else " [pista](ya existe: no se pisa nada)[/]")),
    ]
    partes: list = [resumen(filas), tabla]
    if len(archivos) > ENSENAR:
        partes.append(Text.from_markup(f"[pista]… y {len(archivos) - ENSENAR} más[/]"))
    if malas:
        nombres = ", ".join(e.nombre for e in malas[:5]) + ("…" if len(malas) > 5 else "")
        partes.append(
            Text.from_markup(
                f"[aviso]Se saltan {cuantos(len(malas), 'entrada')} que no son seguras "
                f"({escape(nombres)}): {escape(malas[0].motivo)}.[/]"
            )
        )
    console.print(recuadro(f"Extraer {ruta.name}", *partes))
    if libre is not None and peso > libre:
        fallar(NavajaError(f"No cabe: hacen falta {tamano_legible(peso)} y quedan {tamano_legible(libre)} libres."))
    if simular:
        console.print("[pista]Simulación: no se ha sacado nada.[/]")
        return
    if not confirmar("¿Lo saco?", si):
        console.print("[pista]No se ha sacado nada.[/]")
        return
    progreso = Progress(
        TextColumn("[pista]Sacando[/]"), BarColumn(style="borde", complete_style="acento"),
        DownloadColumn(), console=console, transient=True, disable=not console.is_terminal,
    )
    try:
        with progreso:
            tarea = progreso.add_task("", total=peso or 1)
            creados = extraer(ruta, tipo, entradas, plan, lambda n: progreso.advance(tarea, n))
    except (KeyboardInterrupt, OSError, zipfile.BadZipFile, tarfile.TarError) as error:
        if plan.nueva and plan.raiz.exists():
            shutil.rmtree(plan.raiz, ignore_errors=True)
            quitado = " Se ha quitado lo que llevaba sacado."
        else:
            quitado = f" Lo que llevaba sacado está en {bonita(plan.raiz)}."
        if isinstance(error, KeyboardInterrupt):
            console.print(f"\n[aviso]Cancelado.{escape(quitado)}[/]")
        else:
            detalle = getattr(error, "strerror", None) or str(error)
            error_console.print(f"[error]✘ No se ha podido sacar: {escape(detalle)}.{escape(quitado)}[/]")
        raise typer.Exit(1)
    console.print(
        f"[ok]✔ {cuantos(len(creados), 'archivo')} en {escape(bonita(plan.raiz))}.[/]", soft_wrap=True
    )


def registrar(app: typer.Typer) -> None:
    app.command(
        "extrae", help="Descomprime un .zip o .tar enseñando antes lo que lleva.", rich_help_panel=ARCHIVOS
    )(extrae)
