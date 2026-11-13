"""Modo interactivo: ``navaja`` sin argumentos abre un menú y espera órdenes hasta ``salir``."""

from __future__ import annotations

import difflib
import functools
import os
import re
import shlex
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from rich import box
from rich.cells import cell_len
from rich.console import Group
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from .comandos.ayuda import (
    ayuda_aqui,
    ayuda_corta,
    es_grupo,
    opciones_visibles,
    por_secciones,
    resolver,
    valor_texto,
)
from .comandos.ayuda import subcomandos as opciones_de
from .comun import (
    AJUSTE,
    HERRAMIENTAS,
    NAVAJA,
    PALABRAS_VOLVER,
    REPITES,
    SECCIONES,
    console,
    error_console,
    es_oculto,
    es_utf8,
    tamano_legible,
)
from .entrada import crear_lector, palabras_del_argumento
from .errores import NavajaError
from .filtros import (
    CATEGORIAS,
    EJEMPLOS_FECHA,
    ETIQUETAS,
    FILTRO,
    periodo,
    rango,
    sin_tildes,
)

Lector = Callable[[str], str]
Paso = Callable[[], "list[str] | None"]
"""Una pregunta del modo guiado: devuelve lo que añade a la orden, o None si no toca
con lo que se ha contestado antes (se salta, también al volver hacia atrás)."""

SALIR = {"salir", "exit", "quit"}
MENU = {"menu", "menú"}
AYUDA_SOLA = {"ayuda", "help", "?"}
LIMPIAR_PANTALLA = {"cls", "clear"}
VOLVER = {"", "0"} | PALABRAS_VOLVER
ALIAS = {"ls": "listar", "dir": "listar"}
PREFIJOS = {"navaja", "nav"}
CD = re.compile(r"^cd(?=$|[\s./\\])(.*)$", re.IGNORECASE)
AYUDA_DE = re.compile(r"^(?:ayuda|help|\?)\s+(.+)$|^(.+?)\s+\?$", re.IGNORECASE)

ANTES_DE_PREGUNTAR = {
    "notas abrir": ["notas", "listar"],
    "notas borrar": ["notas", "listar"],
    "acciones ejecutar": ["acciones", "ver"],
}
"""Lo que se enseña antes de las preguntas: para elegir una nota (o una acción) hay que
ver sus números."""

EL_TEXTO_YA_ELIGE = {"renombra cambiar", "renombra avanzado", "ordena nombre"}
"""Aquí el texto (o el patrón) ya dice qué archivos se tocan: no se pregunta «¿Con qué
archivos?» (los filtros siguen valiendo escritos: --solo, --desde…)."""

AYUDA = (
    "[pista]·  un número o un comando  ·  [/][acento]ayuda[/][pista] lo explica todo[/]"
)

activo = False
"""True mientras el modo interactivo está abierto (evita abrir uno dentro de otro)."""


class Salir(Exception):
    """El usuario quiere cerrar el modo interactivo."""


class Atras(Exception):
    """En una pregunta se ha escrito «volver»: hay que repetir la anterior."""


def es_volver(crudo: str) -> bool:
    """«volver» o «atrás» (a la pregunta anterior). «salir» en una pregunta cancela."""
    palabra = crudo.strip().lower()
    if palabra in SALIR:
        raise KeyboardInterrupt  # como Ctrl+C: se cancela sin hacer nada
    return palabra in PALABRAS_VOLVER


def puede_iniciar() -> bool:
    """Solo se abre si hay una persona delante (no en scripts ni tuberías)."""
    return not activo and sys.stdin.isatty() and sys.stdout.isatty()


def expandir(texto: str) -> str:
    """Convierte ``~`` en la carpeta personal."""
    if texto == "~" or texto.startswith(("~/", "~\\")):
        return os.path.expanduser(texto)
    return texto


def quitar_comillas(texto: str) -> str:
    if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'":
        return texto[1:-1]
    return texto


def dividir(linea: str) -> list[str]:
    """Parte una línea en palabras respetando comillas.

    Las barras invertidas se conservan (rutas de Windows y expresiones regulares).
    Lanza ``ValueError`` si falta cerrar unas comillas.
    """
    return [expandir(quitar_comillas(p)) for p in shlex.split(linea, posix=False)]


def citar(texto: str) -> str:
    """Pone comillas a lo que tiene espacios, para mostrar la orden equivalente."""
    return f'"{texto}"' if not texto or any(c.isspace() for c in texto) else texto


def nombre_carpeta(ruta: Path) -> str:
    if ruta == Path.home():
        return "~"
    return ruta.name or str(ruta)


def texto_prompt(camino: list[str]) -> str:
    try:
        carpeta = nombre_carpeta(Path.cwd())
    except OSError:
        carpeta = "?"
    sub = "".join(f"[pista]/{escape(nombre)}[/]" for nombre in camino)
    return f"[acento]{escape(carpeta)}[/]{sub}[pista]>[/] "


ICONOS = {
    "listar": "📂",
    "ocupa": "📊",
    "limpia": "🧹",
    "ordena": "📦",
    "renombra": "🔤",
    "duplicados": "👯",
    "copia": "📋",
    "notas": "📝",
    "acciones": "⚡",
    "tema": "🎨",
    "config": "👤",
    "manual": "📖",
    HERRAMIENTAS: "🧰",
    REPITES: "🔁",
    NAVAJA: "🔧",
}
"""Icono de cada comando y de cada sección del menú. Todos son emojis de un solo carácter
y de dos columnas (sin el selector U+FE0F), para que Rich y la terminal midan igual."""

ANCHO_MENU = 80
"""Lo más ancho que se hacen los recuadros del menú, aunque la ventana sea mayor."""

ANCHO_MINIMO = 30
"""Aunque la ventana sea más estrecha, los recuadros no se hacen más pequeños que esto."""

LARGO_MENU = 46
"""Lo más que mide la frase de cada opción del menú: así cabe en una fila en una ventana
de 80 columnas, con el número, el icono y el nombre más largo delante."""

