"""Utilidades compartidas por todos los comandos."""

from __future__ import annotations

import fnmatch
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from rich.theme import Theme

TEMAS: dict[str, dict[str, str]] = {
    "clasico": {
        "ok": "green",
        "error": "red",
        "aviso": "yellow",
        "pista": "dim",
        "acento": "cyan",
        "titulo": "bold cyan",
        "logro": "bold green",
        "marco": "cyan",
        "borde": "dim",
    },
    "morado": {
        "ok": "#98c379",
        "error": "#e06c75",
        "aviso": "#e5c07b",
        "pista": "#7f848e",
        "acento": "#c678dd",
        "titulo": "bold #c678dd",
        "logro": "bold #98c379",
        "marco": "#c678dd",
        "borde": "#5c4a72",
    },
    "terminal": {
        "ok": "bright_green",
        "error": "bold red",
        "aviso": "yellow",
        "pista": "green4",
        "acento": "green",
        "titulo": "bold bright_green",
        "logro": "bold bright_green",
        "marco": "green",
        "borde": "dark_green",
    },
    "pastel": {
        "ok": "#b5e8b0",
        "error": "#f4a6a6",
        "aviso": "#f6d6a8",
        "pista": "#9a9aa8",
        "acento": "#a8c8f0",
        "titulo": "bold #c5b3e6",
        "logro": "bold #b5e8b0",
        "marco": "#c5b3e6",
        "borde": "#9a9aa8",
    },
}
TEMA_POR_DEFECTO = "clasico"
CONFIG_POR_DEFECTO = {"nombre": "Sergio", "tema": TEMA_POR_DEFECTO}

console = Console(theme=Theme(TEMAS[TEMA_POR_DEFECTO]))
error_console = Console(stderr=True, theme=Theme(TEMAS[TEMA_POR_DEFECTO]))

UNIDADES = ("B", "KB", "MB", "GB", "TB", "PB")


def tamano_legible(numero: float) -> str:
    """Devuelve un tamaño en bytes formateado de forma legible."""
    numero = float(numero)
    for unidad in UNIDADES:
        if numero < 1024 or unidad == UNIDADES[-1]:
            if unidad == "B":
                return f"{int(numero)} B"
            return f"{numero:.1f} {unidad}"
        numero /= 1024
    return f"{numero:.1f} PB"


def directorio_datos() -> Path:
    """Carpeta donde Navaja guarda su estado (notas, deshacer, etc.).

    La variable de entorno ``NAVAJA_DATOS`` la sustituye por otra carpeta.
    """
    propia = os.environ.get("NAVAJA_DATOS")
    if propia:
        destino = Path(propia)
        destino.mkdir(parents=True, exist_ok=True)
        return destino
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    destino = base / "navaja"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def cargar_config(ruta: Path | None = None) -> dict[str, str]:
    """Lee la configuración del usuario; lo que falte o sea inválido toma el valor por defecto."""
    ruta = ruta or directorio_datos() / "config.json"
    config = dict(CONFIG_POR_DEFECTO)
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    if isinstance(datos, dict):
        for clave in config:
            if isinstance(datos.get(clave), str) and datos[clave].strip():
                config[clave] = datos[clave].strip()
    if config["tema"] not in TEMAS:
        config["tema"] = TEMA_POR_DEFECTO
    return config


def guardar_config(config: dict[str, str], ruta: Path | None = None) -> None:
    ruta = ruta or directorio_datos() / "config.json"
    ruta.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def aplicar_tema(nombre: str) -> None:
    """Cambia los colores de ``console`` y ``error_console``."""
    estilos = TEMAS.get(nombre, TEMAS[TEMA_POR_DEFECTO])
    for consola in (console, error_console):
        consola.push_theme(Theme(estilos))


def confirmar(mensaje: str, saltar: bool = False, por_defecto: bool = False) -> bool:
    """Pide confirmación salvo que se haya pasado ``--si``."""
    if saltar:
        return True
    return Confirm.ask(mensaje, default=por_defecto, console=console)


def ruta_libre(destino: Path) -> Path:
    """Devuelve una ruta que no exista, añadiendo un sufijo numérico."""
    if not destino.exists():
        return destino
    base = destino.stem
    sufijo = destino.suffix
    indice = 1
    while True:
        candidato = destino.with_name(f"{base} ({indice}){sufijo}")
        if not candidato.exists():
            return candidato
        indice += 1


def es_oculto(ruta: Path) -> bool:
    return ruta.name.startswith(".")


def iterar_archivos(
    ruta: Path,
    recursivo: bool = False,
    ocultos: bool = False,
    patron: str = "*",
) -> list[Path]:
    """Lista archivos (sin seguir enlaces) filtrando por glob y ocultos."""
    encontrados: list[Path] = []

    if not recursivo:
        try:
            entradas = sorted(ruta.iterdir())
        except OSError:
            return encontrados
        for entrada in entradas:
            if not ocultos and es_oculto(entrada):
                continue
            try:
                if (
                    entrada.is_file()
                    and not entrada.is_symlink()
                    and fnmatch.fnmatch(entrada.name, patron)
                ):
                    encontrados.append(entrada)
            except OSError:
                continue
        return encontrados

    for actual, dirs, archivos in os.walk(ruta):
        if not ocultos:
            dirs[:] = [nombre for nombre in dirs if not nombre.startswith(".")]
        for nombre in sorted(archivos):
            if not ocultos and nombre.startswith("."):
                continue
            if not fnmatch.fnmatch(nombre, patron):
                continue
            candidato = Path(actual) / nombre
            try:
                if candidato.is_file() and not candidato.is_symlink():
                    encontrados.append(candidato)
            except OSError:
                continue
    return encontrados


def crear_tabla(columnas: list[str], titulo: str | None = None) -> Table:
    tabla = Table(title=titulo, header_style="titulo", border_style="borde", expand=False)
    for columna in columnas:
        tabla.add_column(columna, overflow="fold")
    return tabla


def guardar_acciones(nombre: str, acciones: list[dict]) -> None:
    """Guarda el registro de la última operación para poder deshacerla."""
    ruta = directorio_datos() / f"{nombre}_deshacer.json"
    datos = {
        "cuando": datetime.now().isoformat(timespec="seconds"),
        "acciones": acciones,
    }
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def cargar_acciones(nombre: str) -> list[dict]:
    ruta = directorio_datos() / f"{nombre}_deshacer.json"
    if not ruta.exists():
        return []
    try:
        return json.loads(ruta.read_text(encoding="utf-8")).get("acciones", [])
    except (OSError, json.JSONDecodeError):
        return []


def limpiar_acciones(nombre: str) -> None:
    ruta = directorio_datos() / f"{nombre}_deshacer.json"
    ruta.unlink(missing_ok=True)


def editar_texto(texto_inicial: str = "") -> str:
    """Abre el editor del usuario con un texto temporal y devuelve el resultado."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        editor = "notepad" if os.name == "nt" else "nano"
    partes = shlex.split(editor)
    if not shutil.which(partes[0]):
        raise RuntimeError(
            f"No se encontró el editor '{partes[0]}'. Define la variable EDITOR."
        )

    with tempfile.NamedTemporaryFile(
        "w+", suffix=".md", delete=False, encoding="utf-8"
    ) as temporal:
        temporal.write(texto_inicial)
        ruta = Path(temporal.name)

    try:
        resultado = subprocess.run([*partes, str(ruta)])
        if resultado.returncode != 0:
            raise RuntimeError("El editor terminó con un error.")
        return ruta.read_text(encoding="utf-8")
    finally:
        ruta.unlink(missing_ok=True)
