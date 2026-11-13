"""El rótulo de bienvenida: «NAVAJA» en letras grandes con sombra y el saludo debajo.

Los bloques (█) van con el estilo ``titulo`` y la sombra (╗ ║ ╚ ═…) con ``marco``, así el
rótulo tiene dos tonos y cambia con el tema. Si la terminal es estrecha o no escribe
UTF-8 (la salida redirigida a un archivo en PowerShell), se usa el recuadro sencillo de
siempre: mejor eso que un dibujo roto.
"""

from __future__ import annotations

from rich.cells import cell_len
from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from .comun import es_utf8

LETRAS = (
    "███╗   ██╗ █████╗ ██╗   ██╗ █████╗      ██╗ █████╗ ",
    "████╗  ██║██╔══██╗██║   ██║██╔══██╗     ██║██╔══██╗",
    "██╔██╗ ██║███████║██║   ██║███████║     ██║███████║",
    "██║╚██╗██║██╔══██║╚██╗ ██╔╝██╔══██║██   ██║██╔══██║",
    "██║ ╚████║██║  ██║ ╚████╔╝ ██║  ██║╚█████╔╝██║  ██║",
    "╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝",
)

SANGRIA = " "
"""Lo que va delante del saludo para que quede alineado con las letras."""


def letras() -> Text:
    """«NAVAJA» en dos tonos: el bloque con ``titulo`` y la sombra con ``marco``."""
    texto = Text()
    for numero, linea in enumerate(LETRAS):
        if numero:
            texto.append("\n")
        for caracter in linea:
            texto.append(caracter, style="titulo" if caracter == "█" else "marco")
    return texto


def ancho_necesario(saludo: str, detalle: str) -> int:
    """Columnas que ocupa el rótulo."""
    return max(len(LETRAS[0]), len(SANGRIA) + max(cell_len(saludo), cell_len(detalle)))


def cabe(consola: Console, saludo: str, detalle: str) -> bool:
    """¿Se puede dibujar el rótulo en esta consola sin que se rompa?

    Solo en una terminal: con la salida a un archivo o a una tubería sale el recuadro
    sencillo, igual en todos los sistemas.
    """
    return (
        consola.is_terminal
        and es_utf8(consola)
        and consola.width >= ancho_necesario(saludo, detalle)
    )


def rotulo(consola: Console, saludo: str, detalle: str) -> RenderableType:
    """La cabecera de navaja: el rótulo grande si cabe; si no, el recuadro sencillo."""
    if not cabe(consola, saludo, detalle):
        texto = f"[titulo]{escape(saludo)}[/]\n[pista]{escape(detalle)}[/]"
        return Panel(texto, title="navaja", border_style="marco", expand=False)
    return Group(
        Text(""),
        letras(),
        Text(""),
        Text(SANGRIA + saludo, style="titulo"),
        Text(SANGRIA + detalle, style="pista"),
        Text(""),
    )
