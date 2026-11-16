"""navaja json: comprobar, ver como árbol, ordenar o compactar un JSON (o un YAML).

Si está mal, dice en qué línea y qué pasa, en castellano (los mismos mensajes que
``acciones validar``). Lo que escribe va a la pantalla o, con ``--guardar``, a un archivo
nuevo al lado: el original no se toca. YAML necesita ``pyyaml`` (``navaja[yaml]``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

import typer
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from ..comun import AJUSTE, PROGRAMACION, bonita, console, cuantos, error_console, recuadro, resumen, ruta_libre
from ..errores import NavajaError
from ..esquema import ERRORES_JSON

ES_YAML = {".yml", ".yaml"}
INSTALAR_YAML = 'uv tool install --editable ".[yaml]"  (o: pip install pyyaml)'
MAXIMO_HIJOS = 50
"""Lo más que se enseña de una lista u objeto en el árbol; el resto, «… y N más»."""


class ErrorDeFormato(NavajaError):
    """El archivo no es JSON (o YAML) válido: dónde y por qué."""

    def __init__(self, archivo: str, linea: int, columna: int, motivo: str, texto_linea: str = "") -> None:
        super().__init__(f"{archivo}: línea {linea}, columna {columna}: {motivo}.")
        self.archivo = archivo
        self.linea = linea
        self.columna = columna
        self.motivo = motivo
        self.texto_linea = texto_linea


@dataclass
class Leido:
    datos: Any
    yaml: bool
    repetidas: list[str] = field(default_factory=list)  # claves que salen dos veces


def leer(ruta: Path) -> Leido:
    """El contenido del archivo. ``ErrorDeFormato`` con la línea si está mal escrito."""
    try:
        texto = ruta.read_text(encoding="utf-8-sig")  # el Bloc de notas a veces pone BOM
    except UnicodeDecodeError:
        raise NavajaError(f"{ruta.name} no está guardado en UTF-8.") from None
    if ruta.suffix.lower() in ES_YAML:
        return Leido(leer_yaml(texto, ruta.name), yaml=True)
    repetidas: list[str] = []

    def sin_repetir(pares: list[tuple[str, Any]]) -> dict[str, Any]:
        vistas: dict[str, Any] = {}
        for clave, valor in pares:
            if clave in vistas and clave not in repetidas:
                repetidas.append(clave)
            vistas[clave] = valor
        return vistas

    try:
        datos = json.loads(texto, object_pairs_hook=sin_repetir)
    except json.JSONDecodeError as error:
        motivo = next((es for en, es in ERRORES_JSON if error.msg.startswith(en)), error.msg)
        motivo = mejor_motivo(texto, error, motivo)
        lineas = texto.splitlines()
        linea = lineas[error.lineno - 1] if 0 < error.lineno <= len(lineas) else ""
        raise ErrorDeFormato(ruta.name, error.lineno, error.colno, motivo, linea) from None
    return Leido(datos, yaml=False, repetidas=repetidas)


def mejor_motivo(texto: str, error: json.JSONDecodeError, motivo: str) -> str:
    """Si justo antes del error hay una coma y luego «}» o «]», es que sobra esa coma."""
    antes = texto[: error.pos].rstrip()
    despues = texto[error.pos :].lstrip()[:1]
    if antes.endswith(",") and despues in ("}", "]"):
        return "sobra una coma antes de cerrar (JSON no deja una coma tras el último)"
    if despues == "'":
        return "en JSON los textos van entre comillas dobles (\"), no simples (')"
    return motivo


def leer_yaml(texto: str, nombre: str) -> Any:
    try:
        import yaml
    except ImportError:
        raise NavajaError(f"Para leer YAML hace falta pyyaml. Instálalo con: {INSTALAR_YAML}") from None
    try:
        return yaml.safe_load(texto)
    except yaml.MarkedYAMLError as error:
        marca = error.problem_mark
        linea = marca.line + 1 if marca else 0
        columna = marca.column + 1 if marca else 0
        lineas = texto.splitlines()
        raise ErrorDeFormato(
            nombre, linea, columna, f"YAML mal escrito ({error.problem})",
            lineas[linea - 1] if 0 < linea <= len(lineas) else "",
        ) from None
    except yaml.YAMLError as error:
        raise NavajaError(f"{nombre}: YAML mal escrito ({error}).") from None


# ── Describir ──────────────────────────────────────────────────────────────


def tipo_de(valor: Any) -> str:
    if isinstance(valor, dict):
        return "objeto"
    if isinstance(valor, list):
        return "lista"
    if isinstance(valor, bool):
        return "sí/no"
    if isinstance(valor, (int, float)):
        return "número"
    if valor is None:
        return "nulo"
    return "texto"


def profundidad(valor: Any) -> int:
    if isinstance(valor, dict):
        return 1 + max((profundidad(v) for v in valor.values()), default=0)
    if isinstance(valor, list):
        return 1 + max((profundidad(v) for v in valor), default=0)
    return 0


def elementos(valor: Any) -> int:
    """Todos los valores que hay dentro, contando los de dentro de dentro."""
    if isinstance(valor, dict):
        return sum(1 + elementos(v) for v in valor.values())
    if isinstance(valor, list):
        return sum(1 + elementos(v) for v in valor)
    return 0


def corto(valor: Any, largo: int = 60) -> str:
    texto = json.dumps(valor, ensure_ascii=False)
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def arbol_de(valor: Any, nombre: str, nivel_maximo: int = 0) -> Tree:
    """Un árbol de Rich: objetos y listas son ramas; textos y números, hojas con su valor."""
    raiz = Tree(f"[titulo]{escape(nombre)}[/] [pista]{tipo_de(valor)}[/]")
    rellenar(raiz, valor, 1, nivel_maximo)
    return raiz


def rellenar(rama: Tree, valor: Any, nivel: int, nivel_maximo: int) -> None:
    if isinstance(valor, dict):
        pares = list(valor.items())
    elif isinstance(valor, list):
        pares = [(f"[{i}]", v) for i, v in enumerate(valor)]
    else:
        return
    for clave, hijo in pares[:MAXIMO_HIJOS]:
        etiqueta = f"[acento]{escape(str(clave))}[/]"
        if isinstance(hijo, (dict, list)):
            cuantos_ = len(hijo)
            sub = rama.add(f"{etiqueta} [pista]{tipo_de(hijo)} · {cuantos_}[/]")
            if nivel_maximo and nivel >= nivel_maximo:
                continue
            rellenar(sub, hijo, nivel + 1, nivel_maximo)
        else:
            rama.add(f"{etiqueta}: {escape(corto(hijo))}")
    if len(pares) > MAXIMO_HIJOS:
        rama.add(f"[pista]… y {len(pares) - MAXIMO_HIJOS} más[/]")


def formatear(leido: Leido, sangria: int = 2, ordenar: bool = False) -> str:
    if leido.yaml:
        import yaml

        return yaml.safe_dump(
            leido.datos, allow_unicode=True, sort_keys=ordenar, indent=sangria, default_flow_style=False
        )
    return json.dumps(leido.datos, indent=sangria, ensure_ascii=False, sort_keys=ordenar) + "\n"


def compactar(leido: Leido) -> str:
    return json.dumps(leido.datos, ensure_ascii=False, separators=(",", ":")) + "\n"


# ── Órdenes ────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    if isinstance(error, ErrorDeFormato):
        error_console.print(f"[error]✘ {escape(error.archivo)} está mal escrito[/]")
        error_console.print(f"  [pista]Línea {error.linea}, columna {error.columna}:[/] {escape(error.motivo)}.", soft_wrap=True)
        if error.texto_linea:
            error_console.print(f"  [pista]{error.linea} │[/] {escape(error.texto_linea.rstrip())}", soft_wrap=True)
            margen = len(str(error.linea)) + 3 + max(error.columna - 1, 0)
            error_console.print(" " * (2 + margen) + "[error]^[/]")
    else:
        error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def abrir(archivo: Path) -> Leido:
    ruta = archivo.expanduser()
    if not ruta.is_file():
        fallar(NavajaError(f"No existe el archivo {archivo}."))
    try:
        return leer(ruta)
    except NavajaError as error:
        fallar(error)
    except OSError as error:
        fallar(NavajaError(f"No se puede leer {archivo}: {error.strerror or error}"))


def guardar_al_lado(archivo: Path, sufijo: str, contenido: str, yaml: bool = False) -> None:
    extension = archivo.suffix if yaml or archivo.suffix.lower() == ".json" else ".json"
    destino = ruta_libre(archivo.with_name(f"{archivo.stem}-{sufijo}{extension}"))
    try:
        destino.write_text(contenido, encoding="utf-8")
    except OSError as error:
        fallar(NavajaError(f"No se puede guardar: {error.strerror or error}"))
    console.print(f"[ok]✔ Guardado en {escape(bonita(destino))}[/] [pista](el original no se toca)[/]", soft_wrap=True)


ARCHIVO = typer.Argument(..., help="El archivo .json (o .yaml).")
OPCION_GUARDAR = typer.Option(
    False, "--guardar", "-g", help="Guardarlo en un archivo nuevo al lado en vez de enseñarlo.",
    rich_help_panel=AJUSTE,
)


def comprueba(archivo: Path = ARCHIVO) -> None:
    """Dice si está bien escrito y, si no, en qué línea y por qué."""
    leido = abrir(archivo)
    datos = leido.datos
    filas = [
        ("Formato", "YAML" if leido.yaml else "JSON"),
        ("Por fuera", tipo_de(datos) + (f" con {cuantos(len(datos), 'elemento')}" if isinstance(datos, (dict, list)) else "")),
        ("Dentro", f"{cuantos(elementos(datos), 'valor', 'valores')} · {profundidad(datos)} niveles"),
    ]
    if isinstance(datos, dict) and datos:
        claves = list(datos)
        texto = ", ".join(claves[:10]) + (f"… (+{len(claves) - 10})" if len(claves) > 10 else "")
        filas.append(("Claves", escape(texto)))
    partes: list = [Text.from_markup("[ok]✔ Está bien escrito.[/]"), resumen(filas)]
    if leido.repetidas:
        partes.append(
            Text.from_markup(
                f"[aviso]Claves repetidas: {escape(', '.join(leido.repetidas))}. Vale, pero solo "
                "cuenta la última: seguramente es un error.[/]"
            )
        )
    console.print(recuadro(archivo.name, *partes))


def arbol_orden(
    archivo: Path = ARCHIVO,
    profundidad_: int = typer.Option(
        0, "--profundidad", "-p", min=0, help="Cuántos niveles abrir (0 = todos).", rich_help_panel=AJUSTE
    ),
) -> None:
    """Lo enseña como un árbol: objetos y listas con lo que llevan dentro."""
    leido = abrir(archivo)
    console.print(arbol_de(leido.datos, archivo.name, profundidad_))


def formatea(
    archivo: Path = ARCHIVO,
    sangria: int = typer.Option(2, "--sangria", min=0, max=8, help="Espacios de cada nivel."),
    ordena: bool = typer.Option(False, "--ordena", help="Las claves por orden alfabético.", rich_help_panel=AJUSTE),
    guardar: bool = OPCION_GUARDAR,
) -> None:
    """Lo deja bonito: un valor por línea y con sangría."""
    leido = abrir(archivo)
    contenido = formatear(leido, sangria, ordena)
    if guardar:
        guardar_al_lado(archivo.expanduser(), "formateado", contenido, leido.yaml)
    else:
        console.print(Text(contenido.rstrip("\n")), soft_wrap=True, highlight=False)


def compacta(archivo: Path = ARCHIVO, guardar: bool = OPCION_GUARDAR) -> None:
    """Todo en una línea, sin espacios: ocupa menos (para enviarlo o guardarlo)."""
    leido = abrir(archivo)
    contenido = compactar(leido)
    if guardar:
        guardar_al_lado(archivo.expanduser(), "compacto", contenido)
    else:
        console.print(Text(contenido.rstrip("\n")), soft_wrap=True, highlight=False)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(help="Comprueba, enseña como árbol, ordena o compacta un JSON (o YAML).", no_args_is_help=True)
    sub.command("comprueba", help="Si está bien escrito y, si no, en qué línea falla.")(comprueba)
    sub.command("arbol", help="Lo enseña como un árbol.")(arbol_orden)
    sub.command("formatea", help="Lo deja bonito: un valor por línea y con sangría.")(formatea)
    sub.command("compacta", help="Todo en una línea, sin espacios.")(compacta)
    app.add_typer(sub, name="json", rich_help_panel=PROGRAMACION)
