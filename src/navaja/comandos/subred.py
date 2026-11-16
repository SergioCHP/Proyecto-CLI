"""navaja subred: calculadora de subredes para clase (Redes e informática).

Todo sale de ``ipaddress``, que viene con Python. La lógica son funciones puras
(``leer_ip``, ``calcular``, ``dividir``, ``vlsm``, ``misma_red``, ``ejercicio``,
``corregir``, ``pasos``) y los comandos de Typer solo las enseñan bonitas.
"""

from __future__ import annotations

import ipaddress
import random
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import NoReturn, Union

import typer
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from ..comun import AJUSTE, REDES, console, cuantos, error_console, recuadro, resumen, tabla_ligera
from ..errores import NavajaError

Interfaz = Union[ipaddress.IPv4Interface, ipaddress.IPv6Interface]
Red = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
Direccion = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

EJEMPLOS = "192.168.10.200/26, 192.168.10.200 255.255.255.192 o solo 10.0.0.5"

# ── Leer lo que escribe el usuario ─────────────────────────────────────────


def prefijo_de_clase(ip: ipaddress.IPv4Address) -> int:
    """La máscara «de clase» de una IPv4 sin máscara: A → /8, B → /16, C → /24."""
    primero = int(ip) >> 24
    if primero < 128:
        return 8
    if primero < 192:
        return 16
    if primero < 224:
        return 24
    raise NavajaError(
        f"{ip} es de clase {clase(ip)} y esas no tienen máscara de clase: "
        f"escríbela tú (como {ip}/24)."
    )


def leer_mascara(texto: str, version: int) -> int:
    """«/26», «26» o «255.255.255.192» → 26. ``NavajaError`` si no es una máscara."""
    limpio = texto.strip().lstrip("/")
    maximo = 32 if version == 4 else 128
    if limpio.isdigit():
        prefijo = int(limpio)
        if prefijo > maximo:
            raise NavajaError(f"La máscara /{prefijo} no existe: va de /0 a /{maximo}.")
        return prefijo
    if version == 4:
        try:
            return ipaddress.IPv4Network(f"0.0.0.0/{limpio}").prefixlen
        except ValueError:
            pass
    raise NavajaError(
        f"«{texto}» no es una máscara. Escríbela como /26 o como 255.255.255.192 "
        "(los unos seguidos y luego los ceros)."
    )


def leer_ip(texto: str, mascara: str = "") -> Interfaz:
    """Lo que escribe el usuario → la IP con su máscara.

    Vale «192.168.10.200/26», «192.168.10.200/255.255.255.192», la máscara aparte
    (``mascara``) o solo la IP: una IPv4 lleva la máscara de su clase y una IPv6, /64.
    """
    partes = texto.strip().split()
    if len(partes) == 2 and not mascara:  # «192.168.1.5 255.255.255.0» entre comillas
        partes, mascara = [partes[0]], partes[1]
    if len(partes) != 1:
        raise NavajaError(f"«{texto}» no es una IP. Ejemplos: {EJEMPLOS}.")
    ip_texto, _, en_la_ip = partes[0].partition("/")
    try:
        ip = ipaddress.ip_address(ip_texto)
    except ValueError:
        raise NavajaError(f"«{ip_texto}» no es una IP. Ejemplos: {EJEMPLOS}.") from None
    if en_la_ip and mascara.strip():
        raise NavajaError("Escribe la máscara solo una vez: en la IP (/26) o aparte.")
    escrita = en_la_ip or mascara.strip()
    if escrita:
        prefijo = leer_mascara(escrita, ip.version)
    elif isinstance(ip, ipaddress.IPv4Address):
        prefijo = prefijo_de_clase(ip)
    else:
        prefijo = 64
    return ipaddress.ip_interface(f"{ip}/{prefijo}")


def leer_red(texto: str) -> tuple[Red, bool]:
    """La red de lo que se escribe y si se ha tenido que corregir (se escribió un equipo
    de la red, como 192.168.1.77/24, en vez de la red, 192.168.1.0/24)."""
    interfaz = leer_ip(texto)
    return interfaz.network, interfaz.ip != interfaz.network.network_address


# ── Qué es una IP ──────────────────────────────────────────────────────────


