"""navaja genera: UUID, texto de relleno (lorem ipsum) y números al azar."""

from __future__ import annotations

import random
import uuid
from typing import NoReturn

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, PROGRAMACION, console, error_console
from ..errores import NavajaError

LOREM = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt "
    "ut labore et dolore magna aliqua enim ad minim veniam quis nostrud exercitation ullamco "
    "laboris nisi aliquip ex ea commodo consequat duis aute irure in reprehenderit voluptate "
    "velit esse cillum fugiat nulla pariatur excepteur sint occaecat cupidatat non proident "
    "sunt culpa qui officia deserunt mollit anim id est laborum"
).split()
"""Las palabras del lorem ipsum de siempre (un texto latino de dominio público)."""

MAXIMO = 10_000
"""Lo más que se genera de una vez (UUID, números, palabras…)."""


def uuids(cuantos: int) -> list[str]:
    """UUID versión 4: al azar, sin repetirse en la práctica nunca."""
    return [str(uuid.uuid4()) for _ in range(cuantos)]


def lorem(palabras: int, parrafos: int = 1, rng: random.Random | None = None) -> list[str]:
    """``parrafos`` párrafos de ``palabras`` palabras; el primero empieza por «Lorem ipsum»."""
    rng = rng or random.Random()
    resultado = []
    for numero in range(parrafos):
        lista = LOREM[:2] if numero == 0 else []
        while len(lista) < palabras:
            lista.append(rng.choice(LOREM))
        lista = lista[:palabras]
        frases, actual = [], []
        for palabra in lista:
            actual.append(palabra)
            if len(actual) >= rng.randint(6, 12):
                frases.append(actual)
                actual = []
        if actual:
            frases.append(actual)
        resultado.append(" ".join(" ".join(f).capitalize() + "." for f in frases))
    return resultado


def numeros(
    minimo: int, maximo: int, cuantos: int, sin_repetir: bool, rng: random.Random | None = None
) -> list[int]:
    """``cuantos`` números entre ``minimo`` y ``maximo`` (los dos incluidos)."""
    if minimo > maximo:
        minimo, maximo = maximo, minimo
    rng = rng or random.Random()
    if sin_repetir:
        posibles = maximo - minimo + 1
        if cuantos > posibles:
            raise NavajaError(
                f"Sin repetir solo hay {posibles} números entre {minimo} y {maximo}: "
                f"no salen {cuantos}."
            )
        return rng.sample(range(minimo, maximo + 1), cuantos)
    return [rng.randint(minimo, maximo) for _ in range(cuantos)]


# ── Órdenes ────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def uuid_orden(
    cuantos: int = typer.Option(1, "--cuantos", "-n", min=1, max=MAXIMO, help="Cuántos.", rich_help_panel=AJUSTE),
) -> None:
    """Identificadores únicos (UUID v4), uno por línea."""
    for valor in uuids(cuantos):
        console.print(Text(valor), highlight=False)


def lorem_orden(
    palabras: int = typer.Option(50, "--palabras", "-p", min=1, max=MAXIMO, help="Palabras de cada párrafo.", rich_help_panel=AJUSTE),
    parrafos: int = typer.Option(1, "--parrafos", min=1, max=100, help="Cuántos párrafos.", rich_help_panel=AJUSTE),
) -> None:
    """Texto de relleno (lorem ipsum) para maquetar una web o un documento."""
    for posicion, parrafo in enumerate(lorem(palabras, parrafos)):
        if posicion:
            console.print()
        console.print(Text(parrafo), highlight=False)


def numero_orden(
    minimo: int = typer.Argument(1, help="El más pequeño que puede salir."),
    maximo: int = typer.Argument(100, help="El más grande que puede salir."),
    cuantos: int = typer.Option(1, "--cuantos", "-n", min=1, max=MAXIMO, help="Cuántos números.", rich_help_panel=AJUSTE),
    sin_repetir: bool = typer.Option(False, "--sin-repetir", help="Que no salga ninguno dos veces (un sorteo).", rich_help_panel=AJUSTE),
) -> None:
    """Números al azar entre dos (los dos incluidos): un dado, un sorteo…"""
    try:
        lista = numeros(minimo, maximo, cuantos, sin_repetir)
    except NavajaError as error:
        fallar(error)
    console.print(Text(" ".join(str(n) for n in lista)), soft_wrap=True, highlight=False)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(help="UUID, texto de relleno y números al azar.", no_args_is_help=True)
    sub.command("uuid", help="Identificadores únicos (UUID v4).")(uuid_orden)
    sub.command("lorem", help="Texto de relleno (lorem ipsum).")(lorem_orden)
    sub.command("numero", help="Números al azar entre dos.")(numero_orden)
    app.add_typer(sub, name="genera", rich_help_panel=PROGRAMACION)
