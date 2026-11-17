"""navaja foco: pomodoro en la terminal, con cuenta atrás grande e historial de estudio.

``navaja foco`` empieza un bloque de 25 minutos; ``foco empieza`` cambia las duraciones
y ``foco historial`` cuenta cuánto has estudiado y de qué. Cada bloque (completo o
parado a partir del minuto) se guarda en SQLite (``foco.db``).
"""

from __future__ import annotations

import math
import sqlite3
import sys
import time
from contextlib import closing
from datetime import date, datetime, timedelta

import typer
from rich.align import Align
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from ..comun import (
    AJUSTE,
    ESTUDIO,
    console,
    crear_tabla,
    directorio_datos,
    es_utf8,
)
from ..errores import NavajaError
from ..lotes import fallar

TRABAJO = 25
DESCANSO = 5
MINIMO_GUARDAR = 60
"""Un bloque parado antes de este minuto (en segundos) no se apunta."""

CIFRAS = {
    "0": ("███", "█ █", "█ █", "█ █", "███"),
    "1": (" █ ", "██ ", " █ ", " █ ", "███"),
    "2": ("███", "  █", "███", "█  ", "███"),
    "3": ("███", "  █", "███", "  █", "███"),
    "4": ("█ █", "█ █", "███", "  █", "  █"),
    "5": ("███", "█  ", "███", "  █", "███"),
    "6": ("███", "█  ", "███", "█ █", "███"),
    "7": ("███", "  █", "  █", "  █", "  █"),
    "8": ("███", "█ █", "███", "█ █", "███"),
    "9": ("███", "█ █", "███", "  █", "███"),
    ":": ("   ", " █ ", "   ", " █ ", "   "),
}


def mmss(segundos: int) -> str:
    """90 → «01:30»; con horas, «1:05:00»."""
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02}:{segundos:02}"
    return f"{minutos:02}:{segundos:02}"


def numeros_grandes(texto: str, relleno: str = "█") -> str:
    """«25:00» dibujado en 5 líneas. ``relleno`` sustituye al bloque en terminales sin UTF-8."""
    filas = ["  ".join(CIFRAS[c][i] for c in texto) for i in range(5)]
    return "\n".join(fila.replace("█", relleno) for fila in filas)