def clase(ip: Direccion) -> str:
    """A, B, C, D (multicast) o E (reservada). Las IPv6 no tienen clase: «—»."""
    if not isinstance(ip, ipaddress.IPv4Address):
        return "—"
    primero = int(ip) >> 24
    for limite, letra in ((128, "A"), (192, "B"), (224, "C"), (240, "D")):
        if primero < limite:
            return letra
    return "E"


TIPOS_V4 = [
    ("0.0.0.0/8", "«esta red»: no se le da a ningún equipo"),
    ("127.0.0.0/8", "loopback: es el propio equipo (localhost)"),
    ("169.254.0.0/16", "APIPA: el equipo no encontró DHCP y se la puso él solo"),
    ("10.0.0.0/8", "privada"),
    ("172.16.0.0/12", "privada"),
    ("192.168.0.0/16", "privada"),
    ("100.64.0.0/10", "compartida (CGNAT): la usan las operadoras por dentro"),
    ("192.0.2.0/24", "de ejemplo (para documentación)"),
    ("198.51.100.0/24", "de ejemplo (para documentación)"),
    ("203.0.113.0/24", "de ejemplo (para documentación)"),
    ("255.255.255.255/32", "difusión limitada: a todos los de tu red"),
    ("224.0.0.0/4", "multicast: un mensaje a un grupo de equipos"),
    ("240.0.0.0/4", "reservada (clase E): no se usa"),
]
TIPOS_V6 = [
    ("::1/128", "loopback: es el propio equipo (localhost)"),
    ("::/128", "sin especificar: el equipo aún no tiene IP"),
    ("fe80::/10", "de enlace local: solo vale en tu red, como APIPA"),
    ("fc00::/7", "privada (ULA)"),
    ("ff00::/8", "multicast: un mensaje a un grupo de equipos"),
    ("2001:db8::/32", "de ejemplo (para documentación)"),
    ("2000::/3", "pública (unicast global)"),
]


def tipo(ip: Direccion) -> str:
    """Privada, pública, loopback, APIPA… en castellano y explicado."""
    tabla = TIPOS_V4 if isinstance(ip, ipaddress.IPv4Address) else TIPOS_V6
    for red, nombre in tabla:
        if ip in ipaddress.ip_network(red):
            return nombre
    return "pública" if ip.version == 4 else "reservada"


def con_puntos(numero: int) -> str:
    """16777214 → «16.777.214», como se escribe en castellano."""
    return f"{numero:,}".replace(",", ".")


# ── Calcular la subred ─────────────────────────────────────────────────────


@dataclass
class Datos:
    """Todo lo que se sabe de una IP con su máscara."""

    interfaz: Interfaz
    red: Red
    mascara: Direccion
    wildcard: Direccion
    prefijo: int
    broadcast: Direccion | None
    primero: Direccion
    ultimo: Direccion
    hosts: int
    clase: str
    tipo: str
    avisos: list[str] = field(default_factory=list)

    @property
    def version(self) -> int:
        return self.red.version


def calcular(interfaz: Interfaz) -> Datos:
    """Red, broadcast, primer y último equipo, hosts útiles, máscara, wildcard…

    En IPv4 se quitan la red y el broadcast: hosts = 2^(bits de host) − 2. Con /31 (enlace
    entre dos routers) no se quita nada y con /32 hay un solo equipo. IPv6 no tiene
    broadcast: cuentan todas.
    """
    red = interfaz.network
    ip = interfaz.ip
    total = red.num_addresses
    avisos: list[str] = []
    if red.version == 4 and red.prefixlen <= 30:
        broadcast: Direccion | None = red.broadcast_address
        primero, ultimo, hosts = red.network_address + 1, red.broadcast_address - 1, total - 2
        if ip == red.network_address:
            avisos.append(f"{ip} es la dirección de la red: no se le puede dar a un equipo.")
        elif ip == red.broadcast_address:
            avisos.append(f"{ip} es el broadcast de la red: no se le puede dar a un equipo.")
    else:
        broadcast = None
        primero, ultimo, hosts = red.network_address, red[-1], total
        if red.version == 4 and red.prefixlen == 31:
            avisos.append("/31: enlace entre dos equipos (RFC 3021), sin red ni broadcast.")
    return Datos(
        interfaz=interfaz,
        red=red,
        mascara=red.netmask,
        wildcard=red.hostmask,
        prefijo=red.prefixlen,
        broadcast=broadcast,
        primero=primero,
        ultimo=ultimo,
        hosts=hosts,
        clase=clase(ip),
        tipo=tipo(ip),
        avisos=avisos,
    )


