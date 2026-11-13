"""Utilidades compartidas por todos los comandos."""

from __future__ import annotations

import codecs
import fnmatch
import getpass
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console, Group, RenderableType
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, InvalidResponse
from rich.table import Column, Table
from rich.text import Text
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
        "boton": "bold bright_cyan",
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
        "boton": "bold #e5c07b",
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
        "boton": "bold bright_green",
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
        "boton": "bold #f6d6a8",
    },
}
TEMA_POR_DEFECTO = "clasico"
CONFIG_POR_DEFECTO = {"nombre": "", "tema": TEMA_POR_DEFECTO}
"""Sin nombre guardado, navaja te llama por tu usuario del sistema (y la primera vez
que abres el menú te pregunta cómo quieres que te llame)."""

AJUSTE = "Ajustes"
"""Panel de --help (``rich_help_panel``) de las opciones que el modo interactivo
pregunta al elegir el comando por número, con Intro para dejar su valor."""

HERRAMIENTAS = "Herramientas"
REPITES = "Lo que repites"
NAVAJA = "navaja"
SECCIONES = {
    HERRAMIENTAS: "Se usan al momento: les dices qué hacer y lo hacen.",
    REPITES: "Recetas guardadas en acciones.json: se hacen con una palabra.",
    NAVAJA: "Colores, tu nombre y el manual.",
}
"""Grupos de comandos del menú principal y de ``navaja --help``, con lo que los
distingue. Cada comando dice el suyo con ``rich_help_panel`` al registrarse."""

def preparar_salida(flujo: object, entorno: dict[str, str] | None = None) -> None:
    """Que escribir ✔, → o … nunca rompa navaja con una traza.

    Con la salida redirigida o en Git Bash, Python escribe en la codificación de Windows
    (cp1252), donde esos símbolos no existen. Git Bash (mintty, con ``MSYSTEM``) lee UTF-8:
    ahí se pasa a UTF-8 y salen bien también las tildes. En lo demás (``navaja … > a.txt``
    en PowerShell) se deja la codificación, para que las tildes sigan bien, y lo que no
    cabe sale como «?».
    """
    entorno = os.environ if entorno is None else entorno
    codificacion = (getattr(flujo, "encoding", None) or "").lower().replace("-", "")
    reconfigurar = getattr(flujo, "reconfigure", None)
    if codificacion == "utf8" or reconfigurar is None:
        return
    try:
        if entorno.get("MSYSTEM"):
            reconfigurar(encoding="utf-8", errors="replace")
        else:
            reconfigurar(errors="replace")
    except (OSError, ValueError):
        pass  # un flujo que no se deja cambiar: se queda como está


console = Console(theme=Theme(TEMAS[TEMA_POR_DEFECTO]))
error_console = Console(stderr=True, theme=Theme(TEMAS[TEMA_POR_DEFECTO]))

UNIDADES = ("B", "KB", "MB", "GB", "TB", "PB")


def cuantos(n: int, palabra: str, plural: str | None = None) -> str:
    """``cuantos(1, "archivo")`` → «1 archivo»; ``cuantos(3, "archivo")`` → «3 archivos»."""
    return f"{n} {palabra if n == 1 else (plural or palabra + 's')}"


def bonita(ruta: Path) -> str:
    """Con ~ en vez de la carpeta personal: ~/Pictures/Imagenes IA."""
    try:
        return str(Path("~") / ruta.relative_to(Path.home()))
    except ValueError:
        return str(ruta)


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


def usuario_del_sistema() -> str:
    """Tu usuario de Windows (o de Linux/macOS), con la primera letra en mayúscula."""
    try:
        usuario = getpass.getuser()
    except Exception:  # getuser lanza si no encuentra ninguno
        usuario = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    usuario = usuario.strip()
    return usuario[:1].upper() + usuario[1:]


def nombre_para_saludar(config: dict[str, str]) -> str:
    """El nombre que guardaste en config o, si no hay, tu usuario del sistema."""
    return config["nombre"] or usuario_del_sistema()


def guardar_config(config: dict[str, str], ruta: Path | None = None) -> None:
    ruta = ruta or directorio_datos() / "config.json"
    ruta.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def es_utf8(consola: Console) -> bool:
    """¿La consola escribe en UTF-8? Vale cualquier forma del nombre (utf-8, UTF8, utf_8)."""
    try:
        return codecs.lookup(consola.encoding).name == "utf-8"
    except LookupError:
        return False


def aplicar_tema(nombre: str) -> None:
    """Cambia los colores de ``console`` y ``error_console``."""
    estilos = TEMAS.get(nombre, TEMAS[TEMA_POR_DEFECTO])
    for consola in (console, error_console):
        consola.push_theme(Theme(estilos))


