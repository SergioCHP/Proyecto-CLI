"""navaja hoy: tus commits de hoy (o desde el día que digas) en todos los repos de una carpeta.

Para saber por dónde ibas o para el diario de prácticas. Busca los repositorios git dentro
de la carpeta (sin entrar en ``.venv`` ni ``node_modules``) y, en cada uno, enseña los
commits del autor de ese repo (``git config user.email``) en todas las ramas.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import typer
from rich.markup import escape

from ..comun import AJUSTE, PROGRAMACION, bonita, console, tabla_ligera
from ..errores import NavajaError
from ..lotes import fallar

NO_ENTRAR = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
PROFUNDIDAD = 3
"""Cuántos niveles de carpetas se miran buscando repositorios."""

SEPARADOR = "\x1f"
"""Entre los campos de cada commit en la salida de git: no sale nunca en un mensaje."""

ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
DIA_MES_ANYO = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})")
DIA_MES = re.compile(r"(\d{1,2})[/-](\d{1,2})")
HACE = re.compile(r"-(\d{1,4})")


def leer_desde(texto: str, hoy: date | None = None) -> date:
    """«hoy», «ayer», «-3» (hace 3 días), «2026-11-10», «10/11/2026» o «10/11» (la última)."""
    hoy = hoy or date.today()
    limpio = texto.strip().lower()
    if limpio == "hoy":
        return hoy
    if limpio == "ayer":
        return hoy - timedelta(days=1)
    try:
        if coincide := HACE.fullmatch(limpio):
            return hoy - timedelta(days=int(coincide[1]))
        if coincide := ISO.fullmatch(limpio):
            return date(int(coincide[1]), int(coincide[2]), int(coincide[3]))
        if coincide := DIA_MES_ANYO.fullmatch(limpio):
            return date(int(coincide[3]), int(coincide[2]), int(coincide[1]))
        if coincide := DIA_MES.fullmatch(limpio):
            dia, mes = int(coincide[1]), int(coincide[2])
            for anyo in (hoy.year, hoy.year - 1, hoy.year - 2, hoy.year - 3, hoy.year - 4):
                try:
                    ultima = date(anyo, mes, dia)
                except ValueError:
                    continue
                if ultima <= hoy:
                    return ultima
    except ValueError:
        pass
    raise NavajaError(
        f"No entiendo la fecha «{texto}». Prueba con hoy, ayer, -3 (hace 3 días), 10/11 o 2026-11-10."
    )


def buscar_repos(carpeta: Path, profundidad: int = PROFUNDIDAD) -> list[Path]:
    """Los repositorios git en ``carpeta`` (ella misma incluida), por orden alfabético.

    No se entra dentro de un repositorio a buscar más: los submódulos no cuentan.
    """
    repos: list[Path] = []

    def mirar(actual: Path, nivel: int) -> None:
        if (actual / ".git").exists():
            repos.append(actual)
            return
        if nivel >= profundidad:
            return
        try:
            hijas = sorted(
                (h for h in actual.iterdir() if h.is_dir() and h.name not in NO_ENTRAR),
                key=lambda h: h.name.lower(),
            )
        except OSError:  # sin permiso
            return
        for hija in hijas:
            mirar(hija, nivel + 1)

    mirar(carpeta, 0)
    return repos


def git(carpeta: Path, *argumentos: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.quotepath=off", *argumentos],
        cwd=carpeta,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


@dataclass
class Commit:
    corto: str
    cuando: str
    mensaje: str


@dataclass
class Repo:
    ruta: Path
    autor: str | None
    commits: list[Commit] = field(default_factory=list)


def autor_de(repo: Path) -> str | None:
    """El email con el que haces commits en ese repo (o el nombre si no hay email)."""
    for clave in ("user.email", "user.name"):
        valor = git(repo, "config", clave).stdout.strip()
        if valor:
            return valor
    return None


def commits_de(repo: Path, desde: date, autor: str | None) -> list[Commit]:
    argumentos = [
        "log", "--all", "--no-merges",
        f"--since={desde.isoformat()} 00:00:00",
        "--date=format:%d/%m %H:%M",
        f"--format=%h{SEPARADOR}%ad{SEPARADOR}%s",
    ]
    if autor:
        argumentos += ["--fixed-strings", f"--author={autor}"]  # un «+» del email no es regex
    resultado = git(repo, *argumentos)
    if resultado.returncode != 0:  # un repo sin commits todavía
        return []
    commits = []
    for linea in resultado.stdout.splitlines():
        partes = linea.split(SEPARADOR)
        if len(partes) == 3:
            commits.append(Commit(*partes))
    return commits


def nombre_del_repo(repo: Path, carpeta: Path) -> str:
    if repo == carpeta:
        return repo.name or str(repo)
    return repo.relative_to(carpeta).as_posix()


def en_markdown(repos: list[Repo], carpeta: Path, desde: date) -> str:
    lineas = [f"## Commits desde el {desde.strftime('%d/%m/%Y')}", ""]
    for repo in repos:
        lineas.append(f"### {nombre_del_repo(repo.ruta, carpeta)}")
        lineas.extend(f"- {c.mensaje} (`{c.corto}`, {c.cuando})" for c in repo.commits)
        lineas.append("")
    return "\n".join(lineas).rstrip() + "\n"


def hoy(
    carpeta: Path = typer.Argument(
        Path("."), help="Dónde buscar los repositorios (por defecto, aquí).", show_default=False
    ),
    desde: str = typer.Option(
        "hoy", "--desde", "-d", help="Desde qué día: hoy, ayer, -3 (hace 3 días), 10/11 o 2026-11-10.",
        rich_help_panel=AJUSTE,
    ),
    todos: bool = typer.Option(
        False, "--todos", help="Los commits de todo el mundo, no solo los tuyos.", rich_help_panel=AJUSTE
    ),
    markdown: bool = typer.Option(
        False, "--markdown", "--md", help="Sin colores, en Markdown: para pegar en el diario.",
        rich_help_panel=AJUSTE,
    ),
) -> None:
    """Tus commits de hoy (o desde el día que digas) en todos los repos de una carpeta."""
    try:
        if shutil.which("git") is None:
            raise NavajaError(
                "No encuentro git. Instálalo con: winget install Git.Git (Windows) o sudo apt install git (Linux)."
            )
        dia = leer_desde(desde)
        base = carpeta.expanduser()
        if not base.is_dir():
            raise NavajaError(f"No existe la carpeta {bonita(base)}.")
        base = base.resolve()
        rutas = buscar_repos(base)
        if not rutas:
            raise NavajaError(
                f"No hay ningún repositorio git en {bonita(base)} (miro {PROFUNDIDAD} niveles hacia dentro)."
            )
        repos = []
        for ruta in rutas:
            autor = None if todos else autor_de(ruta)
            repos.append(Repo(ruta, autor, commits_de(ruta, dia, autor)))
    except (OSError, subprocess.TimeoutExpired) as error:
        fallar(NavajaError(f"git no respondió: {error}"))
    except NavajaError as error:
        fallar(error)

    con_commits = [r for r in repos if r.commits]
    cuando = "hoy" if dia == date.today() else f"desde el {dia.strftime('%d/%m/%Y')}"
    if markdown:
        if con_commits:
            typer.echo(en_markdown(con_commits, base, dia), nl=False)
        else:
            typer.echo(f"Sin commits {cuando}.")
        return

    if not con_commits:
        console.print(
            f"[aviso]Sin commits {cuando}[/] en {len(repos)} repositorio{'s' if len(repos) != 1 else ''}."
            + ("" if todos else " [pista]Con --todos salen también los de otras personas.[/]")
        )
        return
    for repo in con_commits:
        tabla = tabla_ligera()
        tabla.add_column("Commit", style="pista", no_wrap=True)
        tabla.add_column("Cuándo", style="pista", no_wrap=True)
        tabla.add_column("Mensaje")
        for commit in repo.commits:
            tabla.add_row(escape(commit.corto), escape(commit.cuando), escape(commit.mensaje))
        console.print(
            f"[titulo]{escape(nombre_del_repo(repo.ruta, base))}[/] "
            f"[pista]· {len(repo.commits)} commit{'s' if len(repo.commits) != 1 else ''}[/]"
        )
        console.print(tabla)
        console.print()
    total = sum(len(r.commits) for r in con_commits)
    sin = len(repos) - len(con_commits)
    console.print(
        f"[ok]{total} commit{'s' if total != 1 else ''} {cuando}[/] en {len(con_commits)} "
        f"repositorio{'s' if len(con_commits) != 1 else ''}"
        + (f" [pista](y {sin} sin nada)[/]" if sin else "")
        + "."
    )


def registrar(app: typer.Typer) -> None:
    app.command(
        "hoy", help="Tus commits de hoy en todos los repos de una carpeta (para el diario).",
        rich_help_panel=PROGRAMACION,
    )(hoy)