def bits(direccion: ipaddress.IPv4Address, prefijo: int) -> Text:
    """La IP en binario por octetos: los bits de red en un color y los de host en otro."""
    texto = Text()
    cadena = format(int(direccion), "032b")
    for posicion, bit in enumerate(cadena):
        if posicion and posicion % 8 == 0:
            texto.append(".", style="pista")
        texto.append(bit, style="acento" if posicion < prefijo else "logro")
    return texto


def tabla_binaria(datos: Datos) -> Table:
    """IP, máscara, red y broadcast en decimal y en binario, uno debajo de otro."""
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="pista", no_wrap=True)
    tabla.add_column(no_wrap=True)
    tabla.add_column(no_wrap=True)
    filas = [("IP", datos.interfaz.ip), ("Máscara", datos.mascara), ("Red", datos.red.network_address)]
    if datos.broadcast is not None:
        filas.append(("Broadcast", datos.broadcast))
    for etiqueta, direccion in filas:
        assert isinstance(direccion, ipaddress.IPv4Address)
        tabla.add_row(etiqueta, str(direccion), bits(direccion, datos.prefijo))
    return tabla


# ── Dividir y VLSM ─────────────────────────────────────────────────────────


MAXIMO_PARTES = 1024
"""Más subredes que esto no caben en una tabla que se pueda leer."""


def limite_prefijo(red: Red) -> int:
    """El prefijo más largo que aún deja equipos: /30 en IPv4 (2 hosts) y /127 en IPv6."""
    return 30 if red.version == 4 else 127


def dividir(red: Red, partes: int) -> list[Red]:
    """La red en ``partes`` subredes iguales (FLSM). Si ``partes`` no es potencia de 2,
    salen las de la siguiente (pides 3 y salen 4): cada bit prestado duplica las subredes."""
    if partes < 2:
        raise NavajaError("Para dividir hacen falta al menos 2 partes.")
    if partes > MAXIMO_PARTES:
        raise NavajaError(f"Como mucho {MAXIMO_PARTES} partes: más no se pueden leer en una tabla.")
    prestados = (partes - 1).bit_length()
    nuevo = red.prefixlen + prestados
    if nuevo > limite_prefijo(red):
        raise NavajaError(
            f"{red} no se puede partir en {partes}: harían falta {prestados} bits más (/{nuevo}) "
            f"y cada subred se quedaría sin equipos (como mucho /{limite_prefijo(red)})."
        )
    return list(red.subnets(new_prefix=nuevo))


@dataclass
class Peticion:
    """Una subred que se pide en VLSM: su nombre y cuántos equipos necesita."""

    nombre: str
    hosts: int


PETICION = re.compile(r"^(?:(?P<nombre>[^:=]+)[:=])?(?P<hosts>\d+)$")


def leer_peticiones(textos: list[str]) -> list[Peticion]:
    """«50 20 10» o «ventas:50 aula=20». Sin nombre, se llaman A, B, C… en ese orden."""
    if not textos:
        raise NavajaError("Di cuántos equipos necesita cada subred: navaja subred vlsm 192.168.1.0/24 50 20 10.")
    peticiones = []
    for posicion, texto in enumerate(textos):
        encaje = PETICION.match(texto.strip())
        if not encaje:
            raise NavajaError(f"«{texto}» no es un número de equipos (vale 50 o ventas:50).")
        hosts = int(encaje["hosts"])
        if hosts < 1:
            raise NavajaError("Cada subred necesita al menos 1 equipo.")
        nombre = (encaje["nombre"] or "").strip() or nombre_por_posicion(posicion)
        peticiones.append(Peticion(nombre, hosts))
    return peticiones


def nombre_por_posicion(posicion: int) -> str:
    """0 → A, 25 → Z, 26 → AA…"""
    letras = ""
    posicion += 1
    while posicion:
        posicion, resto = divmod(posicion - 1, 26)
        letras = chr(ord("A") + resto) + letras
    return letras


def bloque_para(hosts: int) -> int:
    """Las direcciones que ocupa una subred con ``hosts`` equipos: la potencia de 2 que
    cabe con la red y el broadcast (50 → 64, 2 → 4)."""
    return 1 << (hosts + 1).bit_length()


