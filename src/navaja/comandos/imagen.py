"""navaja imagen: reducir, comprimir, recortar, pasar a grises, quitar los datos ocultos
(la ubicación GPS) e iconos para una web. Con Pillow (``navaja[imagen]``; las HEIC del
iPhone, con pillow-heif).

Cada foto nueva va al lado de la original («foto-reducida.jpg») y la original no se toca.
Todas salen derechas (las del móvil vienen giradas por dentro) y sin los datos ocultos:
fecha, cámara y, sobre todo, dónde se hizo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.markup import escape

from ..comun import AJUSTE, DOCUMENTOS, console, recuadro, resumen, tamano_legible
from ..errores import NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..lotes import Tarea, al_lado, como_instalar, ejecutar, expandir, fallar, libreria

FORMATOS = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".bmp": "BMP",
    ".gif": "GIF", ".tif": "TIFF", ".tiff": "TIFF", ".ico": "ICO", ".pdf": "PDF",
}
"""Las extensiones a las que se puede guardar y el nombre que les da Pillow."""
DE_LECTURA = set(FORMATOS) | {".heic", ".heif", ".avif"}
SIN_TRANSPARENCIA = {"JPEG", "BMP", "PDF"}
COLORES = {
    "blanco": (255, 255, 255), "negro": (0, 0, 0), "gris": (128, 128, 128), "rojo": (220, 40, 40),
    "verde": (40, 160, 80), "azul": (40, 90, 200), "amarillo": (250, 210, 60),
}
TAMANOS_ICONO = [16, 32, 48, 64, 128, 256]


def pil() -> Any:
    """Pillow, con las HEIC (y AVIF) si está pillow-heif."""
    modulo = libreria("PIL.Image", "Pillow", "imagen", "trabajar con imágenes")
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return modulo


def abrir(ruta: Path) -> Any:
    """La imagen ya derecha (con la orientación de la cámara aplicada)."""
    imagen_ = pil()
    from PIL import ImageOps, UnidentifiedImageError

    if ruta.suffix.lower() in (".heic", ".heif"):
        try:
            import pillow_heif  # noqa: F401
        except ImportError:
            raise NavajaError(
                f"Para las fotos HEIC del iPhone hace falta pillow-heif: {como_instalar()}"
            ) from None
    try:
        foto = imagen_.open(ruta)
        foto.load()
    except UnidentifiedImageError:
        raise NavajaError(f"{ruta.name} no es una imagen (o es de un formato que no se puede leer).") from None
    return ImageOps.exif_transpose(foto)


def color(nombre: str) -> tuple[int, int, int]:
    """«blanco», «#ff8800» o «255,136,0»."""
    texto = nombre.strip().lower()
    if texto in COLORES:
        return COLORES[texto]
    try:
        if texto.startswith("#") and len(texto) == 7:
            return tuple(int(texto[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]
        partes = [int(p) for p in texto.split(",")]
        if len(partes) == 3 and all(0 <= p <= 255 for p in partes):
            return tuple(partes)  # type: ignore[return-value]
    except ValueError:
        pass
    raise NavajaError(f"«{nombre}» no es un color: {', '.join(COLORES)}, #ff8800 o 255,136,0.")


def con_fondo(foto: Any, fondo: tuple[int, int, int] = (255, 255, 255)) -> Any:
    """Lo transparente, de un color (un JPG no puede ser transparente)."""
    imagen_ = pil()
    if foto.mode in ("RGBA", "LA") or (foto.mode == "P" and "transparency" in foto.info):
        foto = foto.convert("RGBA")
        lienzo = imagen_.new("RGB", foto.size, fondo)
        lienzo.paste(foto, mask=foto.getchannel("A"))
        return lienzo
    return foto.convert("RGB") if foto.mode not in ("RGB", "L") else foto


def guardar(foto: Any, destino: Path, calidad: int = 90) -> None:
    """Guarda sin los datos ocultos (EXIF, GPS). JPG y PDF, sin transparencia."""
    formato = FORMATOS.get(destino.suffix.lower())
    if formato is None:
        raise NavajaError(f"No sé guardar imágenes en {destino.suffix}.")
    if formato in SIN_TRANSPARENCIA:
        foto = con_fondo(foto)
    opciones: dict[str, Any] = {}
    if formato in ("JPEG", "WEBP"):
        opciones = {"quality": calidad, "optimize": True}
    elif formato == "PNG":
        opciones = {"optimize": True}
    elif formato == "ICO":
        opciones = {"sizes": [(t, t) for t in TAMANOS_ICONO if t <= min(foto.size)] or [(16, 16)]}
    if formato == "GIF" and foto.mode not in ("P", "L"):
        foto = foto.convert("RGBA" if "A" in foto.mode else "RGB").convert("P", palette=1, colors=256)
    foto.info.pop("exif", None)
    foto.save(destino, format=formato, **opciones)


def proporcion(texto: str) -> float:
    try:
        ancho, alto = (float(p) for p in texto.replace("x", ":").split(":"))
        if ancho <= 0 or alto <= 0:
            raise ValueError
    except ValueError:
        raise NavajaError(f"«{texto}» no es una proporción: 16:9, 1:1, 4:3, 9:16…") from None
    return ancho / alto


def recortar_centro(foto: Any, relacion: float) -> Any:
    """El trozo del centro con esa proporción (ancho / alto), lo más grande posible."""
    ancho, alto = foto.size
    if ancho / alto > relacion:
        nuevo = round(alto * relacion)
        izquierda = (ancho - nuevo) // 2
        return foto.crop((izquierda, 0, izquierda + nuevo, alto))
    nuevo = round(ancho / relacion)
    arriba = (alto - nuevo) // 2
    return foto.crop((0, arriba, ancho, arriba + nuevo))


def reducir(foto: Any, lado: int) -> Any:
    """Que el lado más largo mida como mucho ``lado`` (nunca se agranda)."""
    foto = foto.copy()
    foto.thumbnail((lado, lado), pil().Resampling.LANCZOS)
    return foto


def gps_de(ruta: Path) -> bool:
    """¿Lleva la ubicación dentro?"""
    try:
        foto = pil().open(ruta)
        return bool(foto.getexif().get_ifd(0x8825))
    except Exception:
        return False


# ── Órdenes ────────────────────────────────────────────────────────────────


FOTOS = typer.Argument(..., help="Las fotos (vale *.jpg).")


def lote(fotos: list[str], sufijo: str, transformar, titulo: str, simular: bool, si: bool,
         extension: str | None = None, calidad: int = 90) -> None:
    try:
        rutas = expandir(fotos)
    except NavajaError as error:
        fallar(error)
    reservados: set[str] = set()
    tareas = []
    for ruta in rutas:
        destino = al_lado(ruta, sufijo, extension or (".jpg" if ruta.suffix.lower() in (".heic", ".heif", ".avif") else ruta.suffix), reservados)
        tareas.append(Tarea(ruta, destino, lambda r=ruta, d=destino: guardar(transformar(abrir(r)), d, calidad)))
    ejecutar(tareas, titulo, simular, si)


def info(foto: Path = typer.Argument(..., help="La foto.")) -> None:
    """Tamaño, formato, fecha, cámara y si lleva la ubicación GPS dentro."""
    try:
        ruta = expandir([str(foto)])[0]
        imagen_ = pil()
        abierta = imagen_.open(ruta)
    except NavajaError as error:
        fallar(error)
    except Exception:
        fallar(NavajaError(f"{foto} no es una imagen."))
    exif = abierta.getexif()
    filas = [
        ("Formato", abierta.format or ruta.suffix.lstrip(".").upper()),
        ("Tamaño", f"{abierta.width} × {abierta.height} px · {tamano_legible(ruta.stat().st_size)}"),
    ]
    camara = " ".join(str(exif.get(t, "")).strip() for t in (0x010F, 0x0110)).strip()
    if camara:
        filas.append(("Cámara", escape(camara)))
    fecha = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
    if fecha:
        filas.append(("Hecha", escape(str(fecha))))
    gps = bool(exif.get_ifd(0x8825))
    filas.append(("Ubicación", "[aviso]sí, lleva dónde se hizo[/] [pista](imagen limpia la quita)[/]" if gps else "no"))
    console.print(recuadro(ruta.name, resumen(filas)))


def reduce(
    fotos: list[str] = FOTOS,
    lado: int = typer.Option(1920, "--lado", "-l", min=16, help="Lo más que mide el lado largo, en píxeles.", rich_help_panel=AJUSTE),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Fotos más pequeñas (para mandarlas o subirlas), sin deformarlas."""
    lote(fotos, "-reducida", lambda f: reducir(f, lado), f"Reducir a {lado} px", simular, si)


def comprime(
    fotos: list[str] = FOTOS,
    calidad: int = typer.Option(75, "--calidad", "-c", min=10, max=95, help="De 10 a 95: menos es más pequeño y peor.", rich_help_panel=AJUSTE),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Fotos que ocupan menos (en JPG), casi sin que se note."""
    lote(fotos, "-comprimida", lambda f: f, f"Comprimir (calidad {calidad})", simular, si, ".jpg", calidad)


def limpia(fotos: list[str] = FOTOS, simular: bool = OPCION_SIMULAR, si: bool = OPCION_SI) -> None:
    """Quita los datos ocultos (ubicación GPS, cámara, fecha) antes de compartirlas."""
    lote(fotos, "-limpia", lambda f: f, "Quitar los datos ocultos", simular, si)


def recorta(
    fotos: list[str] = FOTOS,
    proporcion_: str = typer.Option("1:1", "--proporcion", "-p", help="16:9, 1:1, 4:3, 9:16 (vídeo de móvil)…", rich_help_panel=AJUSTE),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Recorta el centro con una proporción (cuadrada para el perfil, 16:9…)."""
    try:
        relacion = proporcion(proporcion_)
    except NavajaError as error:
        fallar(error)
    sufijo = "-" + proporcion_.replace(":", "x")
    lote(fotos, sufijo, lambda f: recortar_centro(f, relacion), f"Recortar a {proporcion_}", simular, si)


def grises(fotos: list[str] = FOTOS, simular: bool = OPCION_SIMULAR, si: bool = OPCION_SI) -> None:
    """En blanco y negro."""
    lote(fotos, "-grises", lambda f: f.convert("LA" if "A" in f.mode else "L"), "Pasar a grises", simular, si)


def icono(
    foto: Path = typer.Argument(..., help="El logo (mejor cuadrado y PNG)."),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Un favicon.ico con todos los tamaños de icono (16 a 256) para una web."""
    def cuadrado(f: Any) -> Any:
        return recortar_centro(f, 1.0) if f.width != f.height else f
    lote([str(foto)], "-icono", cuadrado, "Crear el icono", simular, si, ".ico")


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(help="Reducir, comprimir, recortar, grises, quitar el GPS e iconos.", no_args_is_help=True)
    sub.command("info", help="Tamaño, cámara, fecha y si lleva la ubicación.")(info)
    sub.command("reduce", help="Fotos más pequeñas sin deformarlas.")(reduce)
    sub.command("comprime", help="Que ocupen menos, casi sin que se note.")(comprime)
    sub.command("limpia", help="Les quita la ubicación GPS y los datos ocultos.")(limpia)
    sub.command("recorta", help="Recorta el centro: 1:1, 16:9, 9:16…")(recorta)
    sub.command("grises", help="En blanco y negro.")(grises)
    sub.command("icono", help="Un favicon.ico con todos los tamaños.")(icono)
    app.add_typer(sub, name="imagen", rich_help_panel=DOCUMENTOS)
