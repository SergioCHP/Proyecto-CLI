"""navaja convierte: una sola orden para cambiar de formato. Mira la extensión de entrada y
la de salida y elige la herramienta:

- Imágenes entre sí (también las HEIC del iPhone) y varias imágenes a un solo PDF: Pillow.
- PDF a Word (.docx) con pdf2docx, y PDF a imágenes (una por página) con PyMuPDF.
- Word, Excel, PowerPoint y LibreOffice a PDF: LibreOffice o, en Windows, Word.
- Markdown y HTML a Word o PDF (y entre sí): Pandoc.
- CSV ↔ JSON (con Python) y Excel ↔ CSV (con openpyxl).
- Vídeo y audio (sacar el MP3, a GIF, a MP4, comprimir para WhatsApp…): FFmpeg.

Si falta una librería o un programa, dice cómo instalarlo. El original nunca se toca: el
nuevo va al lado con la extensión nueva y, si ya existe, «(1)». Si uno falla, los demás siguen.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import shutil
import subprocess
import tempfile
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape

from ..comun import DOCUMENTOS, console
from ..errores import NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..lotes import WINDOWS, FaltaAlgo, Tarea, al_lado, ejecutar, expandir, fallar, libreria, programa
from . import imagen

IMAGENES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif", ".avif", ".ico"}
IMAGENES_SALIDA = set(imagen.FORMATOS) - {".pdf"}
OFIMATICA = {".docx", ".doc", ".odt", ".rtf", ".xlsx", ".xls", ".ods", ".pptx", ".ppt", ".odp"}
TEXTOS = {".md", ".markdown", ".html", ".htm", ".txt"}
VIDEOS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv", ".3gp"}
AUDIOS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus", ".wma"}
SALIDA_MULTIMEDIA = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".mp4", ".webm", ".gif", ".mkv"}

SINONIMOS = {"jpeg": "jpg", "word": "docx", "excel": "xlsx", "texto": "txt", "markdown": "md", "imagen": "png", "audio": "mp3", "video": "mp4", "vídeo": "mp4"}


# ── Cada conversión ────────────────────────────────────────────────────────


def imagen_a_imagen(origen: Path, destino: Path, calidad: int) -> None:
    imagen.guardar(imagen.abrir(origen), destino, calidad)


def imagenes_a_pdf(origenes: list[Path], destino: Path) -> None:
    """Varias imágenes en un PDF, una por página, en el orden dado."""
    paginas = [imagen.con_fondo(imagen.abrir(o)) for o in origenes]
    paginas[0].save(destino, format="PDF", save_all=True, append_images=paginas[1:], resolution=150)


def pymupdf() -> Any:
    return libreria("pymupdf", "PyMuPDF", "documentos", "pasar un PDF a imágenes")


def pdf_a_imagenes(origen: Path, destinos: list[Path], dpi: int) -> None:
    documento = pymupdf().open(origen)
    try:
        for pagina, destino in zip(documento, destinos):
            pagina.get_pixmap(dpi=dpi).save(str(destino))
    finally:
        documento.close()


def paginas_de(origen: Path) -> int:
    documento = pymupdf().open(origen)
    try:
        return documento.page_count
    finally:
        documento.close()


def pdf2docx() -> Any:
    """pdf2docx sin su aviso de que «fitz» está anticuado (es cosa suya, no nuestra)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return libreria("pdf2docx", "pdf2docx", "documentos", "pasar un PDF a Word")


def pdf_a_docx(origen: Path, destino: Path) -> None:
    modulo = pdf2docx()
    logging.disable(logging.WARNING)  # pdf2docx escribe en inglés cada paso que da
    try:
        conversor = modulo.Converter(str(origen))
        try:
            conversor.convert(str(destino))
        finally:
            conversor.close()
    finally:
        logging.disable(logging.NOTSET)