CORTO = {
    "ordena": "Por tipo, por fecha, por nombre o por letra.",
    "renombra": "En masa: cambiar texto, numerar, la fecha…",
    "duplicados": "Archivos repetidos, quitados sin perder nada.",
    "copia": "Copia archivos sin tocar los originales.",
    "acciones": "Tus recetas guardadas: verlas y hacerlas.",
    "config": "Tu nombre y dónde guarda navaja tus datos.",
    "manual": "Todo navaja explicado, con opciones y atajos.",
    "ordena tipo": "Imágenes, Documentos, Vídeos… a su carpeta.",
    "ordena fecha": "Una carpeta por mes, por año o por día.",
    "ordena tramo": "Junta los archivos de unas fechas (del… al…).",
    "ordena nombre": "Por nombre: si llevan un texto, juntos.",
    "ordena letra": "Una carpeta por inicial (A, B… y 0-9).",
    "renombra cambiar": "Cambia un texto por otro (IMG_ → foto_).",
    "renombra delante": "Añade texto delante (2026_informe.pdf).",
    "renombra detras": "Añade texto detrás (informe_v2.pdf).",
    "renombra numerar": "Un nombre y un número (playa_001.jpg…).",
    "renombra fecha": "Pone la fecha delante (2026-10-26_IMG_1.jpg).",
    "renombra arreglar": "Minúsculas, sin tildes ni espacios.",
    "renombra plantilla": "Tu formato con huecos ({fecha}_{n:03}{ext}).",
    "renombra avanzado": "Con expresiones regulares (casos difíciles).",
    "renombra deshacer": "Deja los nombres como estaban antes.",
    "copia a": "Copia una carpeta (o unos archivos) a otra.",
    "notas agregar": "Añade una nota o un enlace.",
    "notas abrir": "Abre un enlace o enseña (o cambia) una nota.",
    "acciones ejecutar": "Hace una acción: enseña el plan y pregunta.",
    "acciones editar": "Abre acciones.json en tu editor.",
    "acciones validar": "Comprueba acciones.json sin tocar nada.",
    "acciones versiones": "Versiones viejas: verlas, recuperarlas…",
    "acciones versiones ver": "Lista las versiones viejas guardadas.",
    "acciones versiones recuperar": "Las devuelve a su sitio, sin pisar nada.",
    "acciones versiones borrar": "Borra para siempre las que ya no quieres.",
    "tema ver": "Los temas, con una muestra de sus colores.",
    "config ver": "Tu nombre, tu tema y dónde están tus datos.",
    "config nombre": "Cambia el nombre con el que te saluda.",
    "config autocompletar": "Tab en PowerShell o bash (ord⇥ → ordena).",
}
"""Frase del menú de las opciones cuya ayuda no cabe en ``LARGO_MENU``. Solo para el
menú: ``--help`` y el manual siguen con la frase entera. Las demás usan su ayuda tal cual
(``test_ayuda`` falla si alguna no cabe y no está aquí)."""


def frase_del_menu(camino: list[str], nombre: str, comando: Any) -> str:
    """Lo que hace la opción, en una frase que cabe en una fila del menú."""
    return CORTO.get(" ".join([*camino, nombre])) or comando.get_short_help_str(LARGO_MENU)


