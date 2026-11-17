"""navaja chuleta: chuletas cortas de git, Linux y PowerShell, sin internet.

Las de navaja vienen dentro del paquete (``navaja/chuletas/*.md``). Las tuyas, en la
carpeta ``chuletas`` de tus datos. Si una tuya se llama igual que una de navaja, gana la
tuya: así puedes cambiarla sin tocar el paquete (y una actualización no te la pisa).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import typer
from rich.markdown import Markdown
from rich.markup import escape
from rich.theme import Theme

from ..comun import (
    ESTUDIO,
    abrir_en_editor,
    bonita,
    console,
    directorio_datos,
    problema_del_nombre,
    tabla_ligera,
)
from ..errores import NavajaError
from ..lotes import fallar

NOMBRE_VALIDO = re.compile(r"\w[\w-]*")
"""Letras, números, - y _: ni barras ni puntos, para que el tema no se salga de la carpeta."""

PLANTILLA = """# {tema}

## Lo primero

- `orden` — qué hace
- `otra orden` — qué hace
"""
"""Lo que tiene una chuleta tuya nueva: el formato de las de navaja, para rellenar."""


@dataclass
class Chuleta:
    nombre: str
    texto: str
    tuya: Path | None = None
    """Dónde está, si es tuya; None si es de navaja."""

    @property
    def titulo(self) -> str:
        """La primera línea «# Título», o el nombre si no la tiene."""
        for linea in self.texto.splitlines():
            if linea.startswith("# "):
                return linea[2:].strip()
        return self.nombre


def carpeta_tuyas() -> Path:
    return directorio_datos() / "chuletas"


def de_navaja() -> dict[str, Chuleta]:
    carpeta = resources.files("navaja") / "chuletas"
    chuletas = {}
    for recurso in carpeta.iterdir():
        if recurso.name.endswith(".md"):
            nombre = recurso.name[:-3].lower()
            chuletas[nombre] = Chuleta(nombre, recurso.read_text(encoding="utf-8"))
    return chuletas


def tuyas() -> dict[str, Chuleta]:
    """Las tuyas que se pueden leer. Una que no se puede leer (o no es UTF-8) se salta:
    no debe impedir ver las demás."""
    carpeta = carpeta_tuyas()
    chuletas = {}
    if not carpeta.is_dir():
        return chuletas
    for ruta in sorted(carpeta.glob("*.md")):
        nombre = ruta.stem.lower()
        try:
            chuletas[nombre] = Chuleta(nombre, ruta.read_text(encoding="utf-8"), ruta)
        except (OSError, UnicodeDecodeError):
            continue
    return chuletas


def todas() -> dict[str, Chuleta]:
    """Todas por nombre, en orden alfabético; las tuyas tapan a las de navaja."""
    juntas = de_navaja() | tuyas()
    return dict(sorted(juntas.items()))


def nombre_del_tema(tema: str) -> str:
    """«Git», «git.md» o « git » → «git». Error si no vale como nombre de archivo."""
    nombre = tema.strip().lower()
    if nombre.endswith(".md"):
        nombre = nombre[:-3]
    if not NOMBRE_VALIDO.fullmatch(nombre):
        raise NavajaError(
            f"«{tema}» no vale como tema: solo letras, números, - y _ (sin espacios ni barras)."
        )
    problema = problema_del_nombre(nombre)
    if problema:
        raise NavajaError(problema)
    return nombre


def temas_para_tab(incomplete: str) -> list[tuple[str, str]]:
    """Tab en el tema (en PowerShell y dentro de navaja): los temas con su título."""
    try:
        return [(n, c.titulo) for n, c in todas().items() if n.startswith(incomplete.lower())]
    except Exception:  # Tab nunca debe romper lo que se está escribiendo
        return []


def estilos_markdown() -> Theme:
    """Los colores del Markdown de Rich, sacados del tema de navaja."""
    titulo = console.get_style("titulo")
    acento = console.get_style("acento")
    pista = console.get_style("pista")
    return Theme({
        "markdown.h1": titulo,
        "markdown.h1.border": console.get_style("marco"),
        "markdown.h2": titulo,
        "markdown.h3": acento,
        "markdown.h4": acento,
        "markdown.code": acento,
        "markdown.item.bullet": pista,
        "markdown.item.number": pista,
        "markdown.block_quote": pista,
        "markdown.hr": console.get_style("borde"),
        "markdown.link": acento,
        "markdown.link_url": pista,
    })