@dataclass
class Reparto:
    """Una subred del VLSM ya colocada."""

    peticion: Peticion
    red: ipaddress.IPv4Network

    @property
    def sobran(self) -> int:
        return self.red.num_addresses - 2 - self.peticion.hosts


def vlsm(red: Red, peticiones: list[Peticion]) -> tuple[list[Reparto], list[ipaddress.IPv4Network]]:
    """Reparte la red por equipos necesarios, de la que más pide a la que menos (VLSM).

    Al ir de mayor a menor y ser todo potencias de 2, cada subred empieza justo donde
    acaba la anterior y siempre queda bien alineada. Devuelve el reparto y lo que queda
    libre. ``NavajaError`` si no cabe, diciendo cuánto falta.
    """
    if not isinstance(red, ipaddress.IPv4Network):
        raise NavajaError("VLSM solo con IPv4 (en IPv6 cada subred es un /64 y sobra sitio).")
    ordenadas = sorted(peticiones, key=lambda p: p.hosts, reverse=True)  # estable: empate, en orden
    necesarias = sum(bloque_para(p.hosts) for p in ordenadas)
    if necesarias > red.num_addresses:
        raise NavajaError(
            f"No cabe: hacen falta {con_puntos(necesarias)} direcciones y {red} tiene "
            f"{con_puntos(red.num_addresses)}. Usa una red más grande (con menos bits de "
            "máscara) o pide menos equipos."
        )
    repartos: list[Reparto] = []
    siguiente = int(red.network_address)
    for peticion in ordenadas:
        bloque = bloque_para(peticion.hosts)
        prefijo = 32 - (bloque.bit_length() - 1)
        repartos.append(Reparto(peticion, ipaddress.IPv4Network((siguiente, prefijo))))
        siguiente += bloque
    libre: list[ipaddress.IPv4Network] = []
    if siguiente <= int(red.broadcast_address):
        libre = list(
            ipaddress.summarize_address_range(ipaddress.IPv4Address(siguiente), red.broadcast_address)
        )
    return repartos, libre


# ── ¿Están en la misma red? ────────────────────────────────────────────────


@dataclass
class Comparacion:
    a: Interfaz
    b: Interfaz

    @property
    def a_ve_a_b(self) -> bool:
        return self.b.ip in self.a.network

    @property
    def b_ve_a_a(self) -> bool:
        return self.a.ip in self.b.network

    @property
    def misma(self) -> bool:
        return self.a_ve_a_b and self.b_ve_a_a


def misma_red(primera: str, segunda: str) -> Comparacion:
    """Si la segunda no lleva máscara, se usa la de la primera (lo normal en un ejercicio)."""
    a = leer_ip(primera)
    if "/" in segunda or len(segunda.split()) == 2:
        b = leer_ip(segunda)
    else:
        b = leer_ip(segunda, str(a.network.prefixlen))
    if a.version != b.version:
        raise NavajaError("Una es IPv4 y la otra IPv6: nunca están en la misma red.")
    return Comparacion(a, b)


# ── Modo práctica ──────────────────────────────────────────────────────────


class Nivel(str, Enum):
    facil = "facil"
    medio = "medio"
    dificil = "dificil"


PREFIJOS = {Nivel.facil: (25, 30), Nivel.medio: (17, 30), Nivel.dificil: (9, 30)}
"""Las máscaras de cada nivel: en fácil solo cambia el último octeto."""

PRIVADAS = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
]


def ejercicio(rng: random.Random, nivel: Nivel = Nivel.medio) -> ipaddress.IPv4Interface:
    """Una IP privada al azar que no es ni la red ni el broadcast, con una máscara del nivel."""
    menor, mayor = PREFIJOS[nivel]
    while True:
        prefijo = rng.randint(menor, mayor)
        base = rng.choice([r for r in PRIVADAS if r.prefixlen <= prefijo])
        ip = ipaddress.IPv4Address(int(base.network_address) + rng.randrange(base.num_addresses))
        interfaz = ipaddress.IPv4Interface((ip, prefijo))
        if ip not in (interfaz.network.network_address, interfaz.network.broadcast_address):
            return interfaz


PREGUNTAS = [
    ("mascara", "Máscara (como 255.255.255.0)"),
    ("red", "Dirección de red"),
    ("broadcast", "Broadcast"),
    ("hosts", "Hosts útiles"),
]


