"""Renombrado masivo de archivos: una opción para cada tarea, sin tener que saber regex.

Todas siguen el mismo camino: eligen los archivos, enseñan «antes → después»,
preguntan [s/n] y renombran (se puede deshacer). Cada opción solo decide cómo se
llama cada archivo nuevo: es una función ``(archivo, n) -> nombre nuevo``.
"""

from __future__ import annotations

import re
import unicodedata
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
    console,
    crear_tabla,
    error_console,
    guardar_acciones,
    iterar_archivos,
    limpiar_acciones,
    ruta_libre,
)

Transformar = Callable[[Path, int], str]
"""Recibe el archivo y su número (1, 2, 3… dentro de su carpeta) y devuelve el nombre nuevo."""

PROHIBIDOS_EN_WINDOWS = set('<>:"/\\|?*')
HUECOS = "{nombre}, {ext}, {n} y {fecha}"


class Orden(str, Enum):
    nombre = "nombre"
    fecha = "fecha"


# ── Opciones comunes ───────────────────────────────────────────────────────

OPCION_CARPETA = typer.Option(
    Path("."), "--carpeta", "-c", help="Carpeta con los archivos (por defecto, la actual)."
)
OPCION_SOLO = typer.Option(
    "", "--solo", help="Solo estas extensiones, separadas por comas: jpg,png.", show_default=False
)
OPCION_CONTIENE = typer.Option(
    "",
    "--contiene",
    help="Solo los archivos cuyo nombre lleva este texto (sin mirar mayúsculas).",
    show_default=False,
    rich_help_panel=AJUSTE,
)
OPCION_RECURSIVO = typer.Option(False, "--recursivo", "-r", help="Incluir subcarpetas.")
OPCION_OCULTOS = typer.Option(False, "--ocultos", help="Incluir archivos ocultos.")
OPCION_SIMULAR = typer.Option(
    False, "--simular", help="Solo enseña cómo quedarían los nombres, sin cambiar nada."
)
OPCION_SI = typer.Option(False, "--si", "-s", help="No pide confirmación.")
OPCION_ORDEN = typer.Option(
    Orden.nombre,
    "--orden",
    help="En qué orden se cuentan: por nombre o por fecha.",
    rich_help_panel=AJUSTE,
)


# ── Elegir archivos ────────────────────────────────────────────────────────


def extensiones(solo: str) -> set[str]:
    """``"jpg, .PNG,*.gif"`` → ``{".jpg", ".png", ".gif"}``."""
    resultado = set()
    for parte in solo.replace(";", ",").split(","):
        parte = parte.strip().lower().lstrip("*")
        if parte:
            resultado.add(parte if parte.startswith(".") else f".{parte}")
    return resultado


def seleccionar(
    carpeta: Path,
    solo: str,
    recursivo: bool,
    ocultos: bool,
    orden: Orden = Orden.nombre,
    contiene: str = "",
) -> list[Path]:
    exts = extensiones(solo)
    texto = contiene.lower()
    archivos = [
        a
        for a in iterar_archivos(carpeta, recursivo, ocultos)
        if (not exts or a.suffix.lower() in exts) and texto in a.name.lower()
    ]
    if orden is Orden.fecha:
        return sorted(archivos, key=lambda a: (str(a.parent), a.stat().st_mtime, a.name.lower()))
    return sorted(archivos, key=lambda a: (str(a.parent), a.name.lower()))


# ── Planificar ─────────────────────────────────────────────────────────────


def nombre_valido(nombre: str) -> bool:
    """Vale en Windows, macOS y Linux."""
    return (
        bool(nombre.strip())
        and nombre not in {".", ".."}
        and not any(c in PROHIBIDOS_EN_WINDOWS for c in nombre)
        and not nombre.endswith((" ", "."))
    )


