"""navaja red: tu tarjeta de red de un vistazo.

IP, máscara (y su /prefijo), puerta de enlace, MAC y velocidad de cada tarjeta activa,
con la que sale a internet la primera. Solo mira: no cambia nada de la red. Las tarjetas
salen de psutil (extra ``sistema``); la puerta de enlace, de lo que dice el sistema
(``/proc/net/route`` en Linux, ``route print`` en Windows y ``route get`` en macOS).
"""

from __future__ import annotations

import ipaddress
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer
from rich.console import Group
from rich.markup import escape
from rich.text import Text

from ..comun import REDES, como_se_escribe, console, recuadro, resumen
from ..errores import NavajaError
from ..lotes import fallar, libreria

VIRTUALES = (
    "virtualbox", "vmware", "vethernet", "hyper-v", "docker", "veth", "br-", "virbr",
    "tailscale", "zerotier", "wsl", "vpn", "tap", "tun", "utun", "npcap", "loopback",
)
"""Trozos de nombre de las tarjetas que no son un cable ni una antena de verdad."""


@dataclass
class Tarjeta:
    nombre: str
    activa: bool
    ipv4: list[str] = field(default_factory=list)  # «192.168.1.34/24»
    ipv6: list[str] = field(default_factory=list)
    mac: str = ""
    velocidad: int = 0  # Mbit/s; 0 si no se sabe
    puerta: str = ""
    principal: bool = False

    @property
    def tipo(self) -> str:
        return tipo_de_tarjeta(self.nombre)

    @property
    def virtual(self) -> bool:
        return self.tipo in ("Virtual", "Loopback")


@dataclass
class Puerta:
    """Una ruta por defecto: por qué tarjeta (nombre o IP local) y a qué router."""

    puerta: str
    interfaz: str = ""
    ip_local: str = ""


def tipo_de_tarjeta(nombre: str) -> str:
    """Wi-Fi, Cable, Bluetooth, Virtual o Loopback, por el nombre de la tarjeta."""
    bajo = nombre.lower()
    if bajo == "lo" or bajo.startswith("loopback") or "loopback pseudo" in bajo:
        return "Loopback"
    if "bluetooth" in bajo:
        return "Bluetooth"
    if any(trozo in bajo for trozo in VIRTUALES):
        return "Virtual"
    if "wi-fi" in bajo or "wifi" in bajo or "wlan" in bajo or "inalámbrica" in bajo or bajo.startswith("wl"):
        return "Wi-Fi"
    if "ethernet" in bajo or bajo.startswith(("eth", "en", "em")):
        return "Cable"
    return "Otra"


def con_prefijo(ip: str, mascara: str | None) -> str:
    """«192.168.1.34» y «255.255.255.0» → «192.168.1.34/24». Sin máscara, la IP sola."""
    ip = ip.split("%")[0]  # fe80::1%eth0: el %zona no es parte de la dirección
    if not mascara:
        return ip
    try:
        if ":" in mascara:  # IPv6 no acepta la máscara escrita: se cuentan sus unos
            mascara = str(bin(int(ipaddress.IPv6Address(mascara))).count("1"))
        return str(ipaddress.ip_interface(f"{ip}/{mascara}"))
    except ValueError:
        return ip


def mascara_de(interfaz: str) -> str:
    """«192.168.1.34/24» → «255.255.255.0»."""
    try:
        return str(ipaddress.ip_interface(interfaz).netmask)
    except ValueError:
        return ""


def es_apipa(interfaz: str) -> bool:
    """169.254.x.x: Windows se la pone sola cuando el router no le ha dado ninguna."""
    try:
        return ipaddress.ip_interface(interfaz).ip in ipaddress.ip_network("169.254.0.0/16")
    except ValueError:
        return False


def puertas_linux(texto: str) -> list[Puerta]:
    """Rutas por defecto de ``/proc/net/route`` (las IP van en hexadecimal y al revés)."""
    puertas = []
    for linea in texto.splitlines()[1:]:
        partes = linea.split()
        if len(partes) < 3 or partes[1] != "00000000":
            continue
        try:
            ip = socket.inet_ntoa(int(partes[2], 16).to_bytes(4, "little"))
        except (ValueError, OverflowError):
            continue
        if ip != "0.0.0.0":
            puertas.append(Puerta(ip, interfaz=partes[0]))
    return puertas


