"""navaja doctor: comprueba que todo está listo y dice cómo arreglar lo que falta.

Python, las librerías (las que hacen falta y las opcionales), los programas de fuera que
usarán algunas órdenes, la carpeta de datos, acciones.json y la terminal. Solo mira: no
instala ni cambia nada.
"""

from __future__ import annotations

import platform
import shutil
import sys
import tempfile
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

import typer
from rich.markup import escape
from rich.text import Text

from .. import __version__, esquema, proveedor_ia
from ..comun import NAVAJA, console, directorio_datos, es_utf8, recuadro, tabla_ligera
from ..errores import NavajaError
from ..lotes import como_instalar

WINDOWS = sys.platform == "win32"


@dataclass
class Revision:
    grupo: str
    nombre: str
    estado: str  # "ok", "aviso" (opcional que falta) o "error" (hace falta)
    detalle: str
    arreglo: str = ""


OBLIGATORIAS = [("typer", "los comandos"), ("rich", "los colores y las tablas"), ("prompt_toolkit", "el menú")]
OPCIONALES = [
    # (paquete, para qué, extra)
    ("pypdf", "cuenta, busca y pdf: leer PDF", "pdf"),
    ("cryptography", "pdf protege: contraseñas AES", "pdf"),
    ("Pillow", "imagen, convierte y fondo: fotos", "imagen"),
    ("pillow-heif", "fotos HEIC del iPhone", "imagen"),
    ("qrcode", "qr", "qr"),
    ("PyMuPDF", "convierte: PDF a imágenes", "documentos"),
    ("pdf2docx", "convierte: PDF a Word", "documentos"),
    ("openpyxl", "convierte: Excel ↔ CSV", "documentos"),
    ("yt-dlp", "baja: descargar vídeos", "baja"),
    ("rembg", "fondo: quitar el fondo (pesa)", "fondo"),
    ("Faker", "falsos: datos de prueba", "falsos"),
    ("psutil", "red, puertos y sistema", "sistema"),
]

PROGRAMAS = [
    # (nombre, ejecutables, para qué, winget, apt)
    ("git", ("git",), "control de versiones", "winget install Git.Git", "sudo apt install git"),
    ("LibreOffice", ("soffice", "libreoffice"), "convierte: Word, Excel… a PDF",
     "winget install TheDocumentFoundation.LibreOffice", "sudo apt install libreoffice"),
    ("Pandoc", ("pandoc",), "convierte: Markdown a Word", "winget install JohnMacFarlane.Pandoc",
     "sudo apt install pandoc"),
    ("FFmpeg", ("ffmpeg",), "convierte y baja: vídeo y audio", "winget install Gyan.FFmpeg", "sudo apt install ffmpeg"),
    ("7-Zip", ("7z", "7za"), "abrir .rar y .7z (más adelante)", "winget install 7zip.7zip", "sudo apt install p7zip-full"),
]

RUTAS_WINDOWS = {
    "LibreOffice": [r"C:\Program Files\LibreOffice\program\soffice.exe"],
    "7-Zip": [r"C:\Program Files\7-Zip\7z.exe"],
    "Word": [
        r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
    ],
}


def version_de(paquete: str) -> str | None:
    try:
        return metadata.version(paquete)
    except metadata.PackageNotFoundError:
        return None


def buscar_programa(nombre: str, ejecutables: tuple[str, ...]) -> str | None:
    """Dónde está: en el PATH o, en Windows, donde se instala normalmente."""
    for ejecutable in ejecutables:
        ruta = shutil.which(ejecutable)
        if ruta:
            return ruta
    if WINDOWS:
        for ruta in RUTAS_WINDOWS.get(nombre, []):
            if Path(ruta).is_file():
                return ruta
    return None


def revisar_python(version: tuple[int, int] = sys.version_info[:2]) -> Revision:
    texto = f"{version[0]}.{version[1]}"
    if version >= (3, 12):
        return Revision("Python", "Python", "ok", texto)
    return Revision("Python", "Python", "error", f"{texto}: hace falta 3.12 o más", "uv python install 3.12")


def revisar_librerias() -> list[Revision]:
    lista = []
    for paquete, para in OBLIGATORIAS:
        version = version_de(paquete)
        if version:
            lista.append(Revision("Librerías", paquete, "ok", f"{version} · {para}"))
        else:
            lista.append(Revision("Librerías", paquete, "error", f"falta ({para})", como_instalar()))
    for paquete, para, extra in OPCIONALES:
        version = version_de(paquete)
        if version:
            lista.append(Revision("Librerías", paquete, "ok", f"{version} · {para}"))
        else:
            lista.append(Revision("Librerías", paquete, "aviso", f"opcional, para {para}",
                                  como_instalar(extra)))
    return lista


