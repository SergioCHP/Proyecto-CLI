"""navaja sistema: cómo va el PC, en vivo.

CPU, memoria, discos, batería, cuánto lleva encendido y los programas que más gastan,
en un recuadro que se actualiza solo hasta Ctrl+C (``--una-vez`` lo enseña una vez y
sale). Los programas con varios procesos (Chrome, Code…) se suman en una fila, como en
el Administrador de tareas. Solo mira: no cierra nada. Los datos salen de psutil
(extra ``sistema``).
"""

from __future__ import annotations

import os
import platform
import socket
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import typer
from rich.console import Group
from rich.live import Live
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, REDES, console, cuantos, es_utf8, recuadro, resumen, tabla_ligera, tamano_legible
from ..errores import NavajaError
from ..lotes import fallar, libreria

ANCHO_BARRA = 20
ESPERA_PRIMERA = 0.5
"""Segundos que se mide la CPU la primera vez: psutil necesita dos medidas para un porcentaje."""

SIN_DISCO = {"squashfs", "tmpfs", "devtmpfs", "overlay", "iso9660", "udf", "autofs", "proc", "sysfs"}
"""Sistemas de archivos que no son un disco tuyo (los snap de Ubuntu, la RAM, un CD…)."""

QUITAR_DE_PROCESOS = {0}
"""El PID 0 en Windows es el «Proceso inactivo del sistema»: su CPU es la que sobra."""


class Orden(str, Enum):
    cpu = "cpu"
    memoria = "memoria"


@dataclass
class Programa:
    nombre: str
    procesos: int
    cpu: float  # % del PC entero (100 = todos los núcleos a tope)
    memoria: int  # bytes


def nivel(porcentaje: float, invertido: bool = False) -> str:
    """El estilo del tema según lo lleno que esté: ok, aviso o error.

    ``invertido`` es para la batería: poca carga es lo malo.
    """
    if invertido:
        porcentaje = 100 - porcentaje
    if porcentaje >= 90:
        return "error"
    if porcentaje >= 70:
        return "aviso"
    return "ok"


def barra(porcentaje: float, ancho: int = ANCHO_BARRA, utf8: bool = True, invertido: bool = False) -> str:
    """Una barra con markup del tema: «[ok]██████[/][pista]░░░░[/] 30 %»."""
    porcentaje = max(0.0, min(100.0, porcentaje))
    llenos = round(porcentaje / 100 * ancho)
    lleno, vacio = ("█", "░") if utf8 else ("#", "-")
    estilo = nivel(porcentaje, invertido)
    return f"[{estilo}]{lleno * llenos}[/][pista]{vacio * (ancho - llenos)}[/] {porcentaje:3.0f} %"


