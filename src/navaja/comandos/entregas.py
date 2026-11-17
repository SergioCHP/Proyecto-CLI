"""navaja entregas: deberes y exámenes con fecha, con cuenta atrás y colores.

Se guardan en SQLite (``entregas.db``, como ``notas``). Rojo si quedan menos de 2 días,
amarillo si queda menos de una semana. Al abrir navaja en modo interactivo, el saludo
avisa de lo que vence pronto (``aviso_de_pendientes``).
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import typer
from rich.markup import escape

from ..comun import (
    AJUSTE,
    ESTUDIO,
    confirmar,
    console,
    crear_tabla,
    directorio_datos,
    error_console,
)
from ..errores import NavajaError
from ..lotes import fallar

DIAS_URGENTE = 2
"""Con menos días que estos, la fecha sale en rojo."""

DIAS_PRONTO = 7
"""Con menos días que estos, sale en amarillo (y el saludo avisa)."""

ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
DIA_MES_ANYO = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")
DIA_MES = re.compile(r"(\d{1,2})[/-](\d{1,2})")
EN_DIAS = re.compile(r"\+(\d{1,4})")

TIPOS = {"entrega": "Entrega", "examen": "Examen"}


def _conectar() -> sqlite3.Connection:
    conexion = sqlite3.connect(directorio_datos() / "entregas.db")
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            asignatura TEXT NOT NULL DEFAULT '',
            tipo TEXT NOT NULL DEFAULT 'entrega',
            fecha TEXT NOT NULL,
            hecha INTEGER NOT NULL DEFAULT 0,
            creado TEXT NOT NULL
        )
        """
    )
    return conexion


def _fecha_valida(anyo: int, mes: int, dia: int, original: str) -> date:
    try:
        return date(anyo, mes, dia)
    except ValueError:
        raise NavajaError(f"«{original}» no es una fecha que exista.") from None


def leer_fecha(texto: str, hoy: date | None = None) -> date:
    """«2026-12-15», «15/12/2026», «15/12» (la próxima), «hoy», «mañana» o «+3» (en 3 días)."""
    hoy = hoy or date.today()
    limpio = texto.strip().lower()
    if limpio == "hoy":
        return hoy
    if limpio in ("mañana", "manana"):
        return hoy + timedelta(days=1)
    if coincide := EN_DIAS.fullmatch(limpio):
        return hoy + timedelta(days=int(coincide[1]))
    if coincide := ISO.fullmatch(limpio):
        return _fecha_valida(int(coincide[1]), int(coincide[2]), int(coincide[3]), texto)
    if coincide := DIA_MES_ANYO.fullmatch(limpio):
        return _fecha_valida(int(coincide[3]), int(coincide[2]), int(coincide[1]), texto)
    if coincide := DIA_MES.fullmatch(limpio):
        dia, mes = int(coincide[1]), int(coincide[2])
        for anyo in (hoy.year, hoy.year + 1, hoy.year + 2):  # 29/02 puede tardar en existir
            try:
                proxima = date(anyo, mes, dia)
            except ValueError:
                continue
            if proxima >= hoy:
                return proxima
        raise NavajaError(f"«{texto}» no es una fecha que exista.")
    raise NavajaError(
        f"No entiendo la fecha «{texto}». Prueba con 2026-12-15, 15/12/2026, 15/12, hoy, mañana o +3."
    )


@dataclass
class Plazo:
    """Lo que queda para una fecha, con el estilo del tema y el texto para enseñarlo."""

    dias: int
    estilo: str
    texto: str


def plazo_de(fecha: date, hoy: date | None = None) -> Plazo:
    dias = (fecha - (hoy or date.today())).days
    if dias < 0:
        return Plazo(dias, "error", f"vencida hace {-dias} día{'s' if dias != -1 else ''}")
    if dias < DIAS_URGENTE:  # hoy y mañana
        return Plazo(dias, "error", "¡hoy!" if dias == 0 else "mañana")
    texto = f"en {dias} días"
    if dias < DIAS_PRONTO:
        return Plazo(dias, "aviso", texto)
    return Plazo(dias, "ok", texto)