def con_libreoffice(origen: Path, destino: Path) -> None:
    """LibreOffice sin ventana: escribe en una carpeta temporal y se mueve al nombre libre."""
    soffice = programa("soffice", "pasar documentos a PDF (o instala Word en Windows)", "libreoffice")
    formato = destino.suffix.lstrip(".")
    with tempfile.TemporaryDirectory(prefix="navaja-") as temporal:
        perfil = Path(temporal, "perfil").as_uri()  # un perfil propio: funciona aunque tengas LibreOffice abierto
        orden = [soffice, f"-env:UserInstallation={perfil}", "--headless", "--convert-to", formato, "--outdir", temporal, str(origen)]
        resultado = subprocess.run(orden, capture_output=True, text=True, timeout=300)
        hecho = Path(temporal, f"{origen.stem}.{formato}")
        if resultado.returncode != 0 or not hecho.is_file():
            raise NavajaError(f"LibreOffice no ha podido convertirlo. {resultado.stderr.strip()[:200]}")
        shutil.move(str(hecho), destino)


def con_word(origen: Path, destino: Path) -> None:
    modulo = libreria("docx2pdf", "docx2pdf", "documentos", "pasar Word a PDF con Word")
    modulo.convert(str(origen), str(destino))


def ofimatica_a_pdf(origen: Path, destino: Path) -> None:
    from ..lotes import buscar_programa

    if buscar_programa("soffice", "libreoffice"):
        con_libreoffice(origen, destino)
    elif WINDOWS and origen.suffix.lower() == ".docx":
        con_word(origen, destino)
    else:
        con_libreoffice(origen, destino)  # da el error con cómo instalarlo


def con_pandoc(origen: Path, destino: Path) -> None:
    pandoc = programa("pandoc", "pasar Markdown o HTML a Word o PDF")
    orden = [pandoc, str(origen), "-o", str(destino), "--standalone"]
    if destino.suffix.lower() == ".pdf":
        motor = next((m for m in ("xelatex", "pdflatex", "wkhtmltopdf", "weasyprint") if shutil.which(m)), None)
        if motor is None:
            raise FaltaAlgo("Para que Pandoc haga PDF hace falta un motor (MiKTeX o wkhtmltopdf). Mejor: conviértelo a docx y luego a pdf.")
        orden.append(f"--pdf-engine={motor}")
    resultado = subprocess.run(orden, capture_output=True, text=True, timeout=300)
    if resultado.returncode != 0:
        raise NavajaError(f"Pandoc no ha podido: {resultado.stderr.strip()[:200]}")


def leer_csv(origen: Path) -> list[dict[str, str]]:
    texto = origen.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    return list(csv.DictReader(io.StringIO(texto), dialect=dialecto))


def csv_a_json(origen: Path, destino: Path) -> None:
    destino.write_text(json.dumps(leer_csv(origen), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def json_a_csv(origen: Path, destino: Path) -> None:
    """Una lista de objetos → una fila por objeto; las columnas, todas las claves que salen."""
    datos = json.loads(origen.read_text(encoding="utf-8-sig"))
    if isinstance(datos, dict):
        listas = [v for v in datos.values() if isinstance(v, list)]
        datos = listas[0] if len(listas) == 1 else [datos]
    if not isinstance(datos, list) or not all(isinstance(f, dict) for f in datos):
        raise NavajaError("Para pasarlo a CSV, el JSON tiene que ser una lista de objetos ([{…}, {…}]).")
    columnas = list(dict.fromkeys(clave for fila in datos for clave in fila))
    with destino.open("w", encoding="utf-8-sig", newline="") as salida:  # -sig: Excel lee bien las tildes
        escritor = csv.DictWriter(salida, columnas, delimiter=";")
        escritor.writeheader()
        for fila in datos:
            escritor.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in fila.items()})


def openpyxl() -> Any:
    return libreria("openpyxl", "openpyxl", "documentos", "leer o escribir Excel")