def con_iconos() -> bool:
    """¿Se pueden poner emojis? Hace falta UTF-8 y, en Windows, una terminal moderna
    (Windows Terminal o la de VS Code): la consola antigua los pinta como cuadrados.

    Se mira por las variables que esas terminales ponen (``WT_SESSION``,
    ``TERM_PROGRAM``); se heredan, así que una consola antigua abierta desde Windows
    Terminal también las tiene. Con ``NAVAJA_SIN_ICONOS`` no salen nunca.
    """
    if os.environ.get("NAVAJA_SIN_ICONOS") or not es_utf8(console):
        return False
    if sys.platform == "win32":
        return bool(os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM"))
    return True


def icono(clave: str, iconos: bool) -> str:
    """El icono seguido de un espacio, o nada si no hay o no se pueden poner."""
    return f"{ICONOS[clave]} " if iconos and clave in ICONOS else ""


def recuadro(
    titulo: str,
    subtitulo: str,
    filas: list[tuple[int, str, str]],
    ancho_numero: int,
    ancho_nombre: int,
    iconos: bool,
) -> Panel:
    """Un grupo del menú: número, icono, nombre y lo que hace, una fila por opción.

    Los anchos vienen de fuera para que todos los recuadros queden alineados. Cada fila
    se monta a mano: el número y el nombre no se recortan nunca y, si la ventana es
    estrecha, la frase se acorta con «…» en vez de pasar a la línea de abajo.
    Con ``iconos``, cada fila lleva el de su comando (solo en el menú principal: en un
    submenú, «listar» de notas no es el «listar» de navaja).
    """
    ancho = max(min(console.width, ANCHO_MENU), ANCHO_MINIMO)
    dentro = ancho - 4  # los dos bordes y un espacio a cada lado
    lineas = []
    for numero, nombre, frase in filas:
        linea = Text(no_wrap=True, overflow="ellipsis")
        linea.append(f" {numero:>{ancho_numero}}  ", style="boton")
        linea.append(icono(nombre, iconos))
        linea.append(nombre, style="bold")
        linea.append(" " * (ancho_nombre - cell_len(nombre)))
        sitio = dentro - linea.cell_len - 2
        if sitio >= 8:  # con menos no se entiende la frase: mejor sin ella
            resto = Text(frase, style="pista")
            resto.truncate(sitio, overflow="ellipsis")
            linea.append("  ")
            linea.append_text(resto)
        lineas.append(linea)
    cabe_subtitulo = bool(subtitulo) and cell_len(subtitulo) + 6 <= ancho
    return Panel(
        Group(*lineas),
        title=f"[titulo]{escape(titulo)}[/]" if titulo else None,
        title_align="left",
        # el subtítulo solo si cabe en el borde de abajo
        subtitle=f"[pista]{escape(subtitulo)}[/]" if cabe_subtitulo else None,
        subtitle_align="right",
        border_style="marco",
        box=box.ROUNDED,
        width=ancho,
        padding=(0, 1),
    )


def mostrar_menu(grupo: Any, camino: list[str]) -> None:
    """Las opciones numeradas, un recuadro por sección (en un submenú, uno solo).

    Todos los recuadros miden lo mismo, para que se vean como una columna.
    """
    secciones = por_secciones(grupo)
    nombres = [nombre for _, comandos in secciones for nombre, _ in comandos]
    ancho_numero = len(str(len(nombres)))
    ancho_nombre = max(cell_len(nombre) for nombre in nombres)
    iconos = con_iconos()
    numero = 0
    for seccion_, comandos in secciones:
        filas = []
        for nombre, comando in comandos:
            numero += 1
            filas.append((numero, nombre, frase_del_menu(camino, nombre, comando)))
        if seccion_:
            titulo = f"{icono(seccion_, iconos)}{seccion_}"
            subtitulo = SECCIONES.get(seccion_, "")
        else:  # un submenú: el título es el comando del que cuelga
            titulo = f"{icono(camino[0], iconos)}{' '.join(camino)}" if camino else ""
            subtitulo = ""
        console.print(
            recuadro(titulo, subtitulo, filas, ancho_numero, ancho_nombre, iconos and not camino)
        )
    if camino:
        console.print(
            f"   [boton]{0:>{ancho_numero}}[/]  [bold]volver[/]   [pista]·  Intro también  ·  [/]"
            "[acento]ayuda[/][pista] explica estas opciones[/]",
            no_wrap=True,
            overflow="ellipsis",
        )
    else:
        console.print(
            f"   [boton]{0:>{ancho_numero}}[/]  [bold]salir[/]   {AYUDA}",
            no_wrap=True,
            overflow="ellipsis",
        )
        console.print()


def ejecutar(raiz: Any, argumentos: list[str]) -> int:
    """Ejecuta una orden como si se escribiera en la terminal y devuelve su código."""
    try:
        raiz.main(args=argumentos, prog_name="navaja", standalone_mode=True)
    except SystemExit as salida:
        codigo = salida.code
        return codigo if isinstance(codigo, int) else (0 if codigo is None else 1)
    except KeyboardInterrupt:
        console.print("\n[aviso]Cancelado.[/]")
        return 130
    except Exception as exc:  # un fallo inesperado no debe cerrar navaja
        error_console.print(
            f"[error]Error inesperado ({type(exc).__name__}):[/] {escape(str(exc))}",
            soft_wrap=True,
        )
        return 1
    return 0


def leer_texto(leer: Lector, prompt: str, defecto: str) -> str:
    """Intro deja el valor por defecto; solo espacios valen como espacio («numerar» con « »).

    «volver» lanza ``Atras``; entre comillas («"volver"») es el texto volver.
    """
    crudo = leer(prompt)
    if es_volver(crudo):
        raise Atras
    if crudo == "":
        return defecto
    if not crudo.strip():
        return crudo
    return expandir(quitar_comillas(crudo.strip()))


def pasos_carpeta(comando: Any, leer: Lector) -> list[Paso]:
    """Si la orden cambia archivos de una carpeta, lo primero es preguntar cuál.

    Son las que tienen --carpeta (ordena, renombra) y las que piden confirmación
    (--si) y reciben la carpeta como primer argumento (limpia, duplicados borrar).
    Las que solo miran (listar, ocupa…) trabajan en la actual sin preguntar.
    """
    opciones = {o for p in comando.params for o in getattr(p, "opts", ())}
    if "--carpeta" in opciones:
        return [functools.partial(preguntar_carpeta, leer, True)]
    argumentos = [p for p in comando.params if p.param_type_name == "argument"]
    if (
        "--si" in opciones
        and argumentos
        and not argumentos[0].required
        and getattr(argumentos[0].type, "name", "") == "path"
    ):
        return [functools.partial(preguntar_carpeta, leer, False)]
    return []


def preguntar_carpeta(leer: Lector, como_opcion: bool = True) -> list[str]:
    """Intro = la carpeta actual. Vale una ruta completa, ~\\Documents, «..» o arrastrarla.

    Devuelve ``--carpeta RUTA`` o, si la orden la recibe como argumento, ``RUTA``.
    """
    try:
        actual = Path.cwd()
    except OSError:
        actual = Path(".")
    while True:
        valor = leer_texto(
            leer, f"  ¿En qué carpeta? [pista](Intro = esta: {escape(str(actual))})[/]: ", ""
        )
        if not valor:
            return []
        ruta = Path(valor)
        if ruta.is_dir():
            if ruta.resolve() == actual.resolve():
                return []
            return ["--carpeta", valor] if como_opcion else [valor]
        if ruta.exists():
            console.print("  [aviso]Eso es un archivo, no una carpeta.[/]")
        else:
            console.print(
                f"  [aviso]No existe la carpeta «{escape(valor)}».[/] [pista]Escribe la ruta "
                "completa (C:\\Users\\tu_usuario\\Documents), ~\\Documents, o arrastra la "
                "carpeta aquí desde el explorador.[/]",
                soft_wrap=True,
            )


def parece_carpeta(valor: str) -> bool:
    """«C:\\Users\\…», «~\\Documents» o una carpeta que existe con barras: no es un texto del nombre."""
    if re.match(r"^[a-zA-Z]:[\\/]", valor) or valor.startswith(("~/", "~\\", "\\\\", "/")):
        return True
    return ("/" in valor or "\\" in valor) and Path(valor).is_dir()


def pasos_obligatorios(comando: Any, leer: Lector) -> list[Paso]:
    """Una pregunta por cada argumento que hace falta.

    Los obligatorios, siempre. Los opcionales de texto (como el «por» de
    renombra cambiar) también, con Intro para dejar su valor por defecto. Las
    rutas opcionales (la carpeta) y las listas no se preguntan: se usa la
    carpeta actual. Solo se escriben si detrás va otro valor, para no
    descolocar las posiciones.
    """
    pasos: list[Paso] = []
    pendientes: list[str] = []
    for param in comando.params:
        if param.param_type_name != "argument":
            continue
        es_ruta = getattr(getattr(param, "type", None), "name", "") == "path"
        es_lista = getattr(param, "nargs", 1) == -1
        if not param.required and (es_ruta or es_lista):
            if param.default is not None and not es_lista:
                pendientes.append(valor_texto(param.default))
            continue
        pasos.append(functools.partial(preguntar_argumento, param, leer, pendientes, comando))
        pendientes = []
    return pasos


def preguntar_argumento(
    param: Any, leer: Lector, delante: list[str], comando: Any = None
) -> list[str]:
    """Pregunta un argumento. Si sabe qué valores tiene (los nombres de tus acciones…),
    los enseña y Tab los completa; si no, Tab completa rutas."""
    posibles = palabras_del_argumento(comando, [], "") if comando is not None else []
    con_palabras = getattr(leer, "con_palabras", None)
    if posibles:
        console.print(f"  [pista]Puedes elegir: {escape(', '.join(posibles))}[/]", soft_wrap=True)
    if posibles and con_palabras is not None:
        with con_palabras(posibles):
            return _preguntar_argumento(param, leer, delante)
    return _preguntar_argumento(param, leer, delante)


def _preguntar_argumento(param: Any, leer: Lector, delante: list[str]) -> list[str]:
    texto = escape((getattr(param, "help", None) or param.name or "").rstrip("."))
    es_fecha = param.name in ("desde", "hasta")
    es_lista = getattr(param, "nargs", 1) == -1
    es_ruta = getattr(getattr(param, "type", None), "name", "") == "path"
    if param.required:
        while True:
            valor = leer_texto(leer, f"  {texto}: ", "")
            if not valor:
                console.print("  [aviso]Hace falta un valor.[/]")
                continue
            if not es_ruta and parece_carpeta(valor):
                console.print(
                    "  [aviso]Eso parece una carpeta.[/] [pista]Aquí va un texto del nombre; la "
                    "carpeta se elige en «¿En qué carpeta?» (escribe volver para ir a ella) "
                    "o con cd en el menú.[/]",
                    soft_wrap=True,
                )
                continue
            if es_fecha:
                try:
                    periodo(valor)
                except ValueError as exc:
                    console.print(f"  [aviso]{escape(str(exc))}[/]")
                    continue
            break
    elif es_fecha:
        defecto = "" if param.default is None else valor_texto(param.default)
        valor = preguntar_fecha(leer, f"  {texto} [pista](Intro = {escape(defecto)})[/]: ") or defecto
    else:
        defecto = "" if param.default is None else valor_texto(param.default)
        pista = "vacío" if defecto == "" else defecto
        valor = leer_texto(leer, f"  {texto} [pista](Intro = {escape(pista)})[/]: ", defecto)
    return delante + (dividir(valor) if es_lista else [valor])


def pasos_ajustes(comando: Any, leer: Lector) -> list[Paso]:
    """Una pregunta por cada opción del panel «Ajustes»."""
    return [
        functools.partial(preguntar_ajuste, param, leer)
        for param in comando.params
        if param.param_type_name == "option" and getattr(param, "rich_help_panel", None) == AJUSTE
    ]


def preguntar_ajuste(param: Any, leer: Lector) -> list[str]:
    """Solo añade la opción si cambia algo."""
    texto = escape((getattr(param, "help", None) or param.name or "").rstrip("."))
    nombre = max(param.opts, key=len)
    if getattr(param, "is_flag", False):
        respuesta = leer(f"  {texto} [pista](s/n · Intro = no)[/]: ")
        if es_volver(respuesta):
            raise Atras
        return [nombre] if respuesta.strip().lower() in ("s", "si", "sí", "y") else []
    vacio = param.default is None or getattr(param, "multiple", False)
    defecto = "" if vacio else valor_texto(param.default)
    elecciones = [valor_texto(c) for c in getattr(param.type, "choices", None) or []]
    if elecciones:
        pista = f"{', '.join(elecciones[:-1])} o {elecciones[-1]} · Intro = {defecto}"
    else:
        pista = f"Intro = {defecto}" if defecto else "Intro para saltar"
    while True:
        valor = leer_texto(leer, f"  {texto} [pista]({escape(pista)})[/]: ", defecto)
        if not elecciones:
            break
        # «dia» vale por «día» y «Mes» por «mes»
        parecida = [e for e in elecciones if sin_tildes(e.lower()) == sin_tildes(valor.lower())]
        if parecida:
            valor = parecida[0]
            break
        console.print(f"  [aviso]Escribe {', '.join(elecciones[:-1])} o {elecciones[-1]}.[/]")
    return [nombre, valor] if valor != defecto else []


def preguntar_fecha(leer: Lector, prompt: str) -> str:
    """Pide una fecha hasta que se entienda (o Intro para dejarla vacía)."""
    while True:
        valor = leer_texto(leer, prompt, "")
        if not valor:
            return ""
        try:
            periodo(valor)
            return valor
        except ValueError as exc:
            console.print(f"  [aviso]{escape(str(exc))}[/]")


def pasos_filtro(comando: Any, leer: Lector) -> list[Paso]:
    """Una sola pregunta, «¿Con qué archivos?», en vez de un filtro tras otro."""
    filtros = {
        max(p.opts, key=len)
        for p in comando.params
        if p.param_type_name == "option" and getattr(p, "rich_help_panel", None) == FILTRO
    }
    return [functools.partial(preguntar_filtro, filtros, leer)] if filtros else []


def es_numero(texto: str) -> bool:
    """Solo cifras de 0 a 9 («²» o «٣» también son dígitos para Python, pero int() falla)."""
    return texto.isascii() and texto.isdigit()


def elegir_numero(leer: Lector, prompt: str, cuantas: int, intro: int | None = None) -> int:
    """Pide un número de una lista. 0 o «volver» lanzan ``Atras``; Intro elige ``intro``."""
    while True:
        respuesta = leer(prompt).strip()
        if respuesta == "0" or es_volver(respuesta):
            raise Atras
        if not respuesta and intro is not None:
            return intro
        if es_numero(respuesta) and 1 <= int(respuesta) <= cuantas:
            return int(respuesta)
        console.print(f"  [aviso]Elige un número del 1 al {cuantas} (0 para volver).[/]")


def preguntar_filtro(filtros: set[str], leer: Lector) -> list[str]:
    opciones = [("todos", "Todos los de la carpeta")]
    if "--solo" in filtros:
        opciones.append(("tipo", "Solo de un tipo (imágenes, documentos, vídeos…)"))
    if "--contiene" in filtros:
        opciones.append(("texto", "Los que llevan un texto en el nombre"))
    if "--desde" in filtros:
        opciones.append(("fechas", "Los de unas fechas (de una a otra)"))

    while True:  # «volver» en el detalle trae aquí; aquí, a la pregunta anterior
        console.print("  [bold]¿Con qué archivos?[/]")
        for numero, (_, texto) in enumerate(opciones, start=1):
            console.print(f"    [acento]{numero}[/]  {texto}")
        console.print("    [acento]0[/]  [pista]volver[/]")
        numero = elegir_numero(leer, "  Elige [pista](Intro = 1, todos)[/]: ", len(opciones), intro=1)
        clave = opciones[numero - 1][0]
        try:
            if clave == "tipo":
                return preguntar_tipo(leer)
            if clave == "texto":
                return preguntar_contiene(leer)
            if clave == "fechas":
                return preguntar_fechas(leer)
            return []
        except Atras:
            continue


def preguntar_tipo(leer: Lector) -> list[str]:
    tipos = list(CATEGORIAS)
    for numero, categoria in enumerate(tipos, start=1):
        console.print(f"    [acento]{numero}[/]  {ETIQUETAS[categoria]}")
    console.print("    [acento]0[/]  [pista]volver[/]")
    while True:
        respuesta = leer_texto(
            leer, "  ¿Qué tipo? [pista](un número, o extensiones: jpg,png)[/]: ", ""
        )
        if respuesta == "0":
            raise Atras
        if respuesta.isdigit() and 1 <= int(respuesta) <= len(tipos):
            return ["--solo", tipos[int(respuesta) - 1]]
        if respuesta and not respuesta.isdigit():
            return ["--solo", respuesta]
        console.print(f"  [aviso]Elige un número del 1 al {len(tipos)} o escribe extensiones.[/]")


def preguntar_contiene(leer: Lector) -> list[str]:
    while True:
        texto = leer_texto(leer, "  Texto que tiene que llevar el nombre: ", "")
        if texto:
            return ["--contiene", texto]
        console.print("  [aviso]Hace falta un texto.[/]")


def preguntar_fechas(leer: Lector) -> list[str]:
    ejemplos = escape(EJEMPLOS_FECHA)
    while True:
        desde = preguntar_fecha(
            leer, f"  Desde qué fecha [pista](ej.: {ejemplos} · Intro = desde siempre)[/]: "
        )
        try:
            hasta = preguntar_fecha(leer, "  Hasta qué fecha, incluida [pista](Intro = hoy)[/]: ")
        except Atras:
            continue  # otra vez «desde»
        try:
            rango(desde, hasta)
        except ValueError as exc:
            console.print(f"  [aviso]{escape(str(exc))}[/]")
            continue
        return (["--desde", desde] if desde else []) + (["--hasta", hasta] if hasta else [])


def pista_opciones(nombres: list[str], comando: Any) -> None:
    opciones = opciones_visibles(comando)
    if not opciones:
        return
    largas = " ".join(max(o.opts, key=len) for o in opciones)
    console.print(
        f"[pista]Más opciones: {escape(largas)} · [/]"
        f"[acento]ayuda {escape(' '.join(nombres))}[/][pista] explica cada una[/]",
        soft_wrap=True,
    )


def pasos_copia(comando: Any, leer: Lector) -> list[Paso]:
    """«copia a» por menú: primero qué copiar (toda una carpeta o unos archivos de una
    lista) y, según eso, lo demás. Lo elegido se guarda en ``eleccion`` para las
    preguntas de después; el destino y los archivos se escriben al final de la orden.
    """
    eleccion: dict[str, Any] = {"archivos": False, "carpeta": Path("."), "nombres": [], "destino": ""}
    filtros = {
        max(p.opts, key=len)
        for p in comando.params
        if p.param_type_name == "option" and getattr(p, "rich_help_panel", None) == FILTRO
    }

    def que_copiar() -> list[str]:
        console.print("  [bold]¿Qué quieres copiar?[/]")
        console.print("    [acento]1[/]  Toda una carpeta (o parte, con un filtro)")
        console.print("    [acento]2[/]  Unos archivos que eliges de una lista")
        console.print("    [acento]0[/]  [pista]volver[/]")
        numero = elegir_numero(leer, "  Elige [pista](Intro = 1)[/]: ", 2, intro=1)
        eleccion["archivos"] = numero == 2
        return []

    def carpeta() -> list[str]:
        valor = preguntar_carpeta(leer, True)
        eleccion["carpeta"] = Path(valor[1]) if valor else Path(".")
        return valor

    def archivos() -> list[str] | None:
        if not eleccion["archivos"]:
            return None
        eleccion["nombres"] = elegir_archivos(eleccion["carpeta"], leer)
        return []

    def destino() -> list[str]:
        eleccion["destino"] = elegir_destino(leer)
        return []

    def si_cambia() -> list[str]:
        console.print("  [bold]Si allí ya hay uno distinto con el mismo nombre:[/]")
        console.print("    [acento]1[/]  Guardar la copia al lado, como «nombre (1)»")
        console.print("    [acento]2[/]  Quedarse con el más reciente (el viejo se guarda)")
        console.print("    [acento]0[/]  [pista]volver[/]")
        numero = elegir_numero(leer, "  Elige [pista](Intro = 1)[/]: ", 2, intro=1)
        return ["--si-cambia", "el-mas-nuevo"] if numero == 2 else []

    def filtro() -> list[str] | None:
        return None if eleccion["archivos"] else preguntar_filtro(filtros, leer)

    def destino_y_archivos() -> list[str]:
        """No pregunta: pone el destino y los archivos al final de la orden, detrás de
        «--», para que un archivo que empieza por «-» («-borrador.txt») no se lea como
        una opción. Las opciones (--si-cambia, --solo…) ya han ido antes."""
        if not eleccion["archivos"]:
            return [eleccion["destino"]]
        return ["--", eleccion["destino"], *eleccion["nombres"]]

    return [que_copiar, carpeta, archivos, destino, si_cambia, filtro, destino_y_archivos]


CARPETAS_DE_WINDOWS = {
    "descargas": "Downloads",
    "documentos": "Documents",
    "escritorio": "Desktop",
    "imagenes": "Pictures",
    "musica": "Music",
    "videos": "Videos",
}
"""El Explorador las enseña en castellano, pero en el disco se llaman en inglés:
«C:\\Users\\sergi\\Descargas» no existe; la de verdad es «C:\\Users\\sergi\\Downloads»."""


def carpeta_de_windows(valor: str) -> Path | None:
    """Si ``valor`` acaba en el nombre en castellano de una carpeta de Windows (Descargas,
    Documentos…), la de verdad de tu usuario, si existe."""
    ingles = CARPETAS_DE_WINDOWS.get(sin_tildes(Path(valor).name).lower())
    if ingles is None:
        return None
    ruta = Path.home() / ingles
    return ruta if ruta.is_dir() else None


def confirmar_destino(valor: str, leer: Lector) -> str:
    """Si la carpeta de destino no existe, lo dice con su ruta entera y pregunta antes de
    crearla (una ruta relativa va dentro de la carpeta actual). Si se parece a Descargas,
    Documentos…, propone la de verdad. Devuelve la carpeta elegida, o "" para preguntar
    otra vez."""
    ruta = Path(valor).expanduser()
    if ruta.is_dir():
        return valor
    if ruta.exists():
        console.print("  [aviso]Eso es un archivo, no una carpeta.[/]")
        return ""
    entera = escape(str(ruta.absolute()))
    console.print(f"  [aviso]La carpeta {entera} no existe.[/]", soft_wrap=True)
    conocida = carpeta_de_windows(valor)
    opciones = [("crear", f"Crearla ahí: {entera}")]
    if conocida is not None:
        texto = f"Usar {escape(str(conocida))} (es tu {escape(Path(valor).name)})"
        opciones.insert(0, ("conocida", texto))
    opciones.append(("otra", "Escribir otra"))
    for numero, (_, texto) in enumerate(opciones, start=1):
        console.print(f"    [acento]{numero}[/]  {texto}", soft_wrap=True)
    try:
        numero = elegir_numero(leer, "  Elige [pista](Intro = 1)[/]: ", len(opciones), intro=1)
    except Atras:
        return ""  # 0 o volver: se vuelve a preguntar la carpeta
    clave = opciones[numero - 1][0]
    if clave == "conocida":
        return str(conocida)
    if clave == "crear":
        return str(ruta.absolute())
    return ""


NOMBRES_DE_WINDOWS = {
    "Documentos": "Documents",
    "Descargas": "Downloads",
    "Escritorio": "Desktop",
    "Imágenes": "Pictures",
    "Música": "Music",
    "Vídeos": "Videos",
}
"""Las carpetas de tu usuario con el nombre que enseña el Explorador (para la lista y
para Tab) y el que tienen en el disco."""


def interpretar_carpeta(texto: str, dentro: Path, traducir: bool = True) -> Path:
    """La ruta que se ha escrito, entera. Relativa, va desde ``dentro``. Con ``traducir``,
    si empieza por el nombre en castellano de una carpeta de Windows
    («Documentos\\ESTUDIO»), va a la de verdad («C:\\Users\\tú\\Documents\\ESTUDIO»).
    Dentro de una carpeta concreta no se traduce: «Documentos» es una subcarpeta de ahí."""
    ruta = Path(expandir(quitar_comillas(texto.strip())))
    if traducir and not ruta.is_absolute() and ruta.parts:
        ingles = CARPETAS_DE_WINDOWS.get(sin_tildes(ruta.parts[0]).lower())
        if ingles is not None and not (dentro / ruta).exists() and (Path.home() / ingles).is_dir():
            return Path.home() / ingles / Path(*ruta.parts[1:])
    return Path(os.path.abspath(dentro / ruta))


def unidades() -> list[tuple[str, Path]]:
    """Los otros discos y los USB conectados («USB (E:)»), sin el del sistema. En Linux y
    macOS, lo montado en /media/<usuario> y /Volumes."""
    encontradas: list[tuple[str, Path]] = []
    if os.name == "nt":
        try:
            import ctypes

            tipo_de = ctypes.windll.kernel32.GetDriveTypeW  # type: ignore[attr-defined]
            letras = os.listdrives()  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            return []
        sistema = os.environ.get("SystemDrive", "C:").upper()
        for letra in letras:
            if letra.upper().startswith(sistema):
                continue
            tipo = tipo_de(letra)  # 2 extraíble, 3 disco, 4 de red, 5 CD
            if tipo in (2, 3, 4) and Path(letra).exists():
                nombre = {2: "USB", 3: "Disco", 4: "Red"}[tipo]
                encontradas.append((f"{nombre} ({letra.rstrip(chr(92))})", Path(letra)))
        return encontradas
    for raiz in (Path("/media") / os.environ.get("USER", ""), Path("/Volumes")):
        try:
            encontradas += [(f"USB ({c.name})", c) for c in sorted(raiz.iterdir()) if c.is_dir()]
        except OSError:
            continue
    return encontradas


def sitios_de_destino() -> list[tuple[str, Path]]:
    """Lo que se ofrece en «¿A qué carpeta van las copias?»: tus carpetas (Documentos,
    Descargas…), los USB y discos conectados y la carpeta actual."""
    sitios = [
        (espanol, Path.home() / ingles)
        for espanol, ingles in NOMBRES_DE_WINDOWS.items()
        if (Path.home() / ingles).is_dir()
    ]
    sitios += unidades()
    try:
        sitios.append(("Esta carpeta", Path.cwd()))
    except OSError:
        pass
    return sitios


def leer_con_carpetas(leer: Lector, prompt: str, palabras: list[str], dentro: Path) -> str:
    """Pregunta con Tab completando estas palabras y las carpetas de ``dentro``."""
    con_carpetas = getattr(leer, "con_carpetas", None)
    if con_carpetas is None:  # leyendo sin prompt_toolkit (o en los tests)
        return leer(prompt)
    with con_carpetas(palabras, dentro):
        return leer(prompt)


def elegir_destino(leer: Lector) -> str:
    """«¿A qué carpeta van las copias?»: un número de la lista (Documentos, Descargas, el
    USB…) o una ruta escrita, y luego se entra en ella para elegir dentro. Devuelve la
    ruta entera de la carpeta elegida (puede no existir aún: la crea la copia)."""
    while True:
        sitios = sitios_de_destino()
        console.print("  [bold]¿A qué carpeta van las copias?[/]")
        tabla = Table.grid(padding=(0, 2))
        tabla.add_column(style="acento", justify="right")
        tabla.add_column()
        tabla.add_column(style="pista")
        for numero, (nombre, ruta) in enumerate(sitios, start=1):
            tabla.add_row(str(numero), escape(nombre), escape(str(ruta)))
        tabla.add_row("0", "[pista]volver[/]", "")
        console.print(Padding(tabla, (0, 0, 0, 4)))
        console.print(
            "    [pista]o escribe una ruta: Documentos\\ESTUDIO, E:\\DAM… (Tab completa)[/]"
        )
        try:
            actual = Path.cwd()
        except OSError:
            actual = Path.home()
        respuesta = leer_con_carpetas(
            leer, "  Elige [pista](número o ruta)[/]: ", list(NOMBRES_DE_WINDOWS), actual
        ).strip()
        if es_volver(respuesta) or respuesta == "0":
            raise Atras
        if not respuesta:
            console.print("  [aviso]Elige un número o escribe una ruta.[/]")
            continue
        if es_numero(respuesta) and 1 <= int(respuesta) <= len(sitios):
            base = sitios[int(respuesta) - 1][1]
        else:
            base = interpretar_carpeta(respuesta, actual)
            if base.exists() and not base.is_dir():
                console.print("  [aviso]Eso es un archivo, no una carpeta.[/]")
                continue
            if not base.exists():
                valor = confirmar_destino(str(base), leer)
                if valor:
                    return valor
                continue
        elegida = navegar(base, leer)
        if elegida is not None:
            return elegida


def navegar(carpeta: Path, leer: Lector, limite: int = 50) -> str | None:
    """Dentro de una carpeta: Intro la elige; un número entra en una subcarpeta; «..»
    sube; «+» pide el nombre de una nueva; 0 o volver devuelve None (elegir otro sitio).
    También vale escribir el nombre (o la ruta) de una carpeta, con Tab."""
    while True:
        try:
            subcarpetas = sorted(
                (c for c in carpeta.iterdir() if c.is_dir() and not es_oculto(c)),
                key=lambda c: sin_tildes(c.name).lower(),
            )
        except OSError as exc:
            console.print(
                f"  [aviso]No puedo entrar en {escape(str(carpeta))}: "
                f"{escape(exc.strerror or str(exc))}[/]",
                soft_wrap=True,
            )
            return None
        console.print(f"  [bold]En {escape(str(carpeta))}[/]", soft_wrap=True)
        tabla = Table.grid(padding=(0, 2))
        tabla.add_column(style="acento", justify="right")
        tabla.add_column()
        tabla.add_row("Intro", "Copiar aquí")
        for numero, sub in enumerate(subcarpetas[:limite], start=1):
            tabla.add_row(str(numero), escape(sub.name))
        tabla.add_row("+", "Una carpeta nueva aquí")
        if carpeta.parent != carpeta:
            tabla.add_row("..", f"Subir a {escape(carpeta.parent.name or str(carpeta.parent))}")
        tabla.add_row("0", "[pista]Elegir otro sitio[/]")
        console.print(Padding(tabla, (0, 0, 0, 4)))
        if len(subcarpetas) > limite:
            console.print(
                f"    [pista]Hay {len(subcarpetas)}; salen {limite}. Las demás, escribiendo su "
                "nombre (Tab completa).[/]"
            )
        tapadas = [c.name for c in subcarpetas if es_numero(c.name) or c.name in ("+", "..")]
        if tapadas:  # «3» es la opción 3, no la carpeta «3»
            ejemplo = escape(f".{os.sep}{tapadas[0]}")
            console.print(
                f"    [pista]Para entrar en la carpeta «{escape(tapadas[0])}», escribe {ejemplo}[/]"
            )
        respuesta = leer_con_carpetas(
            leer,
            "  Elige [pista](Intro = aquí)[/]: ",
            [c.name for c in subcarpetas],
            carpeta,
        ).strip()
        if not respuesta:
            return str(carpeta)
        if es_volver(respuesta) or respuesta == "0":
            return None
        if respuesta == "..":
            if carpeta.parent == carpeta:
                console.print(f"  [aviso]Ya estás arriba del todo, en {escape(str(carpeta))}.[/]")
            carpeta = carpeta.parent
            continue
        if respuesta == "+":
            nueva = pedir_carpeta_nueva(carpeta, leer)
            if nueva is not None:
                return str(nueva)
            continue
        if es_numero(respuesta) and 1 <= int(respuesta) <= min(len(subcarpetas), limite):
            carpeta = subcarpetas[int(respuesta) - 1]
            continue
        ruta = interpretar_carpeta(respuesta, carpeta, traducir=False)
        if ruta.is_dir():
            carpeta = ruta
            continue
        if ruta.exists():
            console.print("  [aviso]Eso es un archivo, no una carpeta.[/]")
            continue
        valor = confirmar_destino(str(ruta), leer)
        if valor:
            return valor


NOMBRES_RESERVADOS = {"con", "prn", "aux", "nul"} | {
    f"{puerto}{numero}" for puerto in ("com", "lpt") for numero in range(1, 10)
}
"""Nombres que Windows no deja usar para un archivo ni una carpeta (con o sin extensión)."""


def problema_del_nombre(nombre: str) -> str:
    """Por qué no vale como nombre de carpeta nueva, o "" si vale (en Windows, que es lo
    más estricto: así la carpeta también se puede llevar a un USB)."""
    if nombre in (".", ".."):
        return "Ese nombre no vale: es «aquí» o «arriba»."
    malos = sorted({c for c in nombre if c in '<>:"/\\|?*' or ord(c) < 32})
    if malos:
        return f"No puede llevar {' '.join(malos)}."
    if nombre[-1] in ". ":
        return "No puede acabar en punto ni en espacio."
    if nombre.split(".")[0].lower() in NOMBRES_RESERVADOS:
        return f"«{nombre}» es un nombre reservado de Windows."
    return ""


def pedir_carpeta_nueva(carpeta: Path, leer: Lector) -> Path | None:
    """Pide el nombre de una carpeta nueva dentro de ``carpeta`` (se crea al copiar).
    Intro o volver: None (sigue en la carpeta)."""
    while True:
        try:
            nombre = leer_texto(
                leer, "  Nombre de la carpeta nueva [pista](Intro = ninguna)[/]: ", ""
            ).strip()
        except Atras:
            return None
        if not nombre:
            return None
        problema = problema_del_nombre(nombre)
        if problema:
            console.print(f"  [aviso]{escape(problema)}[/]")
            continue
        nueva = carpeta / nombre
        if nueva.exists() and not nueva.is_dir():
            console.print(f"  [aviso]Ahí ya hay un archivo que se llama «{escape(nombre)}».[/]")
            continue
        return nueva


def elegir_archivos(carpeta: Path, leer: Lector, limite: int = 100) -> list[str]:
    """Enseña los archivos de la carpeta con un número y pregunta cuáles.

    Vale «1 3», «2-5», «1,4» y también nombres o patrones (*.pdf), que se buscan en la
    carpeta al copiar. Devuelve lo que va en la orden: los nombres (o los patrones).
    """
    try:
        lista = sorted(
            (p for p in carpeta.iterdir() if p.is_file() and not es_oculto(p)),
            key=lambda p: sin_tildes(p.name).lower(),
        )
    except OSError as exc:
        console.print(f"  [aviso]No puedo leer esa carpeta: {escape(exc.strerror or str(exc))}[/]")
        raise Atras from None
    if not lista:
        console.print("  [aviso]En esa carpeta no hay archivos (solo carpetas): elige otra.[/]")
        raise Atras
    visibles = lista[:limite]
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", justify="right")
    tabla.add_column()
    tabla.add_column(style="pista", justify="right")
    for numero, archivo in enumerate(visibles, start=1):
        try:
            tamano = tamano_legible(archivo.stat().st_size)
        except OSError:
            tamano = ""
        tabla.add_row(str(numero), escape(archivo.name), tamano)
    console.print(Padding(tabla, (0, 0, 0, 4)))
    if len(lista) > limite:
        console.print(
            f"    [pista]Hay {len(lista)}; salen los {limite} primeros. Los demás, por su "
            "nombre o con un patrón (*.pdf).[/]"
        )
    while True:
        respuesta = leer("  ¿Cuáles? [pista](números: 1 3 · 2-5 · o nombres: *.pdf)[/]: ")
        if es_volver(respuesta) or respuesta.strip() == "0":
            raise Atras
        elegidos = entender_archivos(respuesta, visibles, carpeta)
        if elegidos:
            return elegidos


def entender_archivos(respuesta: str, visibles: list[Path], carpeta: Path) -> list[str]:
    """Lo escrito en «¿Cuáles?»: números («1 3», «1,4»), rangos («2-5») y nombres o
    patrones («"tema 3.docx"», *.pdf), que se comprueban ya en la carpeta. Si algo no
    vale, lo dice y devuelve [] (se vuelve a preguntar)."""
    from .comandos.copia import buscar_archivos  # aquí: copia importa medio navaja

    try:
        trozos = dividir(respuesta)
    except ValueError:
        console.print("  [aviso]Falta cerrar unas comillas.[/]")
        return []
    if not trozos:
        console.print("  [aviso]Elige al menos uno.[/]")
        return []
    elegidos: list[str] = []
    for trozo in trozos:
        if not re.fullmatch(r"[\d,\-]+", trozo) or not re.search(r"\d", trozo):
            try:  # un nombre o un patrón (con comas dentro, si las lleva): que exista ya
                buscar_archivos([trozo], carpeta)
            except NavajaError as error:
                console.print(f"  [aviso]{escape(str(error))}[/]", soft_wrap=True)
                return []
            elegidos.append(trozo)
            continue
        for parte in filter(None, trozo.split(",")):  # «1,4» o «1,3-5»
            numeros = re.fullmatch(r"(\d+)(?:-(\d+))?", parte)
            if numeros is None:
                console.print(f"  [aviso]No entiendo «{escape(parte)}»: escribe 3, o 2-5.[/]")
                return []
            desde, hasta = int(numeros[1]), int(numeros[2] or numeros[1])
            if desde > hasta:
                console.print(
                    f"  [aviso]«{escape(parte)}» va al revés: escribe {hasta}-{desde}.[/]"
                )
                return []
            if not 1 <= desde <= hasta <= len(visibles):
                console.print(
                    f"  [aviso]No hay ningún {escape(parte)}: elige entre 1 y {len(visibles)}.[/]"
                )
                return []
            elegidos += [visibles[i - 1].name for i in range(desde, hasta + 1)]
    return list(dict.fromkeys(elegidos))  # sin repetir, en el orden en que se dijeron


PREGUNTAS_PROPIAS: dict[str, Callable[[Any, Lector], list[Paso]]] = {"copia a": pasos_copia}
"""Órdenes que por menú hacen sus propias preguntas en vez de las de siempre."""


def guiado(
    raiz: Any, camino: list[str], comando: Any, leer: Lector, escribir: list[str] | None = None
) -> None:
    """Pregunta solo lo necesario, ejecuta en la carpeta actual y dice qué más se puede ajustar.

    «volver» repite la pregunta anterior; en la primera, vuelve al menú. La
    confirmación de la orden es [s/n]: con «n» no se hace nada y se vuelve al menú.
    """
    propias = PREGUNTAS_PROPIAS.get(" ".join(camino))
    pasos = propias(comando, leer) if propias else (
        pasos_carpeta(comando, leer)
        + pasos_obligatorios(comando, leer)
        + pasos_ajustes(comando, leer)
        + ([] if " ".join(camino) in EL_TEXTO_YA_ELIGE else pasos_filtro(comando, leer))
    )
    antes = ANTES_DE_PREGUNTAR.get(" ".join(camino))
    if antes and ejecutar(raiz, antes) != 0:
        return  # sin la lista no hay nada que elegir (el error ya ha dicho por qué)
    if pasos:
        console.print("  [pista]volver: a la pregunta anterior · salir: cancelar[/]")
    respuestas: list[list[str]] = []
    hacia_atras = False  # al volver, las preguntas que no tocan también se saltan hacia atrás
    try:
        while len(respuestas) < len(pasos):
            try:
                respuesta = pasos[len(respuestas)]()
            except Atras:
                respuesta, hacia_atras = None, True
            if respuesta is not None:
                respuestas.append(respuesta)
                hacia_atras = False
                continue
            if not hacia_atras:
                respuestas.append([])  # no toca: se salta
                continue
            if not respuestas:
                console.print("[pista]Vuelves al menú.[/]")
                return
            respuestas.pop()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[aviso]Cancelado.[/]")
        return
    valores = [valor for respuesta in respuestas for valor in respuesta]
    argumentos = camino + valores
    if valores:
        orden = " ".join(citar(a) for a in argumentos)
        console.print(f"[pista]→ navaja {escape(orden)}[/]", soft_wrap=True)
    ejecutar(raiz, argumentos)
    pista_opciones(escribir or camino, comando)


def cambiar_carpeta(destino: str) -> None:
    destino = destino.strip()
    if not destino:
        console.print(escape(str(Path.cwd())), soft_wrap=True)
        return
    ruta = Path(expandir(quitar_comillas(destino)))
    try:
        os.chdir(ruta)
    except FileNotFoundError:
        error_console.print(f"[error]No existe la carpeta:[/] {escape(str(ruta))}", soft_wrap=True)
    except NotADirectoryError:
        error_console.print(f"[error]No es una carpeta:[/] {escape(str(ruta))}", soft_wrap=True)
    except OSError as exc:
        error_console.print(f"[error]No se puede entrar:[/] {escape(str(exc))}", soft_wrap=True)


def requiere_algo(comando: Any) -> bool:
    return any(p.required for p in comando.params)


def ayuda_de(grupo: Any, camino: list[str], texto: str, opciones: list[tuple[str, Any]]) -> None:
    """``ayuda ocupa``, ``ayuda 2`` u ``ocupa ?``: la ayuda corta de ese comando."""
    texto = texto.strip()
    if texto.isdigit() and 1 <= int(texto) <= len(opciones):
        nombre, comando = opciones[int(texto) - 1]
        nombres = [nombre]
    else:
        try:
            palabras = dividir(texto)
        except ValueError:
            palabras = []
        if palabras:
            palabras[0] = ALIAS.get(palabras[0].lower(), palabras[0])
        comando, nombres = resolver(grupo, palabras)
    if not nombres:
        console.print(
            f"[aviso]No conozco «{escape(texto)}».[/] [pista]Escribe menu para ver las opciones.[/]",
            soft_wrap=True,
        )
    elif es_grupo(comando):
        mostrar_menu(comando, camino + nombres)
    else:
        ayuda_corta(camino + nombres, comando, escribir=nombres)


class Reenviar(Exception):
    """En un submenú se ha escrito un comando del menú principal."""

    def __init__(self, linea: str) -> None:
        super().__init__(linea)
        self.linea = linea


def submenu(raiz: Any, grupo: Any, camino: list[str], leer: Lector) -> str | None:
    """Abre un submenú. Devuelve la línea si se escribió un comando del menú principal."""
    mostrar_menu(grupo, camino)
    try:
        bucle(raiz, grupo, camino, leer)
    except Reenviar as reenvio:
        return reenvio.linea
    return None


def bucle(raiz: Any, grupo: Any, camino: list[str], leer: Lector) -> None:
    """Pide órdenes hasta salir. Un submenú sigue abierto hasta Intro, 0 o volver."""
    pendiente: str | None = None
    while True:
        if pendiente is not None:
            linea, pendiente = pendiente, None
        else:
            try:
                linea = leer_orden(leer, texto_prompt(camino), camino).strip()
            except (KeyboardInterrupt, EOFError):
                console.print()
                if camino:
                    return
                raise Salir from None

        palabra = linea.lower()
        if camino and palabra in VOLVER:
            return
        if palabra in PALABRAS_VOLVER:
            console.print("[pista]Ya estás en el menú principal. Para cerrar navaja: salir.[/]")
            continue
        if not linea:
            continue
        if palabra in SALIR or (palabra == "0" and not camino):
            raise Salir
        if palabra in MENU:
            mostrar_menu(grupo, camino)
            continue
        if palabra in AYUDA_SOLA:
            ayuda_aqui(grupo, camino)
            continue
        if palabra in LIMPIAR_PANTALLA:
            console.clear()
            continue
        if palabra == "pwd":
            cambiar_carpeta("")
            continue
        cd = CD.match(linea)
        if cd:
            cambiar_carpeta(cd.group(1))
            continue

        opciones = opciones_de(grupo)
        pedida = AYUDA_DE.match(linea)
        if pedida:
            ayuda_de(grupo, camino, pedida.group(1) or pedida.group(2), opciones)
            console.print()
            continue

        reenviada: str | None = None
        if linea.isdigit():
            numero = int(linea)
            if not 1 <= numero <= len(opciones):
                salida = "volver" if camino else "salir"
                console.print(
                    f"[aviso]Elige un número del 1 al {len(opciones)} (0 para {salida}).[/]"
                )
                continue
            nombre, comando = opciones[numero - 1]
            if es_grupo(comando):
                reenviada = submenu(raiz, comando, camino + [nombre], leer)
            else:
                guiado(raiz, camino + [nombre], comando, leer, escribir=[nombre])
                console.print()
        else:
            try:
                palabras = dividir(linea)
            except ValueError:
                console.print("[aviso]Falta cerrar unas comillas.[/]")
                continue
            if palabras and palabras[0].lower() in PREFIJOS:
                if camino:
                    raise Reenviar(linea)
                palabras = palabras[1:]
            if not palabras:
                continue
            palabras[0] = ALIAS.get(palabras[0].lower(), palabras[0])
            primera = palabras[0]

            if camino and primera not in grupo.commands and primera in raiz.commands:
                raise Reenviar(linea)
            if primera.startswith("-"):
                ejecutar(raiz, camino + palabras)
            elif primera in grupo.commands:
                comando, nombres = resolver(grupo, palabras)
                if len(nombres) < len(palabras):
                    ejecutar(raiz, camino + palabras)
                elif es_grupo(comando):
                    reenviada = submenu(raiz, comando, camino + nombres, leer)
                elif requiere_algo(comando):
                    guiado(raiz, camino + nombres, comando, leer, escribir=nombres)
                else:
                    ejecutar(raiz, camino + palabras)
            else:
                nombres = [nombre for nombre, _ in opciones]
                parecido = difflib.get_close_matches(primera, nombres, n=1)
                pista = f" ¿Querías decir [acento]{parecido[0]}[/]?" if parecido else ""
                console.print(
                    f"[aviso]No conozco «{escape(primera)}».[/]{pista} "
                    "[pista]Escribe menu para ver las opciones.[/]",
                    soft_wrap=True,
                )
                continue
            if reenviada is None:
                console.print()

        if reenviada is not None:
            if camino:
                raise Reenviar(reenviada)
            pendiente = reenviada


def leer_orden(leer: Lector, prompt: str, camino: list[str]) -> str:
    """El prompt del menú: con el lector de ``entrada`` completa con Tab según dónde estás."""
    orden = getattr(leer, "orden", None)
    return orden(prompt, camino) if orden is not None else leer(prompt)


def _activar_historial() -> None:
    """Si no se puede usar prompt_toolkit: flechas ↑/↓ con readline en Linux y macOS."""
    try:
        import readline  # noqa: F401
    except ImportError:
        pass


def iniciar(app: typer.Typer, leer: Lector | None = None) -> None:
    """Abre el modo interactivo. Al salir, vuelve a la carpeta desde la que se entró."""
    global activo
    raiz = typer.main.get_command(app)
    if leer is None:
        leer = crear_lector(raiz)
        if leer is None:
            leer = console.input
            _activar_historial()
    original = Path.cwd()
    activo = True
    mostrar_menu(raiz, [])
    try:
        bucle(raiz, raiz, [], leer)
    except Salir:
        pass
    finally:
        activo = False
        try:
            os.chdir(original)
        except OSError:
            pass
    console.print("[pista]Hasta luego.[/]")