PALABRAS_VOLVER = {"volver", "atrás", "atras"}
"""En el modo interactivo, a la pregunta anterior."""


class Confirmar(Confirm):
    """Pregunta de sí o no en castellano: ``[s/n]``; también acepta «sí», «no» e «y»."""

    choices = ["s", "n"]
    validate_error_message = "[aviso]Responde s o n.[/]"

    def render_default(self, default: object) -> Text:
        return Text("(s)" if default else "(n)", style="prompt.default")

    def process_response(self, value: str) -> bool:
        respuesta = value.strip().lower()
        if respuesta in ("s", "si", "sí", "y", "yes"):
            return True
        if respuesta in ("n", "no"):
            return False
        raise InvalidResponse(self.validate_error_message)


def como_se_escribe(texto: str) -> str:
    """Cómo se escribe una orden donde estás: «navaja ordena deshacer» en la terminal,
    «ordena deshacer» dentro del modo interactivo."""
    from . import interactivo  # aquí y no arriba: interactivo importa este módulo

    return texto if interactivo.activo else f"navaja {texto}"


def confirmar(mensaje: str, saltar: bool = False, por_defecto: bool = False) -> bool:
    """Pide confirmación salvo que se haya pasado ``--si``."""
    if saltar:
        return True
    return Confirmar.ask(mensaje, default=por_defecto, console=console)


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


def destino_libre(destino: Path, reservados: set[str]) -> Path:
    """Como ``ruta_libre``, pero recuerda los nombres ya repartidos en el mismo plan:
    si dos archivos van al mismo sitio, el segundo es «nombre (1).ext»."""
    candidato, indice = destino, 1
    while candidato.exists() or str(candidato).lower() in reservados:
        candidato = destino.with_name(f"{destino.stem} ({indice}){destino.suffix}")
        indice += 1
    reservados.add(str(candidato).lower())
    return candidato


def carpeta_papelera() -> Path:
    """La papelera de navaja: lo que se quita aquí se puede devolver a su sitio."""
    return directorio_datos() / "papelera"


ARCHIVOS_DE_SISTEMA = {"desktop.ini", "thumbs.db", ".ds_store"}


def es_oculto(ruta: Path) -> bool:
    """Empieza por punto, es un archivo de sistema (desktop.ini…) o Windows lo marca oculto."""
    if ruta.name.startswith(".") or ruta.name.lower() in ARCHIVOS_DE_SISTEMA:
        return True
    if os.name == "nt":
        try:
            atributos = ruta.lstat().st_file_attributes
        except (OSError, AttributeError):
            return False
        return bool(atributos & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))
    return False


def iterar_archivos(
    ruta: Path,
    recursivo: bool = False,
    ocultos: bool = False,
    patron: str = "*",
    excluir: tuple[str, ...] = (),
) -> list[Path]:
    """Lista archivos (sin seguir enlaces) filtrando por glob y ocultos.

    Con ``recursivo``, no entra en las carpetas que se llamen como alguno de ``excluir``
    (sin mirar mayúsculas, estén donde estén: node_modules, __pycache__…).
    """
    encontrados: list[Path] = []
    saltar = {nombre.lower() for nombre in excluir}

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
            dirs[:] = [nombre for nombre in dirs if not es_oculto(Path(actual) / nombre)]
        if saltar:
            dirs[:] = [nombre for nombre in dirs if nombre.lower() not in saltar]
        for nombre in sorted(archivos):
            if not fnmatch.fnmatch(nombre, patron):
                continue
            candidato = Path(actual) / nombre
            if not ocultos and es_oculto(candidato):
                continue
            try:
                if candidato.is_file() and not candidato.is_symlink():
                    encontrados.append(candidato)
            except OSError:
                continue
    return encontrados


MARCO = 4
"""Columnas que se come un ``recuadro``: los dos bordes y un espacio a cada lado."""

HUECO = 3
"""Columnas entre una columna y la siguiente en una ``tabla_ligera``: un espacio a cada
lado y el separador (que en esta tabla es un espacio)."""


def resumen(filas: list[tuple[str, str]]) -> Table:
    """Lo de arriba de un recuadro: «Carpeta  ~/Descargas», «Ocupa  219 B», una por fila.

    La etiqueta en gris y sin partir; el valor (con markup) se parte si no cabe.
    """
    datos = Table.grid(padding=(0, 2))
    datos.add_column(style="pista", no_wrap=True)
    datos.add_column(overflow="fold")
    for etiqueta, valor in filas:
        datos.add_row(etiqueta, valor)
    return datos


