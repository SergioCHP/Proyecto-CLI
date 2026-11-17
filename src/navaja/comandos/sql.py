"""navaja sql: abre una base SQLite y la consulta, con los resultados en tablas.

Sin consulta, enseña las tablas con sus columnas y cuántas filas tiene cada una. Una
consulta que solo lee (SELECT, WITH, PRAGMA…) se hace sobre la base abierta en modo solo
lectura. Una que cambia algo (INSERT, UPDATE, DELETE, CREATE…) enseña antes lo que va a
hacer y pregunta ``[s/n]``; antes de cambiar nada guarda una copia de la base para poder
volver atrás, y con ``--simular`` la prueba dentro de una transacción que luego deshace.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import typer
from rich.markup import escape
from rich.syntax import Syntax

from ..comun import (
    AJUSTE,
    PROGRAMACION,
    bonita,
    confirmar,
    console,
    crear_tabla,
    directorio_datos,
    ruta_libre,
)
from ..errores import NavajaError
from ..lotes import fallar

ESCRITURA = {
    "INSERT", "UPDATE", "DELETE", "REPLACE", "UPSERT", "CREATE", "DROP", "ALTER",
    "REINDEX", "VACUUM", "ANALYZE", "ATTACH", "DETACH",
}
"""Primeras palabras de una sentencia que cambia la base: pregunta antes y hace copia.
Todo lo demás (SELECT, WITH, PRAGMA… o una palabra mal escrita) se hace con la base en
solo lectura: si en realidad intenta cambiar algo, SQLite no le deja."""

COPIAS = 5
"""Cuántas copias de seguridad se guardan de cada base antes de cambiarla."""

PALABRA = re.compile(r"[A-Za-z]+")


def partir(texto: str) -> list[str]:
    """Las sentencias de un texto SQL, sin las vacías ni los comentarios sueltos.

    Se corta en cada «;» que cierra una sentencia completa (``sqlite3.complete_statement``),
    así un «;» dentro de un texto entre comillas no corta.
    """
    sentencias: list[str] = []
    actual = ""
    for caracter in texto:
        actual += caracter
        if caracter == ";" and sqlite3.complete_statement(actual):
            sentencias.append(actual)
            actual = ""
    if actual.strip():
        sentencias.append(actual)
    limpias = []
    for sentencia in sentencias:
        sin_comentarios = "\n".join(
            linea for linea in sentencia.splitlines() if not linea.strip().startswith("--")
        ).strip()
        if sin_comentarios.rstrip(";").strip():
            limpias.append(sin_comentarios)
    return limpias


def primera_palabra(sentencia: str) -> str:
    coincide = PALABRA.search(sentencia)
    return coincide[0].upper() if coincide else ""


def solo_lee(sentencias: list[str]) -> bool:
    return not any(primera_palabra(s) in ESCRITURA for s in sentencias)


def abrir(base: Path, solo_lectura: bool, crear: bool = False) -> sqlite3.Connection:
    """Conecta sin crear la base por error (salvo con ``crear``)."""
    if not base.exists() and not crear:
        raise NavajaError(f"No existe {bonita(base)}. Para crear una base nueva: --crear")
    if base.is_dir():
        raise NavajaError(f"{bonita(base)} es una carpeta, no una base de datos.")
    modo = "ro" if solo_lectura else ("rwc" if crear else "rw")
    try:
        conexion = sqlite3.connect(f"{base.resolve().as_uri()}?mode={modo}", uri=True)
        conexion.execute("SELECT name FROM sqlite_master LIMIT 1")  # ¿es SQLite de verdad?
    except sqlite3.DatabaseError as error:
        raise NavajaError(f"{bonita(base)} no es una base SQLite ({error}).") from error
    return conexion


def nombre_seguro(nombre: str) -> str:
    return '"' + nombre.replace('"', '""') + '"'


def ensenar_tablas(conexion: sqlite3.Connection, base: Path) -> None:
    objetos = conexion.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')"
        " AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    console.print(f"[titulo]{escape(bonita(base))}[/]", soft_wrap=True)
    if not objetos:
        console.print("[aviso]La base no tiene tablas todavía.[/]")
        return
    for nombre, tipo in objetos:
        filas = conexion.execute(f"SELECT COUNT(*) FROM {nombre_seguro(nombre)}").fetchone()[0]
        columnas = conexion.execute(f"PRAGMA table_info({nombre_seguro(nombre)})").fetchall()
        tabla = crear_tabla(["Columna", "Tipo", ""])
        for _, columna, tipo_columna, no_nula, _, clave in columnas:
            marcas = []
            if clave:
                marcas.append("[acento]clave[/]")
            if no_nula:
                marcas.append("[pista]obligatoria[/]")
            tabla.add_row(escape(columna), escape(tipo_columna or "—"), " ".join(marcas))
        que = "vista" if tipo == "view" else "tabla"
        console.print(f"\n[acento]{escape(nombre)}[/] [pista]· {que} · {filas} fila{'s' if filas != 1 else ''}[/]")
        console.print(tabla)
    console.print('\n[pista]Para consultar: navaja sql BASE "SELECT * FROM tabla"[/]')


def ensenar_resultado(cursor: sqlite3.Cursor, limite: int) -> list[str]:
    """Pinta las filas (como mucho ``limite``) y devuelve los nombres de las columnas."""
    columnas = [d[0] for d in cursor.description]
    filas = cursor.fetchmany(limite + 1)
    tabla = crear_tabla([escape(c) for c in columnas])
    for fila in filas[:limite]:
        tabla.add_row(*("[pista]NULL[/]" if v is None else escape(str(v)) for v in fila))
    console.print(tabla)
    if len(filas) > limite:
        console.print(f"[pista]Solo las {limite} primeras. Más con --limite, o todas con --csv.[/]")
    else:
        console.print(f"[pista]{len(filas)} fila{'s' if len(filas) != 1 else ''}.[/]")
    return columnas


def guardar_csv(conexion: sqlite3.Connection, sentencia: str, destino: Path) -> Path:
    final = ruta_libre(destino.expanduser())
    cursor = conexion.execute(sentencia)
    if cursor.description is None:
        raise NavajaError("Esa consulta no devuelve filas: no hay nada que guardar.")
    try:
        with final.open("w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.writer(archivo, delimiter=";")
            escritor.writerow([d[0] for d in cursor.description])
            total = 0
            for fila in cursor:
                escritor.writerow(["" if v is None else v for v in fila])
                total += 1
    except OSError as error:
        raise NavajaError(f"No se pudo guardar {bonita(final)}: {error.strerror or error}") from error
    console.print(f"[ok]✔ {total} filas en {escape(bonita(final))}[/]", soft_wrap=True)
    return final


def carpeta_copias() -> Path:
    return directorio_datos() / "sql-copias"


def copia_de_seguridad(conexion: sqlite3.Connection, base: Path) -> Path:
    """Copia la base antes de cambiarla (y borra las más viejas: quedan ``COPIAS``)."""
    carpeta = carpeta_copias()
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = ruta_libre(carpeta / f"{base.stem}-{datetime.now():%Y-%m-%d_%H-%M-%S}{base.suffix or '.db'}")
    with closing(sqlite3.connect(destino)) as copia:
        conexion.backup(copia)
    viejas = sorted(carpeta.glob(f"{base.stem}-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for vieja in viejas[COPIAS:]:
        try:
            vieja.unlink()
        except OSError:
            pass
    return destino


def ensenar_sentencias(sentencias: list[str], maximo: int = 8) -> None:
    texto = "\n".join(s if s.rstrip().endswith(";") else s + ";" for s in sentencias[:maximo])
    console.print(Syntax(texto, "sql", theme="ansi_dark", word_wrap=True, background_color="default"))
    if len(sentencias) > maximo:
        console.print(f"[pista]… y {len(sentencias) - maximo} sentencias más.[/]")


def escribir(base: Path, sentencias: list[str], crear: bool, simular: bool, si: bool) -> None:
    nueva = not base.exists()
    if nueva and not crear:
        raise NavajaError(f"No existe {bonita(base)}. Para crear una base nueva: --crear")
    console.print(f"[titulo]Va a cambiar {escape(bonita(base))}[/]" + (" [aviso](se crea nueva)[/]" if nueva else ""), soft_wrap=True)
    ensenar_sentencias(sentencias)
    if simular:
        if nueva:
            console.print("[aviso]Simulado:[/] la base no existe; no se crea nada.")
            return
        with closing(abrir(base, solo_lectura=False)) as conexion:
            conexion.isolation_level = None
            conexion.execute("BEGIN")
            antes = conexion.total_changes
            try:
                for sentencia in sentencias:
                    conexion.execute(sentencia)
                cambios = conexion.total_changes - antes
            finally:
                conexion.execute("ROLLBACK")
        console.print(f"[aviso]Simulado:[/] cambiaría {cambios} fila{'s' if cambios != 1 else ''}. No se guardó nada.")
        return
    if not confirmar("¿Hacer estos cambios?", saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return
    with closing(abrir(base, solo_lectura=False, crear=crear)) as conexion:
        copia = None if nueva else copia_de_seguridad(conexion, base)
        conexion.isolation_level = None
        conexion.execute("BEGIN")
        antes = conexion.total_changes
        try:
            for sentencia in sentencias:
                conexion.execute(sentencia)
        except sqlite3.Error:
            conexion.execute("ROLLBACK")  # todo o nada
            raise
        cambios = conexion.total_changes - antes
        conexion.execute("COMMIT")
    console.print(f"[ok]✔ Hecho:[/] {cambios} fila{'s' if cambios != 1 else ''} cambiada{'s' if cambios != 1 else ''}.")
    if copia:
        console.print(f"[pista]Copia de antes en {escape(bonita(copia))} (para volver atrás, cópiala encima).[/]", soft_wrap=True)


def sql(
    base: Path = typer.Argument(..., help="El archivo de la base SQLite (.db, .sqlite…)."),
    consulta: str | None = typer.Argument(
        None, help='La consulta, entre comillas: "SELECT * FROM clientes". Sin consulta, las tablas.',
        show_default=False,
    ),
    archivo: Path | None = typer.Option(
        None, "--archivo", "-a", help="Lee las sentencias de un archivo .sql (por ejemplo, el de navaja falsos).",
        rich_help_panel=AJUSTE,
    ),
    limite: int = typer.Option(
        100, "--limite", "-n", min=1, max=100_000, help="Cuántas filas enseñar como mucho.",
        rich_help_panel=AJUSTE,
    ),
    csv_: Path | None = typer.Option(
        None, "--csv", help="Guarda el resultado entero en un CSV (nunca pisa uno que ya existe).",
        rich_help_panel=AJUSTE,
    ),
    crear: bool = typer.Option(
        False, "--crear", help="Si la base no existe, la crea (para un CREATE TABLE o un .sql de falsos).",
        rich_help_panel=AJUSTE,
    ),
    simular: bool = typer.Option(
        False, "--simular", help="Prueba los cambios y los deshace: dice cuántas filas cambiaría.",
        rich_help_panel=AJUSTE,
    ),
    si: bool = typer.Option(False, "--si", "-s", help="No pide confirmación."),
) -> None:
    """Abre una base SQLite: sus tablas, consultas con el resultado en tabla y cambios con [s/n]."""
    try:
        base = base.expanduser()
        if consulta and archivo:
            raise NavajaError("Di la consulta o --archivo, no las dos.")
        if archivo:
            try:
                consulta = archivo.expanduser().read_text(encoding="utf-8-sig")
            except FileNotFoundError:
                raise NavajaError(f"No existe {bonita(archivo)}.") from None
            except (OSError, UnicodeDecodeError) as error:
                raise NavajaError(f"No se pudo leer {bonita(archivo)}: {error}") from error

        if not consulta or not consulta.strip():
            if crear and not base.exists():
                raise NavajaError("Para crear una base hace falta algo que meter: una consulta o --archivo.")
            with closing(abrir(base, solo_lectura=True)) as conexion:
                ensenar_tablas(conexion, base)
            return

        sentencias = partir(consulta)
        if not sentencias:
            raise NavajaError("La consulta está vacía (solo hay comentarios).")

        if not solo_lee(sentencias):
            if csv_:
                raise NavajaError("--csv es para guardar lo que devuelve un SELECT, no para cambios.")
            escribir(base, sentencias, crear, simular, si)
            return

        with closing(abrir(base, solo_lectura=True)) as conexion:
            for sentencia in sentencias[:-1]:  # p. ej. un PRAGMA antes del SELECT
                conexion.execute(sentencia)
            ultima = sentencias[-1]
            if csv_:
                guardar_csv(conexion, ultima, csv_)
                return
            cursor = conexion.execute(ultima)
            if cursor.description is None:
                console.print("[ok]✔ Hecho.[/] [pista](no devuelve filas)[/]")
                return
            ensenar_resultado(cursor, limite)
    except sqlite3.Error as error:
        mensaje = str(error)
        if "readonly" in mensaje or "read-only" in mensaje:
            mensaje = "esa consulta intenta cambiar la base; escríbela como INSERT, UPDATE, DELETE…"
        fallar(NavajaError(f"Error de SQL: {mensaje}"))
    except NavajaError as error:
        fallar(error)


def registrar(app: typer.Typer) -> None:
    app.command(
        "sql", help="Abre una base SQLite: tablas, consultas y cambios con [s/n].",
        rich_help_panel=PROGRAMACION,
    )(sql)
