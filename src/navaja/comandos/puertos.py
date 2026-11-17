"""navaja puertos: qué puertos están abiertos en tu PC y qué programa usa cada uno.

``puertos`` enseña los que esperan conexiones (TCP; con ``--udp`` también UDP), con el
programa, su PID, desde dónde se puede entrar y para qué se suele usar ese puerto.
``puertos 8000`` responde «¿quién está usando el 8000?» y, con ``--cerrar``, cierra ese
programa después de enseñarlo y preguntar ``[s/n]``. Las conexiones salen de psutil
(extra ``sistema``).
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from typing import Any

import typer
from rich.markup import escape

from ..comun import REDES, como_se_escribe, confirmar, console, cuantos, error_console, recuadro, tabla_ligera
from ..errores import NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..lotes import fallar, libreria

CONOCIDOS = {
    20: "FTP (datos)", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "Correo (SMTP)", 53: "DNS",
    67: "DHCP (servidor)", 68: "DHCP (cliente)", 80: "Web (HTTP)", 110: "Correo (POP3)",
    123: "Hora (NTP)", 135: "Windows (RPC)", 137: "Windows (NetBIOS)", 138: "Windows (NetBIOS)",
    139: "Windows (NetBIOS)", 143: "Correo (IMAP)", 443: "Web segura (HTTPS)",
    445: "Carpetas compartidas (SMB)", 465: "Correo (SMTPS)", 587: "Correo (envío)",
    993: "Correo (IMAPS)", 995: "Correo (POP3S)", 1433: "SQL Server", 1521: "Oracle",
    1900: "Descubrir aparatos (SSDP)", 3000: "Node / React", 3306: "MySQL / MariaDB",
    3389: "Escritorio remoto", 4200: "Angular", 5000: "Flask", 5173: "Vite", 5353: "Descubrir aparatos (mDNS)",
    5432: "PostgreSQL", 5500: "Live Server (VS Code)", 5900: "VNC", 6379: "Redis",
    8000: "Servidor de Python / Django", 8080: "Web alternativo / Tomcat", 8443: "Web segura alternativo",
    8888: "Jupyter", 9000: "PHP-FPM / SonarQube", 27017: "MongoDB",
}
"""Para qué se suele usar cada puerto: una pista, no una garantía (cualquiera puede usar cualquiera)."""

PROTEGIDOS = {
    "system", "system idle process", "svchost.exe", "lsass.exe", "wininit.exe", "services.exe",
    "csrss.exe", "smss.exe", "winlogon.exe", "spoolsv.exe", "systemd", "init", "launchd",
}
"""Programas del sistema que navaja no cierra nunca: el PC se podría colgar o reiniciar."""

TODAS = ("0.0.0.0", "::", "*", "")
SOLO_ESTE_PC = ("127.0.0.1", "::1", "localhost")


@dataclass
class Escucha:
    """Un programa esperando conexiones en un puerto (con sus IPv4 e IPv6 juntas)."""

    puerto: int
    protocolo: str  # TCP o UDP
    pid: int | None
    direcciones: set[str] = field(default_factory=set)
    programa: str = ""

    @property
    def desde(self) -> str:
        """Desde dónde se puede entrar: «toda la red», «solo este PC» o las IP concretas."""
        if any(d in TODAS for d in self.direcciones):
            return "toda la red"
        if all(d in SOLO_ESTE_PC or d.startswith("127.") for d in self.direcciones):
            return "solo este PC"
        return ", ".join(sorted(self.direcciones))

    @property
    def para_que(self) -> str:
        return CONOCIDOS.get(self.puerto, "")


def escuchas(conexiones: list[Any], udp: bool = False, puerto: int | None = None) -> list[Escucha]:
    """Las que esperan conexiones, de lo que da ``psutil.net_connections``.

    TCP en estado LISTEN; con ``udp``, también las UDP (no tienen estado: están abiertas o
    no). Con ``puerto``, solo ese, y entonces se miran las dos. Ordenadas por puerto.
    """
    juntas: dict[tuple[int, str, int | None], Escucha] = {}
    for conexion in conexiones:
        if not conexion.laddr:
            continue
        protocolo = "UDP" if conexion.type == socket.SOCK_DGRAM else "TCP"
        if protocolo == "TCP" and conexion.status != "LISTEN":
            continue
        if protocolo == "UDP" and not (udp or puerto is not None):
            continue
        numero = conexion.laddr.port if hasattr(conexion.laddr, "port") else conexion.laddr[1]
        if puerto is not None and numero != puerto:
            continue
        ip = conexion.laddr.ip if hasattr(conexion.laddr, "ip") else conexion.laddr[0]
        clave = (numero, protocolo, conexion.pid)
        juntas.setdefault(clave, Escucha(numero, protocolo, conexion.pid)).direcciones.add(ip)
    return sorted(juntas.values(), key=lambda e: (e.puerto, e.protocolo, e.pid or 0))


def comprobar_que_se_puede_cerrar(escucha: Escucha) -> None:
    """``NavajaError`` si no se debe cerrar: sin PID, navaja misma o un programa del sistema."""
    if not escucha.pid:
        raise NavajaError(
            f"No sé qué programa usa el puerto {escucha.puerto} (sin permiso para verlo). "
            "Abre la terminal como administrador y vuelve a probar."
        )
    if escucha.pid == os.getpid():
        raise NavajaError("Ese puerto lo usa navaja misma: no me cierro a mí mismo.")
    if escucha.pid == 4 or escucha.programa.lower() in PROTEGIDOS:
        raise NavajaError(
            f"No cierro {escucha.programa or 'ese programa'} (PID {escucha.pid}): es parte del "
            "sistema y el PC se podría colgar o reiniciar."
        )


def _nombre(psutil: Any, pid: int | None) -> str:
    if not pid:
        return ""
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def recoger(udp: bool, puerto: int | None) -> list[Escucha]:
    psutil = libreria("psutil", "psutil", "sistema", "ver los puertos")
    try:
        conexiones = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        raise NavajaError(
            "El sistema no deja ver las conexiones sin permisos: prueba con sudo (en macOS hace falta)."
        ) from None
    lista = escuchas(conexiones, udp, puerto)
    for escucha in lista:
        escucha.programa = _nombre(psutil, escucha.pid)
    return lista


def tabla_de(lista: list[Escucha]) -> Any:
    tabla = tabla_ligera()
    tabla.add_column("Puerto", justify="right", no_wrap=True)
    tabla.add_column("", no_wrap=True)
    tabla.add_column("Programa")
    tabla.add_column("PID", justify="right", no_wrap=True)
    tabla.add_column("Desde")
    con_pista = any(e.para_que for e in lista)
    if con_pista:
        tabla.add_column("Se suele usar para", style="pista")
    for escucha in lista:
        programa = escape(escucha.programa) if escucha.programa else "[pista](sin permiso)[/]"
        desde = escucha.desde
        estilo = "aviso" if desde == "toda la red" else "pista"
        fila = [
            f"[acento]{escucha.puerto}[/]", escucha.protocolo, programa, str(escucha.pid or "?"),
            f"[{estilo}]{escape(desde)}[/]",
        ]
        tabla.add_row(*fila, *([escape(escucha.para_que)] if con_pista else []))
    return tabla


def cerrar(psutil: Any, escucha: Escucha) -> None:
    """Pide al programa que se cierre; si en 3 segundos sigue, lo obliga."""
    try:
        proceso = psutil.Process(escucha.pid)
        proceso.terminate()
        _, vivos = psutil.wait_procs([proceso], timeout=3)
        for vivo in vivos:
            vivo.kill()
        psutil.wait_procs(vivos, timeout=3)
    except psutil.NoSuchProcess:
        pass  # ya se había cerrado: lo que se quería
    except psutil.AccessDenied:
        raise NavajaError(
            f"No tengo permiso para cerrar {escucha.programa} (PID {escucha.pid}). "
            "Abre la terminal como administrador y vuelve a probar."
        ) from None


def puertos(
    puerto: int | None = typer.Argument(
        None,
        help="Un puerto concreto (8000) para saber quién lo usa; sin nada, todos los abiertos.",
        min=1,
        max=65535,
        show_default=False,
    ),
    udp: bool = typer.Option(False, "--udp", "-u", help="Enseña también los UDP (DNS, DHCP, descubrir aparatos…)."),
    cerrar_programa: bool = typer.Option(
        False, "--cerrar", help="Cierra el programa que usa ese puerto (enseña cuál y pregunta [s/n])."
    ),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Qué puertos están abiertos en tu PC y qué programa usa cada uno."""
    if cerrar_programa and puerto is None:
        error_console.print(
            "[error]✘ Con --cerrar di qué puerto: navaja puertos 8000 --cerrar[/]", soft_wrap=True
        )
        raise typer.Exit(2)
    try:
        lista = recoger(udp, puerto)
    except NavajaError as error:
        fallar(error)

    if puerto is not None and not lista:
        console.print(f"[ok]✔ Nadie está usando el puerto {puerto}: está libre.[/]")
        return
    if not lista:
        console.print("[aviso]No hay ningún puerto esperando conexiones.[/]")
        return

    if puerto is None:
        titulo = f"navaja · puertos · {cuantos(len(lista), 'abierto')}"
    else:
        titulo = f"navaja · puerto {puerto}"
    partes: list[Any] = [tabla_de(lista)]
    if any(e.desde == "toda la red" for e in lista):
        partes.append("[pista]«toda la red»: otros equipos de tu red pueden conectarse (si el cortafuegos les deja).[/]")
    if any(not e.programa for e in lista) and os.name == "nt":
        partes.append("[pista]Algunos programas solo se ven abriendo la terminal como administrador.[/]")
    if puerto is not None and not cerrar_programa:
        partes.append(f"[pista]Para cerrarlo: {escape(como_se_escribe(f'puertos {puerto} --cerrar'))}[/]")
    console.print(recuadro(titulo, *partes))
    if not cerrar_programa:
        return

    psutil = libreria("psutil", "psutil", "sistema", "cerrar programas")
    programas = {e.pid: e for e in lista}  # el mismo programa en TCP y UDP: se cierra una vez
    for escucha in programas.values():
        try:
            comprobar_que_se_puede_cerrar(escucha)
        except NavajaError as error:
            fallar(error)
        quien = f"{escucha.programa or 'el programa'} (PID {escucha.pid})"
        if simular:
            console.print(f"[pista]Simulación: cerraría {escape(quien)}. No se ha tocado nada.[/]")
            continue
        if not confirmar(f"¿Cerrar {escape(quien)}? Lo que no hayas guardado en él se pierde", saltar=si):
            console.print("[aviso]Cancelado.[/]")
            raise typer.Exit(1)
        try:
            cerrar(psutil, escucha)
        except NavajaError as error:
            fallar(error)
        console.print(f"[ok]✔ Cerrado {escape(quien)}: el puerto {puerto} queda libre.[/]")


def registrar(app: typer.Typer) -> None:
    app.command("puertos", help="Qué puertos están abiertos y qué programa usa cada uno.", rich_help_panel=REDES)(puertos)