def puertas_windows(texto: str) -> list[Puerta]:
    """Rutas por defecto de ``route print -4 0.0.0.0``: líneas «0.0.0.0 0.0.0.0 puerta ip métrica».

    Solo se miran números, así que vale en Windows en cualquier idioma.
    """
    puertas = []
    for linea in texto.splitlines():
        partes = linea.split()
        if len(partes) >= 4 and partes[0] == "0.0.0.0" and partes[1] == "0.0.0.0":
            try:
                ipaddress.IPv4Address(partes[2])
                ipaddress.IPv4Address(partes[3])
            except ValueError:  # «En vínculo» (sin router) u otra cosa
                continue
            puertas.append(Puerta(partes[2], ip_local=partes[3]))
    return puertas


def puertas_macos(texto: str) -> list[Puerta]:
    """La ruta por defecto de ``route -n get default`` («gateway: …» e «interface: …»)."""
    datos = {}
    for linea in texto.splitlines():
        clave, _, valor = linea.strip().partition(":")
        datos[clave.strip()] = valor.strip()
    if datos.get("gateway"):
        return [Puerta(datos["gateway"], interfaz=datos.get("interface", ""))]
    return []


def _ejecutar(orden: list[str]) -> str:
    try:
        salida = subprocess.run(
            orden, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return salida.stdout


def puertas_de_enlace(plataforma: str = sys.platform) -> list[Puerta]:
    """Las rutas por defecto del sistema; lista vacía si no se pueden leer."""
    if plataforma == "win32":
        return puertas_windows(_ejecutar(["route", "print", "-4", "0.0.0.0"]))
    if plataforma == "darwin":
        return puertas_macos(_ejecutar(["route", "-n", "get", "default"]))
    try:
        return puertas_linux(Path("/proc/net/route").read_text(encoding="utf-8"))
    except OSError:
        return []


def ip_de_salida() -> str:
    """La IP local con la que se sale a internet. Un socket UDP «conectado» no envía nada:
    solo pregunta al sistema qué tarjeta usaría. Sin red, cadena vacía."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as prueba:
            prueba.connect(("8.8.8.8", 80))
            return prueba.getsockname()[0]
    except OSError:
        return ""


def tarjetas_desde(
    direcciones: dict[str, list[Any]],
    estados: dict[str, Any],
    salida: str,
    puertas: list[Puerta],
    af_link: int,
) -> list[Tarjeta]:
    """Arma las tarjetas con lo que da psutil (``net_if_addrs`` y ``net_if_stats``).

    Cada dirección tiene ``family``, ``address`` y ``netmask``; ``af_link`` es la familia de
    la MAC (``psutil.AF_LINK``). La que tiene la IP ``salida`` es la principal y va primero;
    luego las de verdad (cable, Wi-Fi) y al final las virtuales.
    """
    tarjetas = []
    for nombre, lista in direcciones.items():
        estado = estados.get(nombre)
        tarjeta = Tarjeta(
            nombre,
            activa=bool(getattr(estado, "isup", False)),
            velocidad=int(getattr(estado, "speed", 0) or 0),
        )
        for direccion in lista:
            if direccion.family == socket.AF_INET:
                tarjeta.ipv4.append(con_prefijo(direccion.address, direccion.netmask))
            elif direccion.family == socket.AF_INET6:
                tarjeta.ipv6.append(con_prefijo(direccion.address, direccion.netmask))
            elif direccion.family == af_link and direccion.address:
                tarjeta.mac = direccion.address.upper()
        if tarjeta.mac.replace("-", "").replace(":", "").strip("0") == "":
            tarjeta.mac = ""  # 00:00:00:00:00:00 (loopback): no es una MAC de verdad
        tarjeta.principal = bool(salida) and any(ip.split("/")[0] == salida for ip in tarjeta.ipv4)
        for puerta in puertas:
            if (puerta.interfaz and puerta.interfaz == nombre) or (
                puerta.ip_local and any(ip.split("/")[0] == puerta.ip_local for ip in tarjeta.ipv4)
            ):
                tarjeta.puerta = puerta.puerta
                break
        tarjetas.append(tarjeta)
    principal = next((t for t in tarjetas if t.principal), None)
    if principal and not principal.puerta and len(puertas) == 1:
        principal.puerta = puertas[0].puerta  # sin forma de saber de qué tarjeta: la principal
    tarjetas.sort(key=lambda t: (not t.principal, not t.activa, t.virtual, t.tipo == "Otra", t.nombre.lower()))
    return tarjetas


def recoger() -> list[Tarjeta]:
    psutil = libreria("psutil", "psutil", "sistema", "ver la red")
    return tarjetas_desde(
        psutil.net_if_addrs(), psutil.net_if_stats(), ip_de_salida(), puertas_de_enlace(), psutil.AF_LINK
    )


def visibles(tarjetas: list[Tarjeta], todas: bool) -> list[Tarjeta]:
    """Sin ``--todas``: las encendidas con IPv4, sin la de loopback (127.0.0.1)."""
    if todas:
        return tarjetas
    return [t for t in tarjetas if t.activa and t.ipv4 and t.tipo != "Loopback"]


def velocidad_legible(mbits: int) -> str:
    if mbits >= 1000 and mbits % 1000 == 0:
        return f"{mbits // 1000} Gbit/s"
    return f"{mbits} Mbit/s"


def filas_de(tarjeta: Tarjeta, ipv6: bool) -> list[tuple[str, str]]:
    filas = []
    for ip in tarjeta.ipv4:
        aviso = " [aviso](APIPA: el router no le ha dado IP)[/]" if es_apipa(ip) else ""
        filas.append(("IP", f"[acento]{escape(ip)}[/]{aviso}"))
        filas.append(("Máscara", escape(mascara_de(ip))))
    if not tarjeta.ipv4:
        filas.append(("IP", "[pista]sin IPv4[/]"))
    if tarjeta.puerta:
        filas.append(("Puerta de enlace", f"{escape(tarjeta.puerta)} [pista](tu router)[/]"))
    if ipv6:
        for ip in tarjeta.ipv6:
            filas.append(("IPv6", escape(ip)))
    if tarjeta.mac:
        filas.append(("MAC", escape(tarjeta.mac)))
    if tarjeta.velocidad:
        filas.append(("Velocidad", velocidad_legible(tarjeta.velocidad)))
    if not tarjeta.activa:
        filas.append(("Estado", "[aviso]apagada o sin conectar[/]"))
    return filas


def red(
    todas: bool = typer.Option(
        False, "--todas", "-t", help="También las apagadas, las virtuales sin IP y la de loopback (127.0.0.1)."
    ),
    ipv6: bool = typer.Option(False, "--ipv6", "-6", help="Enseña también las direcciones IPv6."),
) -> None:
    """Tu tarjeta de red: IP, máscara, puerta de enlace, MAC y velocidad."""
    try:
        tarjetas = visibles(recoger(), todas)
    except NavajaError as error:
        fallar(error)
    partes: list[Any] = [resumen([("Equipo", escape(socket.gethostname()))])]
    if not tarjetas:
        partes.append("[aviso]No hay ninguna tarjeta conectada con IP. ¿Está el cable o la wifi?[/]")
    for tarjeta in tarjetas:
        cabecera = f"[titulo]{escape(tarjeta.nombre)}[/] [pista]· {tarjeta.tipo}[/]"
        if tarjeta.principal:
            cabecera += " [ok]★ sale a internet por aquí[/]"
        partes.append(Group(Text.from_markup(cabecera), resumen(filas_de(tarjeta, ipv6))))
    principal = next((t for t in tarjetas if t.principal and t.ipv4), None)
    if principal:
        partes.append(
            f"[pista]Toda tu red explicada: {escape(como_se_escribe('subred ver ' + principal.ipv4[0]))}[/]"
        )
    console.print(recuadro("navaja · red", *partes))


def registrar(app: typer.Typer) -> None:
    app.command("red", help="Tu tarjeta de red: IP, máscara, puerta de enlace, MAC y velocidad.", rich_help_panel=REDES)(red)
