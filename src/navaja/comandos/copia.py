"""navaja copia: copiar archivos de una carpeta a otra al momento, sin escribir una acción.

Por dentro es una acción de tipo copiar hecha en el momento (``Copiar`` de acciones.py),
así que hace lo mismo que ``usb-a-pc``: el mismo plan, la copia segura (a un temporal y
el nombre bueno solo al final), las versiones viejas guardadas aparte, la barra de
progreso y el deshacer. Lo hecho se guarda en su propio registro («copia»), así que
``copia deshacer`` no se mezcla con ``acciones deshacer``.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

import typer
from rich.markup import escape

from ..acciones import Accion, AccionDeArchivos, Resultado
from ..comun import AJUSTE, HERRAMIENTAS, como_se_escribe, confirmar, console, error_console
from ..errores import NavajaError
from ..filtros import (
    OPCION_CARPETA,
    OPCION_CONTIENE,
    OPCION_DESDE,
    OPCION_HASTA,
    OPCION_OCULTOS,
    OPCION_RECURSIVO,
    OPCION_SI,
    OPCION_SIMULAR,
    OPCION_SOLO,
)
from ..motor import Motor
from .mis_acciones import deshacer_registro, fallar, hacer, mostrar_plan

REGISTRO = "copia"


class SiCambia(str, Enum):
    copia_aparte = "copia-aparte"
    el_mas_nuevo = "el-mas-nuevo"


def accion_de_copia(
    carpeta: Path, destino: Path, si_cambia: str, filtro: dict[str, object]
) -> AccionDeArchivos:
    """La acción de tipo copiar que hace «copia a», como si estuviera en acciones.json."""
    accion = Accion.desde_config(
        {
            "nombre": "copia",
            "descripcion": "Los originales se quedan donde están.",
            "tipo": "copiar",
            "carpeta": str(carpeta),
            # absoluta, desde donde estás: el plan y el deshacer no dependen de la carpeta actual
            "destino": str(destino.expanduser().absolute()),
            "si_cambia": si_cambia,
            "filtro": filtro,
        }
    )
    assert isinstance(accion, AccionDeArchivos)
    return accion


def buscar_archivos(pedidos: list[str], carpeta: Path) -> list[Path]:
    """Los archivos que se han escrito, buscados en ``carpeta`` si no llevan ruta.

    Un comodín (``*.pdf``, ``tema?.md``) se expande aquí, en ``carpeta``: así vale igual
    en PowerShell (que no los expande), en bash y dentro del modo interactivo. Lanza
    ``NavajaError`` si alguno no existe o es una carpeta, o si dos se llaman igual (en
    el destino se pisarían).
    """
    elegidos: list[Path] = []
    for pedido in pedidos:
        # una ruta absoluta se queda como está; «..» se resuelve (tema1/../horario.txt)
        ruta = Path(os.path.abspath(carpeta / Path(pedido).expanduser()))
        if not ruta.exists() and any(c in pedido for c in "*?["):
            encontrados = sorted(
                (p for p in ruta.parent.glob(ruta.name) if p.is_file()),
                key=lambda p: p.name.lower(),
            )
            if not encontrados:
                raise NavajaError(f"Ningún archivo coincide con «{pedido}» en {carpeta}.")
            elegidos += encontrados
            continue
        if not ruta.exists():
            raise NavajaError(f"No encuentro «{pedido}» (lo he buscado en {ruta.parent}).")
        if ruta.is_dir():
            raise NavajaError(
                f"«{pedido}» es una carpeta: para copiar lo que tiene, usa -c {pedido} (y -r para "
                "sus subcarpetas)."
            )
        elegidos.append(ruta)

    unicos: dict[Path, Path] = {}  # sin repetir el mismo archivo (a.pdf *.pdf)
    for ruta in elegidos:
        unicos.setdefault(ruta.resolve(), ruta)
    nombres: dict[str, Path] = {}
    for ruta in unicos.values():
        otro = nombres.setdefault(ruta.name.lower(), ruta)
        if otro is not ruta:
            raise NavajaError(
                f"Hay dos archivos que se llaman «{ruta.name}» ({otro.parent} y {ruta.parent}): "
                "en el destino se pisarían. Cópialos por separado."
            )
    return list(unicos.values())


def planificar_archivos(
    paso: AccionDeArchivos, archivos: list[Path], carpeta: Path
) -> tuple[Path, list[Resultado]]:
    """El plan para unos archivos concretos: cada uno al destino con su nombre, sin
    subcarpetas (vengan de donde vengan). Devuelve también la carpeta que se enseña en
    el plan: ``carpeta`` si están todos dentro; si no, la que tienen en común."""
    base = carpeta.resolve()
    if not all(a.resolve().is_relative_to(base) for a in archivos):
        try:
            base = Path(os.path.commonpath([str(a.resolve().parent) for a in archivos]))
        except ValueError:  # en unidades distintas (C: y E:) no tienen ninguna en común
            pass
    paso.comprobar_destino(base)
    plan: list[Resultado] = []
    for archivo in archivos:
        plan += paso.planificar([archivo], archivo.parent)  # su carpeta: va solo con su nombre
    return base, plan


def a(
    destino: Path = typer.Argument(
        ...,
        help="Carpeta a la que van las copias (se crea si no existe): E:/DAM, ~/Documents/copia…",
        show_default=False,
    ),
    archivos: list[str] | None = typer.Argument(
        None,
        help="Solo estos archivos (horario.pdf, \"tema 3.docx\", *.pdf), buscados en la carpeta; "
        "sin nada, toda la carpeta con sus filtros.",
        show_default=False,
    ),
    si_cambia: SiCambia = typer.Option(
        SiCambia.copia_aparte,
        "--si-cambia",
        help="Si allí ya hay otro distinto con el mismo nombre: copia-aparte guarda "
        "«nombre (1)» al lado; el-mas-nuevo deja el más reciente (y guarda el viejo).",
        rich_help_panel=AJUSTE,
    ),
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    desde: str = OPCION_DESDE,
    hasta: str = OPCION_HASTA,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Copia los archivos de una carpeta (o solo los que digas) a otra; los originales se quedan."""
    filtro = {
        clave: valor
        for clave, valor in {
            "solo": solo,
            "contiene": contiene,
            "desde": desde,
            "hasta": hasta,
            "recursivo": recursivo,
            "ocultos": ocultos,
        }.items()
        if valor
    }
    if not carpeta.expanduser().is_dir():
        que = "no es una carpeta" if carpeta.expanduser().exists() else "no existe"
        error_console.print(f"[error]✘ La carpeta {escape(str(carpeta))} {que}.[/]", soft_wrap=True)
        raise typer.Exit(1)
    try:
        paso = accion_de_copia(carpeta, destino, si_cambia.value, filtro)
        if archivos:
            if filtro:
                raise NavajaError(
                    "Con archivos concretos no se usan filtros (--solo, -r…): o dices qué "
                    "archivos, o filtras la carpeta entera."
                )
            elegidos = buscar_archivos(archivos, carpeta.expanduser())
            base, plan = planificar_archivos(paso, elegidos, carpeta.expanduser())
        else:
            base, plan = Motor([]).planificar(paso, carpeta)
    except NavajaError as error:
        fallar(error)
    except ValueError as exc:  # una fecha que no se entiende en --desde o --hasta
        error_console.print(f"[error]✘ {escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(2)

    mostrar_plan(paso, base, plan)
    pendientes = sum(r.estado == "pendiente" for r in plan)
    if not pendientes:
        detalle = "ningún archivo cumple el filtro" if not plan else "todo está ya copiado"
        console.print(f"[aviso]Nada que hacer: {detalle}.[/]")
        return
    if simular:
        console.print("[pista]Simulación: no se ha tocado nada. Sin --simular, lo hace.[/]")
        return
    if not confirmar(paso.pregunta(pendientes), saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        raise typer.Exit(1)  # decir que no también sale con 1: un script sabe que no se hizo

    fallos = hacer(paso, plan, REGISTRO, [])
    if any(r.estado == "hecho" for r in plan):
        console.print(f"[pista]Para deshacerlo: {como_se_escribe('copia deshacer')}[/]")
    if fallos:
        raise typer.Exit(1)


def deshacer(si: bool = OPCION_SI) -> None:
    """Quita las copias que hiciste la última vez (a la papelera de navaja, sin borrarlas)."""
    deshacer_registro(REGISTRO, "la última copia", "No hay ninguna copia que deshacer.", si)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Copia archivos a otra carpeta sin tocar los originales.",
        no_args_is_help=True,
    )
    sub.command("a", help="Copia los archivos de una carpeta a otra (navaja copia a E:/DAM).")(a)
    sub.command("deshacer", help="Quita las copias que hiciste la última vez.")(deshacer)
    app.add_typer(sub, name="copia", rich_help_panel=HERRAMIENTAS)
