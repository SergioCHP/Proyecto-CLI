"""Qué archivos se tocan: por tipo, por un texto del nombre o por fechas.

Lo usan ``ordena`` y ``renombra``. Las fechas se escriben como las diría
cualquiera: ``1/9/2026``, ``septiembre 2026``, ``2026``, ``hoy`` o ``hace 30 días``.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import typer

from .comun import iterar_archivos

FILTRO = "Qué archivos"
"""Panel de --help de los filtros. El modo interactivo no los pregunta uno a uno:
hace una sola pregunta, «¿Con qué archivos?», y según la respuesta pide el detalle."""

CATEGORIAS: dict[str, set[str]] = {
    "imagenes": {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
        ".tif", ".tiff", ".heic", ".raw", ".cr2", ".nef", ".ico",
    },
    "documentos": {
        ".pdf", ".doc", ".docx", ".txt", ".md", ".odt", ".rtf",
        ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".csv", ".epub",
    },
    "videos": {
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".mpg", ".mpeg", ".3gp",
    },
    "audio": {
        ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus",
    },
    "comprimidos": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".iso",
    },
    "codigo": {
        ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp",
        ".h", ".hpp", ".go", ".rs", ".rb", ".php", ".sh", ".html", ".css",
        ".scss", ".json", ".yaml", ".yml", ".toml", ".xml", ".sql", ".lua",
    },
    "ejecutables": {
        ".exe", ".msi", ".deb", ".rpm", ".appimage", ".dmg", ".apk", ".bat",
    },
}

NOMBRES = {
    "imagenes": "Imagenes",
    "videos": "Videos",
    "audio": "Audio",
    "documentos": "Documentos",
    "comprimidos": "Comprimidos",
    "codigo": "Codigo",
    "ejecutables": "Ejecutables",
    "otros": "Otros",
}

ETIQUETAS = {
    "imagenes": "Imágenes (fotos, capturas…)",
    "documentos": "Documentos (pdf, Word, Excel, txt…)",
    "videos": "Vídeos",
    "audio": "Audio y música",
    "comprimidos": "Comprimidos (zip, rar…)",
    "codigo": "Código",
    "ejecutables": "Programas e instaladores (exe, msi…)",
}
"""Cómo se enseña cada tipo en las preguntas (las carpetas siguen siendo NOMBRES)."""

ALIAS_TIPOS = {
    "imagen": "imagenes", "fotos": "imagenes", "foto": "imagenes",
    "video": "videos", "musica": "audio", "documento": "documentos", "docs": "documentos",
    "comprimido": "comprimidos", "zip": "comprimidos", "programas": "ejecutables",
    "instaladores": "ejecutables", "ejecutable": "ejecutables",
}

MESES = {
    "enero": 1, "ene": 1, "febrero": 2, "feb": 2, "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4, "mayo": 5, "may": 5, "junio": 6, "jun": 6,
    "julio": 7, "jul": 7, "agosto": 8, "ago": 8, "septiembre": 9, "setiembre": 9,
    "sep": 9, "sept": 9, "octubre": 10, "oct": 10, "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12,
}
NOMBRE_MES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

EJEMPLOS_FECHA = "1/9/2026, septiembre 2026, 2026, hoy o hace 30 días"


# ── Texto ──────────────────────────────────────────────────────────────────


def sin_tildes(texto: str) -> str:
    """«Año Ñandú» → «Ano Nandu»."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def tipo_de(nombre: str) -> str:
    """Categoría por la extensión: ``imagenes``, ``documentos``… u ``otros``."""
    extension = Path(nombre).suffix.lower()
    for categoria, extensiones_categoria in CATEGORIAS.items():
        if extension in extensiones_categoria:
            return categoria
    return "otros"


def extensiones(solo: str) -> set[str]:
    """``"imágenes, pdf"`` → todas las de imagen más ``.pdf``. Acepta ``jpg``, ``.PNG`` o ``*.gif``."""
    resultado: set[str] = set()
    for parte in solo.replace(";", ",").split(","):
        parte = sin_tildes(parte.strip().lower()).lstrip("*")
        if not parte:
            continue
        categoria = ALIAS_TIPOS.get(parte, parte)
        if categoria in CATEGORIAS:
            resultado |= CATEGORIAS[categoria]
        else:
            resultado.add(parte if parte.startswith(".") else f".{parte}")
    return resultado


# ── Fechas ─────────────────────────────────────────────────────────────────


def _restar_meses(dia: date, meses: int) -> date:
    total = dia.year * 12 + dia.month - 1 - meses
    anio, mes = divmod(total, 12)
    mes += 1
    return date(anio, mes, min(dia.day, calendar.monthrange(anio, mes)[1]))