def planificar(archivos: list[Path], transformar: Transformar) -> list[dict]:
    """Calcula el nombre nuevo de cada archivo y marca lo que no se puede hacer.

    Estados: ``ok`` (se renombra), ``igual`` (no cambia), ``invalido`` (el nombre
    no vale) y ``conflicto`` (otro archivo ya se llama así o se llamaría igual).
    Lanza ``ValueError`` si ``transformar`` no puede calcular un nombre.
    """
    movimientos: list[dict] = []
    reservados: set[str] = set()
    contadores: dict[Path, int] = {}

    for origen in archivos:
        n = contadores[origen.parent] = contadores.get(origen.parent, 0) + 1
        nuevo = transformar(origen, n)
        destino = origen.parent / nuevo
        entrada = {"origen": str(origen), "destino": str(destino), "estado": "ok", "motivo": ""}
        solo_mayusculas = str(destino).lower() == str(origen).lower()

        if nuevo == origen.name:
            entrada["estado"], entrada["motivo"] = "igual", "sin cambios"
        elif not nombre_valido(nuevo) or Path(nuevo).name != nuevo:
            entrada["estado"], entrada["motivo"] = "invalido", "nombre no válido"
        elif str(destino).lower() in reservados:
            entrada["estado"], entrada["motivo"] = "conflicto", "dos archivos acabarían igual"
        elif destino.exists() and not (solo_mayusculas and destino.samefile(origen)):
            entrada["estado"], entrada["motivo"] = "conflicto", "ya existe un archivo con ese nombre"
        else:
            reservados.add(str(destino).lower())
        movimientos.append(entrada)
    return movimientos


def mostrar_plan(movimientos: list[dict], carpeta: Path, limite: int = 200) -> None:
    cambian = [m for m in movimientos if m["estado"] == "ok"]
    problemas = [m for m in movimientos if m["estado"] in ("invalido", "conflicto")]
    iguales = len(movimientos) - len(cambian) - len(problemas)

    resumen = (
        f"[bold]{len(movimientos)}[/] archivo{'' if len(movimientos) == 1 else 's'} · "
        f"[ok]{len(cambian)} {'cambia' if len(cambian) == 1 else 'cambian'}[/]"
    )
    if iguales:
        resumen += f" · [pista]{iguales} se {'queda' if iguales == 1 else 'quedan'} igual[/]"
    if problemas:
        resumen += f" · [error]{len(problemas)} con problemas[/]"
    console.print(Panel(resumen, title="Renombrar", border_style="marco", expand=False))

    filas = cambian + problemas
    if not filas:
        return
    tabla = crear_tabla(["Antes", "Después"] + (["Problema"] if problemas else []))
    for movimiento in filas[:limite]:
        origen = Path(movimiento["origen"])
        try:
            antes = str(origen.relative_to(carpeta))
        except ValueError:
            antes = origen.name
        despues = Path(movimiento["destino"]).name
        fila = [escape(antes), f"[ok]{escape(despues)}[/]"]
        if problemas:
            ok = movimiento["estado"] == "ok"
            fila.append("" if ok else f"[error]{escape(movimiento['motivo'])}[/]")
        tabla.add_row(*fila)
    console.print(tabla)
    if len(filas) > limite:
        console.print(f"[pista]Mostrando {limite} de {len(filas)}.[/]")


# ── Hacerlo ────────────────────────────────────────────────────────────────


