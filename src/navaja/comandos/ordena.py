"""Ordenar una carpeta: mete cada archivo en la subcarpeta que le toca.

Todas las opciones siguen el mismo camino: eligen los archivos (con los filtros
de ``filtros.py``), enseñan «archivo → carpeta», preguntan [s/n] y mueven
(se puede deshacer). Cada opción solo decide a qué carpeta va cada archivo.
"""

from __future__ import annotations

import shutil
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel

from ..comun import (
    AJUSTE,
    cargar_acciones,
    confirmar,
    cuantos,
    console,
    crear_tabla,
    destino_libre,
    error_console,
    guardar_acciones,
    limpiar_acciones,
    como_se_escribe,
    ruta_libre,
)
from ..filtros import (
    CATEGORIAS,
    EJEMPLOS_FECHA,
    NOMBRE_MES,
    NOMBRES,
    OPCION_CARPETA,
    OPCION_CONTIENE,
    OPCION_DESDE,
    OPCION_HASTA,
    OPCION_OCULTOS,
    OPCION_RECURSIVO,
    OPCION_SI,
    OPCION_SIMULAR,
    OPCION_SOLO,
    Filtro,
    rango,
    seleccionar,
    sin_tildes,
    tipo_de,
)

Carpeta = Callable[[Path], str]
"""Recibe el archivo y devuelve la subcarpeta a la que va (por ejemplo «Imagenes»)."""


class Agrupar(str, Enum):
    mes = "mes"
    año = "año"
    día = "día"


OPCION_DESTINO = typer.Option(
    None,
    "--destino",
    "-d",
    help="Dónde se crean las carpetas (por defecto, dentro de la misma carpeta).",
)


# ── Planificar ─────────────────────────────────────────────────────────────


def planificar(archivos: list[Path], base: Path, carpeta_de: Carpeta) -> list[dict]:
    movimientos: list[dict] = []
    reservados: set[str] = set()
    for origen in archivos:
        subcarpeta = carpeta_de(origen)
        deseado = base / subcarpeta / origen.name
        if deseado == origen:
            continue  # ya está donde tiene que estar
        movimientos.append(
            {
                "origen": str(origen),
                "destino": str(destino_libre(deseado, reservados)),
                "carpeta": subcarpeta,
            }
        )
    return movimientos


def mostrar_plan(movimientos: list[dict], carpeta: Path, base: Path, limite: int = 100) -> None:
    conteo = Counter(m["carpeta"] for m in movimientos)
    n = len(movimientos)
    resumen = (
        f"[pista]En[/] {escape(str(carpeta.resolve()))}\n"
        + (f"[pista]Las carpetas, en[/] {escape(str(base.resolve()))}\n" if base != carpeta else "")
        + f"[bold]{cuantos(n, 'archivo')}[/] → [bold]{cuantos(len(conteo), 'carpeta')}[/]\n"
        + "  ·  ".join(f"{escape(c)}: [bold]{k}[/]" for c, k in sorted(conteo.items()))
    )
    console.print(Panel(resumen, title="Ordenar", border_style="marco", expand=False))

    tabla = crear_tabla(["Archivo", "Va a"])
    for movimiento in movimientos[:limite]:
        origen, destino = Path(movimiento["origen"]), Path(movimiento["destino"])
        try:
            archivo = str(origen.relative_to(carpeta))
        except ValueError:
            archivo = origen.name
        try:
            va_a = str(destino.relative_to(base))
        except ValueError:
            va_a = str(destino)
        tabla.add_row(escape(archivo), f"[ok]{escape(va_a)}[/]")
    console.print(tabla)
    if n > limite:
        console.print(f"[pista]Mostrando {limite} de {n}.[/]")


# ── Hacerlo ────────────────────────────────────────────────────────────────