def _pendientes(conexion: sqlite3.Connection) -> list[sqlite3.Row]:
    return conexion.execute(
        "SELECT * FROM entregas WHERE hecha = 0 ORDER BY fecha ASC, id ASC"
    ).fetchall()


def aviso_de_pendientes(hoy: date | None = None) -> str | None:
    """Una línea (con markup) para el saludo: lo que vence pronto, o None si no hay nada.

    Nunca falla: un aviso no debe impedir abrir navaja.
    """
    hoy = hoy or date.today()
    try:
        with closing(_conectar()) as conexion:
            filas = _pendientes(conexion)
    except (sqlite3.Error, OSError):
        return None
    pronto = []
    for fila in filas:
        try:
            plazo = plazo_de(date.fromisoformat(fila["fecha"]), hoy)
        except ValueError:
            continue
        if plazo.dias < DIAS_PRONTO:
            pronto.append((fila, plazo))
    if not pronto:
        return None
    fila, plazo = pronto[0]
    resto = f" (y {len(pronto) - 1} más)" if len(pronto) > 1 else ""
    return (
        f"[{plazo.estilo}]📌 {escape(fila['titulo'])}: {plazo.texto}[/]{resto} "
        "[pista]· navaja entregas listar[/]"
    )


def _mostrar(filas: list[sqlite3.Row], vacio: str) -> None:
    if not filas:
        console.print(f"[aviso]{vacio}[/]")
        return
    hoy = date.today()
    tabla = crear_tabla(["ID", "Qué", "Asignatura", "Fecha", "Queda"])
    for fila in filas:
        fecha = date.fromisoformat(fila["fecha"])
        if fila["hecha"]:
            queda = "[pista]hecha ✔[/]"
        else:
            plazo = plazo_de(fecha, hoy)
            queda = f"[{plazo.estilo}]{plazo.texto}[/]"
        tabla.add_row(
            str(fila["id"]),
            f"{escape(fila['titulo'])}\n[pista]{TIPOS.get(fila['tipo'], fila['tipo'])}[/]",
            escape(fila["asignatura"]),
            fecha.strftime("%d/%m/%Y"),
            queda,
        )
    console.print(tabla)


def _obtener(conexion: sqlite3.Connection, entrega_id: int) -> sqlite3.Row:
    fila = conexion.execute("SELECT * FROM entregas WHERE id = ?", (entrega_id,)).fetchone()
    if fila is None:
        error_console.print(
            f"[error]No hay ninguna entrega con el número {entrega_id}.[/] "
            "[pista]Los números salen en la columna ID de «entregas listar».[/]",
            soft_wrap=True,
        )
        raise typer.Exit(1)
    return fila


ID_ENTREGA = typer.Argument(..., help="Número de la entrega (la columna ID de «entregas listar»).")
SIMULAR = typer.Option(
    False, "--simular", help="Solo enseña lo que haría, sin guardar nada.", rich_help_panel=AJUSTE
)


