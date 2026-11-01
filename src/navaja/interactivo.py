"""Modo interactivo: ``navaja`` sin argumentos abre un menú y espera órdenes hasta ``salir``."""

from __future__ import annotations

import difflib
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
from .comun import AJUSTE, console, error_console
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

SALIR = {"salir", "exit", "quit"}
MENU = {"menu", "menú"}
AYUDA_SOLA = {"ayuda", "help", "?"}
LIMPIAR_PANTALLA = {"cls", "clear"}
VOLVER = {"", "0", "volver"}
ALIAS = {"ls": "listar", "dir": "listar"}
PREFIJOS = {"navaja", "nav"}
CD = re.compile(r"^cd(?=$|[\s./\\])(.*)$", re.IGNORECASE)
AYUDA_DE = re.compile(r"^(?:ayuda|help|\?)\s+(.+)$|^(.+?)\s+\?$", re.IGNORECASE)

AYUDA = (
    "[pista]Elige un número o escribe un comando · [/][acento]ayuda[/][pista] te explica "
    "lo que puedes hacer aquí · [/][acento]salir[/]"
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
    """Intro deja el valor por defecto; solo espacios valen como espacio («numerar» con « »)."""
    crudo = leer(prompt)
    if crudo == "":
        return defecto
    if not crudo.strip():
        return crudo
    return expandir(quitar_comillas(crudo.strip()))


def preguntar_obligatorios(comando: Any, leer: Lector) -> list[str]:
    """Pregunta los argumentos que hacen falta.

    Los obligatorios, siempre. Los opcionales de texto (como el «por» de
    renombra cambiar) también, con Intro para dejar su valor por defecto. Las
    rutas opcionales (la carpeta) y las listas no se preguntan: se usa la
    carpeta actual. Solo se escriben si detrás va otro valor, para no
    descolocar las posiciones.
    """
    valores: list[str] = []
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
        texto = escape((getattr(param, "help", None) or param.name or "").rstrip("."))
        es_fecha = param.name in ("desde", "hasta")
        if param.required:
            while True:
                valor = leer_texto(leer, f"  {texto}: ", "")
                if not valor:
                    console.print("  [aviso]Hace falta un valor.[/]")
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
        valores += pendientes
        pendientes = []
        valores += dividir(valor) if es_lista else [valor]
    return valores


def preguntar_ajustes(comando: Any, leer: Lector) -> list[str]:
    """Pregunta las opciones del panel «Ajustes»; solo añade las que cambian."""
    extra: list[str] = []
    for param in comando.params:
        if param.param_type_name != "option" or getattr(param, "rich_help_panel", None) != AJUSTE:
            continue
        texto = escape((getattr(param, "help", None) or param.name or "").rstrip("."))
        nombre = max(param.opts, key=len)
        if getattr(param, "is_flag", False):
            respuesta = leer(f"  {texto} [pista](s/n · Intro = no)[/]: ").strip().lower()
            if respuesta in ("s", "si", "sí", "y"):
                extra.append(nombre)
            continue
        defecto = "" if param.default is None else valor_texto(param.default)
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
        if valor != defecto:
            extra += [nombre, valor]
    return extra


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


def preguntar_filtro(comando: Any, leer: Lector) -> list[str]:
    """Una sola pregunta, «¿Con qué archivos?», en vez de un filtro tras otro."""
    filtros = {
        max(p.opts, key=len): p
        for p in comando.params
        if p.param_type_name == "option" and getattr(p, "rich_help_panel", None) == FILTRO
    }
    if not filtros:
        return []
    opciones = [("todos", "Todos los de la carpeta")]
    if "--solo" in filtros:
        opciones.append(("tipo", "Solo de un tipo (imágenes, documentos, vídeos…)"))
    if "--contiene" in filtros:
        opciones.append(("texto", "Los que llevan un texto en el nombre"))
    if "--desde" in filtros:
        opciones.append(("fechas", "Los de unas fechas (de una a otra)"))

    console.print("  [bold]¿Con qué archivos?[/]")
    for numero, (_, texto) in enumerate(opciones, start=1):
        console.print(f"    [acento]{numero}[/]  {texto}")
    while True:
        respuesta = leer("  Elige [pista](Intro = 1, todos)[/]: ").strip()
        if not respuesta:
            return []
        if respuesta.isdigit() and 1 <= int(respuesta) <= len(opciones):
            clave = opciones[int(respuesta) - 1][0]
            break
        console.print(f"  [aviso]Elige un número del 1 al {len(opciones)}.[/]")

    if clave == "tipo":
        tipos = [c for c in CATEGORIAS]
        for numero, categoria in enumerate(tipos, start=1):
            console.print(f"    [acento]{numero}[/]  {ETIQUETAS[categoria]}")
        while True:
            respuesta = leer_texto(
                leer, "  ¿Qué tipo? [pista](un número, o extensiones: jpg,png)[/]: ", ""
            )
            if respuesta.isdigit() and 1 <= int(respuesta) <= len(tipos):
                return ["--solo", tipos[int(respuesta) - 1]]
            if respuesta and not respuesta.isdigit():
                return ["--solo", respuesta]
            console.print(f"  [aviso]Elige un número del 1 al {len(tipos)} o escribe extensiones.[/]")
    if clave == "texto":
        while True:
            texto = leer_texto(leer, "  Texto que tiene que llevar el nombre: ", "")
            if texto:
                return ["--contiene", texto]
            console.print("  [aviso]Hace falta un texto.[/]")
    if clave == "fechas":
        ejemplos = escape(EJEMPLOS_FECHA)
        while True:
            desde = preguntar_fecha(
                leer, f"  Desde qué fecha [pista](ej.: {ejemplos} · Intro = desde siempre)[/]: "
            )
            hasta = preguntar_fecha(leer, "  Hasta qué fecha, incluida [pista](Intro = hoy)[/]: ")
            try:
                rango(desde, hasta)
                break
            except ValueError as exc:
                console.print(f"  [aviso]{escape(str(exc))}[/]")
        return (["--desde", desde] if desde else []) + (["--hasta", hasta] if hasta else [])
    return []


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
    """Pregunta solo lo obligatorio, ejecuta en la carpeta actual y dice qué más se puede ajustar."""
    try:
        valores = preguntar_obligatorios(comando, leer)
        valores += preguntar_ajustes(comando, leer)
        valores += preguntar_filtro(comando, leer)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[aviso]Cancelado.[/]")
        return
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