def tiempo_legible(segundos: int) -> str:
    """4500 → «1 h 15 min»; 600 → «10 min»; menos de un minuto → «menos de 1 min»."""
    minutos = int(segundos // 60)
    if minutos < 1:
        return "menos de 1 min" if segundos else "0 min"
    horas, minutos = divmod(minutos, 60)
    if horas and minutos:
        return f"{horas} h {minutos} min"
    return f"{horas} h" if horas else f"{minutos} min"


def sonar() -> None:
    """Avisa con sonido: el de Windows, o el pitido de la terminal en Linux y macOS."""
    try:
        import winsound  # solo existe en Windows

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except ImportError:
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except (OSError, ValueError):
            pass
    except RuntimeError:  # sin tarjeta de sonido
        pass


def _panel(restante: int, titulo: str, detalle: str, estilo: str) -> Panel:
    relleno = "█" if es_utf8(console) else "#"
    cuerpo = Text(numeros_grandes(mmss(restante), relleno), style=estilo)
    return Panel(
        Align.center(cuerpo),
        title=f"[titulo]{escape(titulo)}[/]",
        subtitle=f"[pista]{escape(detalle)}[/]",
        border_style="marco",
        padding=(1, 4),
    )


def cuenta_atras(segundos: int, titulo: str, detalle: str, estilo: str = "acento") -> tuple[int, bool]:
    """Cuenta atrás en pantalla. Devuelve (segundos que pasaron, si llegó al final).

    Con Ctrl+C se para y devuelve lo que llevaba.
    """
    inicio = time.monotonic()
    fin = inicio + segundos
    try:
        with Live(console=console, refresh_per_second=4, transient=True) as vivo:
            while True:
                restante = fin - time.monotonic()
                if restante <= 0:
                    break
                vivo.update(_panel(math.ceil(restante), titulo, detalle, estilo))
                time.sleep(min(0.25, restante))
    except KeyboardInterrupt:
        return min(segundos, int(time.monotonic() - inicio)), False
    return segundos, True


def _conectar() -> sqlite3.Connection:
    conexion = sqlite3.connect(directorio_datos() / "foco.db")
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asignatura TEXT NOT NULL DEFAULT '',
            segundos INTEGER NOT NULL,
            completa INTEGER NOT NULL,
            inicio TEXT NOT NULL
        )
        """
    )
    return conexion


def _guardar(asignatura: str, segundos: int, completa: bool, inicio: datetime) -> None:
    with closing(_conectar()) as conexion, conexion:
        conexion.execute(
            "INSERT INTO sesiones (asignatura, segundos, completa, inicio) VALUES (?, ?, ?, ?)",
            (asignatura, segundos, int(completa), inicio.isoformat(timespec="seconds")),
        )


def _total_de_hoy() -> int:
    hoy = date.today().isoformat()
    with closing(_conectar()) as conexion:
        fila = conexion.execute(
            "SELECT COALESCE(SUM(segundos), 0) AS total FROM sesiones WHERE substr(inicio, 1, 10) = ?",
            (hoy,),
        ).fetchone()
    return int(fila["total"])


def _comprobar(trabajo: int, descanso: int, bloques: int) -> None:
    if trabajo < 1:
        raise NavajaError("El bloque de trabajo tiene que durar al menos 1 minuto.")
    if descanso < 0:
        raise NavajaError("El descanso no puede ser negativo (0 = sin descanso).")
    if bloques < 1:
        raise NavajaError("Tiene que haber al menos 1 bloque.")


def _ensenar_plan(trabajo: int, descanso: int, bloques: int, asignatura: str) -> None:
    tabla = crear_tabla(["Bloque", "Trabajo", "Descanso después"])
    for numero in range(1, bloques + 1):
        ultimo = numero == bloques
        tabla.add_row(
            str(numero),
            f"{trabajo} min",
            "—" if ultimo or descanso == 0 else f"{descanso} min",
        )
    console.print(f"[titulo]Plan[/] [pista]({escape(asignatura or 'sin asignatura')})[/]")
    console.print(tabla)
    total = trabajo * bloques + descanso * (bloques - 1)
    console.print(f"[pista]En total, {tiempo_legible(total * 60)} ({tiempo_legible(trabajo * bloques * 60)} de estudio).[/]")


def correr(trabajo: int, descanso: int, bloques: int, asignatura: str, simular: bool) -> None:
    """Lo que hace ``foco``: los bloques de trabajo con sus descansos, apuntando cada uno."""
    try:
        _comprobar(trabajo, descanso, bloques)
    except NavajaError as error:
        fallar(error)
    asignatura = asignatura.strip()
    _ensenar_plan(trabajo, descanso, bloques, asignatura)
    if simular:
        console.print("[aviso]Simulado:[/] no se espera ni se guarda nada.")
        return

    console.print("[pista]Ctrl+C para parar (lo que lleves se apunta si pasó un minuto).[/]")
    for numero in range(1, bloques + 1):
        inicio = datetime.now()
        detalle = f"bloque {numero} de {bloques}" + (f" · {asignatura}" if asignatura else "")
        pasados, completo = cuenta_atras(trabajo * 60, "A trabajar", detalle)
        if completo or pasados >= MINIMO_GUARDAR:
            _guardar(asignatura, pasados, completo, inicio)
        if not completo:
            console.print(
                f"[aviso]Parado a los {tiempo_legible(pasados)}.[/]"
                + (" [pista]Apuntado.[/]" if pasados >= MINIMO_GUARDAR else " [pista]No se apunta (menos de 1 min).[/]")
            )
            return
        sonar()
        console.print(f"[ok]✔ Bloque {numero} hecho[/] [pista]({trabajo} min)[/]")
        if numero < bloques and descanso > 0:
            _, descansado = cuenta_atras(descanso * 60, "Descanso", f"{descanso} min", "ok")
            if not descansado:
                console.print("[aviso]Descanso saltado.[/]")
                return
            sonar()
    console.print(f"[ok]Terminaste.[/] Hoy llevas [bold]{tiempo_legible(_total_de_hoy())}[/] de estudio.")


def empieza(
    trabajo: int = typer.Option(
        TRABAJO, "--trabajo", "-t", min=1, max=180, help="Minutos de cada bloque de trabajo.",
        rich_help_panel=AJUSTE,
    ),
    descanso: int = typer.Option(
        DESCANSO, "--descanso", "-d", min=0, max=60,
        help="Minutos de descanso entre bloques (0 = sin descanso).", rich_help_panel=AJUSTE,
    ),
    bloques: int = typer.Option(
        1, "--bloques", "-b", min=1, max=12, help="Cuántos bloques seguidos.",
        rich_help_panel=AJUSTE,
    ),
    asignatura: str = typer.Option(
        "", "--asignatura", "-a", help="De qué estudias (para el historial).",
        rich_help_panel=AJUSTE,
    ),
    simular: bool = typer.Option(
        False, "--simular", help="Enseña el plan sin esperar ni guardar nada.",
        rich_help_panel=AJUSTE,
    ),
) -> None:
    """Empieza un pomodoro: cuenta atrás grande, aviso con sonido y descanso."""
    correr(trabajo, descanso, bloques, asignatura, simular)


def historial(
    dias: int = typer.Option(
        7, "--dias", "-n", min=1, max=3650, help="Cuántos días mirar hacia atrás.",
        rich_help_panel=AJUSTE,
    ),
) -> None:
    """Cuánto has estudiado: hoy y en los últimos días, por asignatura."""
    desde = (date.today() - timedelta(days=dias - 1)).isoformat()
    with closing(_conectar()) as conexion:
        filas = conexion.execute(
            """
            SELECT asignatura, COUNT(*) AS bloques, SUM(completa) AS completos,
                   SUM(segundos) AS segundos
            FROM sesiones WHERE substr(inicio, 1, 10) >= ?
            GROUP BY asignatura ORDER BY segundos DESC
            """,
            (desde,),
        ).fetchall()
    if not filas:
        console.print(f"[aviso]No hay bloques apuntados en los últimos {dias} días.[/] [pista]Empieza con: navaja foco[/]")
        return
    tabla = crear_tabla(["Asignatura", "Bloques", "Tiempo"])
    total = 0
    for fila in filas:
        total += fila["segundos"]
        tabla.add_row(
            escape(fila["asignatura"]) or "[pista]sin asignatura[/]",
            str(fila["bloques"]),
            tiempo_legible(fila["segundos"]),
        )
    tabla.add_section()
    tabla.add_row("[bold]Total[/]", str(sum(f["bloques"] for f in filas)), f"[bold]{tiempo_legible(total)}[/]")
    console.print(f"[titulo]Estudio de los últimos {dias} días[/]")
    console.print(tabla)
    console.print(f"[pista]Hoy: {tiempo_legible(_total_de_hoy())}[/]")


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Pomodoro con cuenta atrás e historial de lo que estudias.",
        invoke_without_command=True,
    )

    @sub.callback(invoke_without_command=True)
    def principal(ctx: typer.Context) -> None:
        """Pomodoro: sin nada más, un bloque de 25 minutos (5 de descanso entre bloques)."""
        if ctx.invoked_subcommand is None:
            correr(TRABAJO, DESCANSO, 1, "", False)

    sub.command("empieza", help="Empieza un pomodoro (tú eliges minutos, bloques y asignatura).")(empieza)
    sub.command("historial", help="Cuánto has estudiado, por asignatura.")(historial)
    app.add_typer(sub, name="foco", rich_help_panel=ESTUDIO)
