"""navaja qr: un código QR en la terminal para pasar algo al móvil (un enlace, un texto,
la wifi). Con qrcode (``navaja[qr]``); para guardarlo en PNG, también Pillow.

Se dibuja con medios bloques (▀ ▄ █): cada carácter son dos filas del QR, así cabe en
la ventana. Blanco sobre negro con un borde blanco alrededor, que es lo que leen bien
las cámaras aunque la terminal sea oscura.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, DOCUMENTOS, bonita, console, ruta_libre
from ..errores import NavajaError
from ..lotes import fallar, libreria, pedir_secreto


def matriz(texto: str, borde: int = 3) -> list[list[bool]]:
    """Los módulos del QR (True = negro), con ``borde`` módulos blancos alrededor."""
    qrcode = libreria("qrcode", "qrcode", "qr", "hacer códigos QR")
    codigo = qrcode.QRCode(border=borde, error_correction=qrcode.constants.ERROR_CORRECT_M)
    codigo.add_data(texto)
    try:
        codigo.make(fit=True)
    except Exception:
        raise NavajaError("El texto es demasiado largo para un QR (unos 2.000 caracteres como mucho).") from None
    return codigo.get_matrix()


def dibujar(modulos: list[list[bool]]) -> list[str]:
    """Dos filas del QR por línea: ▀ arriba, ▄ abajo, █ las dos, espacio ninguna.

    Se dibuja lo blanco (el fondo de la terminal hace de negro), así que sale bien tanto en
    terminales oscuras como claras con el estilo que lo pinta de blanco.
    """
    lineas = []
    for fila in range(0, len(modulos), 2):
        arriba = modulos[fila]
        abajo = modulos[fila + 1] if fila + 1 < len(modulos) else [True] * len(arriba)
        linea = []
        for a, b in zip(arriba, abajo):
            blanco_a, blanco_b = not a, not b
            linea.append("█" if blanco_a and blanco_b else "▀" if blanco_a else "▄" if blanco_b else " ")
        lineas.append("".join(linea))
    return lineas


def texto_wifi(red: str, clave: str, tipo: str = "WPA") -> str:
    """El texto que entienden los móviles para conectarse a una wifi al leer el QR."""
    def protege(valor: str) -> str:
        for especial in ("\\", ";", ",", ":", '"'):
            valor = valor.replace(especial, "\\" + especial)
        return valor

    return f"WIFI:T:{tipo if clave else 'nopass'};S:{protege(red)};P:{protege(clave)};;"


def guardar_png(texto: str, destino: Path) -> Path:
    qrcode = libreria("qrcode", "qrcode", "qr", "hacer códigos QR")
    libreria("PIL.Image", "Pillow", "qr", "guardar el QR como imagen")
    imagen: Any = qrcode.make(texto, box_size=10, border=4)
    final = ruta_libre(destino)
    imagen.save(final)
    return final


def qr(
    texto: str = typer.Argument("", help="Lo que lleva el QR: un enlace o un texto (con --wifi, el nombre de la red).", show_default=False),
    wifi: bool = typer.Option(False, "--wifi", "-w", help="Un QR para conectarse a tu wifi (pregunta la contraseña sin que se vea)."),
    guardar: Path = typer.Option(None, "--guardar", "-g", help="Guardarlo también en un PNG.", show_default=False, rich_help_panel=AJUSTE),
) -> None:
    """Un código QR en la terminal para pasar un enlace, un texto o la wifi al móvil."""
    if not texto.strip():
        fallar(NavajaError("Di qué lleva el QR: navaja qr https://… (o con --wifi, el nombre de la red)."))
    contenido = texto
    if wifi:
        clave = pedir_secreto("Contraseña de la wifi (Intro si no tiene)")
        contenido = texto_wifi(texto, clave)
    try:
        lineas = dibujar(matriz(contenido))
    except NavajaError as error:
        fallar(error)
    # Única excepción a «solo colores del tema»: un QR tiene que ser blanco y negro puros
    # para que lo lea la cámara, sea cual sea el tema o el fondo de la terminal.
    console.print(Text("\n".join(lineas), style="#ffffff on #000000"), highlight=False, crop=False, overflow="ignore")
    ancho = len(lineas[0]) if lineas else 0
    if ancho > console.width:
        console.print("[aviso]La ventana es estrecha y el QR se descoloca: hazla más ancha o usa --guardar.[/]")
    descripcion = f"la wifi «{texto}»" if wifi else texto
    console.print(f"[pista]Apunta la cámara del móvil: {escape(descripcion)}[/]", soft_wrap=True)
    if guardar is not None:
        try:
            final = guardar_png(contenido, guardar.expanduser().with_suffix(".png"))
        except NavajaError as error:
            fallar(error)
        console.print(f"[ok]✔ Guardado en {escape(bonita(final))}[/]", soft_wrap=True)


def registrar(app: typer.Typer) -> None:
    app.command("qr", help="Un QR en la terminal para pasar un enlace o la wifi al móvil.", rich_help_panel=DOCUMENTOS)(qr)
