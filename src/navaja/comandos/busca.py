"""navaja busca: buscar un texto dentro de los archivos de una carpeta (y de sus subcarpetas).

También dentro de Word (.docx), LibreOffice (.odt) y PDF (con pypdf), que es donde están
los apuntes. Sin mirar mayúsculas ni tildes («funcion» encuentra «Función»), o con
``--regex`` una expresión regular. Se salta lo de siempre (.git, .venv, node_modules… y lo
del .gitignore) y los archivos que no son de texto.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, ARCHIVOS, bonita, console, cuantos, error_console
from ..errores import NavajaError
from ..filtros import extensiones
from ..ignorados import Ignorados, recorrer
from .cuenta import leer_docx, leer_odt, leer_texto_plano

MAXIMO_TAMANO = 20 * 1024 * 1024
"""Un archivo de texto más grande que esto no se lee (es un log o un volcado)."""
MAXIMO_POR_ARCHIVO = 20
MAXIMO_TOTAL = 500
ANCHO_LINEA = 160
"""Una línea más larga (un .min.js) se recorta alrededor de lo encontrado."""


def sin_tildes_igual_largo(texto: str) -> str:
    """En minúsculas y sin tildes, letra a letra, sin cambiar el largo: así las posiciones de
    lo encontrado sirven para resaltar el texto original («Función» → «funcion»)."""
    salida = []
    for caracter in texto:
        base = unicodedata.normalize("NFD", caracter)[0].lower()
        salida.append(base if len(base) == 1 else caracter)
    return "".join(salida)


def patron(texto: str, regex: bool = False, exacto: bool = False) -> re.Pattern[str]:
    """La expresión con la que se busca. Sin ``regex`` es el texto tal cual; sin ``exacto``,
    sin mirar mayúsculas ni tildes. ``NavajaError`` si la regex está mal."""
    if regex:
        try:
            return re.compile(texto, 0 if exacto else re.IGNORECASE)
        except re.error as error:
            raise NavajaError(f"La expresión regular está mal: {error}.") from None
    return re.compile(re.escape(texto if exacto else sin_tildes_igual_largo(texto)))


@dataclass
class Linea:
    numero: int  # línea (o página en un PDF)
    texto: str
    trozos: list[tuple[int, int]]  # dónde está lo encontrado dentro de texto


@dataclass
class Resultado:
    archivo: Path
    lineas: list[Linea] = field(default_factory=list)
    por_pagina: bool = False  # en un PDF el número es la página
    mas: int = 0  # coincidencias que no se enseñan (más de MAXIMO_POR_ARCHIVO)


def texto_y_paginas(ruta: Path) -> tuple[list[str], bool] | None:
    """Las líneas del archivo (o una por página en un PDF), o None si no es de texto."""
    tipo = ruta.suffix.lower()
    if tipo == ".docx":
        return leer_docx(ruta).splitlines(), False
    if tipo == ".odt":
        return leer_odt(ruta).splitlines(), False
    if tipo == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return None
        lector = PdfReader(str(ruta))
        return [" ".join((pagina.extract_text() or "").split()) for pagina in lector.pages], True
    try:
        if ruta.stat().st_size > MAXIMO_TAMANO:
            return None
        with ruta.open("rb") as archivo:
            if b"\0" in archivo.read(8192):
                return None  # binario: una imagen, un .exe…
    except OSError:
        return None
    return leer_texto_plano(ruta).splitlines(), False


def buscar_en(ruta: Path, expresion: re.Pattern[str], exacto: bool, regex: bool) -> Resultado | None:
    try:
        leido = texto_y_paginas(ruta)
    except (NavajaError, OSError, ValueError):
        return None
    if leido is None:
        return None
    lineas, por_pagina = leido
    resultado = Resultado(ruta, por_pagina=por_pagina)
    for numero, linea in enumerate(lineas, start=1):
        donde = linea if (exacto or regex) else sin_tildes_igual_largo(linea)
        trozos = [(m.start(), m.end()) for m in expresion.finditer(donde) if m.end() > m.start()]
        if not trozos:
            continue
        if len(resultado.lineas) >= MAXIMO_POR_ARCHIVO:
            resultado.mas += 1
            continue
        resultado.lineas.append(Linea(numero, linea, trozos))
    return resultado if resultado.lineas else None


def buscar(
    carpeta: Path, texto: str, regex: bool = False, exacto: bool = False, solo: str = "", todo: bool = False
) -> tuple[list[Resultado], int]:
    """Los archivos con coincidencias y cuántos archivos se han mirado."""
    expresion = patron(texto, regex, exacto)
    tipos = extensiones(solo) if solo else set()
    archivos = recorrer(carpeta, Ignorados.de_carpeta(carpeta, todo)).archivos
    if tipos:
        archivos = [a for a in archivos if a.suffix.lower() in tipos]
    resultados = []
    total = 0
    for archivo in archivos:
        encontrado = buscar_en(archivo, expresion, exacto, regex)
        if encontrado:
            resultados.append(encontrado)
            total += len(encontrado.lineas)
            if total >= MAXIMO_TOTAL:
                break
    return resultados, len(archivos)


def recortar(linea: Linea, ancho: int = ANCHO_LINEA) -> tuple[str, list[tuple[int, int]]]:
    """La línea sin la sangría y, si es muy larga, solo el trozo alrededor de lo encontrado."""
    texto = linea.texto.rstrip()
    sangria = len(texto) - len(texto.lstrip())
    texto = texto.lstrip()
    trozos = [(a - sangria, b - sangria) for a, b in linea.trozos]
    if len(texto) <= ancho:
        return texto, trozos
    inicio = max(0, trozos[0][0] - ancho // 3)
    fin = inicio + ancho
    corte = texto[inicio:fin]
    trozos = [(a - inicio, min(b, fin) - inicio) for a, b in trozos if a >= inicio and a < fin]
    prefijo = "…" if inicio else ""
    sufijo = "…" if fin < len(texto) else ""
    return prefijo + corte + sufijo, [(a + len(prefijo), b + len(prefijo)) for a, b in trozos]


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def busca(
    texto: str = typer.Argument(..., help="Lo que buscas (sin mirar mayúsculas ni tildes)."),
    carpeta: Path = typer.Argument(Path("."), help="Dónde buscar (con sus subcarpetas)."),
    solo: str = typer.Option(
        "", "--solo", help="Solo en estos tipos (documentos, pdf, py,md…).", rich_help_panel=AJUSTE,
        show_default=False,
    ),
    regex: bool = typer.Option(False, "--regex", "-r", help="El texto es una expresión regular."),
    exacto: bool = typer.Option(False, "--exacto", "-e", help="Mirando mayúsculas y tildes."),
    todo: bool = typer.Option(False, "--todo", help="También en .git, .venv y lo del .gitignore."),
) -> None:
    """Busca un texto dentro de los archivos de una carpeta, también en Word y PDF."""
    if not carpeta.is_dir():
        fallar(NavajaError(f"No existe la carpeta {carpeta}."))
    try:
        with console.status("[pista]Buscando…[/]", spinner="dots"):
            resultados, mirados = buscar(carpeta, texto, regex, exacto, solo, todo)
    except NavajaError as error:
        fallar(error)
    if not resultados:
        console.print(
            f"[aviso]No aparece «{escape(texto)}»[/] [pista]en {cuantos(mirados, 'archivo')} de "
            f"{escape(bonita(carpeta.resolve()))}.[/]",
            soft_wrap=True,
        )
        raise typer.Exit(1)
    total = 0
    for resultado in resultados:
        try:
            nombre = resultado.archivo.relative_to(carpeta).as_posix()
        except ValueError:
            nombre = str(resultado.archivo)
        console.print(Text(nombre, style="titulo"))
        etiqueta = "pág." if resultado.por_pagina else ""
        ancho = max(len(str(l.numero)) for l in resultado.lineas)
        for linea in resultado.lineas:
            corte, trozos = recortar(linea)
            fila = Text(f"  {etiqueta}{linea.numero:>{ancho}} │ ", style="pista")
            cuerpo = Text(corte)
            for inicio, fin in trozos:
                cuerpo.stylize("acento", inicio, fin)
                cuerpo.stylize("bold", inicio, fin)
            fila.append_text(cuerpo)
            console.print(fila, soft_wrap=True, highlight=False)
            total += 1
        if resultado.mas:
            console.print(f"  [pista]… y {resultado.mas} más en este archivo[/]")
        console.print()
    console.print(
        f"[ok]✔ {cuantos(total, 'línea')} en {cuantos(len(resultados), 'archivo')}[/] "
        f"[pista](de {mirados} mirados)[/]"
    )
    if total >= MAXIMO_TOTAL:
        console.print(f"[aviso]Hay demasiadas: solo salen las {MAXIMO_TOTAL} primeras. Afina la búsqueda.[/]")


def registrar(app: typer.Typer) -> None:
    app.command(
        "busca", help="Busca un texto dentro de los archivos, también en Word y PDF.", rich_help_panel=ARCHIVOS
    )(busca)
