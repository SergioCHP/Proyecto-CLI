"""navaja chmod: los permisos de Linux en número (755) y en letras (rwxr-xr-x), explicados.

Solo calcula: no cambia los permisos de ningún archivo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NoReturn

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import REDES, console, error_console, recuadro, resumen, tabla_ligera
from ..errores import NavajaError

QUIENES = ("Dueño (u)", "Grupo (g)", "Otros (o)")
LETRAS = "rwx"
ESPECIALES = {
    4: ("setuid", "el programa se ejecuta con los permisos de su dueño (como passwd)"),
    2: ("setgid", "se ejecuta con los del grupo; en una carpeta, lo nuevo hereda su grupo"),
    1: ("sticky", "en una carpeta, cada uno solo puede borrar lo suyo (como /tmp)"),
}
TIPICOS = "644 archivos normales · 755 carpetas y scripts · 600 claves privadas (~/.ssh)"


@dataclass
class Permisos:
    """Los tres grupos de permisos (dueño, grupo, otros) de 0 a 7 y los especiales."""

    tres: tuple[int, int, int]
    especiales: int = 0

    @property
    def octal(self) -> str:
        cifras = "".join(str(n) for n in self.tres)
        return f"{self.especiales}{cifras}" if self.especiales else cifras

    @property
    def letras(self) -> str:
        texto = []
        for posicion, valor in enumerate(self.tres):
            trio = [LETRAS[i] if valor & (4 >> i) else "-" for i in range(3)]
            especial = self.especiales & (4 >> posicion)
            if especial:
                marca = "t" if posicion == 2 else "s"
                trio[2] = marca if trio[2] == "x" else marca.upper()
            texto.append("".join(trio))
        return "".join(texto)


SIMBOLICO = re.compile(r"^[-dlcbps]?([r-][w-][xsS-])([r-][w-][xsS-])([r-][w-][xtT-])$")


def leer_permisos(texto: str) -> Permisos:
    """«755», «0755», «4755», «rwxr-xr-x» o «-rwxr-xr-x» (como sale en ``ls -l``)."""
    limpio = texto.strip()
    if re.fullmatch(r"[0-7]{3,4}", limpio):
        cifras = [int(c) for c in limpio]
        especiales = cifras.pop(0) if len(cifras) == 4 else 0
        return Permisos((cifras[0], cifras[1], cifras[2]), especiales)
    encaje = SIMBOLICO.match(limpio)
    if not encaje:
        raise NavajaError(
            f"«{texto}» no son permisos. Escríbelos como 755 (tres cifras del 0 al 7) o "
            "como rwxr-xr-x (r leer, w escribir, x ejecutar, - nada)."
        )
    tres = []
    especiales = 0
    for posicion, trio in enumerate(encaje.groups()):
        valor = sum(4 >> i for i, letra in enumerate(trio) if letra in "rwxst")
        if trio[2] in "sStT":
            especiales |= 4 >> posicion
        tres.append(valor)
    return Permisos((tres[0], tres[1], tres[2]), especiales)


def que_puede(valor: int, carpeta: bool = False) -> str:
    """5 → «leer y ejecutar». En una carpeta, leer es ver lo que hay, escribir es crear o
    borrar dentro y ejecutar es entrar en ella."""
    acciones = []
    if valor & 4:
        acciones.append("leer" if not carpeta else "ver")
    if valor & 2:
        acciones.append("escribir" if not carpeta else "crear/borrar")
    if valor & 1:
        acciones.append("ejecutar" if not carpeta else "entrar")
    if not acciones:
        return "nada"
    return acciones[0] if len(acciones) == 1 else ", ".join(acciones[:-1]) + " y " + acciones[-1]


def avisos(permisos: Permisos) -> list[str]:
    """Lo que puede ser un problema de seguridad o un error típico."""
    lista = []
    if permisos.tres[2] & 2:
        lista.append("Cualquiera puede cambiarlo o borrar lo de dentro: casi nunca es buena idea.")
    if permisos.tres[0] < max(permisos.tres[1], permisos.tres[2]):
        lista.append("Los demás pueden más que el dueño: suele ser un error.")
    if permisos.tres[0] & 4 == 0:
        lista.append("Ni el dueño puede leerlo.")
    return lista


# ── Orden ──────────────────────────────────────────────────────────────────


def fallar(error: NavajaError) -> NoReturn:
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def chmod(
    permisos: str = typer.Argument(..., help="Los permisos: 755, 4755 o rwxr-xr-x."),
) -> None:
    """Calculadora de permisos de Linux: 755 ↔ rwxr-xr-x, explicando quién puede qué."""
    try:
        leidos = leer_permisos(permisos)
    except NavajaError as error:
        fallar(error)
    tabla = tabla_ligera()
    for columna in ("Quién", "r (4)", "w (2)", "x (1)", "Suma", "En un archivo", "En una carpeta"):
        tabla.add_column(columna, no_wrap=columna not in ("En un archivo", "En una carpeta"))
    for quien, valor in zip(QUIENES, leidos.tres):
        marcas = ["[ok]✔[/]" if valor & (4 >> i) else "[pista]·[/]" for i in range(3)]
        tabla.add_row(
            quien, *marcas, f"[acento]{valor}[/]", que_puede(valor), que_puede(valor, carpeta=True)
        )
    filas = [
        ("Número", f"[acento]{leidos.octal}[/]"),
        ("Letras", f"[acento]{leidos.letras}[/]"),
        ("Para ponerlos", f"chmod {leidos.octal} archivo"),
    ]
    partes: list = [resumen(filas), tabla]
    for bit, (nombre, explicacion) in ESPECIALES.items():
        if leidos.especiales & bit:
            partes.append(Text.from_markup(f"[titulo]{nombre}:[/] {escape(explicacion)}."))
    for aviso in avisos(leidos):
        partes.append(Text.from_markup(f"[aviso]{escape(aviso)}[/]"))
    partes.append(Text.from_markup(f"[pista]Típicos: {escape(TIPICOS)}.[/]"))
    console.print(recuadro(f"Permisos {leidos.octal}", *partes))


def registrar(app: typer.Typer) -> None:
    app.command(
        "chmod", help="Permisos de Linux: 755 ↔ rwxr-xr-x, explicado.", rich_help_panel=REDES
    )(chmod)
