"""Qué se deja fuera al dibujar (``arbol``) o comprimir (``comprime``) una carpeta.

Siempre lo de ``POR_DEFECTO`` (entornos, cachés, .git…) y lo que diga el ``.gitignore``
de la carpeta. Del ``.gitignore`` se entiende lo de todos los días: un nombre
(``*.log``, ``build``), una barra al final para solo carpetas (``dist/``), una barra
delante o en medio para una ruta desde la raíz (``/notas.txt``, ``docs/borradores``) y
``!`` para volver a incluir algo. No mira los ``.gitignore`` de las subcarpetas.
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

POR_DEFECTO = (
    ".git/",
    ".venv/",
    "venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "*.egg-info/",
    "*.pyc",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
)
"""Lo que nunca hace falta: se vuelve a crear solo o es del sistema."""


@dataclass(frozen=True)
class Patron:
    texto: str
    solo_carpetas: bool
    desde_la_raiz: bool
    incluir: bool  # «!algo»: vuelve a incluirlo

    @classmethod
    def de_linea(cls, linea: str) -> "Patron | None":
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            return None
        incluir = linea.startswith("!")
        linea = linea.removeprefix("!")
        solo_carpetas = linea.endswith("/")
        linea = linea.rstrip("/")
        if linea.startswith("**/"):  # «**/build»: en cualquier sitio, como «build»
            linea, desde_la_raiz = linea[3:], False
        else:
            desde_la_raiz = "/" in linea
            linea = linea.lstrip("/")
        if not linea:
            return None
        return cls(linea, solo_carpetas, desde_la_raiz, incluir)

    def encaja(self, relativa: str, es_carpeta: bool) -> bool:
        if self.solo_carpetas and not es_carpeta:
            return False
        if self.desde_la_raiz:
            return fnmatch.fnmatch(relativa, self.texto)
        return fnmatch.fnmatch(relativa.rsplit("/", 1)[-1], self.texto)


class Ignorados:
    """Los patrones de una carpeta. ``ignora("src/__pycache__", True)`` → True."""

    def __init__(self, lineas: list[str]) -> None:
        self.patrones = [p for p in (Patron.de_linea(l) for l in lineas) if p is not None]

    @classmethod
    def de_carpeta(cls, raiz: Path, todo: bool = False, extra: tuple[str, ...] = ()) -> "Ignorados":
        """Los de siempre, los del ``.gitignore`` y los de ``extra``. Con ``todo``, ninguno."""
        if todo:
            return cls([])
        lineas = list(POR_DEFECTO)
        gitignore = raiz / ".gitignore"
        if gitignore.is_file():
            try:
                lineas += gitignore.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            except OSError:
                pass
        return cls(lineas + list(extra))

    def ignora(self, relativa: str, es_carpeta: bool) -> bool:
        """El último patrón que encaja decide (como en git)."""
        decision = False
        for patron in self.patrones:
            if patron.encaja(relativa, es_carpeta):
                decision = not patron.incluir
        return decision


@dataclass
class Recorrido:
    """Lo que hay en una carpeta sin lo ignorado, y lo que se ha dejado fuera."""

    archivos: list[Path]
    fuera: dict[str, int]  # nombre de lo ignorado → cuántos archivos llevaba dentro (o 1)


def recorrer(raiz: Path, ignorados: Ignorados) -> Recorrido:
    """Todos los archivos de ``raiz`` (sin seguir enlaces), en orden, sin los ignorados."""
    archivos: list[Path] = []
    fuera: dict[str, int] = {}
    for actual, carpetas, nombres in os.walk(raiz):
        base = Path(actual)
        quedan = []
        for nombre in sorted(carpetas, key=str.lower):
            ruta = base / nombre
            relativa = ruta.relative_to(raiz).as_posix()
            if ruta.is_symlink():
                continue
            if ignorados.ignora(relativa, True):
                fuera[nombre + "/"] = fuera.get(nombre + "/", 0) + contar_archivos(ruta)
            else:
                quedan.append(nombre)
        carpetas[:] = quedan
        for nombre in sorted(nombres, key=str.lower):
            ruta = base / nombre
            if ruta.is_symlink():
                continue
            if ignorados.ignora(ruta.relative_to(raiz).as_posix(), False):
                fuera[nombre] = fuera.get(nombre, 0) + 1
            else:
                archivos.append(ruta)
    return Recorrido(archivos, fuera)


def contar_archivos(carpeta: Path) -> int:
    total = 0
    for _, _, nombres in os.walk(carpeta):
        total += len(nombres)
    return total


def hijos(carpeta: Path) -> Iterator[Path]:
    """Lo que hay dentro, carpetas primero y por nombre sin mirar mayúsculas."""
    try:
        entradas = list(carpeta.iterdir())
    except OSError:
        return iter(())
    entradas.sort(key=lambda r: (not (r.is_dir() and not r.is_symlink()), r.name.lower()))
    return iter(entradas)