def ensenar_lista(chuletas: dict[str, Chuleta]) -> None:
    tabla = tabla_ligera()
    tabla.add_column("Tema", style="acento", no_wrap=True)
    tabla.add_column("De qué va")
    tabla.add_column("De quién", style="pista", no_wrap=True)
    for nombre, chuleta in chuletas.items():
        tabla.add_row(escape(nombre), escape(chuleta.titulo), "tuya" if chuleta.tuya else "navaja")
    console.print("[titulo]Chuletas[/]")
    console.print(tabla)
    console.print(
        "[pista]Para verla: navaja chuleta git · Para cambiarla o hacer una tuya: "
        f"navaja chuleta NOMBRE --editar (se guardan en {escape(bonita(carpeta_tuyas()))})[/]",
        soft_wrap=True,
    )


def ensenar(chuleta: Chuleta) -> None:
    with console.use_theme(estilos_markdown()):
        console.print(Markdown(chuleta.texto, code_theme="ansi_dark"))
    if chuleta.tuya:
        console.print(f"\n[pista]Es tuya: {escape(bonita(chuleta.tuya))}[/]", soft_wrap=True)


def no_existe(nombre: str, chuletas: dict[str, Chuleta]) -> NavajaError:
    parecidas = difflib.get_close_matches(nombre, list(chuletas), n=3, cutoff=0.5)
    mensaje = f"No hay chuleta de «{nombre}»."
    if parecidas:
        mensaje += f" ¿Querías decir {' o '.join(parecidas)}?"
    mensaje += f" Para hacerla tú: navaja chuleta {nombre} --editar"
    return NavajaError(mensaje)


def preparar_tuya(nombre: str) -> tuple[Path, bool]:
    """La ruta de tu chuleta y si se acaba de crear. Si no existe, se crea con la de navaja
    (para cambiarla) o con una plantilla (si es nueva)."""
    ruta = carpeta_tuyas() / f"{nombre}.md"
    if ruta.exists():
        return ruta, False
    original = de_navaja().get(nombre)
    texto = original.texto if original else PLANTILLA.format(tema=nombre)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
    except OSError as error:
        raise NavajaError(f"No se pudo crear {bonita(ruta)}: {error.strerror or error}") from error
    return ruta, True


def editar_tuya(nombre: str) -> None:
    ruta, nueva = preparar_tuya(nombre)
    if nueva:
        de_donde = "copiando la de navaja" if nombre in de_navaja() else "con una plantilla"
        console.print(f"[ok]✔ Creada tu chuleta {escape(bonita(ruta))}[/] [pista]({de_donde})[/]", soft_wrap=True)
    try:
        abrir_en_editor(ruta)
    except (RuntimeError, OSError) as error:
        raise NavajaError(f"{error} Ábrela tú: {bonita(ruta)}") from error
    console.print(f"[ok]✔ Guardada.[/] [pista]Para verla: navaja chuleta {escape(nombre)}[/]")


def chuleta(
    tema: str | None = typer.Argument(
        None,
        help="El tema: git, linux, powershell o uno tuyo. Sin tema, la lista.",
        autocompletion=temas_para_tab,
        show_default=False,
    ),
    editar: bool = typer.Option(
        False,
        "--editar",
        "-e",
        help="Abre tu copia en el editor (la crea si no está). La de navaja no se toca.",
    ),
) -> None:
    """Chuletas cortas de git, Linux y PowerShell, sin internet. Puedes hacer las tuyas."""
    try:
        if tema is None:
            if editar:
                raise NavajaError("Di qué chuleta editar: navaja chuleta git --editar")
            ensenar_lista(todas())
            return
        nombre = nombre_del_tema(tema)
        if editar:
            editar_tuya(nombre)
            return
        chuletas = todas()
        if nombre not in chuletas:
            raise no_existe(nombre, chuletas)
        ensenar(chuletas[nombre])
    except NavajaError as error:
        fallar(error)


def registrar(app: typer.Typer) -> None:
    app.command(
        "chuleta", help="Chuletas de git, Linux y PowerShell, sin internet.",
        rich_help_panel=ESTUDIO,
    )(chuleta)
