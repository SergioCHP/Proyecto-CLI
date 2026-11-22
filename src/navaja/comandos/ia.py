"""navaja comprobar-ia: dice si la IA está lista y, si no, por qué y cómo arreglarlo.

Enseña a quién se pregunta (Gemini o un servidor compatible con OpenAI), de dónde sale la
clave (sin enseñarla), qué modelo se usa y hace una pregunta mínima para ver que contesta. Sin clave o sin red no hay traza: el motivo en una
línea y el código 4 (``IANoDisponible``).
"""

from __future__ import annotations

import time

import typer
from rich.markup import escape
from rich.text import Text

from .. import proveedor_ia
from ..comun import NAVAJA, console, error_console, recuadro, tabla_ligera
from ..errores import IAError
from ..proveedor_ia import ProveedorIA


def comprobar_ia(
    sin_llamar: bool = typer.Option(
        False, "--sin-llamar", help="Solo mira la configuración, sin preguntar nada a la IA (no gasta cupo)."
    ),
) -> None:
    """Comprueba que la IA (Gemini o tu servidor) está lista: clave, modelo y que contesta."""
    datos = proveedor_ia.configuracion()
    tabla = tabla_ligera()
    tabla.add_column("Qué", no_wrap=True)
    tabla.add_column("Cómo está")
    if datos.con_servidor:
        tabla.add_row("Proveedor", f"servidor compatible con OpenAI · {escape(datos.url)}")
    else:
        tabla.add_row("Proveedor", "Gemini (Google)")
    tabla.add_row("Modelo", escape(datos.modelo))
    if datos.clave:
        tabla.add_row("Clave", f"{escape(proveedor_ia.oculta(datos.clave))} · en {escape(datos.origen)}")
    elif datos.con_servidor:
        tabla.add_row("Clave", f"[pista]ninguna ({proveedor_ia.ENV_CLAVE_SERVIDOR}, solo si el servidor la pide)[/]")
    else:
        tabla.add_row("Clave", "[error]no hay[/]")
    try:
        proveedor = ProveedorIA.desde_entorno()
        if sin_llamar:
            final = "[ok]✔ Configuración lista.[/] [pista]Sin --sin-llamar, además, le pregunta algo.[/]"
        else:
            inicio = time.monotonic()
            with console.status(f"[pista]Preguntando a {escape(proveedor.nombre)}…[/]"):
                proveedor.comprobar()
            tabla.add_row("Respuesta", f"[ok]contesta[/] en {time.monotonic() - inicio:.1f} s")
            final = "[ok]✔ La IA está lista: renombrar-ia y resumir-ia funcionan.[/]"
    except IAError as error:
        console.print(recuadro("comprobar-ia", tabla))
        error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
        raise typer.Exit(error.codigo_salida) from None
    console.print(recuadro("comprobar-ia", tabla, Text.from_markup(final)))


def registrar(app: typer.Typer) -> None:
    app.command(
        "comprobar-ia",
        help="Comprueba que la IA (Gemini o tu servidor) está lista: clave, modelo y si contesta.",
        rich_help_panel=NAVAJA,
    )(comprobar_ia)
