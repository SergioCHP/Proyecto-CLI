"""Notas y enlaces guardados con etiquetas en SQLite."""

from __future__ import annotations

import sqlite3
import webbrowser
from collections import Counter
from contextlib import closing
from datetime import datetime
from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from ..comun import (
    confirmar,
    console,
    crear_tabla,
    directorio_datos,
    editar_texto,
    error_console,
)


def _conectar() -> sqlite3.Connection:
    conexion = sqlite3.connect(directorio_datos() / "notas.db")
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL DEFAULT 'nota',
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL DEFAULT '',
            etiquetas TEXT NOT NULL DEFAULT '',
            creado TEXT NOT NULL,
            actualizado TEXT NOT NULL
        )
        """
    )
    return conexion


def _normalizar_etiquetas(etiquetas: list[str]) -> list[str]:
    resultado: list[str] = []
    for etiqueta in etiquetas:
        for parte in etiqueta.split(","):
            limpia = parte.strip().lower().lstrip("#")
            if limpia and limpia not in resultado:
                resultado.append(limpia)
    return resultado


def _mostrar(filas: list[sqlite3.Row]) -> None:
    if not filas:
        console.print("[yellow]No hay notas que mostrar.[/]")
        return
    tabla = crear_tabla(["ID", "Tipo", "Título", "Etiquetas", "Actualizado"])
    for fila in filas:
        contenido = " ".join(fila["contenido"].split())
        if len(contenido) > 60:
            contenido = contenido[:57] + "…"
        titulo = escape(fila["titulo"])
        if contenido and fila["tipo"] == "nota":
            titulo = f"{titulo}\n[dim]{escape(contenido)}[/]"
        tabla.add_row(
            str(fila["id"]),
            fila["tipo"],
            titulo,
            escape(fila["etiquetas"].replace(",", ", ")),
            fila["actualizado"][:10],
        )
    console.print(tabla)


def _obtener(conexion: sqlite3.Connection, nota_id: int) -> sqlite3.Row | None:
    return conexion.execute("SELECT * FROM notas WHERE id = ?", (nota_id,)).fetchone()


def agregar(
    titulo: str = typer.Argument(..., help="Título de la nota o enlace."),
    texto: str | None = typer.Option(
        None, "--texto", "-t", help="Contenido de la nota. Si se omite, abre el editor."
    ),
    url: str | None = typer.Option(
        None, "--url", "-u", help="URL del enlace."
    ),
    etiqueta: list[str] = typer.Option(
        [], "--etiqueta", "-e", help="Etiqueta (se puede repetir)."
    ),
) -> None:
    """Añade una nota o un enlace."""
    if url:
        tipo = "enlace"
        contenido = url
    else:
        tipo = "nota"
        if texto is not None:
            contenido = texto
        else:
            try:
                contenido = editar_texto()
            except RuntimeError as exc:
                error_console.print(f"[red]{escape(str(exc))}[/]")
                raise typer.Exit(1)
        if not contenido.strip():
            console.print("[yellow]La nota está vacía; no se guardó.[/]")
            raise typer.Exit(1)

    etiquetas = _normalizar_etiquetas(etiqueta)
    ahora = datetime.now().isoformat(timespec="seconds")
    with closing(_conectar()) as conexion, conexion:
        cursor = conexion.execute(
            """
            INSERT INTO notas (tipo, titulo, contenido, etiquetas, creado, actualizado)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tipo, titulo, contenido, ",".join(etiquetas), ahora, ahora),
        )
        nota_id = cursor.lastrowid

    console.print(
        f"[green]Guardad{'o' if tipo == 'enlace' else 'a'}[/] "
        f"{tipo} [bold]{nota_id}[/]: {escape(titulo)}"
    )


def listar(
    etiqueta: str | None = typer.Option(
        None, "--etiqueta", "-e", help="Filtrar por etiqueta."
    ),
    limite: int = typer.Option(
        50, "--limite", "-n", help="Máximo de notas a mostrar.", show_default=True
    ),
) -> None:
    """Lista las notas y enlaces guardados."""
    sql = "SELECT * FROM notas"
    parametros: list = []
    if etiqueta:
        sql += " WHERE (',' || etiquetas || ',') LIKE ?"
        parametros.append(f"%,{etiqueta.strip().lower().lstrip('#')},%")
    sql += " ORDER BY actualizado DESC, id DESC LIMIT ?"
    parametros.append(limite)

    with closing(_conectar()) as conexion:
        filas = conexion.execute(sql, parametros).fetchall()
    _mostrar(filas)


