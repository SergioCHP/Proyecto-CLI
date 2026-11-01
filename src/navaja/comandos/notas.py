"""Notas y enlaces guardados con etiquetas en SQLite."""

from __future__ import annotations

import re
import sqlite3
import webbrowser
from collections import Counter
from contextlib import closing
from datetime import datetime

import typer
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from ..comun import (
    AJUSTE,
    como_se_escribe,
    confirmar,
    console,
    crear_tabla,
    directorio_datos,
    editar_texto,
    error_console,
)
from ..filtros import sin_tildes

PARECE_ENLACE = re.compile(r"^(https?://|www\.)\S+$", re.IGNORECASE)


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


def _fecha(iso: str) -> str:
    """«2026-11-01T16:09:33» → «2026-11-01 16:09»."""
    return iso.replace("T", " ")[:16]


def _mostrar(filas: list[sqlite3.Row], vacio: str = "Todavía no hay notas.") -> None:
    if not filas:
        console.print(f"[aviso]{vacio}[/]")
        return
    tabla = crear_tabla(["ID", "Tipo", "Título", "Etiquetas", "Cambiada"])
    for fila in filas:
        contenido = " ".join(fila["contenido"].split())
        if len(contenido) > 60:
            contenido = contenido[:57] + "…"
        titulo = escape(fila["titulo"])
        if contenido:
            titulo = f"{titulo}\n[pista]{escape(contenido)}[/]"
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


def _no_existe(nota_id: int) -> None:
    error_console.print(
        f"[error]No hay ninguna nota con el número {nota_id}.[/] "
        f"[pista]Los números salen en la columna ID de «{como_se_escribe('notas listar')}».[/]",
        soft_wrap=True,
    )
    raise typer.Exit(1)


ID_NOTA = typer.Argument(..., help="Número de la nota (la columna ID de «notas listar»).")


def agregar(
    titulo: str = typer.Argument(..., help="Título de la nota o del enlace."),
    contenido: str = typer.Argument(
        "",
        help="Texto de la nota o dirección del enlace (https://…); vacío = abrir el editor.",
        show_default=False,
    ),
    etiqueta: list[str] = typer.Option(
        [],
        "--etiqueta",
        "-e",
        help="Etiquetas, separadas por comas (clase, dam).",
        rich_help_panel=AJUSTE,
    ),
    texto: str | None = typer.Option(
        None, "--texto", "-t", help="Texto de la nota (como CONTENIDO).", hidden=True
    ),
    url: str | None = typer.Option(
        None, "--url", "-u", help="Dirección del enlace (como CONTENIDO).", hidden=True
    ),
) -> None:
    """Añade una nota o un enlace. Si el contenido empieza por https:// o www., es un enlace."""
    contenido = (url or texto or contenido or "").strip()
    if url or PARECE_ENLACE.match(contenido):
        tipo = "enlace"
        if contenido.lower().startswith("www."):
            contenido = "https://" + contenido
    else:
        tipo = "nota"
        if not contenido:
            console.print("[pista]Se abre el editor: escribe la nota, guarda y ciérralo.[/]")
            try:
                contenido = editar_texto()
            except RuntimeError as exc:
                error_console.print(f"[error]{escape(str(exc))}[/]")
                raise typer.Exit(1)
        if not contenido.strip():
            console.print("[aviso]La nota está vacía; no se guardó.[/]")
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
        f"[ok]Guardad{'o el' if tipo == 'enlace' else 'a la'}[/] {tipo} "
        f"[bold]{nota_id}[/]: {escape(titulo)}"
    )


def listar(
    etiqueta: str | None = typer.Option(
        None, "--etiqueta", "-e", help="Filtrar por etiqueta."
    ),
    limite: int = typer.Option(50, "--limite", "-n", min=1, help="Cuántas enseñar como mucho."),
) -> None:
    """Lista las notas y enlaces guardados, los últimos cambiados primero."""
    sql = "SELECT * FROM notas"
    parametros: list = []
    if etiqueta:
        sql += " WHERE (',' || etiquetas || ',') LIKE ?"
        parametros.append(f"%,{etiqueta.strip().lower().lstrip('#')},%")
    sql += " ORDER BY actualizado DESC, id DESC LIMIT ?"
    parametros.append(limite)

    with closing(_conectar()) as conexion:
        filas = conexion.execute(sql, parametros).fetchall()
    _mostrar(filas, f"No hay notas con la etiqueta «{etiqueta}»." if etiqueta else "Todavía no hay notas.")