def ordenar(
    carpeta_de: Carpeta,
    carpeta: Path,
    destino: Path | None,
    filtro: Filtro,
    simular: bool,
    si: bool,
) -> None:
    """El camino común: elegir → plan → confirmar → mover → guardar para deshacer."""
    if not carpeta.is_dir():
        error_console.print(f"[error]La carpeta no existe:[/] {escape(str(carpeta))}", soft_wrap=True)
        raise typer.Exit(1)
    base = destino or carpeta

    try:
        archivos = seleccionar(carpeta, filtro)
    except ValueError as exc:
        error_console.print(f"[error]{escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(2)
    if filtro.recursivo and base.resolve() != carpeta.resolve():
        destino_resuelto = base.resolve()
        archivos = [a for a in archivos if not a.resolve().is_relative_to(destino_resuelto)]

    movimientos = planificar(archivos, base, carpeta_de)
    if not movimientos:
        detalle = filtro.describir()
        extra = f" ({detalle})" if detalle else ""
        console.print(
            f"[aviso]No hay nada que ordenar{escape(extra)}[/] [pista](en {escape(str(carpeta.resolve()))})[/]",
            soft_wrap=True,
        )
        return

    mostrar_plan(movimientos, carpeta, base)
    if simular:
        console.print("[pista]Simulación: no se ha movido nada. Sin --simular, lo hace.[/]")
        return
    carpetas = len({m["carpeta"] for m in movimientos})
    pregunta = f"¿Mover {cuantos(len(movimientos), 'archivo')} a {cuantos(carpetas, 'carpeta')}?"
    if not confirmar(pregunta, saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return

    realizados: list[dict] = []
    errores = 0
    for movimiento in movimientos:
        origen, destino_final = Path(movimiento["origen"]), Path(movimiento["destino"])
        try:
            destino_final.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origen), str(destino_final))
            realizados.append({"origen": str(origen), "destino": str(destino_final)})
        except OSError as exc:
            errores += 1
            error_console.print(
                f"[error]No se pudo mover[/] {escape(str(origen))}: {escape(str(exc))}",
                soft_wrap=True,
            )

    if realizados:
        guardar_acciones("ordena", realizados)
    console.print(f"[ok]{'Movido' if len(realizados) == 1 else 'Movidos'} {cuantos(len(realizados), 'archivo')}.[/]")
    if errores:
        console.print(f"[aviso]No se pudo mover: {cuantos(errores, 'archivo')}.[/]")
    if realizados:
        console.print(f"[pista]Para deshacerlo: {como_se_escribe('ordena deshacer')}[/]")


# ── A qué carpeta va cada archivo ──────────────────────────────────────────


def carpeta_por_tipo(archivo: Path) -> str:
    return NOMBRES[tipo_de(archivo.name)]


def carpeta_por_fecha(agrupar: Agrupar) -> Carpeta:
    """mes → «2026/10 octubre» · año → «2026» · día → «2026-10-26»."""

    def carpeta_de(archivo: Path) -> str:
        fecha = datetime.fromtimestamp(archivo.stat().st_mtime)
        if agrupar is Agrupar.año:
            return f"{fecha.year:04d}"
        if agrupar is Agrupar.día:
            return fecha.strftime("%Y-%m-%d")
        return str(Path(f"{fecha.year:04d}") / f"{fecha.month:02d} {NOMBRE_MES[fecha.month]}")

    return carpeta_de


def nombre_del_tramo(desde: str, hasta: str) -> str:
    """«del 2026-09-01 al 2026-10-31» (o «2026-11-01» si es un solo día): se ordena
    bien y no lleva barras."""
    inicio, fin = rango(desde, hasta)
    assert inicio and fin
    if inicio.date() == fin.date():
        return f"{inicio:%Y-%m-%d}"
    return f"del {inicio:%Y-%m-%d} al {fin:%Y-%m-%d}"