def buscar(
    texto: str = typer.Argument(..., help="Texto a buscar."),
    limite: int = typer.Option(
        50, "--limite", "-n", help="Máximo de resultados.", show_default=True
    ),
) -> None:
    """Busca en títulos, contenido y etiquetas."""
    patron = f"%{texto}%"
    with closing(_conectar()) as conexion:
        filas = conexion.execute(
            """
            SELECT * FROM notas
            WHERE titulo LIKE ? OR contenido LIKE ? OR etiquetas LIKE ?
            ORDER BY actualizado DESC, id DESC LIMIT ?
            """,
            (patron, patron, patron, limite),
        ).fetchall()
    _mostrar(filas)


def abrir(
    nota_id: int = typer.Argument(..., help="ID de la nota o enlace."),
    editar: bool = typer.Option(
        False, "--editar", help="Abrir el contenido en el editor y guardarlo."
    ),
) -> None:
    """Abre un enlace en el navegador o muestra una nota."""
    with closing(_conectar()) as conexion:
        fila = _obtener(conexion, nota_id)
        if fila is None:
            error_console.print(f"[red]No existe la nota {nota_id}.[/]")
            raise typer.Exit(1)

        if editar:
            try:
                nuevo = editar_texto(fila["contenido"])
            except RuntimeError as exc:
                error_console.print(f"[red]{escape(str(exc))}[/]")
                raise typer.Exit(1)
            ahora = datetime.now().isoformat(timespec="seconds")
            with conexion:
                conexion.execute(
                    "UPDATE notas SET contenido = ?, actualizado = ? WHERE id = ?",
                    (nuevo, ahora, nota_id),
                )
            console.print(f"[green]Actualizada[/] la nota {nota_id}.")
            return

        if fila["tipo"] == "enlace":
            webbrowser.open(fila["contenido"])
            console.print(f"[green]Abriendo[/] {escape(fila['contenido'])}")
            return

        etiquetas = escape(fila["etiquetas"].replace(",", ", ")) or "sin etiquetas"
        console.print(
            Panel(
                Text(fila["contenido"]) if fila["contenido"] else "[dim](vacía)[/]",
                title=f"[bold]{escape(fila['titulo'])}[/] · {etiquetas}",
                subtitle=f"id {fila['id']} · {fila['actualizado']}",
                border_style="cyan",
            )
        )


def borrar(
    nota_id: int = typer.Argument(..., help="ID de la nota o enlace."),
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación."
    ),
) -> None:
    """Borra una nota o enlace."""
    with closing(_conectar()) as conexion:
        fila = _obtener(conexion, nota_id)
        if fila is None:
            error_console.print(f"[red]No existe la nota {nota_id}.[/]")
            raise typer.Exit(1)
        if not confirmar(
            f"¿Borrar «{escape(fila['titulo'])}»?", saltar=si, por_defecto=False
        ):
            console.print("[yellow]Cancelado.[/]")
            return
        with conexion:
            conexion.execute("DELETE FROM notas WHERE id = ?", (nota_id,))
    console.print(f"[green]Borrada[/] la nota {nota_id}.")


def etiquetas() -> None:
    """Muestra todas las etiquetas y cuántas notas tienen cada una."""
    with closing(_conectar()) as conexion:
        filas = conexion.execute("SELECT etiquetas FROM notas").fetchall()

    conteo: Counter[str] = Counter()
    for fila in filas:
        for etiqueta in fila["etiquetas"].split(","):
            if etiqueta:
                conteo[etiqueta] += 1

    if not conteo:
        console.print("[yellow]Todavía no hay etiquetas.[/]")
        return

    tabla = crear_tabla(["Etiqueta", "Notas"])
    for etiqueta, cantidad in conteo.most_common():
        tabla.add_row(escape(etiqueta), str(cantidad))
    console.print(tabla)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Guarda notas y enlaces con etiquetas.",
        no_args_is_help=True,
    )
    sub.command("agregar", help="Añade una nota o enlace.")(agregar)
    sub.command("listar", help="Lista notas y enlaces.")(listar)
    sub.command("buscar", help="Busca por título, contenido o etiqueta.")(buscar)
    sub.command("abrir", help="Abre un enlace o muestra/edita una nota.")(abrir)
    sub.command("borrar", help="Borra una nota o enlace.")(borrar)
    sub.command("etiquetas", help="Lista las etiquetas existentes.")(etiquetas)
    app.add_typer(sub, name="notas")
