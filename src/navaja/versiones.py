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

import contextlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .comun import cargar_acciones, directorio_datos, quitar_solo_lectura, ruta_libre

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
    def sitio_conocido(self) -> bool:
        """False si se encontró en la carpeta sin estar en el índice: no se sabe de dónde salió."""
        return str(self.sitio) not in ("", ".")

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
    def de_dict(datos: Any) -> Version | None:
        """Una entrada del índice, o None si está mal (falta algo, otro tipo, una ruta fuera de
        la carpeta de versiones…): se ignora esa y las demás se quedan."""
        if not isinstance(datos, dict):
            return None
        guardada, sitio, cuando = datos.get("guardada"), datos.get("sitio"), datos.get("cuando")
        if not (isinstance(guardada, str) and isinstance(sitio, str) and isinstance(cuando, str)):
            return None
        try:
            momento = datetime.fromisoformat(cuando)
        except ValueError:
            return None
        if momento.tzinfo is not None:  # con zona horaria: a la hora local, como las demás
            momento = momento.astimezone().replace(tzinfo=None)
        # Solo dentro de la carpeta de versiones: caducar borra sin preguntar, y un índice
        # editado a mano no debe poder llevarse por delante un archivo tuyo
        if not _dentro_de_versiones(Path(guardada)):
            return None
        accion = datos.get("accion")
        return Version(Path(guardada), Path(sitio), accion if isinstance(accion, str) else "?", momento)


def _dentro_de_versiones(ruta: Path) -> bool:
    if not ruta.is_absolute():
        return False
    raiz = os.path.normcase(os.path.abspath(carpeta_versiones()))
    return os.path.normcase(os.path.abspath(ruta)).startswith(raiz + os.sep)


def _indice() -> Path:
    return carpeta_versiones() / INDICE


def _clave(ruta: Path) -> str:
    return os.path.normcase(str(ruta))


def _leer_indice() -> list[Version] | None:
    """Lo apuntado en el índice (sin las entradas malas); [] si no hay índice; None si está
    roto (no es JSON, o no es una lista). Lanza ``OSError`` si no se puede leer (bloqueado por
    el antivirus…): eso no es estar roto, y no hay que escribir encima."""
    if not _indice().exists():
        return []
    texto = _indice().read_text(encoding="utf-8-sig")  # -sig: el Bloc de notas pone BOM
    try:
        datos = json.loads(texto)
    except ValueError:
        return None
    if not isinstance(datos, list):
        return None
    return [v for v in (Version.de_dict(d) for d in datos) if v is not None]


def sin_indice(conocidas: set[str]) -> list[Version]:
    """Las que están en la carpeta y no en el índice (índice roto o borrado, o un fallo a
    medias): con la fecha de su subcarpeta («20261117-103000») o, si no es una fecha, la de la
    carpeta. De dónde salieron no se sabe, pero así se ven, caducan y se pueden borrar."""
    raiz = carpeta_versiones()
    if not raiz.is_dir():
        return []
    encontradas = []
    for carpeta in (c for c in raiz.iterdir() if c.is_dir()):
        try:
            cuando = datetime.strptime(carpeta.name, "%Y%m%d-%H%M%S")
        except ValueError:
            try:
                cuando = datetime.fromtimestamp(carpeta.stat().st_mtime)
            except OSError:
                continue
        for archivo in carpeta.rglob("*"):
            try:
                if not archivo.is_file() or _clave(archivo) in conocidas:
                    continue
            except OSError:  # ha desaparecido o no deja mirarlo: no se lista
                continue
            encontradas.append(Version(archivo, Path(""), "?", cuando))
    return encontradas


def _apuntadas() -> list[Version]:
    """Las del índice cuyo archivo sigue ahí. ``OSError`` si el índice no se puede leer."""
    return [v for v in (_leer_indice() or []) if v.guardada.is_file()]