@dataclass
class Correccion:
    pregunta: str
    tuya: str
    buena: str
    bien: bool


def corregir(interfaz: ipaddress.IPv4Interface, respuestas: dict[str, str]) -> list[Correccion]:
    """Compara cada respuesta con la buena. Las IP valen con espacios y los hosts con
    puntos de miles (2.046)."""
    datos = calcular(interfaz)
    buenas = {
        "mascara": str(datos.mascara),
        "red": str(datos.red.network_address),
        "broadcast": str(datos.broadcast),
        "hosts": str(datos.hosts),
    }
    resultado = []
    for clave, pregunta in PREGUNTAS:
        tuya = respuestas.get(clave, "").strip()
        if clave == "hosts":
            bien = tuya.replace(".", "").replace(" ", "") == buenas[clave]
            buena = con_puntos(datos.hosts)
        else:
            try:
                bien = ipaddress.IPv4Address(tuya.replace(" ", "")) == ipaddress.IPv4Address(buenas[clave])
            except ValueError:
                bien = False
            buena = buenas[clave]
        resultado.append(Correccion(pregunta, tuya or "—", buena, bien))
    return resultado


def pasos(interfaz: ipaddress.IPv4Interface) -> list[str]:
    """Cómo se resuelve a mano, con el «número mágico» (256 − el octeto de la máscara)."""
    datos = calcular(interfaz)
    n = datos.prefijo
    octetos_ip = [int(o) for o in str(interfaz.ip).split(".")]
    octetos_mascara = [int(o) for o in str(datos.mascara).split(".")]
    lineas = [f"/{n} son {n} unos seguidos de {32 - n} ceros: la máscara es {datos.mascara}."]
    if n < 32:
        indice = n // 8
        mascara = octetos_mascara[indice]
        salto = 256 - mascara
        valor = octetos_ip[indice]
        inicio = valor // salto * salto
        ordinal = f"{indice + 1}.º"
        lineas += [
            f"El octeto que manda es el {ordinal} (el primero que no es 255): vale {mascara}. "
            f"El salto es 256 − {mascara} = {salto}.",
            f"Las redes van de {salto} en {salto} en ese octeto. {valor} cae entre {inicio} y "
            f"{inicio + salto - 1}: la red es {datos.red.network_address}.",
            f"El broadcast es la última de ese tramo (la siguiente red menos 1): {datos.broadcast}.",
        ]
    lineas.append(
        f"Hosts útiles: 2^{32 - n} − 2 = {con_puntos(2 ** (32 - n))} − 2 = {con_puntos(datos.hosts)} "
        "(se quitan la red y el broadcast)."
    )
    return lineas


# ── Comandos ───────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def ver(
    ip: list[str] = typer.Argument(
        ..., help="La IP y su máscara (192.168.10.200/26 o 192.168.10.200 255.255.255.192)."
    ),
) -> None:
    """Todo sobre una IP: red, broadcast, equipos, máscara, clase y en binario."""
    try:
        datos = calcular(leer_ip(" ".join(ip)))
    except NavajaError as error:
        fallar(error)
    filas = [
        ("Red", f"[acento]{datos.red}[/]"),
        ("Máscara", f"{datos.mascara} [pista](/{datos.prefijo})[/]"),
    ]
    if datos.version == 4:
        filas.append(("Wildcard", str(datos.wildcard)))
    if datos.broadcast is not None:
        filas.append(("Broadcast", str(datos.broadcast)))
    filas += [
        ("Equipos", f"{datos.primero} – {datos.ultimo}"),
        ("Hosts útiles", f"[logro]{con_puntos(datos.hosts)}[/]"),
        ("Tipo", escape(datos.tipo)),
    ]
    if datos.version == 4:
        filas.append(("Clase", datos.clase))
    filas.append(("Versión", f"IPv{datos.version}"))
    partes: list = [resumen(filas)]
    if datos.version == 4:
        partes.append(tabla_binaria(datos))
        partes.append(Text.from_markup("[acento]■[/] [pista]bits de red[/]   [logro]■[/] [pista]bits de host[/]"))
    for aviso in datos.avisos:
        partes.append(Text.from_markup(f"[aviso]{escape(aviso)}[/]"))
    console.print(recuadro(f"Subred de {datos.interfaz.ip}/{datos.prefijo}", *partes))


