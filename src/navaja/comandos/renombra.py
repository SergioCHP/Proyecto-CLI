"""Renombrado masivo de archivos: una opción para cada tarea, sin tener que saber regex.

Todas siguen el mismo camino: eligen los archivos, enseñan «antes → después»,
preguntan [s/n] y renombran (se puede deshacer). Cada opción solo decide cómo se
llama cada archivo nuevo: es una función ``(archivo, n) -> nombre nuevo``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel

from ..comun import (
    HERRAMIENTAS,
    AJUSTE,
    cargar_acciones,
    confirmar,
    cuantos,
    console,
    crear_tabla,
    error_console,
    guardar_acciones,
    limpiar_acciones,
    como_se_escribe,
    ruta_libre,
)
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
    Filtro,
    extensiones,  # noqa: F401  (se reexporta: los tests y otros módulos la usan desde aquí)
    sin_tildes,
)
from ..filtros import seleccionar as seleccionar_filtro

Transformar = Callable[[Path, int], str]
"""Recibe el archivo y su número (1, 2, 3… dentro de su carpeta) y devuelve el nombre nuevo."""

PROHIBIDOS_EN_WINDOWS = set('<>:"/\\|?*')
HUECOS = "{nombre}, {ext}, {n} y {fecha}"


class Orden(str, Enum):
    nombre = "nombre"
    fecha = "fecha"


# ── Opciones y elegir archivos ─────────────────────────────────────────────

OPCION_ORDEN = typer.Option(
    Orden.nombre,
    "--orden",
    help="En qué orden se cuentan: por nombre o por fecha.",
    rich_help_panel=AJUSTE,
)


def seleccionar(
    carpeta: Path,
    solo: str,
    recursivo: bool,
    ocultos: bool,
    orden: Orden = Orden.nombre,
    contiene: str = "",
    desde: str = "",
    hasta: str = "",
) -> list[Path]:
    filtro = Filtro(solo, contiene, desde, hasta, recursivo, ocultos)
    return ordenados(seleccionar_filtro(carpeta, filtro), orden)


def ordenados(archivos: list[Path], orden: Orden) -> list[Path]:
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


def motivo_invalido(nombre: str) -> str:
    """Por qué un nombre no vale, en palabras."""
    malos = sorted({c for c in nombre if c in PROHIBIDOS_EN_WINDOWS})
    if malos:
        return f"no puede llevar {' '.join(malos)}"
    if not nombre.strip():
        return "se queda vacío"
    if nombre.endswith((" ", ".")):
        return "no puede acabar en punto ni en espacio"
    return "nombre no válido"


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

        entrada["nuevo"] = nuevo
        if nuevo == origen.name:
            entrada["estado"], entrada["motivo"] = "igual", "sin cambios"
        elif not nombre_valido(nuevo) or Path(nuevo).name != nuevo:
            entrada["estado"], entrada["motivo"] = "invalido", motivo_invalido(nuevo)
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
        f"[pista]En[/] {escape(str(carpeta.resolve()))}\n"
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
        despues = movimiento.get("nuevo") or Path(movimiento["destino"]).name
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
    filtro: Filtro,
    simular: bool,
    si: bool,
    orden: Orden = Orden.nombre,
    sin_cambios: str = "Ningún nombre cambia.",
) -> None:
    """El camino común: elegir → plan → confirmar → renombrar → guardar para deshacer.

    ``sin_cambios`` es lo que se dice si no cambia ningún nombre.
    """
    if not carpeta.is_dir():
        error_console.print(f"[error]La carpeta no existe:[/] {escape(str(carpeta))}", soft_wrap=True)
        raise typer.Exit(1)

    try:
        archivos = ordenados(seleccionar_filtro(carpeta, filtro), orden)
    except ValueError as exc:
        error_console.print(f"[error]{escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(2)
    if not archivos:
        detalle = filtro.describir()
        extra = f" ({detalle})" if detalle else ""
        console.print(
            f"[aviso]No hay archivos{escape(extra)}[/] [pista](en {escape(str(carpeta.resolve()))})[/]",
            soft_wrap=True,
        )
        return

    try:
        movimientos = planificar(archivos, transformar)
    except ValueError as exc:
        error_console.print(f"[error]{escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(2)

    aplicables = [m for m in movimientos if m["estado"] == "ok"]
    if all(m["estado"] == "igual" for m in movimientos):
        console.print(
            f"[aviso]{escape(sin_cambios)}[/] [pista](en {escape(str(carpeta.resolve()))})[/]",
            soft_wrap=True,
        )
        return
    mostrar_plan(movimientos, carpeta)
    if not aplicables:
        console.print("[aviso]Ningún nombre se puede cambiar: mira la columna «Problema».[/]")
        return
    if simular:
        console.print("[pista]Simulación: no se ha cambiado nada. Sin --simular, lo hace.[/]")
        return
    if not confirmar(f"¿Renombrar {cuantos(len(aplicables), 'archivo')}?", saltar=si, por_defecto=False):
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
    console.print(f"[ok]{'Renombrado' if len(realizados) == 1 else 'Renombrados'} {cuantos(len(realizados), 'archivo')}.[/]")
    if errores:
        console.print(f"[aviso]No se pudo renombrar: {cuantos(errores, 'archivo')}.[/]")
    if realizados:
        console.print(f"[pista]Para deshacerlo: {como_se_escribe('renombra deshacer')}[/]")


# ── Cómo se calcula cada nombre ────────────────────────────────────────────


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
    """Rellena los huecos {nombre}, {ext}, {n} y {fecha}."""
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


def cambiar_texto(archivo: Path, buscar: str, por: str) -> str:
    """«IMG_» → «foto_» en el nombre, sin mirar mayúsculas; la extensión no se toca.

    Se puede escribir el nombre entero con su extensión: «informe.pdf» → «final»
    (o «final.pdf») deja «final.pdf».
    """
    extension = archivo.suffix
    if extension and len(buscar) > len(extension) and buscar.lower().endswith(extension.lower()):
        buscar = buscar[: -len(extension)]
        if por.lower().endswith(extension.lower()):
            por = por[: -len(extension)]
    if not buscar:
        return archivo.name
    nuevo = re.sub(re.escape(buscar), lambda _: por, archivo.stem, flags=re.IGNORECASE)
    return nuevo + extension


def cambiar(
    buscar: str = typer.Argument(
        ..., help="Qué texto del nombre quieres cambiar (ej.: IMG_, o el nombre entero)."
    ),
    por: str = typer.Argument("", help="Texto nuevo. Vacío para borrar el que buscas."),
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
    """Cambia un texto por otro en el nombre."""
    renombrar(
        lambda a, n: cambiar_texto(a, buscar, por),
        carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
        sin_cambios=f"Ningún nombre lleva «{buscar}».",
    )


def delante(
    texto: str = typer.Argument(..., help="Texto que va delante del nombre."),
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
    """Añade texto delante del nombre."""
    renombrar(
        lambda a, n: texto + a.name,
        carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
    )


def detras(
    texto: str = typer.Argument(..., help="Texto que va detrás del nombre (antes de la extensión)."),
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
    """Añade texto detrás del nombre."""
    renombrar(
        lambda a, n: a.stem + texto + a.suffix,
        carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
    )


def numerar(
    nombre: str = typer.Argument(..., help="Nombre común; detrás va el número."),
    separador: str = typer.Option(
        "_", "--separador", help="Lo que va entre el nombre y el número.", rich_help_panel=AJUSTE
    ),
    cifras: int = typer.Option(
        3, "--cifras", min=1, help="Cifras del número (3 → 001, 1 → 1).", rich_help_panel=AJUSTE
    ),
    empieza: int = typer.Option(1, "--empieza", min=0, help="Primer número."),
    orden: Orden = OPCION_ORDEN,
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
    """Pone a todos el mismo nombre con un número."""
    renombrar(
        lambda a, n: f"{nombre}{separador}{n + empieza - 1:0{cifras}d}{a.suffix}",
        carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si, orden,
    )


def fecha(
    formato: str = typer.Option(
        "%Y-%m-%d", "--formato", help="Formato de la fecha (%Y año, %m mes, %d día)."
    ),
    separador: str = typer.Option("_", "--separador", help="Lo que va entre la fecha y el nombre."),
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
    """Pone delante la fecha de modificación de cada archivo."""

    def con_fecha(archivo: Path, n: int) -> str:
        try:
            marca = datetime.fromtimestamp(archivo.stat().st_mtime).strftime(formato) + separador
        except ValueError:
            raise ValueError(
                f"El formato de fecha «{formato}» no vale. Usa %Y (año), %m (mes) y %d (día): "
                "%Y-%m-%d → 2026-10-26."
            ) from None
        # si ya la tiene (por ejecutarlo dos veces), no la repite
        return archivo.name if archivo.name.startswith(marca) else marca + archivo.name

    renombrar(
        con_fecha, carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si
    )


def arreglar(
    separador: str = typer.Option("-", "--separador", help="Lo que sustituye a espacios y símbolos."),
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
    """Minúsculas, sin tildes, sin eñes y sin espacios."""
    renombrar(
        lambda a, n: nombre_arreglado(a.name, separador),
        carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si,
    )


def plantilla(
    formato: str = typer.Argument(
        ..., help="Cómo se llama cada archivo, con huecos: {fecha:%Y-%m-%d}_{n:03}{ext}."
    ),
    orden: Orden = OPCION_ORDEN,
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
    """Tú decides el formato del nombre con huecos."""
    renombrar(
        lambda a, n: formatear_plantilla(formato, a, n),
        carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si, orden,
    )


def error_de_regex(exc: Exception, regex: re.Pattern | None = None) -> str:
    """Los errores más comunes de las expresiones regulares, en castellano."""
    texto = str(exc)
    if m := re.match(r"invalid group reference (\d+)", texto):
        grupos = regex.groups if regex is not None else 0
        return f"usa \\{m[1]}, pero el patrón tiene {cuantos(grupos, 'grupo')} entre paréntesis."
    traducciones = {
        "missing ), unterminated subpattern": "falta cerrar un paréntesis «)».",
        "unbalanced parenthesis": "sobra un paréntesis «)».",
        "nothing to repeat": "un *, + o ? no tiene nada delante.",
        "unterminated character set": "falta cerrar un corchete «]».",
        "bad escape (end of pattern)": "acaba en «\\» y detrás no hay nada.",
    }
    for ingles, castellano in traducciones.items():
        if texto.startswith(ingles):
            return castellano
    return texto


def avanzado(
    patron: str = typer.Argument(..., help="Expresión regular a buscar."),
    reemplazo: str = typer.Argument(..., help="Texto de reemplazo. Usa \\1, \\2… para los grupos."),
    completo: bool = typer.Option(
        False, "--completo", help="Aplicarlo al nombre completo (incluida la extensión)."
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
    """Con expresiones regulares, para casos difíciles."""
    try:
        regex = re.compile(patron)
    except re.error as exc:
        error_console.print(
            f"[error]El patrón no es una expresión regular válida:[/] {escape(error_de_regex(exc))}",
            soft_wrap=True,
        )
        raise typer.Exit(2)

    def con_regex(archivo: Path, n: int) -> str:
        try:
            if completo:
                return regex.sub(reemplazo, archivo.name)
            return regex.sub(reemplazo, archivo.stem) + archivo.suffix
        except (re.error, IndexError) as exc:
            raise ValueError(f"El reemplazo «{reemplazo}» no vale: {error_de_regex(exc, regex)}") from None

    renombrar(
        con_regex, carpeta, Filtro(solo, contiene, desde, hasta, recursivo, ocultos), simular, si
    )


def deshacer(si: bool = OPCION_SI) -> None:
    """Deja los nombres como estaban antes del último renombrado."""
    acciones = cargar_acciones("renombra")
    if not acciones:
        console.print("[aviso]No hay ningún renombrado que deshacer.[/]")
        return

    console.print(f"Se devolverían [bold]{cuantos(len(acciones), 'nombre')}[/] a como estaban.")
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
    console.print(f"[ok]{'Devuelto' if devueltos == 1 else 'Devueltos'} {cuantos(devueltos, 'nombre')}.[/]")
    if errores:
        console.print(f"[aviso]No se pudo devolver: {cuantos(errores, 'nombre')}.[/]")


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
    sub.command("deshacer", help="Deja los nombres como estaban antes del último renombrado.")(deshacer)
    app.add_typer(sub, name="renombra", rich_help_panel=HERRAMIENTAS)