def revisar_programas() -> list[Revision]:
    lista = []
    for nombre, ejecutables, para, winget, apt in PROGRAMAS:
        ruta = buscar_programa(nombre, ejecutables)
        if ruta:
            lista.append(Revision("Programas", nombre, "ok", f"{para} · {ruta}"))
        else:
            lista.append(Revision("Programas", nombre, "aviso", f"no está · {para}", winget if WINDOWS else apt))
    if WINDOWS:
        word = buscar_programa("Word", ())
        lista.append(
            Revision("Programas", "Word", "ok", f"pasar a PDF · {word}")
            if word else Revision("Programas", "Word", "aviso", "no está (vale LibreOffice para pasar a PDF)")
        )
        winget = buscar_programa("winget", ("winget",))
        lista.append(
            Revision("Programas", "winget", "ok", "instalar programas")
            if winget else Revision("Programas", "winget", "aviso", "no está", "Instala «Instalador de aplicación» desde Microsoft Store")
        )
    return lista


def revisar_datos(carpeta: Path | None = None) -> Revision:
    """La carpeta de datos tiene que existir (o poder crearse) y dejar escribir."""
    try:
        carpeta = carpeta or directorio_datos()
        carpeta.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=carpeta, prefix=".doctor-", delete=True):
            pass
    except OSError as error:
        return Revision("navaja", "Carpeta de datos", "error", f"no se puede escribir: {error.strerror or error}",
                        "Revisa los permisos de la carpeta o cambia NAVAJA_DATOS")
    return Revision("navaja", "Carpeta de datos", "ok", str(carpeta))


def revisar_acciones() -> Revision:
    try:
        ruta = esquema.buscar(None)
    except NavajaError:
        return Revision("navaja", "acciones.json", "aviso", "no hay (solo hace falta para «acciones»)",
                        "navaja acciones editar")
    try:
        acciones = esquema.cargar(ruta)
    except NavajaError as error:
        return Revision("navaja", "acciones.json", "error", str(error), f"navaja acciones validar --config {ruta}")
    return Revision("navaja", "acciones.json", "ok", f"{len(acciones)} acciones · {ruta}")


def revisar_ia() -> Revision:
    """Solo mira si hay clave (sin llamar a nadie): probarla de verdad es «comprobar-ia»."""
    datos = proveedor_ia.configuracion()
    if datos.apagada:
        return Revision("navaja", "IA (Gemini)", "aviso", f"apagada con {proveedor_ia.ENV_SIN_IA}")
    if not datos.clave:
        return Revision("navaja", "IA (Gemini)", "aviso", "sin clave (solo hace falta para renombrar-ia y resumir-ia)",
                        f"Pon {proveedor_ia.ENV_CLAVE} en .env (copia .env.example)")
    return Revision("navaja", "IA (Gemini)", "ok", f"clave en {datos.origen} · {datos.modelo}",
                    "navaja comprobar-ia la prueba")


def revisar_terminal() -> Revision:
    if es_utf8(console):
        return Revision("navaja", "Terminal", "ok", f"UTF-8 · {platform.system()} {platform.release()}")
    return Revision("navaja", "Terminal", "aviso", f"no escribe en UTF-8 ({console.encoding}): sin iconos",
                    "Usa Windows Terminal o la terminal de VS Code")


def revisar_todo() -> list[Revision]:
    return [
        revisar_python(),
        *revisar_librerias(),
        *revisar_programas(),
        revisar_datos(),
        revisar_acciones(),
        revisar_ia(),
        revisar_terminal(),
    ]


MARCAS = {"ok": "[ok]✔[/]", "aviso": "[aviso]![/]", "error": "[error]✘[/]"}


def doctor() -> None:
    """Revisa que todo esté listo: Python, librerías, programas, datos y acciones.json."""
    revisiones = revisar_todo()
    tabla = tabla_ligera()
    for columna in ("", "Qué", "Cómo está", "Cómo arreglarlo"):
        tabla.add_column(columna, no_wrap=columna in ("", "Qué"))
    grupo = ""
    for revision in revisiones:
        if revision.grupo != grupo:
            grupo = revision.grupo
            tabla.add_row("", f"[titulo]{escape(grupo)}[/]", "", "")
        tabla.add_row(
            MARCAS[revision.estado], escape(revision.nombre), escape(revision.detalle),
            f"[acento]{escape(revision.arreglo)}[/]" if revision.arreglo else "",
        )
    errores = sum(r.estado == "error" for r in revisiones)
    avisos = sum(r.estado == "aviso" for r in revisiones)
    if errores:
        final = f"[error]✘ {errores} {'cosa' if errores == 1 else 'cosas'} por arreglar.[/]"
    elif avisos:
        final = f"[ok]✔ Todo lo necesario está bien.[/] [pista]Lo marcado con ! es opcional: solo lo usan algunas órdenes.[/]"
    else:
        final = "[ok]✔ Todo está perfecto.[/]"
    console.print(recuadro(f"navaja {__version__} · doctor", tabla, Text.from_markup(final)))
    if errores:
        raise typer.Exit(1)


def registrar(app: typer.Typer) -> None:
    app.command(
        "doctor", help="Revisa que todo esté listo y dice cómo arreglar lo que falta.", rich_help_panel=NAVAJA
    )(doctor)
