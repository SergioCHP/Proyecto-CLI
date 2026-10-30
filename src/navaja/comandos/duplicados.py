"""Búsqueda de archivos duplicados por contenido, con papelera recuperable."""

from __future__ import annotations

import hashlib
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

import typer
from rich.markup import escape
from rich.panel import Panel

from ..comun import (
    cargar_acciones,
    confirmar,
    console,
    crear_tabla,
    directorio_datos,
    error_console,
    guardar_acciones,
    iterar_archivos,
    limpiar_acciones,
    ruta_libre,
    tamano_legible,
)

BLOQUE = 1024 * 1024
MUESTRA = 64 * 1024

MULTIPLOS = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024**2,
    "MB": 1024**2,
    "G": 1024**3,
    "GB": 1024**3,
}


class Conservar(str, Enum):
    antiguo = "antiguo"
    reciente = "reciente"
    corto = "corto"


@dataclass
class Grupo:
    """Archivos con el mismo contenido. El primero es el que se conserva."""

    tamano: int
    archivos: list[Path]

    @property
    def original(self) -> Path:
        return self.archivos[0]

    @property
    def sobrantes(self) -> list[Path]:
        return self.archivos[1:]

    @property
    def desperdicio(self) -> int:
        return self.tamano * len(self.sobrantes)


def a_bytes(texto: str) -> int:
    """Convierte textos como ``500K``, ``10MB`` o ``1,5GB`` en bytes."""
    coincide = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]*)\s*", texto)
    unidad = coincide.group(2).upper() if coincide else ""
    if not coincide or unidad not in MULTIPLOS:
        raise ValueError(
            f"Tamaño no válido: «{texto}». Usa por ejemplo 500K, 10MB o 1GB."
        )
    numero = float(coincide.group(1).replace(",", "."))
    return int(numero * MULTIPLOS[unidad])


def huella(ruta: Path, limite: int | None = None) -> str:
    """SHA-256 del archivo completo o solo de sus primeros ``limite`` bytes."""
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        if limite is not None:
            resumen.update(archivo.read(limite))
        else:
            for bloque in iter(lambda: archivo.read(BLOQUE), b""):
                resumen.update(bloque)
    return resumen.hexdigest()


def _agrupar(
    rutas: list[Path], clave: Callable[[Path], str], fallos: list[Path]
) -> list[list[Path]]:
    """Agrupa por ``clave`` y devuelve solo los grupos con más de un archivo."""
    grupos: dict[str, list[Path]] = defaultdict(list)
    for ruta in rutas:
        try:
            grupos[clave(ruta)].append(ruta)
        except OSError:
            fallos.append(ruta)
    return [grupo for grupo in grupos.values() if len(grupo) > 1]


def buscar_duplicados(
    rutas: list[Path],
    minimo: int = 1,
    fallos: list[Path] | None = None,
) -> list[Grupo]:
    """Encuentra archivos con el mismo contenido.

    Va de lo barato a lo caro: primero agrupa por tamaño, después por un
    hash de los primeros 64 KB y solo al final por el hash completo.
    Los archivos que no se pueden leer se añaden a ``fallos``.
    """
    if fallos is None:
        fallos = []

    por_tamano: dict[int, list[Path]] = defaultdict(list)
    vistos: set[tuple[int, int]] = set()
    for ruta in rutas:
        try:
            info = ruta.stat()
        except OSError:
            fallos.append(ruta)
            continue
        if info.st_size < minimo:
            continue
        # Dos enlaces duros al mismo archivo no ocupan el doble: se cuentan una vez.
        inodo = (info.st_dev, info.st_ino)
        if info.st_ino and inodo in vistos:
            continue
        vistos.add(inodo)
        por_tamano[info.st_size].append(ruta)

    grupos: list[Grupo] = []
    for tamano, candidatos in por_tamano.items():
        if len(candidatos) < 2:
            continue
        for parecidos in _agrupar(candidatos, lambda r: huella(r, MUESTRA), fallos):
            if tamano <= MUESTRA:
                iguales = [parecidos]
            else:
                iguales = _agrupar(parecidos, huella, fallos)
            grupos.extend(Grupo(tamano, sorted(grupo)) for grupo in iguales)

    grupos.sort(key=lambda g: (-g.desperdicio, str(g.original)))
    return grupos


def _fecha(ruta: Path) -> float:
    try:
        return ruta.stat().st_mtime
    except OSError:
        return 0.0


def ordenar_grupo(archivos: list[Path], criterio: Conservar) -> list[Path]:
    """Pone primero el archivo que se conserva según el criterio."""
    if criterio is Conservar.reciente:
        return sorted(archivos, key=lambda r: (-_fecha(r), len(str(r)), str(r)))
    if criterio is Conservar.corto:
        return sorted(archivos, key=lambda r: (len(str(r)), _fecha(r), str(r)))
    return sorted(archivos, key=lambda r: (_fecha(r), len(str(r)), str(r)))