def buscar(
    texto: str = typer.Argument(..., help="Qué buscar (sin mirar mayúsculas ni tildes)."),
    limite: int = typer.Option(50, "--limite", "-n", min=1, help="Cuántas enseñar como mucho."),
) -> None:
    """Busca en títulos, contenido y etiquetas, sin mirar mayúsculas ni tildes."""
    buscado = sin_tildes(texto).lower()
    with closing(_conectar()) as conexion:
        todas = conexion.execute(
            "SELECT * FROM notas ORDER BY actualizado DESC, id DESC"
        ).fetchall()
    filas = [
        fila
        for fila in todas
        if buscado in sin_tildes(f"{fila['titulo']} {fila['contenido']} {fila['etiquetas']}").lower()
    ]
    _mostrar(filas[:limite], f"Ninguna nota lleva «{texto}».")


def abrir(
    nota_id: int = ID_NOTA,
    editar: bool = typer.Option(
        False,
        "--editar",
        help="Abrirla en el editor para cambiarla.",
        rich_help_panel=AJUSTE,
    ),
) -> None:
    """Abre un enlace en el navegador o muestra una nota."""
    with closing(_conectar()) as conexion:
        fila = _obtener(conexion, nota_id)
        if fila is None:
            _no_existe(nota_id)

        if editar:
            try:
                nuevo = editar_texto(fila["contenido"])
            except RuntimeError as exc:
                error_console.print(f"[error]{escape(str(exc))}[/]")
                raise typer.Exit(1)
            ahora = datetime.now().isoformat(timespec="seconds")
            with conexion:
                conexion.execute(
                    "UPDATE notas SET contenido = ?, actualizado = ? WHERE id = ?",
                    (nuevo, ahora, nota_id),
                )
            console.print(f"[ok]Cambiada[/] la nota {nota_id}.")
            return

        if fila["tipo"] == "enlace":
            webbrowser.open(fila["contenido"])
            console.print(f"[ok]Abriendo[/] {escape(fila['contenido'])}")
            return

        etiquetas = escape(fila["etiquetas"].replace(",", ", ")) or "sin etiquetas"
        console.print(
            Panel(
                Text(fila["contenido"]) if fila["contenido"] else "[pista](vacía)[/]",
                title=f"[bold]{escape(fila['titulo'])}[/] · {etiquetas}",
                subtitle=f"nº {fila['id']} · {_fecha(fila['actualizado'])}",
                border_style="marco",
            )
        )


def borrar(
    nota_id: int = ID_NOTA,
    si: bool = typer.Option(
        False, "--si", "-s", help="No pide confirmación."
    ),
) -> None:
    """Borra una nota o enlace."""
    with closing(_conectar()) as conexion:
        fila = _obtener(conexion, nota_id)
        if fila is None:
            _no_existe(nota_id)
        if not confirmar(
            f"¿Borrar «{escape(fila['titulo'])}»?", saltar=si, por_defecto=False
        ):
            console.print("[aviso]Cancelado.[/]")
            return
        with conexion:
            conexion.execute("DELETE FROM notas WHERE id = ?", (nota_id,))
    console.print(f"[ok]Borrad{'o el enlace' if fila['tipo'] == 'enlace' else 'a la nota'}[/] {nota_id}.")


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
        console.print("[aviso]Todavía no hay etiquetas.[/]")
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
    sub.command("agregar", help="Añade una nota o un enlace (si empieza por https://).")(agregar)
    sub.command("listar", help="Lista notas y enlaces, los últimos primero.")(listar)
    sub.command("buscar", help="Busca por título, contenido o etiqueta.")(buscar)
    sub.command("abrir", help="Abre un enlace en el navegador o enseña (o cambia) una nota.")(abrir)
    sub.command("borrar", help="Borra una nota o enlace.")(borrar)
    sub.command("etiquetas", help="Lista las etiquetas existentes.")(etiquetas)
    app.add_typer(sub, name="notas")
