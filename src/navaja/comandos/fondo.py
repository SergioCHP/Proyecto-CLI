"""navaja fondo: quitar el fondo de las fotos con inteligencia artificial, sin internet.

Con rembg (``navaja[fondo]``): la primera vez descarga el modelo (unos 170 MB) y después
todo se hace en tu PC; las fotos no salen de él. El resultado es un PNG transparente al
lado de la original («foto-sin-fondo.png») o, con ``--color``, con un fondo liso (fotos de
carné o de producto).
"""

from __future__ import annotations

from typing import Any

import typer

from ..comun import AJUSTE, DOCUMENTOS, console
from ..errores import NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..lotes import Tarea, al_lado, ejecutar, expandir, fallar, libreria
from . import imagen

def rembg() -> Any:
    return libreria("rembg", "rembg", "fondo", "quitar el fondo (ocupa unos 300 MB con el modelo)")


MODELO = "isnet-general-use"
"""El modelo de IA: unos 170 MB y bueno con personas y objetos. (El que rembg usa si no se le
dice nada pesa 1 GB y tarda mucho más.)"""
_sesion: Any = None


def sesion() -> Any:
    """El modelo cargado una sola vez (cargarlo es lo que más tarda)."""
    global _sesion
    if _sesion is None:
        _sesion = rembg().new_session(MODELO)
    return _sesion


def quitar_fondo(foto: Any, mascara: bool = False) -> Any:
    """La foto sin fondo (RGBA) o, con ``mascara``, solo la silueta en blanco y negro."""
    return rembg().remove(foto, session=sesion(), only_mask=mascara)


def poner_fondo(foto: Any, color: tuple[int, int, int]) -> Any:
    return imagen.con_fondo(foto, color)


def fondo(
    fotos: list[str] = typer.Argument(..., help="Las fotos (vale *.jpg)."),
    color: str = typer.Option(
        "", "--color", "-c", help="Un fondo liso en vez de transparente: blanco, azul, #ff8800…",
        rich_help_panel=AJUSTE, show_default=False,
    ),
    mascara: bool = typer.Option(False, "--mascara", help="Solo la silueta en blanco y negro."),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Quita el fondo de las fotos (con IA, sin internet): un PNG transparente al lado."""
    try:
        rutas = expandir(fotos)
        relleno = imagen.color(color) if color else None
        if not simular:
            rembg()
            imagen.pil()
    except NavajaError as error:
        fallar(error)
    reservados: set[str] = set()
    tareas = []
    sufijo = "-silueta" if mascara else "-sin-fondo"
    extension = ".jpg" if relleno and not mascara else ".png"
    for ruta in rutas:
        destino = al_lado(ruta, sufijo, extension, reservados)

        def hacer(r=ruta, d=destino) -> None:
            resultado = quitar_fondo(imagen.abrir(r), mascara)
            if relleno and not mascara:
                resultado = poner_fondo(resultado, relleno)
            imagen.guardar(resultado, d, 92)

        tareas.append(Tarea(ruta, destino, hacer))
    console.print("[pista]La primera vez descarga el modelo de IA (unos 170 MB); luego va sin internet.[/]")
    ejecutar(tareas, "Quitar el fondo", simular, si, hilos=1)


def registrar(app: typer.Typer) -> None:
    app.command("fondo", help="Quita el fondo de las fotos con IA, sin internet.", rich_help_panel=DOCUMENTOS)(fondo)