def _papelera() -> Path:
    return directorio_datos() / "papelera"


def _relativa(ruta: Path, base: Path) -> str:
    try:
        return str(ruta.relative_to(base))
    except ValueError:
        return str(ruta)


def _escanear(
    ruta: Path,
    recursivo: bool,
    ocultos: bool,
    minimo: str,
    conservar: Conservar,
) -> list[Grupo]:
    if not ruta.is_dir():
        error_console.print(f"[red]La carpeta no existe:[/] {escape(str(ruta))}")
        raise typer.Exit(1)
    try:
        minimo_bytes = a_bytes(minimo)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--minimo")

    datos = directorio_datos().resolve()
    fallos: list[Path] = []
    with console.status("Comparando contenidos…"):
        archivos = [
            archivo
            for archivo in iterar_archivos(ruta, recursivo, ocultos)
            if not archivo.resolve().is_relative_to(datos)
        ]
        grupos = buscar_duplicados(archivos, minimo_bytes, fallos)

    if fallos:
        error_console.print(
            f"[yellow]{len(fallos)} archivos no se pudieron leer y se han ignorado.[/]"
        )
    for grupo in grupos:
        grupo.archivos = ordenar_grupo(grupo.archivos, conservar)
    return grupos


def _mostrar(grupos: list[Grupo], ruta: Path, limite: int) -> None:
    sobrantes = sum(len(grupo.sobrantes) for grupo in grupos)
    recuperable = sum(grupo.desperdicio for grupo in grupos)
    console.print(
        Panel(
            f"Grupos: [bold]{len(grupos)}[/]  ·  "
            f"Copias sobrantes: [bold]{sobrantes}[/]  ·  "
            f"Recuperable: [bold green]{tamano_legible(recuperable)}[/]",
            title="Duplicados",
            border_style="cyan",
        )
    )

    tabla = crear_tabla(["#", "Tamaño", "Archivos"])
    for indice, grupo in enumerate(grupos[:limite], start=1):
        lineas = [f"[green]✔ {escape(_relativa(grupo.original, ruta))}[/]"]
        lineas += [
            f"[red]✘ {escape(_relativa(archivo, ruta))}[/]"
            for archivo in grupo.sobrantes
        ]
        tabla.add_row(
            str(indice),
            f"{tamano_legible(grupo.tamano)} × {len(grupo.archivos)}",
            "\n".join(lineas),
        )
    console.print(tabla)
    if len(grupos) > limite:
        console.print(
            f"[dim]Mostrando {limite} de {len(grupos)} grupos. "
            "Usa --mayores para ver más.[/]"
        )
    console.print("[dim]✔ se conserva  ·  ✘ copia sobrante[/]")


def _sin_duplicados(recursivo: bool) -> None:
    console.print("[green]No hay archivos duplicados.[/]")
    if not recursivo:
        console.print(
            "[dim]Solo he mirado esta carpeta; usa -r para incluir subcarpetas.[/]"
        )


OPCION_RECURSIVO = typer.Option(False, "--recursivo", "-r", help="Incluir subcarpetas.")
OPCION_OCULTOS = typer.Option(False, "--ocultos", help="Incluir archivos ocultos.")
OPCION_MINIMO = typer.Option(
    "1B",
    "--minimo",
    "-m",
    help="Ignora archivos más pequeños (500K, 10MB…). Con 0 entran los vacíos.",
    show_default=True,
)
OPCION_CONSERVAR = typer.Option(
    Conservar.antiguo,
    "--conservar",
    "-c",
    help="Cuál se queda: el más antiguo, el más reciente o el de ruta más corta.",
)


def buscar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta donde buscar.", show_default=True
    ),
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    minimo: str = OPCION_MINIMO,
    conservar: Conservar = OPCION_CONSERVAR,
    mayores: int = typer.Option(
        20, "--mayores", "-n", help="Grupos a mostrar.", show_default=True
    ),
) -> None:
    """Muestra los archivos repetidos sin tocar nada."""
    grupos = _escanear(ruta, recursivo, ocultos, minimo, conservar)
    if not grupos:
        _sin_duplicados(recursivo)
        return
    _mostrar(grupos, ruta, mayores)
    console.print("[dim]Para quitar las copias: navaja duplicados borrar …[/]")