def carpeta_por_letra(archivo: Path) -> str:
    """«Activitat.pdf» → «A» · «Ñandú.jpg» → «Ñ» · «2024 notas.txt» → «0-9».

    Los signos del principio no cuentan («_borrador» va a «B»). Sin letras ni
    números en el nombre (sin contar la extensión) → «Otros».
    """
    for caracter in archivo.stem:
        if caracter in "ñÑ":
            return "Ñ"
        if caracter.isdigit():
            return "0-9"
        letra = sin_tildes(caracter).upper()
        if letra.isalpha():
            return letra
    return "Otros"


def nombre_de_carpeta(texto: str) -> str:
    """Comprueba que sirve como carpeta en Windows. ``ValueError`` si no."""
    nombre = texto.strip().rstrip(". ")
    if not nombre:
        raise ValueError("Falta el nombre de la carpeta.")
    if any(c in nombre for c in '<>:"/\\|?*'):
        raise ValueError(
            f"«{nombre}» no vale como carpeta: no puede llevar < > : \" / \\ | ? *. "
            "Ponle otro con --nombre."
        )
    return nombre


# ── Las opciones ───────────────────────────────────────────────────────────


def tipo(
    carpeta: Path = OPCION_CARPETA,
    destino: Path | None = OPCION_DESTINO,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    desde: str = OPCION_DESDE,
    hasta: str = OPCION_HASTA,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Por tipo: cada archivo a su carpeta (Imagenes, Documentos, Videos…)."""
    ordenar(
        carpeta_por_tipo, carpeta, destino,
        Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
    )


def fecha(
    por: Agrupar = typer.Option(
        Agrupar.mes,
        "--por",
        help="Una carpeta por mes (2026/10 octubre), por año (2026) o por día (2026-10-26).",
        rich_help_panel=AJUSTE,
    ),
    carpeta: Path = OPCION_CARPETA,
    destino: Path | None = OPCION_DESTINO,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    desde: str = OPCION_DESDE,
    hasta: str = OPCION_HASTA,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Por fecha: una carpeta por mes, por año o por día."""
    ordenar(
        carpeta_por_fecha(por), carpeta, destino,
        Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
    )


def tramo(
    desde: str = typer.Argument(..., help=f"Desde qué fecha ({EJEMPLOS_FECHA})."),
    hasta: str = typer.Argument("hoy", help="Hasta qué fecha, incluida."),
    nombre: str = typer.Option(
        "",
        "--nombre",
        help="Nombre de la carpeta; si lo dejas vacío, se llama «del <desde> al <hasta>».",
        show_default=False,
        rich_help_panel=AJUSTE,
    ),
    carpeta: Path = OPCION_CARPETA,
    destino: Path | None = OPCION_DESTINO,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Junta en una carpeta los archivos de unas fechas (de una a otra)."""
    try:
        subcarpeta = nombre_de_carpeta(nombre.strip() or nombre_del_tramo(desde, hasta))
    except ValueError as exc:
        error_console.print(f"[error]{escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(2)
    ordenar(
        lambda archivo: subcarpeta, carpeta, destino,
        Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
    )


def por_nombre(
    texto: str = typer.Argument(..., help="Texto que llevan los nombres (ej.: factura)."),
    nombre: str = typer.Option(
        "",
        "--nombre",
        help="Nombre de la carpeta; si lo dejas vacío, se llama como el texto.",
        show_default=False,
        rich_help_panel=AJUSTE,
    ),
    carpeta: Path = OPCION_CARPETA,
    destino: Path | None = OPCION_DESTINO,
    solo: str = OPCION_SOLO,
    desde: str = OPCION_DESDE,
    hasta: str = OPCION_HASTA,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Por nombre: los que llevan un texto, juntos (factura → factura/)."""
    if not texto.strip():
        error_console.print("[error]Escribe el texto que llevan los nombres (ej.: factura).[/]")
        raise typer.Exit(2)
    try:
        subcarpeta = nombre_de_carpeta(nombre.strip() or texto)
    except ValueError as exc:
        error_console.print(f"[error]{escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(2)
    ordenar(
        lambda archivo: subcarpeta, carpeta, destino,
        Filtro(solo, texto, desde, hasta, recursivo, ocultos), simular, si,
    )


def letra(
    carpeta: Path = OPCION_CARPETA,
    destino: Path | None = OPCION_DESTINO,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    desde: str = OPCION_DESDE,
    hasta: str = OPCION_HASTA,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Por letra: una carpeta por inicial (A, B… y 0-9 para números)."""
    ordenar(
        carpeta_por_letra, carpeta, destino,
        Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
    )


def tipos() -> None:
    """Qué extensiones van a cada carpeta al ordenar por tipo."""
    tabla = crear_tabla(["Carpeta", "Extensiones"])
    for categoria, extensiones_categoria in CATEGORIAS.items():
        tabla.add_row(NOMBRES[categoria], " ".join(sorted(extensiones_categoria)))
    tabla.add_row(NOMBRES["otros"], "(cualquier otra)")
    console.print(tabla)
    console.print("[pista]Los nombres de tipo también valen en --solo: --solo imagenes[/]")


def _borrar_carpetas_vacias(carpetas: set[Path], origenes: set[Path]) -> None:
    """Quita las carpetas que creó ordena y han quedado vacías (nunca una de origen)."""
    for carpeta in sorted(carpetas, key=lambda c: len(c.parts), reverse=True):
        if any(origen == carpeta or carpeta in origen.parents for origen in origenes):
            continue
        try:
            carpeta.rmdir()  # solo funciona si está vacía
        except OSError:
            pass


def deshacer(si: bool = OPCION_SI) -> None:
    """Devuelve a su sitio lo último que ordenaste."""
    acciones = cargar_acciones("ordena")
    if not acciones:
        console.print("[aviso]No hay nada que deshacer.[/]")
        return

    console.print(f"Se devolverían [bold]{cuantos(len(acciones), 'archivo')}[/] a su sitio.")
    if not confirmar("¿Deshacer lo último que ordenaste?", saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return

    devueltos = errores = 0
    creadas: set[Path] = set()
    origenes: set[Path] = set()
    for accion in reversed(acciones):
        origen, destino = Path(accion["origen"]), Path(accion["destino"])
        origenes.add(origen.parent)
        if not destino.exists():
            continue
        try:
            origen.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destino), str(ruta_libre(origen)))
            devueltos += 1
            creadas.update([destino.parent, destino.parent.parent])
        except OSError as exc:
            errores += 1
            error_console.print(
                f"[error]No se pudo devolver[/] {escape(str(destino))}: {escape(str(exc))}",
                soft_wrap=True,
            )

    _borrar_carpetas_vacias(creadas, origenes)
    limpiar_acciones("ordena")
    console.print(f"[ok]{'Devuelto' if devueltos == 1 else 'Devueltos'} {cuantos(devueltos, 'archivo')}.[/]")
    if errores:
        console.print(f"[aviso]No se pudo devolver: {cuantos(errores, 'archivo')}.[/]")


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Ordena una carpeta: por tipo, por fechas, por nombre o por letra.",
        no_args_is_help=True,
    )
    sub.command("tipo", help="Por tipo: Imagenes, Documentos, Videos… cada uno a su carpeta.")(tipo)
    sub.command("fecha", help="Por fecha: una carpeta por mes (2026/10 octubre), año o día.")(fecha)
    sub.command("tramo", help="Junta en una carpeta los archivos de unas fechas (del… al…).")(tramo)
    sub.command("nombre", help="Por nombre: los que llevan un texto, juntos (factura → factura/).")(por_nombre)
    sub.command("letra", help="Por letra: una carpeta por inicial (A, B… y 0-9 para números).")(letra)
    sub.command("tipos", help="Qué extensiones van a cada carpeta de tipo.")(tipos)
    sub.command("deshacer", help="Devuelve a su sitio lo último que ordenaste.")(deshacer)
    app.add_typer(sub, name="ordena")