def tiempo_encendido(segundos: float) -> str:
    """90061 → «1 día 1 h 1 min»; menos de un minuto → «menos de 1 min»."""
    minutos = int(segundos // 60)
    if minutos < 1:
        return "menos de 1 min"
    dias, minutos = divmod(minutos, 24 * 60)
    horas, minutos = divmod(minutos, 60)
    trozos = []
    if dias:
        trozos.append(cuantos(dias, "día"))
    if horas:
        trozos.append(f"{horas} h")
    if minutos or not trozos:
        trozos.append(f"{minutos} min")
    return " ".join(trozos)


def juntar_programas(procesos: list[tuple[str, float, int]], nucleos: int) -> list[Programa]:
    """Suma los procesos que se llaman igual. Cada uno es (nombre, % de CPU de psutil, bytes).

    psutil da la CPU de un proceso sobre un núcleo (puede pasar de 100); se divide entre
    los núcleos para que sea del PC entero, como en el Administrador de tareas.
    """
    juntos: dict[str, Programa] = {}
    for nombre, cpu, memoria in procesos:
        programa = juntos.setdefault(nombre.lower(), Programa(nombre, 0, 0.0, 0))
        programa.procesos += 1
        programa.cpu += (cpu or 0.0) / max(1, nucleos)
        programa.memoria += memoria or 0
    return list(juntos.values())


def los_que_mas(programas: list[Programa], orden: Orden, cuantos_: int) -> list[Programa]:
    if orden is Orden.memoria:
        clave = lambda p: (p.memoria, p.cpu)  # noqa: E731
    else:
        clave = lambda p: (round(p.cpu, 1), p.memoria)  # noqa: E731
    return sorted(programas, key=clave, reverse=True)[:cuantos_]


def es_disco(particion: Any) -> bool:
    """¿Es una unidad tuya? Fuera los CD, los snap de Ubuntu, la RAM y similares."""
    if particion.fstype.lower() in SIN_DISCO or "cdrom" in (particion.opts or ""):
        return False
    return bool(particion.fstype)


def texto_bateria(porcentaje: float, enchufado: bool, segundos: int | None) -> str:
    """«82 % · cargando», «45 % · quedan 2 h 10 min», «100 % · enchufado»."""
    if enchufado:
        detalle = "enchufado" if porcentaje >= 99.5 else "cargando"
    elif segundos:
        detalle = f"quedan {tiempo_encendido(segundos)}"
    else:
        detalle = "con batería"
    return detalle


def nombre_del_sistema() -> str:
    sistema = platform.system()
    if sistema == "Darwin":
        return f"macOS {platform.mac_ver()[0]}"
    if sistema == "Windows":
        return f"Windows {platform.release()}"
    try:
        datos = platform.freedesktop_os_release()
        return datos.get("PRETTY_NAME") or f"Linux {platform.release()}"
    except OSError:
        return f"Linux {platform.release()}"


class Muestreo:
    """Lo que hace falta guardar entre una vuelta y otra: psutil calcula la CPU de cada
    proceso comparando con la medida anterior del mismo objeto."""

    def __init__(self) -> None:
        self.psutil = libreria("psutil", "psutil", "sistema", "ver cómo va el PC")
        self.procesos: dict[int, Any] = {}
        self.nucleos = self.psutil.cpu_count() or 1
        self.psutil.cpu_percent(interval=None)  # la primera medida: la de verdad, en la siguiente
        self._medir_procesos()

    def _medir_procesos(self) -> list[tuple[str, float, int]]:
        psutil = self.psutil
        vistos: dict[int, Any] = {}
        datos = []
        for proceso in psutil.process_iter(["name", "memory_info"]):
            if proceso.pid in QUITAR_DE_PROCESOS:
                continue
            anterior = self.procesos.get(proceso.pid)
            medido = anterior if anterior is not None and anterior == proceso else proceso  # PID reusado: otro
            vistos[proceso.pid] = medido
            try:
                cpu = medido.cpu_percent(interval=None)
                nombre = proceso.info.get("name") or proceso.name()
                memoria = proceso.info.get("memory_info")
                datos.append((nombre, cpu, memoria.rss if memoria else 0))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        self.procesos = vistos
        return datos

    def tomar(self, orden: Orden, cuantos_: int) -> dict[str, Any]:
        psutil = self.psutil
        memoria = psutil.virtual_memory()
        intercambio = psutil.swap_memory()
        discos = []
        vistos = set()
        for particion in psutil.disk_partitions(all=False):
            if not es_disco(particion) or particion.device in vistos:
                continue
            try:
                uso = psutil.disk_usage(particion.mountpoint)
            except (OSError, PermissionError):  # un lector de tarjetas vacío
                continue
            vistos.add(particion.device)
            discos.append((particion.mountpoint, uso))
        try:
            bateria = psutil.sensors_battery()
        except (AttributeError, NotImplementedError, OSError):
            bateria = None
        try:
            frecuencia = psutil.cpu_freq()
        except (AttributeError, NotImplementedError, OSError, FileNotFoundError):
            frecuencia = None
        programas = juntar_programas(self._medir_procesos(), self.nucleos)
        return {
            "cpu": psutil.cpu_percent(interval=None),
            "nucleos": self.nucleos,
            "fisicos": psutil.cpu_count(logical=False) or 0,
            "frecuencia": frecuencia.current if frecuencia else 0,
            "memoria": memoria,
            "intercambio": intercambio,
            "discos": discos,
            "bateria": bateria,
            "sin_limite": getattr(psutil, "POWER_TIME_UNLIMITED", None),
            "desconocido": getattr(psutil, "POWER_TIME_UNKNOWN", None),
            "encendido": time.time() - psutil.boot_time(),
            "programas": los_que_mas(programas, orden, cuantos_),
            "total_procesos": sum(p.procesos for p in programas),
        }


def panel(datos: dict[str, Any], orden: Orden, vivo: bool, utf8: bool) -> Any:
    memoria = datos["memoria"]
    usada = memoria.total - memoria.available  # lo que de verdad no puedes usar, como Windows
    nucleos = f"{datos['nucleos']} núcleos"
    if datos["fisicos"] and datos["fisicos"] != datos["nucleos"]:
        nucleos += f" ({datos['fisicos']} físicos)"
    if datos["frecuencia"]:
        nucleos += f" · {datos['frecuencia'] / 1000:.1f} GHz"
    filas = [
        ("Equipo", f"{escape(socket.gethostname())} [pista]· {escape(nombre_del_sistema())}[/]"),
        ("Encendido", f"hace {tiempo_encendido(datos['encendido'])}"),
        ("CPU", f"{barra(datos['cpu'], utf8=utf8)} [pista]· {nucleos}[/]"),
        ("Memoria", f"{barra(usada / memoria.total * 100, utf8=utf8)} [pista]· {tamano_legible(usada)} de "
                    f"{tamano_legible(memoria.total)}[/]"),
    ]
    intercambio = datos["intercambio"]
    if intercambio.total:
        filas.append(("Intercambio", f"{barra(intercambio.percent, utf8=utf8)} [pista]· {tamano_legible(intercambio.used)} "
                                     f"de {tamano_legible(intercambio.total)}[/]"))
    for punto, uso in datos["discos"]:
        filas.append((escape(punto), f"{barra(uso.percent, utf8=utf8)} [pista]· libres {tamano_legible(uso.free)} "
                                     f"de {tamano_legible(uso.total)}[/]"))
    bateria = datos["bateria"]
    if bateria is not None:
        segundos = bateria.secsleft
        if segundos in (datos["sin_limite"], datos["desconocido"]) or segundos is None or segundos < 0:
            segundos = None
        filas.append(("Batería", f"{barra(bateria.percent, utf8=utf8, invertido=True)} [pista]· "
                                 f"{texto_bateria(bateria.percent, bool(bateria.power_plugged), segundos)}[/]"))

    tabla = tabla_ligera()
    tabla.add_column("Programa")
    tabla.add_column("Procesos", justify="right")
    tabla.add_column("CPU", justify="right", style="acento" if orden is Orden.cpu else None)
    tabla.add_column("Memoria", justify="right", style="acento" if orden is Orden.memoria else None)
    for programa in datos["programas"]:
        tabla.add_row(escape(programa.nombre), str(programa.procesos), f"{programa.cpu:.1f} %",
                      tamano_legible(programa.memoria))
    que = "CPU" if orden is Orden.cpu else "memoria"
    partes: list[Any] = [
        resumen(filas),
        Group(
            Text.from_markup(
                f"[titulo]Lo que más {que} gasta[/] [pista]· {cuantos(datos['total_procesos'], 'proceso')} en total[/]"
            ),
            tabla,
        ),
    ]
    if vivo:
        partes.append("[pista]Se actualiza solo · Ctrl+C para salir[/]")
    return recuadro("navaja · sistema", *partes)


def sistema(
    orden: Orden = typer.Option(
        Orden.cpu, "--orden", "-o", help="Qué programas salen primero: los que más cpu o más memoria gastan.",
        rich_help_panel=AJUSTE,
    ),
    cuantos_: int = typer.Option(5, "--cuantos", "-n", min=1, max=30, help="Cuántos programas enseña."),
    una_vez: bool = typer.Option(
        False, "--una-vez", help="Lo enseña una vez y sale (sin esto se actualiza hasta Ctrl+C)."
    ),
    cada: int = typer.Option(2, "--cada", min=1, max=60, help="Segundos entre una actualización y la siguiente."),
) -> None:
    """Cómo va el PC: CPU, memoria, discos, batería y lo que más gasta."""
    try:
        muestreo = Muestreo()
    except NavajaError as error:
        fallar(error)
    utf8 = es_utf8(console)
    vivo = not una_vez and console.is_terminal and not os.environ.get("NAVAJA_SIN_VIVO")
    try:
        time.sleep(ESPERA_PRIMERA)
        if not vivo:
            console.print(panel(muestreo.tomar(orden, cuantos_), orden, False, utf8))
            return
        with Live(panel(muestreo.tomar(orden, cuantos_), orden, True, utf8), console=console,
                  auto_refresh=False) as pantalla:
            while True:
                time.sleep(cada)
                pantalla.update(panel(muestreo.tomar(orden, cuantos_), orden, True, utf8), refresh=True)
    except KeyboardInterrupt:
        console.print("[pista]Hasta luego.[/]")


def registrar(app: typer.Typer) -> None:
    app.command("sistema", help="Cómo va el PC: CPU, memoria, discos, batería y lo que más gasta.", rich_help_panel=REDES)(sistema)
