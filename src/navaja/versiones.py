"""Las versiones viejas que sustituye «copiar» con «si_cambia: el-mas-nuevo».

Antes iban a la papelera común (la de «duplicados»): «duplicados vaciar» las borraba sin
decirlo y, después de la siguiente acción, ninguna orden las devolvía. Ahora tienen su
propia carpeta en el directorio de datos y un índice (``indice.json``) que dice de dónde
salió cada una, cuándo y qué acción la sustituyó. «acciones versiones» las enseña, las
devuelve a su sitio o las borra cuando ya no hacen falta.

El índice se limpia solo: lo que ya no está en la carpeta (porque «acciones deshacer» lo
devolvió o porque se borró) no se lista.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .comun import directorio_datos

INDICE = "indice.json"


def carpeta_versiones() -> Path:
    """Donde se guardan las versiones viejas: una subcarpeta con fecha por ejecución."""
    return directorio_datos() / "versiones"


@dataclass
class Version:
    """Una versión vieja guardada: dónde está ahora y de dónde salió."""

    guardada: Path
    """El archivo, dentro de ``carpeta_versiones()``."""
    sitio: Path
    """Donde estaba antes de que la sustituyeran (y adonde vuelve al recuperarla)."""
    accion: str
    cuando: datetime

    @property
    def tamano(self) -> int:
        try:
            return self.guardada.stat().st_size
        except OSError:
            return 0

    def a_dict(self) -> dict[str, str]:
        return {
            "guardada": str(self.guardada),
            "sitio": str(self.sitio),
            "accion": self.accion,
            "cuando": self.cuando.isoformat(timespec="seconds"),
        }

    @staticmethod
    def de_dict(datos: dict[str, str]) -> Version:
        return Version(
            Path(datos["guardada"]), Path(datos["sitio"]), datos.get("accion", "?"),
            datetime.fromisoformat(datos["cuando"]),
        )


def _indice() -> Path:
    return carpeta_versiones() / INDICE


def cargar() -> list[Version]:
    """Las versiones que siguen guardadas, de la más reciente a la más antigua.

    Si el índice no se puede leer, no se lista nada, pero los archivos siguen en la carpeta:
    no se pierde ninguno.
    """
    try:
        datos = json.loads(_indice().read_text(encoding="utf-8"))
        versiones = [Version.de_dict(d) for d in datos]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    vivas = [v for v in versiones if v.guardada.is_file()]
    return sorted(vivas, key=lambda v: v.cuando, reverse=True)


def guardar(versiones: list[Version]) -> None:
    carpeta_versiones().mkdir(parents=True, exist_ok=True)
    _indice().write_text(
        json.dumps([v.a_dict() for v in versiones], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def apuntar(nuevas: list[Version]) -> None:
    """Añade al índice las versiones que acaba de apartar una acción."""
    if nuevas:
        guardar(cargar() + nuevas)


def olvidar(quitadas: list[Version]) -> None:
    """Quita del índice estas versiones (ya recuperadas o borradas)."""
    fuera = {v.guardada for v in quitadas}
    guardar([v for v in cargar() if v.guardada not in fuera])


def quitar_carpetas_vacias() -> None:
    """Las subcarpetas con fecha que se han quedado sin nada."""
    raiz = carpeta_versiones()
    if not raiz.is_dir():
        return
    for carpeta in sorted((c for c in raiz.rglob("*") if c.is_dir()), key=lambda c: len(c.parts), reverse=True):
        try:
            carpeta.rmdir()
        except OSError:
            pass
