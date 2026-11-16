"""navaja baja: descargar vídeos (o solo el audio) de YouTube, Instagram, TikTok, X,
Facebook, Twitch y muchas webs más, con yt-dlp (``navaja[baja]``).

Antes de bajar nada enseña qué es (título, duración, tamaño) y pregunta [s/n]. Para
juntar vídeo y audio en buena calidad o sacar el MP3 hace falta FFmpeg; sin él, baja la
mejor versión que ya viene junta. Solo para vídeos tuyos, con permiso o para uso personal,
respetando las normas de cada web.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TransferSpeedColumn

from ..comun import AJUSTE, DOCUMENTOS, bonita, confirmar, console, cuantos, error_console, tabla_ligera, tamano_legible
from ..errores import NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..lotes import buscar_programa, fallar, libreria

ACTUALIZAR = 'uv tool install --editable ".[todo]" --reinstall-package yt-dlp'


def yt_dlp() -> Any:
    return libreria("yt_dlp", "yt-dlp", "baja", "descargar vídeos")


def carpeta_por_defecto() -> Path:
    """Descargas/Videos (o Downloads/Videos)."""
    casa = Path.home()
    for nombre in ("Downloads", "Descargas"):
        if (casa / nombre).is_dir():
            return casa / nombre / "Videos"
    return casa / "Videos"


def leer_enlaces(enlaces: list[str]) -> list[str]:
    """Los enlaces escritos. Un .txt que existe vale por todos los enlaces que lleva dentro
    (uno por línea; lo que empieza por # no cuenta)."""
    todos: list[str] = []
    for enlace in (e.strip() for e in enlaces):
        if not enlace:
            continue
        ruta = Path(enlace).expanduser()
        if enlace.lower().endswith(".txt") and ruta.is_file():
            try:
                lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
            except OSError as error:
                raise NavajaError(f"No se puede leer {enlace}: {error.strerror or error}") from None
            todos += [l.strip() for l in lineas if l.strip() and not l.strip().startswith("#")]
        else:
            todos.append(enlace)
    if not todos:
        raise NavajaError("Di el enlace del vídeo: navaja baja https://…")
    malos = [e for e in todos if not e.startswith(("http://", "https://", "www."))]
    if malos:
        raise NavajaError(f"«{malos[0]}» no es un enlace (tiene que empezar por https://) ni un .txt con enlaces.")
    return list(dict.fromkeys("https://" + e if e.startswith("www.") else e for e in todos))


def formato(audio: bool, calidad: int, con_ffmpeg: bool) -> dict[str, Any]:
    """Las opciones de yt-dlp para lo que se pide."""
    if audio:
        opciones: dict[str, Any] = {"format": "bestaudio/best"}
        if con_ffmpeg:
            opciones["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        return opciones
    tope = f"[height<={calidad}]" if calidad else ""
    if con_ffmpeg:
        return {"format": f"bestvideo{tope}+bestaudio/best{tope}/best", "merge_output_format": "mp4"}
    return {"format": f"best{tope}[vcodec!=none][acodec!=none]/best{tope}/best"}


@dataclass
class Video:
    enlace: str
    titulo: str
    duracion: str
    tamano: int | None
    web: str
    error: str = ""


def duracion_texto(segundos: float | None) -> str:
    if not segundos:
        return "—"
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}:{minutos:02}:{segundos:02}" if horas else f"{minutos}:{segundos:02}"


def mirar(modulo: Any, enlaces: list[str], opciones: dict[str, Any]) -> list[Video]:
    """Lo que hay en cada enlace, sin bajarlo. Un enlace malo no para los demás."""
    videos = []
    with modulo.YoutubeDL({**opciones, "quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        for enlace in enlaces:
            try:
                info = ydl.extract_info(enlace, download=False)
            except Exception as error:  # yt-dlp lanza DownloadError con el motivo
                videos.append(Video(enlace, "", "", None, "", motivo(error)))
                continue
            entradas = info.get("entries") if info.get("_type") == "playlist" else None
            if entradas is not None:
                lista = [e for e in entradas if e]
                videos.append(Video(enlace, f"{info.get('title') or 'Lista'} ({cuantos(len(lista), 'vídeo')})", "—", None, info.get("extractor_key", "")))
                continue
            tamano = info.get("filesize") or info.get("filesize_approx")
            if not tamano and info.get("requested_formats"):
                tamano = sum((f.get("filesize") or f.get("filesize_approx") or 0) for f in info["requested_formats"]) or None
            videos.append(Video(enlace, info.get("title") or enlace, duracion_texto(info.get("duration")), tamano, info.get("extractor_key", "")))
    return videos


def motivo(error: Exception) -> str:
    texto = str(error).replace("ERROR: ", "").strip()
    if "Sign in" in texto or "login" in texto.lower() or "cookies" in texto.lower():
        return "pide iniciar sesión (prueba con --cookies chrome)."
    if "Unsupported URL" in texto:
        return "esa web no está entre las que se pueden bajar."
    if "Private" in texto or "unavailable" in texto.lower():
        return "el vídeo es privado o ya no está."
    return (texto.splitlines() or ["no se puede"])[0][:160] + f" (si pasa con todos, actualiza yt-dlp: {ACTUALIZAR})"


def baja(
    enlaces: list[str] = typer.Argument(..., help="El enlace del vídeo (o varios, o un .txt con uno por línea)."),
    audio: bool = typer.Option(False, "--audio", "-a", help="Solo el audio, en MP3 (con FFmpeg).", rich_help_panel=AJUSTE),
    calidad: int = typer.Option(1080, "--calidad", "-c", min=0, help="Altura máxima: 360, 720, 1080… (0 = la mejor).", rich_help_panel=AJUSTE),
    subtitulos: str = typer.Option("", "--subtitulos", help="Bajar también los subtítulos en ese idioma (es, en…).", show_default=False),
    destino: Path = typer.Option(None, "--destino", "-d", help="Dónde dejarlos (por defecto, Descargas/Videos).", show_default=False),
    cookies: str = typer.Option("", "--cookies", help="Usar la sesión de tu navegador (chrome, edge, firefox) si la web la pide.", show_default=False),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Descarga vídeos (o el audio) de YouTube, Instagram, TikTok… con su enlace."""
    try:
        modulo = yt_dlp()
        lista_enlaces = leer_enlaces(enlaces)
    except NavajaError as error:
        fallar(error)
    con_ffmpeg = buscar_programa("ffmpeg") is not None
    carpeta = (destino or carpeta_por_defecto()).expanduser()
    opciones = formato(audio, calidad, con_ffmpeg)
    if cookies:
        opciones["cookiesfrombrowser"] = (cookies.lower(),)
    with console.status("[pista]Mirando los enlaces…[/]", spinner="dots"):
        videos = mirar(modulo, lista_enlaces, opciones)
    tabla = tabla_ligera()
    for columna in ("", "Título", "Duración", "Tamaño", "Web"):
        tabla.add_column(columna, no_wrap=columna not in ("Título",))
    for video in videos:
        if video.error:
            tabla.add_row("[error]✘[/]", f"{escape(video.enlace)}\n[error]{escape(video.error)}[/]", "", "", "")
        else:
            tabla.add_row("[ok]✔[/]", escape(video.titulo), video.duracion, tamano_legible(video.tamano) if video.tamano else "—", escape(video.web))
    console.print(tabla)
    buenos = [v for v in videos if not v.error]
    que = "el audio (MP3)" if audio and con_ffmpeg else "el audio" if audio else f"el vídeo (hasta {calidad}p)" if calidad else "el vídeo"
    console.print(f"[pista]Se baja {que} en {escape(bonita(carpeta))}.[/]", soft_wrap=True)
    if not con_ffmpeg:
        console.print("[aviso]Sin FFmpeg: se baja la versión que ya viene junta (puede ser peor) y el audio sin pasar a MP3. navaja doctor dice cómo instalarlo.[/]", soft_wrap=True)
    if not buenos:
        raise typer.Exit(1)
    if simular:
        console.print("[pista]Simulación: no se ha bajado nada.[/]")
        return
    if not confirmar(f"¿Bajo {cuantos(len(buenos), 'vídeo')}?", si):
        console.print("[pista]No se ha bajado nada.[/]")
        return
    carpeta.mkdir(parents=True, exist_ok=True)
    fallos = descargar(modulo, [v.enlace for v in buenos], carpeta, opciones, subtitulos)
    hechos = len(buenos) - len(fallos)
    if hechos:
        console.print(f"[ok]✔ {cuantos(hechos, 'descarga')} en {escape(bonita(carpeta))}[/]", soft_wrap=True)
    for enlace, error in fallos:
        error_console.print(f"[error]✘ {escape(enlace)}: {escape(error)}[/]", soft_wrap=True)
    if fallos or len(buenos) < len(videos):
        raise typer.Exit(1)


def descargar(modulo: Any, enlaces: list[str], carpeta: Path, opciones: dict[str, Any], subtitulos: str) -> list[tuple[str, str]]:
    """Baja cada enlace con una barra de progreso. Lo que ya está bajado no se repite."""
    fallos = []
    progreso = Progress(
        TextColumn("[pista]{task.description}[/]"), BarColumn(style="borde", complete_style="acento"),
        DownloadColumn(), TransferSpeedColumn(), console=console, transient=True, disable=not console.is_terminal,
    )

    def avance(estado: dict[str, Any]) -> None:
        if estado.get("status") == "downloading":
            total = estado.get("total_bytes") or estado.get("total_bytes_estimate")
            nombre = Path(estado.get("filename", "")).name[:40]
            progreso.update(tarea, description=escape(nombre), completed=estado.get("downloaded_bytes", 0), total=total)

    ajustes = {
        **opciones,
        "outtmpl": str(carpeta / "%(title).150B [%(id)s].%(ext)s"),
        "windowsfilenames": True,
        "nooverwrites": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [avance],
    }
    if subtitulos:
        ajustes.update({"writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": [subtitulos]})
    with progreso:
        tarea = progreso.add_task("", total=None)
        with modulo.YoutubeDL(ajustes) as ydl:
            for enlace in enlaces:
                try:
                    ydl.download([enlace])
                except Exception as error:
                    fallos.append((enlace, motivo(error)))
    return fallos


def registrar(app: typer.Typer) -> None:
    app.command("baja", help="Descarga vídeos o el audio de YouTube, Instagram, TikTok…", rich_help_panel=DOCUMENTOS)(baja)
