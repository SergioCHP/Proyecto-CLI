"""navaja comprime: un .zip (o .tar.gz) de una carpeta, sin lo que sobra.

Deja fuera lo mismo que ``arbol`` (.git, .venv, node_modules, __pycache__… y lo del
``.gitignore``): justo lo que no se entrega en una práctica. Enseña antes qué va a meter
y pregunta [s/n]; con ``--simular`` no crea nada. El archivo se escribe primero con un
nombre temporal y solo se le pone el bueno cuando está entero: nunca queda un zip a medias
con el nombre bueno, y nunca se pisa uno que ya existe.
"""

from __future__ import annotations

import os
import tarfile
import zipfile
from enum import Enum
from pathlib import Path

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import (
    AJUSTE,
    ARCHIVOS,
    barra_de_archivos,
    bonita,
    confirmar,
    console,
    cuantos,
    error_console,
    recuadro,
    resumen,
    ruta_libre,
    tamano_legible,
)
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..ignorados import Ignorados, recorrer


class Formato(str, Enum):
    zip = "zip"
    targz = "tar.gz"


def nombre_de(carpeta: Path) -> str:
    resuelta = carpeta.resolve()
    return resuelta.name or resuelta.anchor.strip("\\/:") or "carpeta"


def destino_por_defecto(origen: Path, formato: Formato) -> Path:
    """Al lado de la carpeta (o del archivo), con su nombre: «Proyecto-CLI.zip»."""
    resuelto = origen.resolve()
    base = resuelto.stem if resuelto.is_file() else nombre_de(resuelto)
    return resuelto.parent / f"{base}.{formato.value}"


def que_meter(origen: Path, todo: bool, sin: tuple[str, ...]) -> tuple[list[Path], dict[str, int]]:
    """Los archivos que van dentro y lo que se queda fuera (nombre → cuántos archivos)."""
    if origen.is_file():
        return [origen], {}
    recorrido = recorrer(origen, Ignorados.de_carpeta(origen, todo, sin))
    return recorrido.archivos, recorrido.fuera


def nombre_dentro(origen: Path, archivo: Path) -> str:
    """Dentro del zip todo va en una carpeta con el nombre de la de origen: al
    descomprimirlo sale «Proyecto-CLI/…» y no un montón de archivos sueltos."""
    if origen.is_file():
        return archivo.name
    return f"{nombre_de(origen)}/{archivo.relative_to(origen).as_posix()}"


def escribir(origen: Path, archivos: list[Path], destino: Path, formato: Formato) -> Path:
    """Crea el archivo comprimido en un temporal y le pone el nombre al final (si mientras
    tanto ha aparecido uno con ese nombre, «(1)»). Devuelve dónde ha quedado."""
    temporal = destino.with_name(f".{destino.name}.navaja-parcial")
    try:
        with barra_de_archivos(archivos) as avance:
            if formato is Formato.zip:
                with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipeado:
                    for archivo in archivos:
                        avance(archivo)
                        zipeado.write(archivo, nombre_dentro(origen, archivo))
            else:
                with tarfile.open(temporal, "w:gz") as tar:
                    for archivo in archivos:
                        avance(archivo)
                        tar.add(archivo, nombre_dentro(origen, archivo), recursive=False)
        final = ruta_libre(destino)
        os.replace(temporal, final)
        return final
    except BaseException:
        temporal.unlink(missing_ok=True)
        raise


def comprime(
    carpeta: Path = typer.Argument(Path("."), help="La carpeta (o el archivo) que quieres comprimir."),
    formato: Formato = typer.Option(
        Formato.zip, "--formato", "-f", help="zip (Windows lo abre solo) o tar.gz (Linux).", rich_help_panel=AJUSTE
    ),
    sin: list[str] = typer.Option(
        [], "--sin", help="Dejar fuera también esto (un nombre o *.log); se puede repetir.", rich_help_panel=AJUSTE
    ),
    todo: bool = typer.Option(False, "--todo", help="Meterlo todo: también .git, .venv y lo del .gitignore."),
    destino: Path = typer.Option(
        None, "--destino", "-d", show_default=False,
        help="Una carpeta (o un nombre .zip) donde dejarlo; por defecto, al lado de la carpeta.",
    ),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Crea un .zip o .tar.gz de una carpeta, sin .git, .venv ni lo del .gitignore."""
    origen = carpeta.expanduser()
    if not origen.exists():
        error_console.print(f"[error]✘ No existe {escape(str(carpeta))}.[/]", soft_wrap=True)
        raise typer.Exit(1)
    if destino is not None:
        final = destino.expanduser()
        if not final.name.lower().endswith((".zip", ".tar.gz", ".tgz")):  # es una carpeta
            final = final / destino_por_defecto(origen, formato).name
    else:
        final = destino_por_defecto(origen, formato)
    final = ruta_libre(final)
    archivos, fuera = que_meter(origen, todo, tuple(sin))
    archivos = [a for a in archivos if a.resolve() != final.resolve()]
    if not archivos:
        console.print("[aviso]No hay nada que comprimir (o todo está en lo que se deja fuera).[/]")
        return
    peso = sum(a.stat().st_size for a in archivos)
    filas = [
        ("Comprimir", escape(bonita(origen.resolve()))),
        ("En", f"[acento]{escape(bonita(final))}[/]"),
        ("Dentro", f"{cuantos(len(archivos), 'archivo')} · {tamano_legible(peso)} sin comprimir"),
    ]
    if fuera:
        nombres = sorted(fuera, key=lambda n: -fuera[n])
        texto = ", ".join(nombres[:6]) + (f"… (+{len(nombres) - 6})" if len(nombres) > 6 else "")
        filas.append(("Fuera", f"{escape(texto)} [pista]({cuantos(sum(fuera.values()), 'archivo')}; --todo los mete)[/]"))
    console.print(recuadro("Comprimir", resumen(filas)))
    if simular:
        console.print("[pista]Simulación: no se ha creado nada.[/]")
        return
    if not confirmar("¿Lo creo?", si):
        console.print("[pista]No se ha creado nada.[/]")
        return
    final.parent.mkdir(parents=True, exist_ok=True)
    try:
        final = escribir(origen, archivos, final, formato)
    except KeyboardInterrupt:
        console.print("\n[aviso]Cancelado: no se ha creado nada.[/]")
        raise typer.Exit(1)
    except OSError as error:
        error_console.print(f"[error]✘ No se ha podido crear: {escape(error.strerror or str(error))}[/]")
        raise typer.Exit(1)
    final_peso = final.stat().st_size
    if peso and final_peso < peso:
        ahorro = f" ({100 - round(final_peso * 100 / peso)} % menos)"
    else:
        ahorro = " (no ocupa menos: son archivos pequeños o ya estaban comprimidos)"
    console.print(
        Text.from_markup(f"[ok]✔ Creado {escape(bonita(final))}: {tamano_legible(final_peso)}{ahorro}.[/]"),
        soft_wrap=True,
    )


def registrar(app: typer.Typer) -> None:
    app.command(
        "comprime", help="Crea un .zip de una carpeta sin .git, .venv ni lo que sobra.", rich_help_panel=ARCHIVOS
    )(comprime)
