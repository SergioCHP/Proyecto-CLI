"""Leer lo que se escribe en el modo interactivo: Tab completa y ↑/↓ recuperan lo de antes.

Usa prompt_toolkit. Las órdenes del menú se completan con Tab (comandos, subcomandos,
opciones y rutas) y se guardan en ``historial.txt`` del directorio de datos, así que ↑
recupera también lo de otras veces. Las preguntas guiadas («¿En qué carpeta?»…) tienen
su propio historial, solo de esta vez, y completan rutas.

Si prompt_toolkit no puede usar la terminal, ``crear_lector`` devuelve ``None`` y el modo
interactivo lee como siempre (``console.input``).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .comandos.ayuda import es_grupo, opciones_visibles
from .comandos.ayuda import subcomandos as opciones_de
from .comun import console, directorio_datos

ATAJOS = ["ayuda", "menu", "manual", "cd", "pwd", "ls", "dir", "cls", "salir"]
"""Palabras propias del modo interactivo que también se completan."""

PIDEN_COMANDO = {"ayuda", "help", "?", "manual"}
"""Después de estas palabras va el nombre de un comando."""

PREFIJOS = {"navaja", "nav"}


def a_ansi(texto: str) -> str:
    """El prompt con markup de Rich (y los colores del tema) convertido a códigos ANSI."""
    with console.capture() as captura:
        console.print(texto, end="")
    return captura.get()


def es_ruta(param: Any) -> bool:
    """¿Este argumento u opción es una carpeta o un archivo?"""
    return getattr(param.type, "name", "") == "path"


def sugerencias(raiz: Any, camino: list[str], antes: list[str], palabra: str) -> tuple[list[str], str]:
    """Qué se puede escribir en ``palabra``, sabiendo lo escrito ``antes``.

    Devuelve las palabras posibles y si, además, hay que completar rutas
    («rutas», «carpetas» o «» si no).
    """
    if antes and antes[0].lower() in PREFIJOS:
        antes = antes[1:]
    grupo = raiz
    for nombre in camino:
        grupo = grupo.commands[nombre]

    if not antes:
        nombres = [nombre for nombre, _ in opciones_de(grupo)]
        if camino:
            nombres += [n for n, _ in opciones_de(raiz) if n not in nombres] + ["volver"]
        return nombres + ATAJOS, ""

    primera = antes[0].lower()
    if primera == "cd":
        return [], "carpetas" if len(antes) == 1 else ""
    if primera in PIDEN_COMANDO:
        actual: Any = raiz
        for nombre in antes[1:]:
            if not es_grupo(actual) or nombre not in actual.commands:
                return [], ""
            actual = actual.commands[nombre]
        return ([n for n, _ in opciones_de(actual)] if es_grupo(actual) else []), ""

    actual = grupo if antes[0] in grupo.commands else raiz
    for nombre in antes:
        if es_grupo(actual) and nombre in actual.commands:
            actual = actual.commands[nombre]
            continue
        if es_grupo(actual):
            return [], ""  # un subcomando que no existe: nada que sugerir
        break  # ya estamos en los argumentos y opciones del comando
    if es_grupo(actual):
        return [n for n, _ in opciones_de(actual)], ""
    visibles = opciones_visibles(actual)
    if palabra.startswith("-"):
        return [nombre for opcion in visibles for nombre in opcion.opts], ""
    anterior = next((o for o in visibles if antes[-1] in o.opts), None)
    if anterior is not None and not anterior.is_flag:
        return [], ("rutas" if es_ruta(anterior) else "")  # el valor de esa opción
    largas = [nombre for opcion in visibles for nombre in opcion.opts if nombre.startswith("--")]
    argumentos = [p for p in actual.params if p.param_type_name == "argument"]
    return (largas if not palabra else []), ("rutas" if any(map(es_ruta, argumentos)) else "")


def crear_lector(raiz: Any) -> Any | None:
    """El lector del modo interactivo con prompt_toolkit, o ``None`` si no se puede usar.

    Con la variable de entorno ``NAVAJA_SIN_TAB=1`` no se usa (se lee como antes).
    """
    if os.environ.get("NAVAJA_SIN_TAB"):
        return None
    # Sin esto, tras cada Intro prompt_toolkit pregunta a la terminal dónde está el cursor
    # y, si no contesta (muchas no lo hacen), espera 1 segundo antes de seguir.
    os.environ.setdefault("PROMPT_TOOLKIT_NO_CPR", "1")
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion, PathCompleter
        from prompt_toolkit.document import Document
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.history import FileHistory, InMemoryHistory
    except ImportError:
        return None

    rutas = PathCompleter(expanduser=True)
    carpetas = PathCompleter(expanduser=True, only_directories=True)

    def completar_ruta(completador: Any, palabra: str, evento: Any) -> Iterable[Any]:
        yield from completador.get_completions(Document(palabra, len(palabra)), evento)

    class Ordenes(Completer):
        """Tab en el prompt del menú: comandos, subcomandos, opciones y rutas."""

        def __init__(self) -> None:
            self.camino: list[str] = []

        def get_completions(self, document: Any, complete_event: Any) -> Iterable[Any]:
            texto = document.text_before_cursor
            partes = texto.split()
            if texto and not texto[-1].isspace():
                antes, palabra = partes[:-1], partes[-1]
            else:
                antes, palabra = partes, ""
            nombres, tipo = sugerencias(raiz, self.camino, antes, palabra)
            vistos = set()
            for nombre in nombres:
                if nombre.lower().startswith(palabra.lower()) and nombre not in vistos:
                    vistos.add(nombre)
                    yield Completion(nombre, start_position=-len(palabra))
            if tipo:
                yield from completar_ruta(rutas if tipo == "rutas" else carpetas, palabra, complete_event)

    class Respuestas(Completer):
        """Tab en las preguntas guiadas: rutas (para «¿En qué carpeta?»)."""

        def get_completions(self, document: Any, complete_event: Any) -> Iterable[Any]:
            yield from rutas.get_completions(document, complete_event)

    class Lector:
        """Se llama como ``console.input``: ``lector(prompt)`` para las preguntas y
        ``lector.orden(prompt, camino)`` para el prompt del menú."""

        def __init__(self) -> None:
            self.ordenes = Ordenes()
            self.menu: Any = PromptSession(
                history=FileHistory(str(historial())),
                completer=self.ordenes,
                complete_while_typing=False,
            )
            self.preguntas: Any = PromptSession(
                history=InMemoryHistory(),
                completer=Respuestas(),
                complete_while_typing=False,
            )

        def orden(self, prompt: str, camino: list[str]) -> str:
            self.ordenes.camino = list(camino)
            return self.menu.prompt(ANSI(a_ansi(prompt)))

        def __call__(self, prompt: str = "") -> str:
            return self.preguntas.prompt(ANSI(a_ansi(prompt)))

    try:
        return Lector()
    except Exception:  # sin consola de verdad (p. ej. Git Bash en Windows): como siempre
        return None


def historial() -> Path:
    """Dónde se guardan las órdenes del modo interactivo."""
    return directorio_datos() / "historial.txt"
