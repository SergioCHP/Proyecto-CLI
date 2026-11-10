"""«acciones versiones»: ver, recuperar y borrar las versiones viejas que sustituyó una copia.

Cuando «copiar» con «si_cambia: el-mas-nuevo» sustituye un archivo, el viejo se guarda
(``navaja.versiones``). Aquí se ven todas, se devuelve a su sitio la que haga falta y se
borran para siempre las que ya no sirven.
"""

from __future__ import annotations

import shutil
from datetime import datetime

import typer
from rich.markup import escape

from .. import versiones
from ..comun import (
    bonita,
    como_se_escribe,
    confirmar,
    console,
    crear_tabla,
    cuantos,
    error_console,
    ruta_libre,
    tamano_legible,
)
from ..filtros import OPCION_SI, rango
from ..versiones import Version


def cuando_legible(momento: datetime) -> str:
    hoy = datetime.now().date()
    if momento.date() == hoy:
        return f"hoy {momento:%H:%M}"
    if (hoy - momento.date()).days == 1:
        return f"ayer {momento:%H:%M}"
    return f"{momento:%d/%m/%Y %H:%M}"


def numeros_para_tab(ctx: typer.Context, incomplete: str) -> list[tuple[str, str]]:
    """Tab en los números: cada uno con el archivo al que corresponde."""
    return [
        (str(n), f"{v.sitio.name} ({cuando_legible(v.cuando)})")
        for n, v in enumerate(versiones.cargar(), start=1)
        if str(n).startswith(incomplete)
    ]


def elegir(numeros: list[int], lista: list[Version]) -> list[Version]:
    """Las versiones de esos números (los de «versiones ver»); error claro si alguno no está."""
    malos = [n for n in numeros if not 1 <= n <= len(lista)]
    if malos:
        error_console.print(
            f"[error]No hay ninguna versión con el número {', '.join(map(str, malos))}.[/] "
            f"[pista]Van del 1 al {len(lista)}: {como_se_escribe('acciones versiones ver')}[/]",
            soft_wrap=True,
        )
        raise typer.Exit(1)
    return [lista[n - 1] for n in dict.fromkeys(numeros)]  # sin repetir, en el orden dado


def pintar(lista: list[Version]) -> None:
    tabla = crear_tabla(["Nº", "Archivo", "Estaba en", "Sustituida", "Por", "Tamaño"])
    todas = versiones.cargar()
    for version in lista:
        numero = todas.index(version) + 1 if version in todas else "?"
        tabla.add_row(
            str(numero),
            escape(version.sitio.name),
            escape(bonita(version.sitio.parent)),
            cuando_legible(version.cuando),
            escape(version.accion),
            tamano_legible(version.tamano),
        )
    console.print(tabla)


def ver() -> None:
    """Las versiones viejas guardadas, de la más reciente a la más antigua."""
    lista = versiones.cargar()
    if not lista:
        console.print(
            "[ok]No hay versiones viejas guardadas.[/] [pista]Se guardan cuando «copiar» con "
            "«si_cambia: el-mas-nuevo» sustituye un archivo.[/]",
            soft_wrap=True,
        )
        return
    pintar(lista)
    total = sum(v.tamano for v in lista)
    console.print(
        f"[bold]{cuantos(len(lista), 'versión', 'versiones')}[/] ({tamano_legible(total)}). "
        f"[pista]Devolver una: {como_se_escribe('acciones versiones recuperar 1')} · "
        f"borrarlas: {como_se_escribe('acciones versiones borrar')}[/]",
        soft_wrap=True,
    )


