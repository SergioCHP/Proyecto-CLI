"""Modo interactivo: ``navaja`` sin argumentos abre un menú y espera órdenes hasta ``salir``."""

from __future__ import annotations

import difflib
import os
import re
import shlex
import sys
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape
from rich.table import Table

from .comun import console, error_console

Lector = Callable[[str], str]

SALIR = {"salir", "exit", "quit"}
MENU = {"menu", "menú", "ayuda", "help", "?"}
LIMPIAR_PANTALLA = {"cls", "clear"}
VOLVER = {"", "0", "volver"}
ALIAS = {"ls": "listar", "dir": "listar"}
PREFIJOS = {"navaja", "nv"}
CD = re.compile(r"^cd(?=$|[\s./\\])(.*)$", re.IGNORECASE)

AYUDA = (
    "[pista]Elige un número o escribe un comando (ej.: [/][acento]ocupa -n 5[/][pista])"
    " · [/][acento]cd[/][pista] carpeta · [/][acento]menu[/][pista] · [/][acento]salir[/]"
)

activo = False
"""True mientras el modo interactivo está abierto (evita abrir uno dentro de otro)."""


class Salir(Exception):
    """El usuario quiere cerrar el modo interactivo."""


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


def es_grupo(comando: Any) -> bool:
    return hasattr(comando, "commands")


def opciones_de(grupo: Any) -> list[tuple[str, Any]]:
    """Subcomandos visibles en el orden en que se registraron."""
    return [
        (nombre, grupo.commands[nombre])
        for nombre in grupo.list_commands(None)
        if not getattr(grupo.commands[nombre], "hidden", False)
    ]


def mostrar_menu(grupo: Any, camino: list[str]) -> None:
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", justify="right")
    tabla.add_column(style="bold", no_wrap=True)
    tabla.add_column(style="pista")
    for numero, (nombre, comando) in enumerate(opciones_de(grupo), start=1):
        tabla.add_row(str(numero), nombre, escape(comando.get_short_help_str(70)))
    tabla.add_row("0", "volver" if camino else "salir", "")
    console.print(tabla)


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


def preguntar_argumentos(comando: Any, leer: Lector) -> list[str]:
    valores: list[str] = []
    for param in comando.params:
        if param.param_type_name != "argument":
            continue
        texto = escape((getattr(param, "help", None) or param.name or "").rstrip("."))
        if param.required:
            while True:
                valor = leer(f"  {texto}: ").strip()
                if valor:
                    break
                console.print("  [aviso]Hace falta un valor.[/]")
        else:
            defecto = param.default
            pista = "aquí" if str(defecto) == "." else str(defecto)
            valor = leer(f"  {texto} [pista](Intro = {escape(pista)})[/]: ").strip()
            if not valor:
                if defecto is None:
                    continue
                valor = str(defecto)
        if getattr(param, "nargs", 1) == -1:
            valores += dividir(valor)
        else:
            valores.append(expandir(quitar_comillas(valor)))
    return valores


def mostrar_opciones(opciones: list[Any]) -> None:
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", no_wrap=True)
    tabla.add_column()
    for opcion in opciones:
        nombres = ", ".join(sorted(opcion.opts, key=len))
        ayuda = escape(getattr(opcion, "help", None) or "")
        defecto = opcion.default
        if isinstance(defecto, Enum):
            defecto = defecto.value
        if not getattr(opcion, "is_flag", False) and defecto not in (None, ""):
            ayuda += f" [pista](por defecto: {escape(str(defecto))})[/]"
        tabla.add_row(nombres, ayuda)
    console.print(tabla)


def preguntar_opciones(comando: Any, leer: Lector) -> list[str]:
    opciones = [
        p
        for p in comando.params
        if p.param_type_name == "option" and not getattr(p, "hidden", False)
    ]
    if not opciones:
        return []
    while True:
        linea = leer("  Opciones [pista](Intro = ninguna · ? = ver cuáles hay)[/]: ").strip()
        if linea == "?":
            mostrar_opciones(opciones)
            continue
        try:
            return dividir(linea)
        except ValueError:
            console.print("  [aviso]Falta cerrar unas comillas.[/]")


def guiado(raiz: Any, camino: list[str], comando: Any, leer: Lector) -> None:
    """Pregunta lo que necesita la orden, enseña la orden equivalente y la ejecuta."""
    try:
        argumentos = camino + preguntar_argumentos(comando, leer)
        argumentos += preguntar_opciones(comando, leer)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[aviso]Cancelado.[/]")
        return
    orden = " ".join(citar(a) for a in argumentos)
    console.print(f"[pista]→ navaja {escape(orden)}[/]", soft_wrap=True)
    ejecutar(raiz, argumentos)


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


def resolver(grupo: Any, palabras: list[str]) -> tuple[Any, list[str]]:
    """Baja por los grupos mientras las palabras sean nombres de comando.

    ``["ordena", "aplicar", "~/X"]`` → (comando aplicar, ["ordena", "aplicar"]).
    """
    comando, nombres = grupo, []
    for palabra in palabras:
        if not es_grupo(comando) or palabra not in comando.commands:
            break
        comando = comando.commands[palabra]
        nombres.append(palabra)
    return comando, nombres


def bucle(raiz: Any, grupo: Any, camino: list[str], leer: Lector) -> None:
    """Pide órdenes hasta salir. En un submenú, vuelve al menú anterior tras ejecutar algo."""
    while True:
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
        if not linea:
            continue
        if palabra in SALIR or (palabra == "0" and not camino):
            raise Salir
        if palabra in MENU:
            mostrar_menu(grupo, camino)
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
        if linea.isdigit():
            numero = int(linea)
            if not 1 <= numero <= len(opciones):
                console.print(f"[aviso]Elige un número del 1 al {len(opciones)}.[/]")
                continue
            nombre, comando = opciones[numero - 1]
            if es_grupo(comando):
                mostrar_menu(comando, camino + [nombre])
                bucle(raiz, comando, camino + [nombre], leer)
            else:
                guiado(raiz, camino + [nombre], comando, leer)
                console.print()
            if camino:
                return
            continue

        try:
            palabras = dividir(linea)
        except ValueError:
            console.print("[aviso]Falta cerrar unas comillas.[/]")
            continue
        if not camino and palabras and palabras[0].lower() in PREFIJOS:
            palabras = palabras[1:]
        if not palabras:
            continue
        palabras[0] = ALIAS.get(palabras[0].lower(), palabras[0])
        primera = palabras[0]

        if primera.startswith("-"):
            ejecutar(raiz, camino + palabras)
        elif primera in grupo.commands:
            comando, nombres = resolver(grupo, palabras)
            if len(nombres) < len(palabras):
                ejecutar(raiz, camino + palabras)
            elif es_grupo(comando):
                mostrar_menu(comando, camino + nombres)
                bucle(raiz, comando, camino + nombres, leer)
            elif requiere_algo(comando):
                guiado(raiz, camino + nombres, comando, leer)
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
        console.print()
        if camino:
            return


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
    console.print(f"\n{AYUDA}\n")
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