def dividir_orden(
    red: str = typer.Argument(..., help="La red que quieres partir (192.168.1.0/24)."),
    partes: int = typer.Argument(..., help="En cuántas subredes iguales.", min=2),
) -> None:
    """Parte una red en subredes iguales (FLSM)."""
    try:
        base, corregida = leer_red(red)
        subredes = dividir(base, partes)
    except NavajaError as error:
        fallar(error)
    tabla = tabla_ligera()
    for columna in ("Nº", "Red", "Primer equipo", "Último equipo", "Broadcast"):
        tabla.add_column(columna, no_wrap=True)
    for numero, subred in enumerate(subredes, start=1):
        datos = calcular(ipaddress.ip_interface(f"{subred.network_address}/{subred.prefixlen}"))
        tabla.add_row(
            str(numero), f"[acento]{subred}[/]", str(datos.primero), str(datos.ultimo),
            str(datos.broadcast or "—"),
        )
    datos = calcular(ipaddress.ip_interface(f"{subredes[0].network_address}/{subredes[0].prefixlen}"))
    prestados = subredes[0].prefixlen - base.prefixlen
    filas = [
        ("Red", str(base)),
        ("Bits prestados", f"{prestados} [pista](2^{prestados} = {len(subredes)} subredes)[/]"),
        ("Cada una", f"/{datos.prefijo} · {datos.mascara} · [logro]{con_puntos(datos.hosts)}[/] hosts"),
    ]
    partes_ = [resumen(filas), tabla]
    if corregida:
        partes_.append(Text.from_markup(f"[aviso]Has escrito un equipo de la red: se usa {base}.[/]"))
    if len(subredes) != partes:
        sobran = len(subredes) - partes
        partes_.append(
            Text.from_markup(
                f"[aviso]Pediste {partes}: salen {len(subredes)}, porque cada bit prestado "
                f"duplica las subredes. Te {'sobra' if sobran == 1 else 'sobran'} "
                f"{cuantos(sobran, 'subred', 'subredes')}.[/]"
            )
        )
    console.print(recuadro(f"{base} en {cuantos(len(subredes), 'subred', 'subredes')}", *partes_))


def vlsm_orden(
    red: str = typer.Argument(..., help="La red que quieres repartir (192.168.1.0/24)."),
    hosts: list[str] = typer.Argument(
        ..., help="Equipos de cada subred, separados por espacios (50 20 10 o ventas:50)."
    ),
) -> None:
    """Reparte una red por los equipos que necesita cada subred (VLSM)."""
    try:
        base, corregida = leer_red(red)
        repartos, libre = vlsm(base, leer_peticiones(hosts))
    except NavajaError as error:
        fallar(error)
    tabla = tabla_ligera()
    for columna in ("Subred", "Pide", "Red", "Primer equipo", "Último equipo", "Broadcast", "Sobran"):
        tabla.add_column(columna, no_wrap=True)
    for reparto in repartos:
        subred = reparto.red
        tabla.add_row(
            escape(reparto.peticion.nombre),
            con_puntos(reparto.peticion.hosts),
            f"[acento]{subred}[/]",
            str(subred.network_address + 1),
            str(subred.broadcast_address - 1),
            str(subred.broadcast_address),
            f"[pista]{con_puntos(reparto.sobran)}[/]",
        )
    usadas = sum(r.red.num_addresses for r in repartos)
    filas = [
        ("Red", str(base)),
        ("Usadas", f"{con_puntos(usadas)} de {con_puntos(base.num_addresses)} direcciones"),
    ]
    if libre:
        filas.append(("Queda libre", ", ".join(str(r) for r in libre)))
    partes_ = [resumen(filas), tabla]
    if corregida:
        partes_.append(Text.from_markup(f"[aviso]Has escrito un equipo de la red: se usa {base}.[/]"))
    partes_.append(
        Text.from_markup(
            "[pista]De la que más pide a la que menos; cada una ocupa la potencia de 2 que le "
            "cabe con la red y el broadcast (50 equipos → 64 direcciones, /26).[/]"
        )
    )
    console.print(recuadro(f"VLSM de {base}", *partes_))