def recuperar(
    numeros: list[int] = typer.Argument(
        ...,
        help="Números de las versiones (los de «versiones ver»): 1, o 1 3 4.",
        autocompletion=numeros_para_tab,
        show_default=False,
    ),
    si: bool = OPCION_SI,
) -> None:
    """Devuelve versiones viejas a su sitio; si allí ya hay un archivo, la deja al lado."""
    lista = versiones.cargar()
    if not lista:
        console.print("[aviso]No hay versiones viejas guardadas.[/]")
        return
    elegidas = elegir(numeros, lista)
    pintar(elegidas)
    ocupados = sum(v.sitio.exists() for v in elegidas)
    if ocupados:
        console.print(
            f"[pista]{cuantos(ocupados, 'sitio')} ya {'tiene' if ocupados == 1 else 'tienen'} un "
            "archivo: la versión vieja se deja al lado, como «nombre (1)», sin pisar nada.[/]",
            soft_wrap=True,
        )
    if not confirmar(
        f"¿Recuperar {cuantos(len(elegidas), 'versión', 'versiones')}?", saltar=si, por_defecto=False
    ):
        console.print("[aviso]Cancelado.[/]")
        return

    devueltas: list[Version] = []
    for version in elegidas:
        destino = ruta_libre(version.sitio)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(version.guardada), str(destino))
        except OSError as exc:
            error_console.print(
                f"[error]No se pudo recuperar[/] {escape(version.sitio.name)}: "
                f"{escape(exc.strerror or str(exc))}",
                soft_wrap=True,
            )
            continue
        devueltas.append(version)
        aparte = "" if destino == version.sitio else f" [pista](como «{escape(destino.name)}»)[/]"
        console.print(f"[ok]Recuperada[/] {escape(bonita(destino))}{aparte}", soft_wrap=True)
    versiones.olvidar(devueltas)
    versiones.quitar_carpetas_vacias()
    if len(devueltas) < len(elegidas):
        raise typer.Exit(1)


def borrar(
    numeros: list[int] | None = typer.Argument(
        None,
        help="Números de las versiones (los de «versiones ver»). Sin números, todas (o las "
        "de --hasta).",
        autocompletion=numeros_para_tab,
        show_default=False,
    ),
    hasta: str = typer.Option(
        "",
        "--hasta",
        help="Solo las sustituidas hasta esa fecha: \"hace 30 días\", \"septiembre 2026\", "
        "\"1/9/2026\".",
        show_default=False,
    ),
    si: bool = OPCION_SI,
) -> None:
    """Borra para siempre versiones viejas que ya no necesitas (todas, unas o las antiguas)."""
    lista = versiones.cargar()
    if not lista:
        console.print("[ok]No hay versiones viejas guardadas.[/]")
        return
    elegidas = elegir(numeros, lista) if numeros else lista
    if hasta.strip():
        try:
            _, fin = rango("", hasta)
        except ValueError as exc:
            error_console.print(f"[error]--hasta: {escape(str(exc))}[/]", soft_wrap=True)
            raise typer.Exit(1) from None
        elegidas = [v for v in elegidas if fin is None or v.cuando <= fin]
        if not elegidas:
            console.print(f"[ok]Ninguna versión es de hasta «{escape(hasta)}».[/]")
            return
    pintar(elegidas)
    total = sum(v.tamano for v in elegidas)
    if not confirmar(
        f"¿Borrar para siempre {cuantos(len(elegidas), 'versión', 'versiones')} "
        f"({tamano_legible(total)})? No se podrá deshacer.",
        saltar=si,
        por_defecto=False,
    ):
        console.print("[aviso]Cancelado.[/]")
        return

    borradas: list[Version] = []
    liberado = 0
    for version in elegidas:
        tamano = version.tamano
        try:
            version.guardada.unlink()
        except OSError as exc:
            error_console.print(
                f"[error]No se pudo borrar[/] {escape(version.sitio.name)}: "
                f"{escape(exc.strerror or str(exc))}",
                soft_wrap=True,
            )
            continue
        borradas.append(version)
        liberado += tamano
    versiones.olvidar(borradas)
    versiones.quitar_carpetas_vacias()
    console.print(
        f"[ok]Borradas {cuantos(len(borradas), 'versión', 'versiones')}: "
        f"liberados {tamano_legible(liberado)}.[/]"
    )
    if len(borradas) < len(elegidas):
        raise typer.Exit(1)


def registrar_en(acciones: typer.Typer) -> None:
    """Añade el grupo «versiones» dentro de «acciones»."""
    grupo = typer.Typer(
        help="Las versiones viejas que sustituyó una copia: verlas, recuperarlas o borrarlas.",
        no_args_is_help=True,
    )
    grupo.command("ver", help="Lista las versiones viejas guardadas, con su número.")(ver)
    grupo.command("recuperar", help="Devuelve versiones viejas a su sitio, sin pisar nada.")(recuperar)
    grupo.command("borrar", help="Borra para siempre versiones viejas que ya no necesitas.")(borrar)
    acciones.add_typer(grupo, name="versiones")