def cargar() -> list[Version]:
    """Las versiones que siguen guardadas, de la más reciente a la más antigua.

    Las del índice y, además, las que están en la carpeta sin estar en él (``sin_indice``):
    con el índice roto, borrado o bloqueado, ninguna se pierde de vista.
    """
    try:
        apuntadas = _apuntadas()
    except OSError:
        apuntadas = []
    todas = apuntadas + sin_indice({_clave(v.guardada) for v in apuntadas})
    return sorted(todas, key=lambda v: v.cuando, reverse=True)


def guardar(versiones: list[Version]) -> None:
    """Escribe el índice a un temporal y lo cambia de golpe: cortado a medias, queda el de antes.
    Uno roto no se pisa sin más: se guarda aparte («indice.roto.json», o «(1)» si ya hay uno).
    Si el que hay no se puede leer (bloqueado), lanza ``OSError`` y no escribe nada."""
    carpeta_versiones().mkdir(parents=True, exist_ok=True)
    indice = _indice()
    if _leer_indice() is None:
        os.replace(indice, ruta_libre(indice.with_name("indice.roto.json")))
    temporal = indice.with_name(INDICE + ".navaja")
    try:
        temporal.write_text(
            json.dumps([v.a_dict() for v in versiones], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporal, indice)
    except BaseException:
        with contextlib.suppress(OSError):
            temporal.unlink(missing_ok=True)
        raise


def apuntar(nuevas: list[Version]) -> None:
    """Añade al índice las versiones que acaba de apartar una acción. Solo con lo que se sabe:
    las «sin índice» no se escriben (se encuentran solas en la carpeta). ``OSError`` si el
    índice no se puede leer o escribir: entonces se quedan «sin índice», pero no se pierden."""
    if nuevas:
        nuevas_claves = {_clave(v.guardada) for v in nuevas}
        guardar([v for v in _apuntadas() if _clave(v.guardada) not in nuevas_claves] + nuevas)


def olvidar(quitadas: list[Version]) -> None:
    """Quita del índice estas versiones (ya recuperadas o borradas). ``OSError`` si no se puede."""
    fuera = {_clave(v.guardada) for v in quitadas}
    guardar([v for v in _apuntadas() if _clave(v.guardada) not in fuera])


def caducar(dias: int, ahora: datetime | None = None) -> tuple[int, int]:
    """Borra las versiones guardadas hace más de ``dias`` días (con 0, ninguna) y dice cuántas
    y cuánto ocupaban. Así no se acumulan: cada «el-mas-nuevo» guarda la vieja, y sin esto se
    quedaban para siempre. Lo que no se pueda borrar se queda (se intentará la próxima vez)."""
    if dias <= 0:
        return 0, 0
    try:
        limite = (ahora or datetime.now()) - timedelta(days=dias)
    except OverflowError:  # un número de días disparatado: no caduca nada
        return 0, 0
    pendientes = para_deshacer()
    borradas: list[Version] = []
    ocupaban = 0
    for version in cargar():
        if version.cuando >= limite or os.path.normcase(str(version.guardada)) in pendientes:
            continue  # reciente, o la necesita un deshacer pendiente (de copia o de acciones)
        tamano = version.tamano
        try:
            quitar_solo_lectura(version.guardada)
            version.guardada.unlink()
        except OSError:
            continue
        borradas.append(version)
        ocupaban += tamano
    if borradas:
        try:  # si el índice no se puede escribir, no pasa nada: ``cargar`` ya no lista lo borrado
            olvidar(borradas)
        except OSError:
            pass
        quitar_carpetas_vacias()
    return len(borradas), ocupaban


REGISTROS_CON_VERSIONES = ("acciones", "copia")
"""Los registros de deshacer que pueden apuntar a una versión vieja («apartado»)."""


def para_deshacer() -> set[str]:
    """Las versiones que necesita algún deshacer pendiente: esas no caducan (si caducaran,
    deshacer ya no podría devolver la vieja)."""
    return {
        os.path.normcase(str(registro["apartado"]))
        for nombre in REGISTROS_CON_VERSIONES
        for registro in cargar_acciones(nombre)
        if isinstance(registro, dict) and isinstance(registro.get("apartado"), str)
    }


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