def renombrar(
    transformar: Transformar,
    carpeta: Path,
    solo: str,
    recursivo: bool,
    ocultos: bool,
    simular: bool,
    si: bool,
    orden: Orden = Orden.nombre,
    contiene: str = "",
) -> None:
    """El camino común: elegir → plan → confirmar → renombrar → guardar para deshacer."""
    if not carpeta.is_dir():
        error_console.print(f"[error]La carpeta no existe:[/] {escape(str(carpeta))}", soft_wrap=True)
        raise typer.Exit(1)

    archivos = seleccionar(carpeta, solo, recursivo, ocultos, orden, contiene)
    if not archivos:
        extra = f" con extensión {', '.join(sorted(extensiones(solo)))}" if solo else ""
        extra += f" que contengan «{contiene}»" if contiene else ""
        console.print(f"[aviso]No hay archivos{escape(extra)} en esta carpeta.[/]")
        return

    try:
        movimientos = planificar(archivos, transformar)
    except ValueError as exc:
        error_console.print(f"[error]{escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(2)

    mostrar_plan(movimientos, carpeta)
    aplicables = [m for m in movimientos if m["estado"] == "ok"]
    if not aplicables:
        console.print("[aviso]Ningún nombre cambia.[/]")
        return
    if simular:
        console.print("[pista]Simulación: no se ha cambiado nada. Sin --simular, lo hace.[/]")
        return
    if not confirmar(f"¿Renombrar {len(aplicables)} archivos?", saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return

    realizados: list[dict] = []
    errores = 0
    for movimiento in aplicables:
        origen, destino = Path(movimiento["origen"]), Path(movimiento["destino"])
        try:
            origen.rename(destino)
            realizados.append({"origen": str(origen), "destino": str(destino)})
        except OSError as exc:
            errores += 1
            error_console.print(
                f"[error]No se pudo renombrar[/] {escape(str(origen))}: {escape(str(exc))}",
                soft_wrap=True,
            )

    if realizados:
        guardar_acciones("renombra", realizados)
    console.print(f"[ok]Renombrados {len(realizados)} archivos.[/]")
    if errores:
        console.print(f"[aviso]{errores} archivos no se pudieron renombrar.[/]")
    if realizados:
        console.print("[pista]Para deshacerlo: renombra deshacer[/]")


# ── Cómo se calcula cada nombre ────────────────────────────────────────────


def sin_tildes(texto: str) -> str:
    """«Año Ñandú» → «Ano Nandu»."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def nombre_arreglado(nombre: str, separador: str = "-") -> str:
    """«Foto Año (1).JPG» → «foto-ano-1.jpg»."""
    ruta = Path(nombre)
    base = sin_tildes(ruta.stem).lower()
    base = re.sub(r"[^a-z0-9._-]+", separador, base)
    if separador:
        base = re.sub(f"{re.escape(separador)}{{2,}}", separador, base)
    base = base.strip(f"{separador} .")
    return (base or "archivo") + sin_tildes(ruta.suffix).lower()


def formatear_plantilla(plantilla: str, archivo: Path, n: int) -> str:
    """Rellena los huecos {nombre}, {ext}, {n} y {fecha} (mismos que acciones.json)."""
    fecha = datetime.fromtimestamp(archivo.stat().st_mtime)
    try:
        return plantilla.format(fecha=fecha, n=n, ext=archivo.suffix.lower(), nombre=archivo.stem)
    except KeyError as exc:
        raise ValueError(
            f"La plantilla tiene un hueco que no existe: {{{exc.args[0]}}}. Usa {HUECOS}."
        ) from None
    except (ValueError, IndexError) as exc:
        raise ValueError(f"La plantilla no es válida ({exc}). Usa {HUECOS}.") from None


# ── Las opciones ───────────────────────────────────────────────────────────


def cambiar(
    buscar: str = typer.Argument(..., help="Texto que buscas en el nombre (sin contar la extensión)."),
    por: str = typer.Argument("", help="Texto nuevo. Vacío para borrar el que buscas."),
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Cambia un texto por otro en el nombre."""
    renombrar(
        lambda a, n: a.stem.replace(buscar, por) + a.suffix,
        carpeta, solo, recursivo, ocultos, simular, si, contiene=contiene,
    )


def delante(
    texto: str = typer.Argument(..., help="Texto que va delante del nombre."),
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Añade texto delante del nombre."""
    renombrar(
        lambda a, n: texto + a.name,
        carpeta, solo, recursivo, ocultos, simular, si, contiene=contiene,
    )


def detras(
    texto: str = typer.Argument(..., help="Texto que va detrás del nombre (antes de la extensión)."),
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Añade texto detrás del nombre."""
    renombrar(
        lambda a, n: a.stem + texto + a.suffix,
        carpeta, solo, recursivo, ocultos, simular, si, contiene=contiene,
    )


def numerar(
    nombre: str = typer.Argument(..., help="Nombre común; detrás va el número."),
    separador: str = typer.Option(
        "_", "--separador", help="Lo que va entre el nombre y el número.", rich_help_panel=AJUSTE
    ),
    cifras: int = typer.Option(
        3, "--cifras", help="Cifras del número (3 → 001, 1 → 1).", rich_help_panel=AJUSTE
    ),
    desde: int = typer.Option(1, "--desde", help="Primer número."),
    orden: Orden = OPCION_ORDEN,
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Pone a todos el mismo nombre con un número."""
    if cifras < 1 or desde < 0:
        raise typer.BadParameter("--cifras tiene que ser 1 o más y --desde, 0 o más.")
    renombrar(
        lambda a, n: f"{nombre}{separador}{n + desde - 1:0{cifras}d}{a.suffix}",
        carpeta, solo, recursivo, ocultos, simular, si, orden, contiene=contiene,
    )


def fecha(
    formato: str = typer.Option(
        "%Y-%m-%d", "--formato", help="Formato de la fecha (%Y año, %m mes, %d día)."
    ),
    separador: str = typer.Option("_", "--separador", help="Lo que va entre la fecha y el nombre."),
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Pone delante la fecha de modificación de cada archivo."""

    def con_fecha(archivo: Path, n: int) -> str:
        marca = datetime.fromtimestamp(archivo.stat().st_mtime).strftime(formato) + separador
        # si ya la tiene (por ejecutarlo dos veces), no la repite
        return archivo.name if archivo.name.startswith(marca) else marca + archivo.name

    renombrar(con_fecha, carpeta, solo, recursivo, ocultos, simular, si, contiene=contiene)


def arreglar(
    separador: str = typer.Option("-", "--separador", help="Lo que sustituye a espacios y símbolos."),
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Minúsculas, sin tildes, sin eñes y sin espacios."""
    renombrar(
        lambda a, n: nombre_arreglado(a.name, separador),
        carpeta, solo, recursivo, ocultos, simular, si, contiene=contiene,
    )


def plantilla(
    formato: str = typer.Argument(
        ..., help="Cómo se llama cada archivo, con huecos: {fecha:%Y-%m-%d}_{n:03}{ext}."
    ),
    orden: Orden = OPCION_ORDEN,
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Tú decides el formato del nombre con huecos."""
    renombrar(
        lambda a, n: formatear_plantilla(formato, a, n),
        carpeta, solo, recursivo, ocultos, simular, si, orden, contiene=contiene,
    )


def avanzado(
    patron: str = typer.Argument(..., help="Expresión regular a buscar."),
    reemplazo: str = typer.Argument(..., help="Texto de reemplazo. Usa \\1, \\2… para los grupos."),
    completo: bool = typer.Option(
        False, "--completo", help="Aplicarlo al nombre completo (incluida la extensión)."
    ),
    carpeta: Path = OPCION_CARPETA,
    solo: str = OPCION_SOLO,
    contiene: str = OPCION_CONTIENE,
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Con expresiones regulares, para casos difíciles."""
    try:
        regex = re.compile(patron)
    except re.error as exc:
        error_console.print(f"[error]Expresión regular inválida:[/] {escape(str(exc))}")
        raise typer.Exit(2)

    def con_regex(archivo: Path, n: int) -> str:
        if completo:
            return regex.sub(reemplazo, archivo.name)
        return regex.sub(reemplazo, archivo.stem) + archivo.suffix

    renombrar(con_regex, carpeta, solo, recursivo, ocultos, simular, si, contiene=contiene)


def deshacer(si: bool = OPCION_SI) -> None:
    """Revierte el último renombrado."""
    acciones = cargar_acciones("renombra")
    if not acciones:
        console.print("[aviso]No hay ningún renombrado que deshacer.[/]")
        return

    console.print(f"Se devolverían [bold]{len(acciones)}[/] nombres.")
    if not confirmar("¿Deshacer el último renombrado?", saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return

    devueltos = errores = 0
    for accion in reversed(acciones):
        origen, destino = Path(accion["origen"]), Path(accion["destino"])
        if not destino.exists():
            continue
        try:
            destino.rename(ruta_libre(origen) if str(origen).lower() != str(destino).lower() else origen)
            devueltos += 1
        except OSError as exc:
            errores += 1
            error_console.print(
                f"[error]No se pudo devolver[/] {escape(str(destino))}: {escape(str(exc))}",
                soft_wrap=True,
            )

    limpiar_acciones("renombra")
    console.print(f"[ok]Restaurados {devueltos} nombres.[/]")
    if errores:
        console.print(f"[aviso]{errores} nombres no se pudieron restaurar.[/]")


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Renombra archivos en masa: cambiar texto, numerar, poner la fecha…",
        no_args_is_help=True,
    )
    sub.command("cambiar", help="Cambia un texto por otro (IMG_1234.jpg → foto_1234.jpg).")(cambiar)
    sub.command("delante", help="Añade texto delante (informe.pdf → 2026_informe.pdf).")(delante)
    sub.command("detras", help="Añade texto detrás (informe.pdf → informe_v2.pdf).")(detras)
    sub.command("numerar", help="Un nombre y un número (playa_001.jpg, playa_002.jpg…).")(numerar)
    sub.command("fecha", help="Pone la fecha delante (IMG_1.jpg → 2026-10-26_IMG_1.jpg).")(fecha)
    sub.command("arreglar", help="Minúsculas, sin tildes ni espacios (Foto Año.JPG → foto-ano.jpg).")(
        arreglar
    )
    sub.command("plantilla", help="Tú decides el formato con huecos ({fecha}_{n:03}{ext}).")(plantilla)
    sub.command("avanzado", help="Con expresiones regulares, para casos difíciles.")(avanzado)
    sub.command("deshacer", help="Revierte el último renombrado.")(deshacer)
    app.add_typer(sub, name="renombra")
