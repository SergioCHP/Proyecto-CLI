"""navaja base: un número en binario, octal, decimal y hexadecimal, con los pasos.

Los pasos son los de clase: divisiones sucesivas para pasar de decimal a otra base
(los restos leídos de abajo arriba) y la suma de potencias para volver a decimal.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import NoReturn

import typer
from rich.console import Group
from rich.markup import escape
from rich.text import Text

from ..comun import REDES, console, error_console, recuadro, resumen, tabla_ligera
from ..errores import NavajaError

CIFRAS = "0123456789ABCDEF"
NOMBRES = {2: "Binario", 8: "Octal", 10: "Decimal", 16: "Hexadecimal"}
PREFIJOS = {"0b": 2, "0o": 8, "0x": 16}
MAXIMO_PASOS = 64
"""Con más divisiones que esto, los pasos ya no se leen: solo sale el resultado."""


@dataclass
class Numero:
    valor: int
    base: int
    nota: str = ""


def leer_numero(texto: str, base: int | None = None) -> Numero:
    """«200», «0b1010», «0o17», «0xC8», «C8h» o «C8» (con letras, hexadecimal).

    Con ``base`` se lee en esa base. ``NavajaError`` si no es un número o es negativo.
    """
    limpio = texto.strip().replace(" ", "").replace("_", "")
    if limpio.startswith("-"):
        raise NavajaError("Solo números enteros positivos (sin signo).")
    if not limpio:
        raise NavajaError("Falta el número.")
    nota = ""
    if base is None:
        prefijo = limpio[:2].lower()
        if prefijo in PREFIJOS:
            base, limpio = PREFIJOS[prefijo], limpio[2:]
        elif limpio[-1] in "hH" and len(limpio) > 1 and es_de_base(limpio[:-1], 16):
            base, limpio = 16, limpio[:-1]
        elif limpio.isdigit():
            base = 10
        elif es_de_base(limpio, 16):
            base, nota = 16, "Como lleva letras, se lee como hexadecimal."
        else:
            raise NavajaError(
                f"«{texto}» no es un número. Ejemplos: 200, 0b11001000, 0o310, 0xC8 o C8h."
            )
    if not limpio or not es_de_base(limpio, base):
        validas = CIFRAS[:base]
        raise NavajaError(
            f"«{texto}» no es un número en base {base}: solo valen las cifras "
            f"{', '.join(validas[:-1])} y {validas[-1]}."
        )
    return Numero(int(limpio, base), base, nota)


def es_de_base(texto: str, base: int) -> bool:
    return bool(texto) and all(c.upper() in CIFRAS[:base] for c in texto)


def en_base(numero: int, base: int) -> str:
    """El número escrito en ``base`` (2, 8, 10 o 16), con las letras en mayúscula."""
    if numero == 0:
        return "0"
    cifras = []
    while numero:
        numero, resto = divmod(numero, base)
        cifras.append(CIFRAS[resto])
    return "".join(reversed(cifras))


def agrupado(texto: str, cada: int = 4, rellenar: bool = False) -> str:
    """«11001000» → «1100 1000»: de derecha a izquierda, como se lee en clase. Con
    ``rellenar``, ceros delante hasta completar el primer grupo («10100» → «0001 0100»)."""
    if rellenar:
        texto = "0" * (-len(texto) % cada) + texto
    trozos = [texto[max(0, i - cada) : i] for i in range(len(texto), 0, -cada)]
    return " ".join(reversed(trozos))


def divisiones(numero: int, base: int) -> list[tuple[int, int, int]]:
    """Divisiones sucesivas: (dividendo, cociente, resto) hasta que el cociente es 0."""
    pasos = []
    while True:
        cociente, resto = divmod(numero, base)
        pasos.append((numero, cociente, resto))
        if cociente == 0:
            return pasos
        numero = cociente


def potencias(cifras: str, base: int) -> list[tuple[str, int, int]]:
    """Cada cifra con su potencia y lo que vale: «C8» → (C, 1, 192), (8, 0, 8)."""
    largo = len(cifras)
    return [
        (cifra.upper(), largo - 1 - posicion, CIFRAS.index(cifra.upper()) * base ** (largo - 1 - posicion))
        for posicion, cifra in enumerate(cifras)
    ]


def ip_en_binario(texto: str) -> list[tuple[int, str]] | None:
    """Una IPv4 → cada octeto con sus 8 bits; None si no es una IPv4."""
    try:
        ip = ipaddress.IPv4Address(texto.strip())
    except ValueError:
        return None
    return [(int(octeto), format(int(octeto), "08b")) for octeto in str(ip).split(".")]


# ── Orden ──────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def base(
    numero: str = typer.Argument(..., help="El número (200, 0b1010, 0o17, 0xC8 o C8h) o una IP."),
    de: int = typer.Option(
        0, "--de", help="En qué base está el número: 2, 8, 10 o 16 (0 = lo adivina).",
        show_default=False,
    ),
    a: int = typer.Option(
        0, "--a", help="A qué base enseñar los pasos: 2, 8, 10 o 16 (0 = la típica).",
        show_default=False,
    ),
) -> None:
    """Pasa un número entre binario, octal, decimal y hexadecimal, con los pasos."""
    for valor, opcion in ((de, "--de"), (a, "--a")):
        if valor not in (0, 2, 8, 10, 16):
            raise typer.BadParameter("tiene que ser 2, 8, 10 o 16.", param_hint=opcion)
    octetos = ip_en_binario(numero) if not de else None
    if octetos:
        mostrar_ip(numero.strip(), octetos)
        return
    try:
        leido = leer_numero(numero, de or None)
    except NavajaError as error:
        fallar(error)
    destino = a or (2 if leido.base == 10 else 10)
    filas = []
    for b, nombre in NOMBRES.items():
        texto = en_base(leido.valor, b)
        if b == 2:
            texto = agrupado(texto, 4)
        marca = f"[acento]{escape(texto)}[/]" if b == leido.base else escape(texto)
        filas.append((nombre, marca + (" [pista]← el tuyo[/]" if b == leido.base else "")))
    partes: list = [resumen(filas)]
    if leido.nota:
        partes.append(Text.from_markup(f"[pista]{escape(leido.nota)}[/]"))
    if destino != leido.base:
        partes.append(explicar(leido, destino))
    console.print(recuadro(f"{en_base(leido.valor, leido.base)} en base {leido.base}", *partes))


def explicar(leido: Numero, destino: int) -> Group | Text:
    """Los pasos para pasar el número de su base a ``destino``."""
    if leido.base != 10 and destino != 10:
        if {leido.base, destino} in ({2, 16}, {2, 8}):
            bits = 4 if 16 in (leido.base, destino) else 3
            binario = agrupado(en_base(leido.valor, 2), bits, rellenar=True)
            grupos = binario.split()
            traduccion = ", ".join(f"{g} → {CIFRAS[int(g, 2)]}" for g in grupos)
            return Text.from_markup(
                f"[titulo]Atajo:[/] cada {bits} bits son una cifra en base {2 ** bits}: "
                f"{escape(traduccion)}."
            )
        return Text.from_markup(
            f"[pista]Para pasar de base {leido.base} a base {destino}, se pasa primero a decimal "
            f"({leido.valor}) y luego de decimal a base {destino}.[/]"
        )
    if leido.base == 10:
        pasos = divisiones(leido.valor, destino)
        if len(pasos) > MAXIMO_PASOS:
            return Text.from_markup("[pista]Demasiadas divisiones para enseñarlas una a una.[/]")
        tabla = tabla_ligera()
        for columna in ("División", "Cociente", "Resto"):
            tabla.add_column(columna, no_wrap=True, justify="right")
        for dividendo, cociente, resto in pasos:
            tabla.add_row(f"{dividendo} ÷ {destino}", str(cociente), f"[acento]{CIFRAS[resto]}[/]")
        lectura = Text.from_markup(
            f"[pista]Los restos, de abajo arriba:[/] [acento]{en_base(leido.valor, destino)}[/]"
        )
        return Group(tabla, lectura)
    cifras = en_base(leido.valor, leido.base)
    if len(cifras) > MAXIMO_PASOS:
        return Text.from_markup("[pista]Demasiadas cifras para enseñar la suma.[/]")
    terminos = potencias(cifras, leido.base)
    suma = " + ".join(
        f"{CIFRAS.index(c) if c in CIFRAS else c}·{leido.base}^{p}" for c, p, _ in terminos
    )
    valores = " + ".join(str(v) for _, _, v in terminos)
    return Text.from_markup(
        f"[titulo]Paso a decimal:[/] cada cifra por su potencia de {leido.base}.\n"
        f"{escape(suma)}\n= {escape(valores)} = [acento]{leido.valor}[/]"
    )


def mostrar_ip(texto: str, octetos: list[tuple[int, str]]) -> None:
    tabla = tabla_ligera()
    for numero in range(1, 5):
        tabla.add_column(f"{numero}.º octeto", justify="right", no_wrap=True)
    tabla.add_row(*(str(decimal) for decimal, _ in octetos))
    tabla.add_row(*(f"[acento]{bits}[/]" for _, bits in octetos))
    junta = ".".join(bits for _, bits in octetos)
    console.print(
        recuadro(
            f"{texto} en binario",
            tabla,
            Text.from_markup(f"[pista]Entera:[/] {junta}"),
            Text.from_markup("[pista]Cada octeto es un número de 0 a 255 en 8 bits. Para "
                             "la red y el broadcast: navaja subred ver.[/]"),
        )
    )


def registrar(app: typer.Typer) -> None:
    app.command(
        "base", help="Pasa números entre binario, octal, decimal y hexadecimal.", rich_help_panel=REDES
    )(base)
