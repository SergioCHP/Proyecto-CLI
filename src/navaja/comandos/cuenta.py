"""navaja cuenta: palabras, caracteres, páginas y minutos de lectura de un trabajo.

Lee .txt, .md, .html, .docx y .odt con lo que trae Python (un .docx y un .odt son un
zip con XML dentro). Para .pdf hace falta ``pypdf`` (``navaja[pdf]``): si no está, se
dice cómo instalarlo.
"""

from __future__ import annotations

import html
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from xml.etree import ElementTree

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, DOCUMENTOS, console, error_console, recuadro, resumen, tabla_ligera
from ..errores import NavajaError

PALABRA = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*")
"""Letras o números seguidos; «bien-estar» y «l'aigua» cuentan como una."""

POR_PAGINA = 300
"""Palabras de una página con letra de 12 e interlineado normal (unas 250-350)."""
LEYENDO = 230
"""Palabras por minuto leyendo en silencio."""
EN_VOZ_ALTA = 130
"""Palabras por minuto en una exposición."""

TEXTO_PLANO = {".txt", ".md", ".markdown", ".csv", ".tex", ".rst", ".py", ".java", ".js"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TEXTO_ODT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
INSTALAR_PDF = 'uv tool install --editable ".[todo]"  (desde la carpeta de navaja)'


@dataclass
class Cuenta:
    palabras: int
    caracteres: int
    sin_espacios: int
    parrafos: int

    @property
    def paginas(self) -> float:
        return self.palabras / POR_PAGINA

    def __add__(self, otra: "Cuenta") -> "Cuenta":
        return Cuenta(
            self.palabras + otra.palabras,
            self.caracteres + otra.caracteres,
            self.sin_espacios + otra.sin_espacios,
            self.parrafos + otra.parrafos,
        )


def contar(texto: str) -> Cuenta:
    parrafos = [p for p in re.split(r"\n\s*\n|\n", texto) if p.strip()]
    return Cuenta(
        palabras=len(PALABRA.findall(texto)),
        caracteres=len(texto.strip()),
        sin_espacios=len(re.sub(r"\s", "", texto)),
        parrafos=len(parrafos),
    )


def minutos(palabras: int, por_minuto: int) -> str:
    """«menos de 1 min», «1 min», «9 min» o «1 h 5 min»."""
    total = palabras / por_minuto
    if total < 1:
        return "menos de 1 min"
    redondo = math.ceil(total)
    horas, resto = divmod(redondo, 60)
    return f"{horas} h {resto} min" if horas else f"{redondo} min"


def paginas_texto(paginas: float) -> str:
    if paginas < 0.5:
        return "menos de media"
    return f"unas {max(1, round(paginas))}" if paginas >= 1.5 else "una"


# ── Sacar el texto de cada formato ─────────────────────────────────────────


def leer_texto_plano(ruta: Path) -> str:
    datos = ruta.read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")


def limpiar_markdown(texto: str) -> str:
    """Sin los símbolos de Markdown, que no son palabras: #, *, enlaces, tablas, código."""
    texto = re.sub(r"^```.*?^```", "", texto, flags=re.MULTILINE | re.DOTALL)
    texto = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^\s*\|?[-:| ]+\|?\s*$", "", texto, flags=re.MULTILINE)
    return texto.replace("|", " ").replace("**", "").replace("`", "")


def limpiar_html(texto: str) -> str:
    texto = re.sub(r"<(script|style)\b.*?</\1>", " ", texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"<(br|/p|/div|/h\d|/li)\b[^>]*>", "\n", texto, flags=re.IGNORECASE)
    return html.unescape(re.sub(r"<[^>]+>", " ", texto))


def leer_xml_de_zip(ruta: Path, dentro: str) -> ElementTree.Element:
    try:
        with zipfile.ZipFile(ruta) as zipeado:
            return ElementTree.fromstring(zipeado.read(dentro))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        raise NavajaError(f"{ruta.name} está dañado o no es un {ruta.suffix} de verdad.") from None


def leer_docx(ruta: Path) -> str:
    """Los párrafos de word/document.xml (el cuerpo; sin encabezados ni notas al pie)."""
    raiz = leer_xml_de_zip(ruta, "word/document.xml")
    parrafos = []
    for parrafo in raiz.iter(f"{W}p"):
        trozos = []
        for nodo in parrafo.iter():
            if nodo.tag == f"{W}t" and nodo.text:
                trozos.append(nodo.text)
            elif nodo.tag in (f"{W}tab", f"{W}br"):
                trozos.append(" ")
        parrafos.append("".join(trozos))
    return "\n".join(parrafos)


def leer_odt(ruta: Path) -> str:
    raiz = leer_xml_de_zip(ruta, "content.xml")
    return "\n".join(
        "".join(nodo.itertext())
        for nodo in raiz.iter()
        if nodo.tag in (f"{TEXTO_ODT}p", f"{TEXTO_ODT}h")
    )


def leer_pdf(ruta: Path) -> str:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        raise NavajaError(f"Para contar un PDF hace falta pypdf. Instálalo con: {INSTALAR_PDF}") from None
    try:
        lector = PdfReader(str(ruta))
        if lector.is_encrypted:
            raise NavajaError(f"{ruta.name} tiene contraseña: no se puede leer.")
        return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
    except PdfReadError:
        raise NavajaError(f"{ruta.name} está dañado o no es un PDF de verdad.") from None


def texto_de(ruta: Path) -> str:
    """El texto de un archivo según su extensión. ``NavajaError`` si no se sabe leer."""
    tipo = ruta.suffix.lower()
    if tipo in TEXTO_PLANO:
        texto = leer_texto_plano(ruta)
        return limpiar_markdown(texto) if tipo in (".md", ".markdown") else texto
    if tipo in (".html", ".htm"):
        return limpiar_html(leer_texto_plano(ruta))
    if tipo == ".docx":
        return leer_docx(ruta)
    if tipo == ".odt":
        return leer_odt(ruta)
    if tipo == ".pdf":
        return leer_pdf(ruta)
    if tipo == ".doc":
        raise NavajaError(f"{ruta.name} es un .doc antiguo: ábrelo en Word y guárdalo como .docx.")
    raise NavajaError(f"No sé contar las palabras de un {tipo or 'archivo sin extensión'} ({ruta.name}).")


# ── Orden ──────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def cuenta(
    archivos: list[Path] = typer.Argument(..., help="El trabajo (.docx, .pdf, .odt, .md o .txt); pueden ser varios."),
    minimo: int = typer.Option(
        0, "--minimo", "-m", min=0, help="Las palabras que piden, para ver si llegas.",
        rich_help_panel=AJUSTE, show_default=False,
    ),
) -> None:
    """Cuenta las palabras, caracteres, páginas y minutos de lectura de un trabajo."""
    cuentas: list[tuple[Path, Cuenta]] = []
    for archivo in archivos:
        ruta = archivo.expanduser()
        if not ruta.is_file():
            fallar(NavajaError(f"No existe el archivo {archivo}."))
        try:
            cuentas.append((ruta, contar(texto_de(ruta))))
        except NavajaError as error:
            fallar(error)
        except OSError as error:
            fallar(NavajaError(f"No se puede leer {archivo}: {error.strerror or error}"))
    total = cuentas[0][1]
    for _, otra in cuentas[1:]:
        total = total + otra
    partes: list = []
    if len(cuentas) > 1:
        tabla = tabla_ligera()
        for columna in ("Archivo", "Palabras", "Caracteres", "Páginas"):
            tabla.add_column(columna, justify="left" if columna == "Archivo" else "right", no_wrap=columna != "Archivo")
        for ruta, una in cuentas:
            tabla.add_row(escape(ruta.name), con_puntos(una.palabras), con_puntos(una.caracteres), f"{una.paginas:.1f}")
        partes.append(tabla)
    filas = [
        ("Palabras", f"[acento]{con_puntos(total.palabras)}[/]"),
        ("Caracteres", f"{con_puntos(total.caracteres)} [pista]({con_puntos(total.sin_espacios)} sin espacios)[/]"),
        ("Párrafos", con_puntos(total.parrafos)),
        ("Páginas", f"{paginas_texto(total.paginas)} [pista](a {POR_PAGINA} palabras por página)[/]"),
        ("Leerlo", minutos(total.palabras, LEYENDO)),
        ("En voz alta", f"{minutos(total.palabras, EN_VOZ_ALTA)} [pista](para una exposición)[/]"),
    ]
    partes.insert(0, resumen(filas))
    if minimo:
        if total.palabras >= minimo:
            partes.append(Text.from_markup(f"[ok]✔ Llegas: piden {con_puntos(minimo)} y tienes {con_puntos(total.palabras - minimo)} de más.[/]"))
        else:
            partes.append(Text.from_markup(f"[error]✘ Te faltan {con_puntos(minimo - total.palabras)} palabras para las {con_puntos(minimo)} que piden.[/]"))
    titulo = cuentas[0][0].name if len(cuentas) == 1 else f"{len(cuentas)} archivos"
    console.print(recuadro(titulo, *partes))


def con_puntos(numero: int) -> str:
    return f"{numero:,}".replace(",", ".")


def registrar(app: typer.Typer) -> None:
    app.command(
        "cuenta", help="Palabras, páginas y minutos de lectura de un trabajo.", rich_help_panel=DOCUMENTOS
    )(cuenta)