def csv_a_xlsx(origen: Path, destino: Path) -> None:
    libro = openpyxl().Workbook()
    hoja = libro.active
    filas = leer_csv(origen)
    if filas:
        hoja.append([clave for clave in filas[0] if clave is not None])
        for fila in filas:
            valores: list[str | None] = []
            for clave, valor in fila.items():
                # una fila con más columnas que la cabecera: csv las junta en una lista con clave None
                valores += valor if clave is None else [valor]
            hoja.append([numero_o_texto(v) for v in valores])
    libro.save(destino)


NUMERO = re.compile(r"-?(\d+)(?:[.,](\d+))?", re.ASCII)


def numero_o_texto(valor: str | None) -> Any:
    """«12» → 12 y «7,5» → 7.5; lo demás se queda como texto, también lo que parece un número
    pero no se sabe seguro qué número es:

    - «08001» (código postal, teléfono): se perdería el cero.
    - Más de 15 cifras (una cuenta, un código largo): Excel las redondea.
    - «1.500» o «2,250»: en España es mil quinientos; en inglés, uno y medio. Con tres
      decimales justos no se adivina («0,125» sí es un número: nadie escribe miles con 0).
    - «inf», «nan», «1_000», «+5» o cifras que no son 0-9.
    """
    if valor is None:
        return None
    limpio = valor.strip()
    encaje = NUMERO.fullmatch(limpio)
    if not encaje:
        return valor
    entero, decimales = encaje.group(1), encaje.group(2) or ""
    if (len(entero) > 1 and entero.startswith("0")) or len(entero + decimales) > 15:
        return valor
    if len(decimales) == 3 and entero != "0":
        return valor
    return float(limpio.replace(",", ".")) if decimales else int(limpio)


def xlsx_a_csv(origen: Path, destino: Path) -> None:
    libro = openpyxl().load_workbook(origen, read_only=True, data_only=True)
    hoja = libro.active
    with destino.open("w", encoding="utf-8-sig", newline="") as salida:
        escritor = csv.writer(salida, delimiter=";")
        for fila in hoja.iter_rows(values_only=True):
            escritor.writerow(["" if v is None else v for v in fila])
    libro.close()


