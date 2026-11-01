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
from rich.markup import escape
from rich.table import Table

from .comandos.ayuda import (
    ayuda_aqui,
    ayuda_corta,
    es_grupo,
    opciones_visibles,
    resolver,
    valor_texto,
)
from .comandos.ayuda import subcomandos as opciones_de
from .comun import AJUSTE, PALABRAS_VOLVER, console, error_console
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
Paso = Callable[[], list[str]]
"""Una pregunta del modo guiado: devuelve lo que añade a la orden."""

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
}
"""Lo que se enseña antes de las preguntas: para elegir una nota hay que ver sus números."""

EL_TEXTO_YA_ELIGE = {"renombra cambiar", "renombra avanzado", "ordena nombre"}
"""Aquí el texto (o el patrón) ya dice qué archivos se tocan: no se pregunta «¿Con qué
archivos?» (los filtros siguen valiendo escritos: --solo, --desde…)."""

AYUDA = (
    "[pista]Elige un número o escribe un comando · [/][acento]ayuda[/][pista] te explica "
    "lo que puedes hacer aquí · [/][acento]salir[/]"
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


def mostrar_menu(grupo: Any, camino: list[str]) -> None:
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", justify="right")
    tabla.add_column(style="bold", no_wrap=True)
    tabla.add_column(style="pista")
    for numero, (nombre, comando) in enumerate(opciones_de(grupo), start=1):
        tabla.add_row(str(numero), nombre, escape(comando.get_short_help_str(70)))
    tabla.add_row("0", "volver" if camino else "salir", "")
    console.print(tabla)
    if camino:
        console.print(
            "[acento]ayuda[/][pista] explica estas opciones · Intro o [/][acento]0[/]"
            "[pista] para volver[/]"
        )
    else:
        console.print(f"\n{AYUDA}\n")


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
        pasos.append(functools.partial(preguntar_argumento, param, leer, pendientes))
        pendientes = []
    return pasos


def preguntar_argumento(param: Any, leer: Lector, delante: list[str]) -> list[str]:
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


def elegir_numero(leer: Lector, prompt: str, cuantas: int, intro: int | None = None) -> int:
    """Pide un número de una lista. 0 o «volver» lanzan ``Atras``; Intro elige ``intro``."""
    while True:
        respuesta = leer(prompt).strip()
        if respuesta == "0" or es_volver(respuesta):
            raise Atras
        if not respuesta and intro is not None:
            return intro
        if respuesta.isdigit() and 1 <= int(respuesta) <= cuantas:
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


def guiado(
    raiz: Any, camino: list[str], comando: Any, leer: Lector, escribir: list[str] | None = None
) -> None:
    """Pregunta solo lo necesario, ejecuta en la carpeta actual y dice qué más se puede ajustar.

    «volver» repite la pregunta anterior; en la primera, vuelve al menú. La
    confirmación de la orden es [s/n]: con «n» no se hace nada y se vuelve al menú.
    """
    pasos = (
        pasos_carpeta(comando, leer)
        + pasos_obligatorios(comando, leer)
        + pasos_ajustes(comando, leer)
        + ([] if " ".join(camino) in EL_TEXTO_YA_ELIGE else pasos_filtro(comando, leer))
    )
    antes = ANTES_DE_PREGUNTAR.get(" ".join(camino))
    if antes:
        ejecutar(raiz, antes)
    if pasos:
        console.print("  [pista]volver: a la pregunta anterior · salir: cancelar[/]")
    respuestas: list[list[str]] = []
    try:
        while len(respuestas) < len(pasos):
            try:
                respuestas.append(pasos[len(respuestas)]())
            except Atras:
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
                linea = leer(texto_prompt(camino)).strip()
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


def _activar_historial() -> None:
    """Flechas ↑/↓ en Linux y macOS (en Windows ya las da la consola)."""
    try:
        import readline  # noqa: F401
    except ImportError:
        pass


def iniciar(app: typer.Typer, leer: Lector | None = None) -> None:
    """Abre el modo interactivo. Al salir, vuelve a la carpeta desde la que se entró."""
    global activo
    leer = leer or console.input
    raiz = typer.main.get_command(app)
    original = Path.cwd()
    activo = True
    _activar_historial()
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
