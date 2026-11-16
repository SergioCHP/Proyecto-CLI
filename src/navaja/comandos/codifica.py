"""navaja codifica: Base64, URL y HTML de ida y vuelta, y leer un token JWT.

Todo sin internet, para no pegar datos en webs de dudosa confianza.
"""

from __future__ import annotations

import base64
import binascii
import html
import json
import urllib.parse
from datetime import datetime, timezone
from typing import Any, NoReturn

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import PROGRAMACION, console, error_console, recuadro, resumen
from ..errores import NavajaError

# ── Lógica ─────────────────────────────────────────────────────────────────


def a_base64(texto: str) -> str:
    return base64.b64encode(texto.encode("utf-8")).decode("ascii")


def _bytes_de_base64(texto: str) -> bytes:
    """Vale también la variante de URL (- y _) y sin los = del final."""
    limpio = "".join(texto.split()).replace("-", "+").replace("_", "/")
    limpio += "=" * (-len(limpio) % 4)
    try:
        return base64.b64decode(limpio, validate=True)
    except (binascii.Error, ValueError):
        raise NavajaError(
            f"«{texto}» no es Base64: solo lleva letras, números, + y / (o - y _), y = al final."
        ) from None


def de_base64(texto: str) -> str:
    """El texto que lleva dentro. ``NavajaError`` si no es Base64 o no es texto."""
    datos = _bytes_de_base64(texto)
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        raise NavajaError(
            f"Es Base64, pero dentro no hay texto sino datos ({len(datos)} bytes): "
            "una imagen o un archivo."
        ) from None


def a_url(texto: str) -> str:
    """Para meter un texto en una URL: «año 2026» → «a%C3%B1o%202026»."""
    return urllib.parse.quote(texto, safe="")


def de_url(texto: str) -> str:
    """«a%C3%B1o+2026» → «año 2026» (el + de los formularios también es un espacio)."""
    return urllib.parse.unquote_plus(texto)


def a_html(texto: str) -> str:
    return html.escape(texto, quote=True)


def de_html(texto: str) -> str:
    return html.unescape(texto)


FECHAS_JWT = {"exp": "Caduca", "iat": "Creado", "nbf": "Vale desde"}


def leer_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """La cabecera y los datos de un JWT (las dos primeras partes, en Base64 de URL)."""
    partes = token.strip().split(".")
    if len(partes) != 3:
        raise NavajaError(
            "Un JWT tiene tres partes separadas por puntos (cabecera.datos.firma): "
            f"este tiene {len(partes)}."
        )
    resultado = []
    for parte, nombre in zip(partes[:2], ("la cabecera", "los datos")):
        try:
            contenido = json.loads(_bytes_de_base64(parte).decode("utf-8"))
        except (NavajaError, UnicodeDecodeError, json.JSONDecodeError):
            raise NavajaError(f"No se puede leer {nombre} del JWT: no es Base64 con JSON dentro.") from None
        if not isinstance(contenido, dict):
            raise NavajaError(f"{nombre.capitalize()} del JWT no es un objeto JSON.")
        resultado.append(contenido)
    return resultado[0], resultado[1]


def fechas_jwt(datos: dict[str, Any], ahora: datetime | None = None) -> list[tuple[str, str]]:
    """«Caduca: 2026-11-16 12:00 (ya ha caducado)» con las fechas que lleva el token."""
    ahora = ahora or datetime.now(timezone.utc)
    filas = []
    for clave, etiqueta in FECHAS_JWT.items():
        valor = datos.get(clave)
        if not isinstance(valor, (int, float)):
            continue
        try:
            fecha = datetime.fromtimestamp(valor, timezone.utc)
        except (OverflowError, OSError, ValueError):
            continue
        texto = fecha.astimezone().strftime("%Y-%m-%d %H:%M")
        if clave == "exp":
            texto += " (ya ha caducado)" if fecha <= ahora else " (aún vale)"
        filas.append((etiqueta, texto))
    return filas


# ── Órdenes ────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def mostrar(titulo: str, resultado: str) -> None:
    """El resultado tal cual, sin recuadro, para copiarlo o pasarlo a otra orden."""
    if console.is_terminal:
        console.print(f"[pista]{escape(titulo)}:[/]")
    console.print(Text(resultado), soft_wrap=True, highlight=False)


OPCION_AL_REVES = typer.Option(
    False, "--descodifica", "-d", help="Al revés: de codificado a texto normal."
)


def base64_orden(
    texto: str = typer.Argument(..., help="El texto que quieres pasar a Base64 (o al revés, con -d)."),
    descodifica: bool = OPCION_AL_REVES,
) -> None:
    """Base64: texto ↔ letras, números, + y /. Lo usan los correos y las imágenes en una web."""
    try:
        if descodifica:
            mostrar("Texto", de_base64(texto))
        else:
            mostrar("Base64", a_base64(texto))
    except NavajaError as error:
        fallar(error)


def url_orden(
    texto: str = typer.Argument(..., help="El texto para una URL (o al revés, con -d)."),
    descodifica: bool = OPCION_AL_REVES,
) -> None:
    """URL: los espacios y las tildes como %20, %C3%B1… (o al revés)."""
    mostrar("Texto" if descodifica else "Para la URL", de_url(texto) if descodifica else a_url(texto))


def html_orden(
    texto: str = typer.Argument(..., help="El texto para meter en HTML (o al revés, con -d)."),
    descodifica: bool = OPCION_AL_REVES,
) -> None:
    """HTML: < > & y las comillas como &lt; &gt; &amp;… (o al revés)."""
    mostrar("Texto" if descodifica else "Para HTML", de_html(texto) if descodifica else a_html(texto))


def jwt_orden(token: str = typer.Argument(..., help="El token JWT (eyJ…).")) -> None:
    """Lo que lleva dentro un token JWT: cabecera, datos y fechas. No comprueba la firma."""
    try:
        cabecera, datos = leer_jwt(token)
    except NavajaError as error:
        fallar(error)
    partes: list = [
        Text.from_markup("[titulo]Cabecera[/]"),
        Text(json.dumps(cabecera, indent=2, ensure_ascii=False)),
        Text.from_markup("[titulo]Datos[/]"),
        Text(json.dumps(datos, indent=2, ensure_ascii=False)),
    ]
    fechas = fechas_jwt(datos)
    if fechas:
        partes.append(resumen([(etiqueta, escape(valor)) for etiqueta, valor in fechas]))
    partes.append(
        Text.from_markup(
            "[aviso]La firma no se comprueba: cualquiera puede escribir esto. No te fíes de lo "
            "que dice sin la clave.[/]"
        )
    )
    console.print(recuadro("Token JWT", *partes))


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Base64, URL y HTML de ida y vuelta, y leer un token JWT.",
        no_args_is_help=True,
    )
    sub.command("base64", help="Texto ↔ Base64 (con -d, al revés).")(base64_orden)
    sub.command("url", help="Texto ↔ URL: espacios y tildes como %20 (con -d, al revés).")(url_orden)
    sub.command("html", help="Texto ↔ HTML: < > & como &lt; &gt; &amp; (con -d, al revés).")(html_orden)
    sub.command("jwt", help="Lo que lleva dentro un token JWT (sin comprobar la firma).")(jwt_orden)
    app.add_typer(sub, name="codifica", rich_help_panel=PROGRAMACION)