def tabla_ligera() -> Table:
    """Tabla sin bordes propios, para ir dentro de un ``recuadro``: solo la línea bajo
    las cabeceras."""
    return Table(
        box=box.SIMPLE_HEAD,
        show_edge=False,
        header_style="titulo",
        border_style="borde",
        pad_edge=False,
        expand=False,
    )


def recuadro(titulo: str, *partes: RenderableType) -> Panel:
    """El recuadro de una herramienta (ocupa, listar): mide lo que su contenido, nunca
    más que la ventana, con las partes una debajo de otra y una línea entre ellas."""
    separadas: list[RenderableType] = []
    for parte in partes:
        if separadas:
            separadas.append(Text(""))
        separadas.append(parte)
    return Panel(
        Group(*separadas),
        title=f"[titulo]{escape(titulo)}[/]",
        title_align="left",
        border_style="marco",
        box=box.ROUNDED,
        expand=False,
        padding=(0, 1),
    )


def crear_tabla(columnas: list[str], titulo: str | None = None) -> Table:
    tabla = Table(title=titulo, header_style="titulo", border_style="borde", expand=False)
    for columna in columnas:
        tabla.add_column(columna, overflow="fold")
    return tabla


def _peso(ruta: Path) -> int:
    """Lo que cuenta un archivo en la barra: su tamaño (1 si está vacío o no se puede leer,
    para que también avance)."""
    try:
        return max(ruta.stat().st_size, 1)
    except OSError:
        return 1


@contextmanager
def barra_de_archivos(rutas: list[Path]) -> Iterator[Callable[[Path], None]]:
    """Barra de progreso para hacer algo con ``rutas``, una tras otra.

    Da una función a la que se llama con cada ruta justo antes de empezar con ella:
    enseña su nombre, «N de M» y el tiempo que lleva, y suma lo que pesaba la anterior.
    El tiempo que queda no: con los primeros archivos pequeños sale disparatado.

    Avanza por tamaño, no por número de archivos: un vídeo de 2 GB pesa más que un
    .txt. Al terminar se borra (lo que queda en pantalla es el resumen), y fuera de
    una terminal no sale (tampoco en Git Bash: Python no lo ve como terminal).

    Todo con los colores del tema. Un nombre largo se corta con «…» para que la barra
    sea siempre de una línea, y en la consola clásica de Windows el spinner es de rayitas
    (el de puntos es braille y ahí puede salir como cuadraditos).
    """
    total = len(rutas)
    pesos = {ruta: _peso(ruta) for ruta in rutas}
    progreso = Progress(
        SpinnerColumn("line" if console.legacy_windows else "dots", style="acento"),
        TextColumn("[pista]{task.fields[cuenta]}[/]"),
        BarColumn(
            bar_width=24, style="borde", complete_style="acento", finished_style="ok",
            pulse_style="pista",
        ),
        TaskProgressColumn(text_format="[pista]{task.percentage:>3.0f}%[/]"),
        TimeElapsedColumn(),
        # el nombre es lo único que encoge (ratio): lo demás no se aprieta ni se parte
        TextColumn(
            "{task.description}", table_column=Column(no_wrap=True, overflow="ellipsis", ratio=1)
        ),
        console=console,
        expand=True,
        transient=True,
        disable=not console.is_terminal,
    )
    # Lo que Rich pinta con sus colores (el reloj), con los del tema
    colores = Theme({"progress.elapsed": console.get_style("pista")})
    tarea = progreso.add_task("", total=sum(pesos.values()), cuenta=f"0 de {total}")
    empezados = 0
    anterior = 0  # lo que pesa el archivo en curso: se suma al empezar el siguiente

    def avance(ruta: Path) -> None:
        nonlocal empezados, anterior
        progreso.advance(tarea, anterior)
        anterior = pesos.get(ruta, 1)
        empezados += 1
        progreso.update(
            tarea, description=escape(ruta.name), cuenta=f"{empezados} de {total}"
        )

    with console.use_theme(colores), progreso:
        yield avance


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


def _editor() -> list[str]:
    """El editor del usuario (variable EDITOR) o, si no hay, el Bloc de notas / nano."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        editor = "notepad" if os.name == "nt" else "nano"
    partes = shlex.split(editor)
    if not partes or not shutil.which(partes[0]):
        raise RuntimeError(
            f"No se encontró el editor '{partes[0] if partes else editor}'. Define la variable EDITOR."
        )
    return partes


def abrir_en_editor(ruta: Path) -> None:
    """Abre un archivo en el editor y espera a que se cierre."""
    resultado = subprocess.run([*_editor(), str(ruta)])
    if resultado.returncode != 0:
        raise RuntimeError("El editor terminó con un error.")


def editar_texto(texto_inicial: str = "") -> str:
    """Abre el editor del usuario con un texto temporal y devuelve el resultado."""
    partes = _editor()

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
