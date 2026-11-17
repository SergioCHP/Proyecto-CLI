"""navaja estudia: tarjetas de memoria con repetición espaciada (algoritmo SM-2, como Anki).

Las tarjetas salen de tus apuntes en Markdown: una línea ``P: pregunta`` y otra
``R: respuesta`` (la respuesta puede seguir en las líneas de debajo). ``estudia importa``
las guarda en SQLite (``estudia.db``) y ``estudia`` te pregunta cada una justo cuando
toca repasarla: si la sabes, tarda más en volver; si no, vuelve mañana.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from ..comun import (
    AJUSTE,
    ESTUDIO,
    bonita,
    console,
    crear_tabla,
    directorio_datos,
    resumen,
)
from ..errores import NavajaError
from ..lotes import fallar

MARCA = re.compile(r"([PR]):\s*(.*)", re.IGNORECASE)
VINETA = re.compile(r"^[-*+]\s+")

FACILIDAD_INICIAL = 2.5
FACILIDAD_MINIMA = 1.3
DIAS_APRENDIDA = 21
"""Una tarjeta con un intervalo así de largo cuenta como aprendida."""

NOTAS = {"1": 1, "2": 3, "3": 4, "4": 5}
"""Lo que pulsas → la calidad (0-5) que usa SM-2: 1 otra vez, 2 difícil, 3 bien, 4 fácil."""


def hoy() -> date:
    return date.today()


# ── Leer tarjetas ──────────────────────────────────────────────────────────


def leer_tarjetas(texto: str) -> list[tuple[str, str]]:
    """Las parejas (pregunta, respuesta) de un texto Markdown.

    ``P:`` abre una tarjeta y ``R:`` su respuesta; esta sigue en las líneas siguientes
    hasta una línea en blanco o el siguiente ``P:``. Una pregunta sin respuesta se ignora.
    """
    tarjetas: list[tuple[str, str]] = []
    pregunta: str | None = None
    respuesta: list[str] = []
    en_respuesta = False

    def cerrar() -> None:
        nonlocal pregunta, respuesta, en_respuesta
        cuerpo = "\n".join(linea for linea in respuesta if linea).strip()
        if pregunta and cuerpo:
            tarjetas.append((pregunta.strip(), cuerpo))
        pregunta, respuesta, en_respuesta = None, [], False

    for linea in texto.splitlines():
        limpia = VINETA.sub("", linea.strip())
        marca = MARCA.fullmatch(limpia)
        if marca and marca[1].upper() == "P":
            cerrar()
            pregunta = marca[2].strip()
        elif marca and marca[1].upper() == "R" and pregunta is not None and not en_respuesta:
            respuesta = [marca[2].strip()]
            en_respuesta = True
        elif en_respuesta:
            if limpia:
                respuesta.append(limpia)
            else:
                cerrar()
        elif pregunta is not None and limpia:
            pregunta += " " + limpia  # la pregunta ocupa varias líneas
    cerrar()
    return tarjetas


# ── SM-2 ───────────────────────────────────────────────────────────────────


def siguiente(facilidad: float, repeticiones: int, intervalo: int, calidad: int) -> tuple[float, int, int]:
    """Un paso de SM-2: devuelve (facilidad, repeticiones, intervalo en días).

    Con calidad menor de 3 se vuelve a empezar (mañana) sin tocar la facilidad. Con 3 o
    más, el intervalo es 1 día, luego 6 y luego el anterior por la facilidad; la facilidad
    sube si fue fácil y baja si costó (nunca por debajo de 1,3).
    """
    if calidad < 3:
        return facilidad, 0, 1
    if repeticiones == 0:
        intervalo = 1
    elif repeticiones == 1:
        intervalo = 6
    else:
        intervalo = round(intervalo * facilidad)
    fallo = 5 - calidad
    facilidad = max(FACILIDAD_MINIMA, facilidad + 0.1 - fallo * (0.08 + fallo * 0.02))
    return facilidad, repeticiones + 1, intervalo


# ── Base de datos ──────────────────────────────────────────────────────────


def _conectar() -> sqlite3.Connection:
    conexion = sqlite3.connect(directorio_datos() / "estudia.db")
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS tarjetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asignatura TEXT NOT NULL DEFAULT '',
            pregunta TEXT NOT NULL,
            respuesta TEXT NOT NULL,
            origen TEXT NOT NULL DEFAULT '',
            facilidad REAL NOT NULL DEFAULT 2.5,
            repeticiones INTEGER NOT NULL DEFAULT 0,
            intervalo INTEGER NOT NULL DEFAULT 0,
            proxima TEXT NOT NULL,
            creada TEXT NOT NULL,
            UNIQUE (asignatura, pregunta)
        )
        """
    )
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS repasos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarjeta_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            calidad INTEGER NOT NULL
        )
        """
    )
    return conexion


@dataclass
class Resultado:
    nuevas: int = 0
    cambiadas: int = 0
    iguales: int = 0


def guardar_tarjetas(
    conexion: sqlite3.Connection,
    tarjetas: list[tuple[str, str]],
    asignatura: str,
    origen: str,
    guardar: bool = True,
) -> Resultado:
    """Añade las nuevas; si una pregunta ya estaba con otra respuesta, la actualiza sin
    perder lo que llevas aprendido. Con ``guardar=False`` solo cuenta."""
    cuenta = Resultado()
    for pregunta, respuesta in tarjetas:
        fila = conexion.execute(
            "SELECT id, respuesta FROM tarjetas WHERE asignatura = ? AND pregunta = ?",
            (asignatura, pregunta),
        ).fetchone()
        if fila is None:
            cuenta.nuevas += 1
            if guardar:
                conexion.execute(
                    "INSERT INTO tarjetas (asignatura, pregunta, respuesta, origen, proxima, creada)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        asignatura, pregunta, respuesta, origen, hoy().isoformat(),
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
        elif fila["respuesta"] != respuesta:
            cuenta.cambiadas += 1
            if guardar:
                conexion.execute(
                    "UPDATE tarjetas SET respuesta = ?, origen = ? WHERE id = ?",
                    (respuesta, origen, fila["id"]),
                )
        else:
            cuenta.iguales += 1
    return cuenta


def archivos_md(ruta: Path) -> list[Path]:
    if not ruta.exists():
        raise NavajaError(f"No existe {bonita(ruta)}.")
    if ruta.is_file():
        return [ruta]
    archivos = sorted(p for p in ruta.rglob("*.md") if p.is_file())
    if not archivos:
        raise NavajaError(f"No hay archivos .md en {bonita(ruta)}.")
    return archivos


# ── Órdenes ────────────────────────────────────────────────────────────────


def importa(
    ruta: Path = typer.Argument(..., help="Un apunte .md o una carpeta con apuntes (busca dentro)."),
    asignatura: str = typer.Option(
        "", "--asignatura", "-a", help="A qué asignatura pertenecen las tarjetas.",
        rich_help_panel=AJUSTE,
    ),
    simular: bool = typer.Option(
        False, "--simular", help="Cuenta las tarjetas sin guardar nada.", rich_help_panel=AJUSTE
    ),
) -> None:
    """Saca tarjetas de tus apuntes (líneas «P:» y «R:») y las guarda para repasar."""
    asignatura = asignatura.strip()
    try:
        archivos = archivos_md(ruta.expanduser())
    except NavajaError as error:
        fallar(error)

    total = Resultado()
    sin_tarjetas = 0
    with closing(_conectar()) as conexion, conexion:
        for archivo in archivos:
            try:
                texto = archivo.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                console.print(f"[aviso]No se pudo leer {escape(bonita(archivo))}; se salta.[/]", soft_wrap=True)
                continue
            tarjetas = leer_tarjetas(texto)
            if not tarjetas:
                sin_tarjetas += 1
                continue
            parcial = guardar_tarjetas(conexion, tarjetas, asignatura, archivo.name, guardar=not simular)
            total.nuevas += parcial.nuevas
            total.cambiadas += parcial.cambiadas
            total.iguales += parcial.iguales

    if not (total.nuevas or total.cambiadas or total.iguales):
        console.print(
            "[aviso]No encontré ninguna tarjeta.[/] [pista]En el apunte, escribe «P: pregunta» "
            "y debajo «R: respuesta».[/]"
        )
        return
    prefijo = "[aviso]Simulado[/] (no se guardó nada): " if simular else "[ok]✔[/] "
    console.print(
        f"{prefijo}{total.nuevas} nuevas, {total.cambiadas} con la respuesta cambiada, "
        f"{total.iguales} que ya estaban."
    )
    if sin_tarjetas:
        console.print(f"[pista]{sin_tarjetas} archivo(s) sin tarjetas.[/]")
    if not simular and total.nuevas:
        console.print("[pista]Para repasar: navaja estudia[/]")


def _pendientes(conexion: sqlite3.Connection, asignatura: str | None, limite: int) -> list[sqlite3.Row]:
    sql = "SELECT * FROM tarjetas WHERE proxima <= ?"
    parametros: list = [hoy().isoformat()]
    if asignatura:
        sql += " AND LOWER(asignatura) = ?"
        parametros.append(asignatura.strip().lower())
    sql += " ORDER BY proxima ASC, id ASC LIMIT ?"
    parametros.append(limite)
    return conexion.execute(sql, parametros).fetchall()


def _repasar_una(conexion: sqlite3.Connection, fila: sqlite3.Row, calidad: int) -> sqlite3.Row:
    facilidad, repeticiones, intervalo = siguiente(
        fila["facilidad"], fila["repeticiones"], fila["intervalo"], calidad
    )
    proxima = (hoy() + timedelta(days=intervalo)).isoformat()
    with conexion:
        conexion.execute(
            "UPDATE tarjetas SET facilidad = ?, repeticiones = ?, intervalo = ?, proxima = ? WHERE id = ?",
            (facilidad, repeticiones, intervalo, proxima, fila["id"]),
        )
        conexion.execute(
            "INSERT INTO repasos (tarjeta_id, fecha, calidad) VALUES (?, ?, ?)",
            (fila["id"], hoy().isoformat(), calidad),
        )
    return conexion.execute("SELECT * FROM tarjetas WHERE id = ?", (fila["id"],)).fetchone()


def _cuando(dias: int) -> str:
    return "mañana" if dias == 1 else f"en {dias} días"


def sesion(limite: int, asignatura: str | None) -> None:
    """El repaso: pregunta, enseña la respuesta, pregunta cómo fue y reprograma."""
    with closing(_conectar()) as conexion:
        cola = [dict(f) for f in _pendientes(conexion, asignatura, limite)]
        if not cola:
            total = conexion.execute("SELECT COUNT(*) AS n FROM tarjetas").fetchone()["n"]
            if total == 0:
                console.print(
                    "[aviso]Todavía no tienes tarjetas.[/] "
                    "[pista]Crea apuntes con líneas «P:» y «R:» y usa: navaja estudia importa CARPETA[/]"
                )
            else:
                console.print("[ok]🎉 No te toca repasar nada hoy.[/] [pista]Mira cuándo vuelven con: navaja estudia estadisticas[/]")
            return

        console.print(
            f"[titulo]Repaso[/] [pista]· {len(cola)} tarjeta{'s' if len(cola) != 1 else ''}. "
            "Intro para ver la respuesta; luego 1 otra vez · 2 difícil · 3 bien · 4 fácil · s salir[/]"
        )
        hechas = 0
        bien = 0
        try:
            while cola:
                fila = cola.pop(0)
                etiqueta = f" · {escape(fila['asignatura'])}" if fila["asignatura"] else ""
                console.print(Panel(Text(fila["pregunta"]), title=f"[titulo]Pregunta[/]{etiqueta}", border_style="marco"))
                console.input("[pista]Intro para ver la respuesta… [/]")
                console.print(Panel(Text(fila["respuesta"]), title="[ok]Respuesta[/]", border_style="borde"))
                eleccion = Prompt.ask(
                    "¿Cómo la sabías?", choices=[*NOTAS, "s"], default="3", console=console
                )
                if eleccion == "s":
                    break
                calidad = NOTAS[eleccion]
                nueva = _repasar_una(conexion, fila, calidad)
                hechas += 1
                if calidad >= 3:
                    bien += 1
                    console.print(f"[pista]Vuelve {_cuando(nueva['intervalo'])}.[/]\n")
                else:
                    console.print("[aviso]Otra vez al final de esta sesión; y mañana de nuevo.[/]\n")
                    cola.append(dict(nueva))
        except (EOFError, KeyboardInterrupt):
            console.print()
        console.print(
            f"[ok]✔ Repasadas {hechas}[/] [pista]({bien} bien, {hechas - bien} por repetir).[/]"
            + (f" Quedan {len(cola)} por hacer." if cola else "")
        )


def repasa(
    limite: int = typer.Option(
        20, "--limite", "-n", min=1, max=500, help="Cuántas tarjetas como mucho en esta sesión.",
        rich_help_panel=AJUSTE,
    ),
    asignatura: str | None = typer.Option(
        None, "--asignatura", "-a", help="Solo las de esta asignatura.", rich_help_panel=AJUSTE
    ),
) -> None:
    """Repasa las tarjetas que te tocan hoy."""
    sesion(limite, asignatura)


def _racha(fechas: list[str]) -> int:
    """Días seguidos repasando, contando desde hoy (o desde ayer si hoy aún no repasaste)."""
    dias = {date.fromisoformat(f) for f in fechas}
    dia = hoy() if hoy() in dias else hoy() - timedelta(days=1)
    racha = 0
    while dia in dias:
        racha += 1
        dia -= timedelta(days=1)
    return racha


def estadisticas() -> None:
    """Cuántas tarjetas tienes, cuántas tocan hoy, las aprendidas y tu racha de días."""
    ahora = hoy().isoformat()
    with closing(_conectar()) as conexion:
        total = conexion.execute("SELECT COUNT(*) AS n FROM tarjetas").fetchone()["n"]
        if total == 0:
            console.print("[aviso]Todavía no tienes tarjetas.[/] [pista]Usa: navaja estudia importa CARPETA[/]")
            return
        pendientes = conexion.execute("SELECT COUNT(*) AS n FROM tarjetas WHERE proxima <= ?", (ahora,)).fetchone()["n"]
        nuevas = conexion.execute(
            "SELECT COUNT(*) AS n FROM tarjetas WHERE id NOT IN (SELECT tarjeta_id FROM repasos)"
        ).fetchone()["n"]
        aprendidas = conexion.execute(
            "SELECT COUNT(*) AS n FROM tarjetas WHERE intervalo >= ?", (DIAS_APRENDIDA,)
        ).fetchone()["n"]
        hechas_hoy = conexion.execute("SELECT COUNT(*) AS n FROM repasos WHERE fecha = ?", (ahora,)).fetchone()["n"]
        fechas = [f["fecha"] for f in conexion.execute("SELECT DISTINCT fecha FROM repasos")]
        por_asignatura = conexion.execute(
            "SELECT asignatura, COUNT(*) AS n, SUM(proxima <= ?) AS toca FROM tarjetas"
            " GROUP BY asignatura ORDER BY n DESC",
            (ahora,),
        ).fetchall()

    racha = _racha(fechas)
    console.print(
        resumen([
            ("Tarjetas", str(total)),
            ("Te tocan hoy", f"[aviso]{pendientes}[/]" if pendientes else "[ok]0[/]"),
            ("Sin estudiar aún", str(nuevas)),
            ("Aprendidas", f"{aprendidas} [pista](las que tardan {DIAS_APRENDIDA} días o más en volver)[/]"),
            ("Repasadas hoy", str(hechas_hoy)),
            ("Racha", f"{racha} día{'s' if racha != 1 else ''} seguido{'s' if racha != 1 else ''}"),
        ])
    )
    if len(por_asignatura) > 1 or (por_asignatura and por_asignatura[0]["asignatura"]):
        tabla = crear_tabla(["Asignatura", "Tarjetas", "Hoy"])
        for fila in por_asignatura:
            tabla.add_row(escape(fila["asignatura"]) or "[pista]sin asignatura[/]", str(fila["n"]), str(fila["toca"]))
        console.print(tabla)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Tarjetas de memoria con repetición espaciada, sacadas de tus apuntes.",
        invoke_without_command=True,
    )

    @sub.callback(invoke_without_command=True)
    def principal(ctx: typer.Context) -> None:
        """Estudia: sin nada más, repasa las tarjetas que te tocan hoy."""
        if ctx.invoked_subcommand is None:
            sesion(20, None)

    sub.command("repasa", help="Repasa las tarjetas que te tocan hoy.")(repasa)
    sub.command("importa", help="Saca tarjetas de tus apuntes (líneas P: y R:).")(importa)
    sub.command("estadisticas", help="Tarjetas, pendientes, aprendidas y tu racha.")(estadisticas)
    app.add_typer(sub, name="estudia", rich_help_panel=ESTUDIO)