def misma(
    primera: str = typer.Argument(..., help="La primera IP, con su máscara (192.168.1.10/24)."),
    segunda: str = typer.Argument(..., help="La segunda IP (sin máscara, usa la de la primera)."),
) -> None:
    """Dice si dos IP están en la misma red (y se hablan sin router)."""
    try:
        comparacion = misma_red(primera, segunda)
    except NavajaError as error:
        fallar(error)
    a, b = comparacion.a, comparacion.b
    filas = [
        (str(a.ip), f"red [acento]{a.network}[/]"),
        (str(b.ip), f"red [acento]{b.network}[/]"),
    ]
    if comparacion.misma:
        veredicto = "[ok]✔ Sí, están en la misma red: se hablan directamente, sin router.[/]"
    elif a.network.prefixlen == b.network.prefixlen or not (comparacion.a_ve_a_b or comparacion.b_ve_a_a):
        veredicto = "[error]✘ No, están en redes distintas: para hablarse necesitan un router.[/]"
    else:
        quien, otro = (a.ip, b.ip) if comparacion.a_ve_a_b else (b.ip, a.ip)
        veredicto = (
            f"[aviso]Solo a medias: {quien} cree que {otro} está en su red, pero al revés no, "
            "porque tienen máscaras distintas. Es un error de configuración típico.[/]"
        )
    console.print(recuadro("¿Misma red?", resumen(filas), Text.from_markup(veredicto)))


def practica(
    ejercicios: int = typer.Option(5, "--ejercicios", "-n", min=1, help="Cuántos ejercicios.", rich_help_panel=AJUSTE),
    nivel: Nivel = typer.Option(
        Nivel.medio, "--nivel", help="facil (solo el último octeto), medio o dificil.", rich_help_panel=AJUSTE
    ),
) -> None:
    """Ejercicios de subredes al azar: los corrige y explica los fallos paso a paso."""
    rng = random.Random()
    perfectos = hechos = 0
    console.print("[pista]Escribe salir para terminar.[/]")
    try:
        for numero in range(1, ejercicios + 1):
            interfaz = ejercicio(rng, nivel)
            console.print(f"\n[titulo]Ejercicio {numero} de {ejercicios}:[/] [acento]{interfaz}[/]")
            respuestas = {}
            for clave, pregunta in PREGUNTAS:
                respuesta = console.input(f"  {pregunta}: ")
                if respuesta.strip().lower() in ("salir", "exit"):
                    raise KeyboardInterrupt
                respuestas[clave] = respuesta
            correccion = corregir(interfaz, respuestas)
            hechos += 1
            mostrar_correccion(correccion)
            if all(c.bien for c in correccion):
                perfectos += 1
                console.print("  [logro]¡Perfecto![/]")
            else:
                console.print("  [titulo]Cómo se hace:[/]")
                for linea in pasos(interfaz):
                    console.print(f"  [pista]·[/] {escape(linea)}", soft_wrap=True)
    except (KeyboardInterrupt, EOFError):
        console.print()
    if hechos:
        console.print(
            f"\n[titulo]Resultado:[/] {perfectos} de {cuantos(hechos, 'ejercicio')} sin fallos."
        )


def mostrar_correccion(correccion: list[Correccion]) -> None:
    tabla = tabla_ligera()
    for columna in ("", "Pregunta", "Tu respuesta", "La buena"):
        tabla.add_column(columna, no_wrap=True)
    for fila in correccion:
        marca = "[ok]✔[/]" if fila.bien else "[error]✘[/]"
        buena = "" if fila.bien else f"[acento]{escape(fila.buena)}[/]"
        tabla.add_row(marca, escape(fila.pregunta), escape(fila.tuya), buena)
    console.print(tabla)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Calculadora de subredes: le das una IP y te lo dice todo.",
        no_args_is_help=True,
    )
    sub.command("ver", help="Todo sobre una IP: red, broadcast, equipos, máscara y en binario.")(ver)
    sub.command("dividir", help="Parte una red en subredes iguales (FLSM).")(dividir_orden)
    sub.command("vlsm", help="Reparte una red según los equipos de cada subred (VLSM).")(vlsm_orden)
    sub.command("misma", help="¿Están dos IP en la misma red?")(misma)
    sub.command("practica", help="Ejercicios al azar: los corrige y explica los fallos.")(practica)
    app.add_typer(sub, name="subred", rich_help_panel=REDES)