def agregar(
    titulo: str = typer.Argument(..., help="Qué hay que entregar o qué examen es."),
    fecha: str = typer.Argument(
        ..., help="Cuándo: 2026-12-15, 15/12/2026, 15/12, hoy, mañana o +3 (en 3 días)."
    ),
    asignatura: str = typer.Option(
        "", "--asignatura", "-a", help="De qué asignatura es (programación, redes…).",
        rich_help_panel=AJUSTE,
    ),
    examen: bool = typer.Option(
        False, "--examen", help="Es un examen (si no, una entrega).", rich_help_panel=AJUSTE
    ),
    simular: bool = SIMULAR,
) -> None:
    """Apunta una entrega o un examen con su fecha."""
    try:
        dia = leer_fecha(fecha)
    except NavajaError as error:
        fallar(error)
    tipo = "examen" if examen else "entrega"
    plazo = plazo_de(dia)
    resumen = (
        f"{TIPOS[tipo].lower()} [bold]{escape(titulo)}[/] el {dia.strftime('%d/%m/%Y')} "
        f"([{plazo.estilo}]{plazo.texto}[/])"
    )
    if simular:
        console.print(f"[aviso]Simulado:[/] se apuntaría {resumen}. No se guardó nada.")
        return
    with closing(_conectar()) as conexion, conexion:
        cursor = conexion.execute(
            "INSERT INTO entregas (titulo, asignatura, tipo, fecha, creado) VALUES (?, ?, ?, ?, ?)",
            (
                titulo.strip(),
                asignatura.strip(),
                tipo,
                dia.isoformat(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        entrega_id = cursor.lastrowid
    console.print(f"[ok]✔ Apuntad{'o' if examen else 'a'}[/] ({entrega_id}): {resumen}")


def listar(
    todas: bool = typer.Option(
        False, "--todas", help="Enseña también las que ya están hechas.", rich_help_panel=AJUSTE
    ),
    asignatura: str | None = typer.Option(
        None, "--asignatura", "-a", help="Solo las de esta asignatura.", rich_help_panel=AJUSTE
    ),
) -> None:
    """Lista lo que tienes pendiente, lo más cercano primero, con cuenta atrás."""
    sql = "SELECT * FROM entregas"
    condiciones: list[str] = []
    parametros: list[str] = []
    if not todas:
        condiciones.append("hecha = 0")
    if asignatura:
        condiciones.append("LOWER(asignatura) = ?")
        parametros.append(asignatura.strip().lower())
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY hecha ASC, fecha ASC, id ASC"
    with closing(_conectar()) as conexion:
        filas = conexion.execute(sql, parametros).fetchall()
    _mostrar(filas, "No tienes nada pendiente. 🎉" if not todas else "Todavía no has apuntado nada.")


def hecha(entrega_id: int = ID_ENTREGA, simular: bool = SIMULAR) -> None:
    """Marca una entrega o examen como hecho."""
    with closing(_conectar()) as conexion:
        fila = _obtener(conexion, entrega_id)
        if fila["hecha"]:
            console.print(f"[aviso]«{escape(fila['titulo'])}» ya estaba hecha.[/]")
            return
        if simular:
            console.print(f"[aviso]Simulado:[/] se marcaría como hecha «{escape(fila['titulo'])}».")
            return
        with conexion:
            conexion.execute("UPDATE entregas SET hecha = 1 WHERE id = ?", (entrega_id,))
    console.print(f"[ok]✔ Hecha[/]: {escape(fila['titulo'])}")


def borrar(
    entrega_id: int = ID_ENTREGA,
    si: bool = typer.Option(False, "--si", "-s", help="No pide confirmación."),
    simular: bool = SIMULAR,
) -> None:
    """Borra una entrega o examen."""
    with closing(_conectar()) as conexion:
        fila = _obtener(conexion, entrega_id)
        if simular:
            console.print(f"[aviso]Simulado:[/] se borraría «{escape(fila['titulo'])}».")
            return
        if not confirmar(f"¿Borrar «{escape(fila['titulo'])}»?", saltar=si, por_defecto=False):
            console.print("[aviso]Cancelado.[/]")
            return
        with conexion:
            conexion.execute("DELETE FROM entregas WHERE id = ?", (entrega_id,))
    console.print(f"[ok]✔ Borrada[/] {escape(fila['titulo'])}.")


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Deberes y exámenes con fecha y cuenta atrás.",
        no_args_is_help=True,
    )
    sub.command("agregar", help="Apunta una entrega o un examen con su fecha.")(agregar)
    sub.command("listar", help="Lista lo pendiente, lo más cercano primero.")(listar)
    sub.command("hecha", help="Marca una entrega como hecha.")(hecha)
    sub.command("borrar", help="Borra una entrega o examen.")(borrar)
    app.add_typer(sub, name="entregas", rich_help_panel=ESTUDIO)