def con_ffmpeg(origen: Path, destino: Path, comprimir: bool) -> None:
    """Vídeo y audio. Al MP4 con H.264 (lo abre todo, también WhatsApp); --comprime lo deja
    en 720p con más compresión. A GIF, a 10 imágenes por segundo y 480 px de ancho."""
    ffmpeg = programa("ffmpeg", "convertir vídeo y audio")
    salida = destino.suffix.lower()
    orden = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(origen)]
    if salida in AUDIOS:
        orden += ["-vn"] + {".mp3": ["-c:a", "libmp3lame", "-q:a", "2"], ".ogg": ["-c:a", "libvorbis", "-q:a", "5"],
                            ".m4a": ["-c:a", "aac", "-b:a", "192k"]}.get(salida, [])
    elif salida == ".gif":
        orden += ["-vf", "fps=10,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", "-loop", "0"]
    elif salida in (".mp4", ".mkv"):
        crf = "28" if comprimir else "23"
        orden += ["-c:v", "libx264", "-preset", "veryfast", "-crf", crf, "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
        if comprimir:
            orden += ["-vf", "scale='min(1280,iw)':-2"]
    elif salida == ".webm":
        orden += ["-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "0", "-c:a", "libopus"]
    orden.append(str(destino))
    resultado = subprocess.run(orden, capture_output=True, text=True, timeout=None)
    if resultado.returncode != 0:
        raise NavajaError(f"FFmpeg no ha podido: {(resultado.stderr.strip().splitlines() or ['?'])[-1][:200]}")


# ── Elegir la conversión ───────────────────────────────────────────────────


def normalizar(formato: str) -> str:
    limpio = formato.strip().lower().lstrip(".*")
    return "." + SINONIMOS.get(limpio, limpio)


def conversion(entrada: str, salida: str) -> str | None:
    """Qué tipo de conversión es (o None si no se sabe hacer)."""
    if entrada == salida and entrada not in VIDEOS:
        return None  # un vídeo al mismo formato sí: se vuelve a comprimir (--comprime)
    if entrada in IMAGENES and salida in IMAGENES_SALIDA:
        return "imagen"
    if entrada in IMAGENES and salida == ".pdf":
        return "imagenes-pdf"
    if entrada == ".pdf" and salida in (".png", ".jpg"):
        return "pdf-imagenes"
    if entrada == ".pdf" and salida == ".docx":
        return "pdf-docx"
    if entrada in OFIMATICA and salida == ".pdf":
        return "ofimatica-pdf"
    if entrada in TEXTOS and salida in (".docx", ".pdf", ".html", ".md", ".odt") and salida not in (entrada, ".txt"):
        return "pandoc"
    if (entrada, salida) in ((".csv", ".json"), (".json", ".csv"), (".csv", ".xlsx"), (".xlsx", ".csv")):
        return f"{entrada[1:]}-{salida[1:]}"
    if entrada in VIDEOS | AUDIOS and salida in SALIDA_MULTIMEDIA and not (entrada in AUDIOS and salida in (".gif", ".mp4", ".webm", ".mkv")):
        return "ffmpeg"
    return None


QUE_SE_PUEDE = (
    "imágenes entre sí (jpg, png, webp, heic…) y a pdf; pdf a docx, png o jpg; Word, Excel y "
    "PowerPoint a pdf; md o html a docx, pdf o html; csv ↔ json; csv ↔ xlsx; vídeo a mp3, "
    "gif, mp4 o webm; audio entre mp3, wav, ogg, m4a y flac"
)


def separar_formato(partes: list[str]) -> tuple[list[str], str]:
    """«foto.heic otra.heic a jpg» → (["foto.heic", "otra.heic"], ".jpg")."""
    if len(partes) >= 3 and partes[-2].lower() in ("a", "en", "to"):
        return partes[:-2], normalizar(partes[-1])
    raise NavajaError("Escribe los archivos, «a» y el formato: navaja convierte trabajo.pdf a docx.")


def planificar(rutas: list[Path], salida: str, opciones: dict[str, Any]) -> list[Tarea]:
    reservados: set[str] = set()
    tareas: list[Tarea] = []
    imagenes_para_pdf = [r for r in rutas if conversion(r.suffix.lower(), salida) == "imagenes-pdf"]
    if imagenes_para_pdf and not opciones["separados"]:
        primera = imagenes_para_pdf[0]
        if len(imagenes_para_pdf) == 1:
            destino = al_lado(primera, "", ".pdf", reservados)
            etiqueta = ""
        else:  # todas en uno: se llama como la carpeta («fotos-pizarra.pdf»)
            carpeta = primera.resolve().parent
            destino = al_lado(carpeta / f"{carpeta.name or 'imagenes'}.pdf", "", ".pdf", reservados)
            etiqueta = f"{destino.name} ({len(imagenes_para_pdf)} páginas)"
        tareas.append(Tarea(primera, destino, lambda d=destino: imagenes_a_pdf(imagenes_para_pdf, d), etiqueta))
    for ruta in rutas:
        tipo = conversion(ruta.suffix.lower(), salida)
        if tipo is None:
            raise NavajaError(
                f"No sé pasar {ruta.suffix or 'un archivo sin extensión'} a {salida}. Se puede: {QUE_SE_PUEDE}."
            )
        if tipo == "imagenes-pdf" and not opciones["separados"]:
            continue
        if tipo == "pdf-imagenes":
            total = paginas_de(ruta)
            destinos = [al_lado(ruta, f"-p{n}", salida, reservados) for n in range(1, total + 1)]
            etiqueta = destinos[0].name if total == 1 else f"{destinos[0].name} … {destinos[-1].name}"
            tareas.append(Tarea(ruta, destinos[0], lambda r=ruta, d=destinos: pdf_a_imagenes(r, d, opciones["dpi"]), etiqueta))
            continue
        sufijo = ("-comprimido" if opciones["comprime"] else "-convertido") if ruta.suffix.lower() == salida else ""
        destino = al_lado(ruta, sufijo, salida, reservados)
        hacer: Callable[[], object] = {
            "imagen": lambda r=ruta, d=destino: imagen_a_imagen(r, d, opciones["calidad"]),
            "imagenes-pdf": lambda r=ruta, d=destino: imagenes_a_pdf([r], d),
            "pdf-docx": lambda r=ruta, d=destino: pdf_a_docx(r, d),
            "ofimatica-pdf": lambda r=ruta, d=destino: ofimatica_a_pdf(r, d),
            "pandoc": lambda r=ruta, d=destino: con_pandoc(r, d),
            "csv-json": lambda r=ruta, d=destino: csv_a_json(r, d),
            "json-csv": lambda r=ruta, d=destino: json_a_csv(r, d),
            "csv-xlsx": lambda r=ruta, d=destino: csv_a_xlsx(r, d),
            "xlsx-csv": lambda r=ruta, d=destino: xlsx_a_csv(r, d),
            "ffmpeg": lambda r=ruta, d=destino: con_ffmpeg(r, d, opciones["comprime"]),
        }[tipo]
        tareas.append(Tarea(ruta, destino, hacer))
    return tareas


def comprobar_herramientas(tareas: list[Tarea], salida: str) -> None:
    """Antes de preguntar nada: si falta lo que hace falta, se dice ya (y no a mitad)."""
    tipos = {conversion(t.origen.suffix.lower(), salida) for t in tareas}
    if tipos & {"imagen", "imagenes-pdf"}:
        imagen.pil()
    if "pdf-docx" in tipos:
        pdf2docx()
    if "ffmpeg" in tipos:
        programa("ffmpeg", "convertir vídeo y audio")
    if "pandoc" in tipos:
        programa("pandoc", "pasar Markdown o HTML a Word o PDF")
    if tipos & {"csv-xlsx", "xlsx-csv"}:
        openpyxl()
    if "ofimatica-pdf" in tipos:
        from ..lotes import buscar_programa

        docx_en_windows = WINDOWS and all(t.origen.suffix.lower() == ".docx" for t in tareas)
        if not buscar_programa("soffice", "libreoffice") and not docx_en_windows:
            programa("soffice", "pasar documentos a PDF", "libreoffice")


def convierte(
    partes: list[str] = typer.Argument(..., help="Los archivos, «a» y el formato: foto.heic a jpg (vale *.heic a jpg)."),
    calidad: int = typer.Option(90, "--calidad", min=10, max=95, help="Calidad de las imágenes JPG y WebP (10 a 95)."),
    dpi: int = typer.Option(150, "--dpi", min=36, max=600, help="Resolución de las páginas al pasar un PDF a imágenes."),
    comprime: bool = typer.Option(False, "--comprime", help="Vídeo más ligero (720p) para mandarlo por WhatsApp o correo."),
    separados: bool = typer.Option(False, "--separados", help="Varias imágenes a PDF: un PDF por imagen (si no, todas en uno)."),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Cambia de formato: imágenes, PDF ↔ Word, documentos a PDF, CSV, vídeo y audio."""
    try:
        archivos, salida = separar_formato(partes)
        rutas = expandir(archivos)
        tareas = planificar(rutas, salida, {"calidad": calidad, "dpi": dpi, "comprime": comprime, "separados": separados})
        comprobar_herramientas(tareas, salida)
    except NavajaError as error:
        fallar(error)
    hilos = 1 if conversion(rutas[0].suffix.lower(), salida) in ("ffmpeg", "ofimatica-pdf") else 4
    ejecutar(tareas, f"Convertir a {salida.lstrip('.')}", simular, si, hilos)
    if any(conversion(r.suffix.lower(), salida) == "pdf-docx" for r in rutas):
        console.print("[pista]Un PDF escaneado o con un diseño complicado no queda perfecto en Word: revísalo.[/]")


def registrar(app: typer.Typer) -> None:
    app.command(
        "convierte", help="Cambia de formato: imágenes, PDF ↔ Word, a PDF, CSV, vídeo y audio.",
        rich_help_panel=DOCUMENTOS,
    )(convierte)
