"""navaja arbol: el árbol de carpetas de un proyecto, para verlo o pegarlo en el README.

Se salta lo de siempre (.git, .venv, __pycache__…) y lo del ``.gitignore``
(``ignorados.py``). Con ``--guardar`` lo deja en un Markdown nuevo, sin pisar nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, ARCHIVOS, bonita, console, cuantos, error_console, ruta_libre
from ..ignorados import Ignorados, hijos

MAXIMO_LINEAS = 1000
"""Con más, el árbol ya no se puede leer: se corta y se dice cuántas faltan."""


@dataclass
class Arbol:
    lineas: list[tuple[str, str, bool]] = field(default_factory=list)  # (ramas, nombre, carpeta)
    carpetas: int = 0
    archivos: int = 0
    sin_ver: int = 0  # lo que no cabe en MAXIMO_LINEAS o pasa de la profundidad
    ignorados: int = 0


def dibujar(
    raiz: Path,
    profundidad: int = 0,
    todo: bool = False,
    solo_carpetas: bool = False,
    maximo: int = MAXIMO_LINEAS,
) -> Arbol:
    """Las líneas del árbol con sus ramas (├── └── │). ``profundidad`` 0 = sin límite."""
    ignorados = Ignorados.de_carpeta(raiz, todo)
    arbol = Arbol()

    def visibles(carpeta: Path, contar: bool = True) -> list[tuple[Path, bool]]:
        entradas = []
        for ruta in hijos(carpeta):
            es_carpeta = ruta.is_dir() and not ruta.is_symlink()
            if ignorados.ignora(ruta.relative_to(raiz).as_posix(), es_carpeta):
                arbol.ignorados += contar
                continue
            if solo_carpetas and not es_carpeta:
                continue
            entradas.append((ruta, es_carpeta))
        return entradas

    def bajar(carpeta: Path, prefijo: str, nivel: int) -> None:
        entradas = visibles(carpeta)
        for posicion, (ruta, es_carpeta) in enumerate(entradas):
            if len(arbol.lineas) >= maximo:
                arbol.sin_ver += len(entradas) - posicion
                return
            ultima = posicion == len(entradas) - 1
            arbol.lineas.append((prefijo + ("└── " if ultima else "├── "), ruta.name, es_carpeta))
            if es_carpeta:
                arbol.carpetas += 1
                if profundidad and nivel >= profundidad:
                    arbol.sin_ver += len(visibles(ruta, contar=False))
                else:
                    bajar(ruta, prefijo + ("    " if ultima else "│   "), nivel + 1)
            else:
                arbol.archivos += 1

    bajar(raiz, "", 1)
    return arbol


def como_texto(raiz: Path, arbol: Arbol) -> str:
    """El árbol en texto plano: la carpeta arriba y las carpetas con «/» al final."""
    lineas = [f"{nombre_de(raiz)}/"]
    lineas += [f"{ramas}{nombre}{'/' if carpeta else ''}" for ramas, nombre, carpeta in arbol.lineas]
    if arbol.sin_ver:
        lineas.append(f"… y {arbol.sin_ver} más")
    return "\n".join(lineas)


def como_markdown(raiz: Path, arbol: Arbol) -> str:
    return f"```text\n{como_texto(raiz, arbol)}\n```\n"


def nombre_de(raiz: Path) -> str:
    return raiz.resolve().name or str(raiz.resolve())


def arbol(
    carpeta: Path = typer.Argument(Path("."), help="La carpeta del proyecto."),
    profundidad: int = typer.Option(
        0, "--profundidad", "-p", min=0, help="Cuántos niveles bajar (0 = todos).", rich_help_panel=AJUSTE
    ),
    solo_carpetas: bool = typer.Option(False, "--solo-carpetas", help="Sin archivos, solo las carpetas."),
    todo: bool = typer.Option(False, "--todo", help="Sin saltarse nada (ni .git, ni .venv, ni el .gitignore)."),
    guardar: Path = typer.Option(
        None, "--guardar", "-g", help="Guardarlo en un Markdown (si existe, se crea otro al lado).",
        show_default=False,
    ),
) -> None:
    """Dibuja el árbol de carpetas de un proyecto (para el README o la memoria)."""
    if not carpeta.is_dir():
        error_console.print(f"[error]✘ No existe la carpeta {escape(str(carpeta))}.[/]", soft_wrap=True)
        raise typer.Exit(1)
    dibujo = dibujar(carpeta, profundidad, todo, solo_carpetas)
    texto = Text(f"{nombre_de(carpeta)}/", style="titulo")
    for ramas, nombre, es_carpeta in dibujo.lineas:
        texto.append("\n")
        texto.append(ramas, style="pista")
        texto.append(nombre + ("/" if es_carpeta else ""), style="acento" if es_carpeta else "")
    if dibujo.sin_ver:
        texto.append(f"\n… y {dibujo.sin_ver} más", style="pista")
    console.print(texto, soft_wrap=True, highlight=False)
    resumen = f"{cuantos(dibujo.carpetas, 'carpeta')}, {cuantos(dibujo.archivos, 'archivo')}"
    if dibujo.ignorados:
        resumen += f" · {dibujo.ignorados} sin enseñar (como .venv o lo del .gitignore; --todo los enseña)"
    console.print(f"\n[pista]{escape(resumen)}[/]")
    if guardar is not None:
        destino = ruta_libre(guardar.expanduser())
        try:
            destino.write_text(como_markdown(carpeta, dibujo), encoding="utf-8")
        except OSError as error:
            error_console.print(f"[error]✘ No se puede guardar: {escape(error.strerror or str(error))}[/]")
            raise typer.Exit(1)
        aviso = "" if destino == guardar.expanduser() else " (ya había uno con ese nombre)"
        console.print(f"[ok]✔ Guardado en {escape(bonita(destino))}{aviso}.[/]", soft_wrap=True)


def registrar(app: typer.Typer) -> None:
    app.command(
        "arbol", help="Dibuja el árbol de carpetas de un proyecto.", rich_help_panel=ARCHIVOS
    )(arbol)