def _mes_entero(anio: int, mes: int) -> tuple[date, date]:
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def periodo(texto: str, hoy: date | None = None) -> tuple[date, date]:
    """Primer y último día de lo que se ha escrito.

    ``1/9/2026`` → ese día. ``septiembre 2026`` o ``9/2026`` → ese mes. ``2026`` →
    ese año. ``hoy``, ``ayer``, ``hace 30 días`` (o semanas, meses, años).
    Lanza ``ValueError`` con un mensaje en castellano si no lo entiende.
    """
    hoy = hoy or date.today()
    limpio = sin_tildes(texto.strip().lower())
    limpio = re.sub(r"\s+de\s+", " ", limpio)
    try:
        if limpio == "hoy":
            return hoy, hoy
        if limpio == "ayer":
            dia = hoy - timedelta(days=1)
            return dia, dia
        if m := re.fullmatch(r"hace (\d+) (dia|dias|semana|semanas|mes|meses|ano|anos)", limpio):
            n, unidad = int(m.group(1)), m.group(2)
            if unidad.startswith("dia"):
                dia = hoy - timedelta(days=n)
            elif unidad.startswith("semana"):
                dia = hoy - timedelta(weeks=n)
            elif unidad.startswith("mes"):
                dia = _restar_meses(hoy, n)
            else:
                dia = _restar_meses(hoy, 12 * n)
            return dia, dia
        if m := re.fullmatch(r"(\d{4})", limpio):
            anio = int(m.group(1))
            return date(anio, 1, 1), date(anio, 12, 31)
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", limpio):
            dia = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return dia, dia
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})", limpio):
            return _mes_entero(int(m.group(1)), int(m.group(2)))
        if m := re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2}|\d{4}))?", limpio):
            anio = int(m.group(3)) if m.group(3) else hoy.year
            anio += 2000 if anio < 100 else 0
            dia = date(anio, int(m.group(2)), int(m.group(1)))
            return dia, dia
        if m := re.fullmatch(r"(\d{1,2})[/.-](\d{4})", limpio):
            return _mes_entero(int(m.group(2)), int(m.group(1)))
        if m := re.fullmatch(r"([a-z]+)(?: (\d{4}))?", limpio):
            if m.group(1) in MESES:
                anio = int(m.group(2)) if m.group(2) else hoy.year
                return _mes_entero(anio, MESES[m.group(1)])
    except ValueError:
        pass  # 31/2/2026, mes 13…: se explica abajo
    raise ValueError(f"No entiendo la fecha «{texto}». Escribe, por ejemplo: {EJEMPLOS_FECHA}.")


def rango(desde: str, hasta: str) -> tuple[datetime | None, datetime | None]:
    """De dos textos (pueden estar vacíos) a un intervalo con horas: del primer al último segundo."""
    inicio = datetime.combine(periodo(desde)[0], time.min) if desde.strip() else None
    fin = datetime.combine(periodo(hasta)[1], time.max) if hasta.strip() else None
    if inicio and fin and inicio > fin:
        raise ValueError(
            f"La fecha «desde» ({inicio:%d/%m/%Y}) es posterior a «hasta» ({fin:%d/%m/%Y}). "
            "Revisa el orden."
        )
    return inicio, fin


def describir_rango(inicio: datetime | None, fin: datetime | None) -> str:
    def corto(momento: datetime) -> str:
        return momento.strftime("%d/%m/%Y")

    if inicio and fin:
        return f"del {corto(inicio)} al {corto(fin)}"
    if inicio:
        return f"desde el {corto(inicio)}"
    if fin:
        return f"hasta el {corto(fin)}"
    return "de cualquier fecha"


# ── Elegir archivos ────────────────────────────────────────────────────────


@dataclass
class Filtro:
    solo: str = ""
    contiene: str = ""
    desde: str = ""
    hasta: str = ""
    recursivo: bool = False
    ocultos: bool = False

    def describir(self) -> str:
        partes = []
        if self.solo:
            partes.append(f"tipo {self.solo}")
        if self.contiene:
            partes.append(f"con «{self.contiene}» en el nombre")
        if self.desde or self.hasta:
            partes.append(describir_rango(*rango(self.desde, self.hasta)))
        return ", ".join(partes)


def seleccionar(carpeta: Path, filtro: Filtro) -> list[Path]:
    """Archivos de la carpeta que cumplen el filtro, por orden alfabético. ``ValueError`` si una fecha no vale."""
    exts = extensiones(filtro.solo)
    texto = filtro.contiene.lower()
    inicio, fin = rango(filtro.desde, filtro.hasta)
    elegidos = []
    for archivo in iterar_archivos(carpeta, filtro.recursivo, filtro.ocultos):
        if exts and archivo.suffix.lower() not in exts:
            continue
        if texto and texto not in archivo.name.lower():
            continue
        if inicio or fin:
            momento = datetime.fromtimestamp(archivo.stat().st_mtime)
            if (inicio and momento < inicio) or (fin and momento > fin):
                continue
        elegidos.append(archivo)
    return sorted(elegidos, key=lambda a: (str(a.parent).lower(), sin_tildes(a.name).lower()))


# ── Opciones de Typer que comparten ordena y renombra ──────────────────────

OPCION_CARPETA = typer.Option(
    Path("."), "--carpeta", "-c", help="Carpeta con los archivos (por defecto, la actual)."
)
OPCION_SOLO = typer.Option(
    "",
    "--solo",
    help="Solo de este tipo (imagenes, documentos, videos…) o extensiones (jpg,png).",
    show_default=False,
    rich_help_panel=FILTRO,
)
OPCION_CONTIENE = typer.Option(
    "",
    "--contiene",
    help="Solo los archivos cuyo nombre lleva este texto (sin mirar mayúsculas).",
    show_default=False,
    rich_help_panel=FILTRO,
)
OPCION_DESDE = typer.Option(
    "",
    "--desde",
    help=f"Solo los modificados desde esta fecha ({EJEMPLOS_FECHA}).",
    show_default=False,
    rich_help_panel=FILTRO,
)
OPCION_HASTA = typer.Option(
    "",
    "--hasta",
    help="Solo los modificados hasta esta fecha (incluida).",
    show_default=False,
    rich_help_panel=FILTRO,
)
OPCION_RECURSIVO = typer.Option(False, "--recursivo", "-r", help="Incluir subcarpetas.")
OPCION_OCULTOS = typer.Option(
    False, "--ocultos", help="Incluir archivos ocultos y de sistema (desktop.ini…)."
)
OPCION_SIMULAR = typer.Option(
    False, "--simular", help="Solo enseña lo que haría, sin cambiar nada."
)
OPCION_SI = typer.Option(False, "--si", "-s", help="No pide confirmación.")