def borrar(
    ruta: Path = typer.Argument(
        Path("."), help="Carpeta donde buscar.", show_default=True
    ),
    recursivo: bool = OPCION_RECURSIVO,
    ocultos: bool = OPCION_OCULTOS,
    minimo: str = OPCION_MINIMO,
    conservar: Conservar = OPCION_CONSERVAR,
    si: bool = typer.Option(False, "--si", "-s", help="No pide confirmación."),
) -> None:
    """Mueve las copias sobrantes a la papelera de navaja (recuperable)."""
    grupos = _escanear(ruta, recursivo, ocultos, minimo, conservar)
    if not grupos:
        _sin_duplicados(recursivo)
        return

    _mostrar(grupos, ruta, limite=len(grupos))
    total = sum(len(grupo.sobrantes) for grupo in grupos)
    if not confirmar(
        f"¿Mover {total} copias a la papelera de navaja?", saltar=si, por_defecto=False
    ):
        console.print("[yellow]Cancelado.[/]")
        return

    carpeta = _papelera() / datetime.now().strftime("%Y%m%d-%H%M%S")
    realizados: list[dict] = []
    liberado = 0
    errores = 0
    for grupo in grupos:
        if not grupo.original.exists():
            error_console.print(
                f"[yellow]Me salto un grupo: ya no existe "
                f"{escape(str(grupo.original))}[/]"
            )
            continue
        for copia in grupo.sobrantes:
            try:
                carpeta.mkdir(parents=True, exist_ok=True)
                destino = ruta_libre(carpeta / copia.name)
                shutil.move(str(copia), str(destino))
                realizados.append({"origen": str(copia), "destino": str(destino)})
                liberado += grupo.tamano
            except OSError as exc:
                errores += 1
                error_console.print(
                    f"[red]No se pudo mover[/] {escape(str(copia))}: {escape(str(exc))}"
                )

    if realizados:
        guardar_acciones("duplicados", cargar_acciones("duplicados") + realizados)
    console.print(
        f"[green]Movidas {len(realizados)} copias "
        f"({tamano_legible(liberado)}) a la papelera.[/]"
    )
    if errores:
        console.print(f"[yellow]{errores} copias no se pudieron mover.[/]")
    if realizados:
        console.print(
            "[dim]Recuperarlas: navaja duplicados restaurar  ·  "
            "Liberar el espacio: navaja duplicados vaciar[/]"
        )


def restaurar(
    si: bool = typer.Option(False, "--si", "-s", help="No pide confirmación."),
) -> None:
    """Devuelve a su sitio todo lo que hay en la papelera."""
    acciones = cargar_acciones("duplicados")
    pendientes = [a for a in acciones if Path(a["destino"]).exists()]
    if not pendientes:
        console.print("[yellow]No hay nada en la papelera que restaurar.[/]")
        return

    console.print(f"Se devolverían [bold]{len(pendientes)}[/] archivos a su sitio.")
    if not confirmar("¿Restaurarlos?", saltar=si, por_defecto=False):
        console.print("[yellow]Cancelado.[/]")
        return

    devueltos = 0
    errores = 0
    for accion in reversed(pendientes):
        origen = Path(accion["origen"])
        destino = Path(accion["destino"])
        try:
            origen.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destino), str(ruta_libre(origen)))
            devueltos += 1
        except OSError as exc:
            errores += 1
            error_console.print(
                f"[red]No se pudo devolver[/] {escape(str(destino))}: {escape(str(exc))}"
            )

    for carpeta in {Path(a["destino"]).parent for a in pendientes}:
        try:
            carpeta.rmdir()
        except OSError:
            pass

    if errores:
        console.print(f"[yellow]{errores} archivos no se pudieron devolver.[/]")
    else:
        limpiar_acciones("duplicados")
    console.print(f"[green]Restaurados {devueltos} archivos.[/]")


def vaciar(
    si: bool = typer.Option(False, "--si", "-s", help="No pide confirmación."),
) -> None:
    """Borra para siempre lo que hay en la papelera de navaja."""
    papelera = _papelera()
    archivos = [f for f in papelera.rglob("*") if f.is_file()] if papelera.exists() else []
    if not archivos:
        console.print("[green]La papelera de navaja está vacía.[/]")
        return

    total = sum(archivo.stat().st_size for archivo in archivos)
    console.print(
        f"La papelera tiene [bold]{len(archivos)}[/] archivos "
        f"([bold]{tamano_legible(total)}[/]) en {escape(str(papelera))}"
    )
    if not confirmar(
        "¿Borrarlos para siempre? No se podrá deshacer.", saltar=si, por_defecto=False
    ):
        console.print("[yellow]Cancelado.[/]")
        return

    try:
        shutil.rmtree(papelera)
    except OSError as exc:
        error_console.print(f"[red]No se pudo vaciar del todo:[/] {escape(str(exc))}")
        raise typer.Exit(1)
    limpiar_acciones("duplicados")
    console.print(f"[green]Liberados {tamano_legible(total)}.[/]")


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Busca archivos repetidos por contenido y los quita sin perder nada.",
        no_args_is_help=True,
    )
    sub.command("buscar", help="Muestra los duplicados sin tocar nada.")(buscar)
    sub.command("borrar", help="Mueve las copias a la papelera de navaja.")(borrar)
    sub.command("restaurar", help="Devuelve a su sitio lo que hay en la papelera.")(
        restaurar
    )
    sub.command("vaciar", help="Borra para siempre la papelera de navaja.")(vaciar)
    app.add_typer(sub, name="duplicados")
