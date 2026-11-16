"""navaja pdf: unir, separar, sacar, quitar y girar páginas, comprimir y poner o quitar
contraseña. Con pypdf (``navaja[pdf]``).

El original nunca se toca: cada orden crea un PDF nuevo al lado («apuntes-p1-3.pdf»,
«apuntes-con-clave.pdf»…) y, si ya existe, «(1)».
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape

from ..comun import AJUSTE, DOCUMENTOS, console, cuantos, recuadro, resumen, tamano_legible
from ..errores import NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..lotes import Tarea, al_lado, ejecutar, expandir, fallar, libreria, pedir_secreto


def pypdf() -> Any:
    return libreria("pypdf", "pypdf", "pdf", "trabajar con PDF")


def leer_paginas(texto: str, total: int) -> list[int]:
    """«1-3,7,10-» con 12 páginas → [0, 1, 2, 6, 9, 10, 11] (empezando en 0, sin repetir).

    También «-3» (de la 1 a la 3) y «ultima». ``NavajaError`` si alguna no existe.
    """
    paginas: list[int] = []
    for parte in texto.replace(" ", "").lower().split(","):
        if not parte:
            continue
        parte = parte.replace("ultima", str(total)).replace("última", str(total))
        encaje = re.fullmatch(r"(\d*)-(\d*)|(\d+)", parte)
        if not encaje:
            raise NavajaError(f"«{parte}» no son páginas. Escríbelas como 1-3,7 o 10- (de la 10 al final).")
        if encaje.group(3):
            desde = hasta = int(encaje.group(3))
        else:
            desde = int(encaje.group(1) or 1)
            hasta = int(encaje.group(2) or total)
        if desde < 1 or hasta > total or desde > hasta:
            raise NavajaError(f"Las páginas {parte} no existen: el PDF tiene {cuantos(total, 'página')}.")
        for numero in range(desde, hasta + 1):
            if numero - 1 not in paginas:
                paginas.append(numero - 1)
    if not paginas:
        raise NavajaError("Di qué páginas: 1-3,7 o 10-.")
    return paginas


def abrir(ruta: Path, clave: str = "") -> Any:
    """El lector del PDF. Si tiene contraseña, hace falta ``clave``."""
    modulo = pypdf()
    try:
        lector = modulo.PdfReader(str(ruta))
    except Exception:
        raise NavajaError(f"{ruta.name} está dañado o no es un PDF.") from None
    if lector.is_encrypted:
        if not clave or not lector.decrypt(clave):
            raise NavajaError(f"{ruta.name} tiene contraseña" + (": no es esa." if clave else ": usa pdf desprotege."))
    return lector


def escribir(paginas: list[Any], destino: Path, comprimir: bool = False, clave: str = "") -> None:
    modulo = pypdf()
    escritor = modulo.PdfWriter()
    for pagina in paginas:
        escritor.add_page(pagina)
    if comprimir:
        for pagina in escritor.pages:
            pagina.compress_content_streams()
        # los nombres de las opciones cambiaron en pypdf 7 (antes: remove_identicals, remove_orphans)
        parametros = inspect.signature(escritor.compress_identical_objects).parameters
        if "remove_duplicates" in parametros:
            escritor.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
        else:
            escritor.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    if clave:
        escritor.encrypt(clave, algorithm="AES-256")
    with destino.open("wb") as salida:
        escritor.write(salida)


def nombre_paginas(paginas: list[int]) -> str:
    """[0, 1, 2, 6] → «p1-3,7» para el nombre del archivo."""
    tramos: list[str] = []
    inicio = anterior = paginas[0]
    for numero in paginas[1:] + [None]:
        if numero is not None and numero == anterior + 1:
            anterior = numero
            continue
        tramos.append(f"{inicio + 1}" if inicio == anterior else f"{inicio + 1}-{anterior + 1}")
        if numero is not None:
            inicio = anterior = numero
    texto = ",".join(tramos)
    return "p" + (texto if len(texto) <= 30 else f"{paginas[0] + 1}-{paginas[-1] + 1}")


def uno(archivo: Path) -> Path:
    try:
        rutas = expandir([str(archivo)])
    except NavajaError as error:
        fallar(error)
    if rutas[0].suffix.lower() != ".pdf":
        fallar(NavajaError(f"{rutas[0].name} no es un PDF."))
    return rutas[0]


ARCHIVO = typer.Argument(..., help="El PDF.")
PAGINAS = typer.Argument(..., help="Qué páginas: 1-3,7 o 10- (de la 10 al final).")

# ── Órdenes ────────────────────────────────────────────────────────────────


def info(archivo: Path = ARCHIVO) -> None:
    """Páginas, tamaño, si tiene contraseña y los datos que lleva dentro."""
    ruta = uno(archivo)
    modulo = pypdf()
    try:
        lector = modulo.PdfReader(str(ruta))
    except Exception:
        fallar(NavajaError(f"{ruta.name} está dañado o no es un PDF."))
    filas = [("Tamaño", tamano_legible(ruta.stat().st_size))]
    if lector.is_encrypted:
        filas.append(("Contraseña", "[aviso]sí[/] [pista](pdf desprotege para quitarla)[/]"))
    else:
        filas.append(("Páginas", str(len(lector.pages))))
        datos = lector.metadata or {}
        for clave, etiqueta in (("/Title", "Título"), ("/Author", "Autor"), ("/Producer", "Hecho con")):
            if datos.get(clave):
                filas.append((etiqueta, escape(str(datos[clave]))))
        filas.append(("Contraseña", "no"))
    console.print(recuadro(ruta.name, resumen(filas)))


def une(
    archivos: list[str] = typer.Argument(..., help="Los PDF en orden (vale *.pdf)."),
    nombre: str = typer.Option("", "--nombre", "-n", help="Cómo se llama el nuevo (por defecto, el del primero + «-unido»).", show_default=False),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Junta varios PDF en uno, en el orden en que los escribes."""
    try:
        rutas = expandir(archivos)
    except NavajaError as error:
        fallar(error)
    if len(rutas) < 2:
        fallar(NavajaError("Para unir hacen falta al menos dos PDF."))
    primero = rutas[0]
    destino = al_lado(primero.with_name(f"{nombre}.pdf"), "") if nombre else al_lado(primero, "-unido", ".pdf")

    def hacer() -> None:
        paginas = []
        for ruta in rutas:
            paginas += list(abrir(ruta).pages)
        escribir(paginas, destino)

    console.print(f"[pista]En este orden: {escape(', '.join(r.name for r in rutas))}[/]", soft_wrap=True)
    ejecutar([Tarea(primero, destino, hacer)], f"Unir {cuantos(len(rutas), 'PDF', 'PDF')}", simular, si)


def saca(archivo: Path = ARCHIVO, paginas: str = PAGINAS, simular: bool = OPCION_SIMULAR, si: bool = OPCION_SI) -> None:
    """Un PDF nuevo solo con esas páginas (el original se queda igual)."""
    ruta = uno(archivo)
    try:
        lector = abrir(ruta)
        elegidas = leer_paginas(paginas, len(lector.pages))
    except NavajaError as error:
        fallar(error)
    destino = al_lado(ruta, f"-{nombre_paginas(elegidas)}")
    ejecutar([Tarea(ruta, destino, lambda: escribir([lector.pages[i] for i in elegidas], destino))],
             f"Sacar {cuantos(len(elegidas), 'página')}", simular, si)


def quita(archivo: Path = ARCHIVO, paginas: str = PAGINAS, simular: bool = OPCION_SIMULAR, si: bool = OPCION_SI) -> None:
    """Un PDF nuevo sin esas páginas (el original se queda igual)."""
    ruta = uno(archivo)
    try:
        lector = abrir(ruta)
        fuera = set(leer_paginas(paginas, len(lector.pages)))
    except NavajaError as error:
        fallar(error)
    quedan = [i for i in range(len(lector.pages)) if i not in fuera]
    if not quedan:
        fallar(NavajaError("No quedaría ninguna página."))
    destino = al_lado(ruta, f"-sin-{nombre_paginas(sorted(fuera))}")
    ejecutar([Tarea(ruta, destino, lambda: escribir([lector.pages[i] for i in quedan], destino))],
             f"Quitar {cuantos(len(fuera), 'página')}", simular, si)


def separa(
    archivo: Path = ARCHIVO,
    paginas: str = typer.Argument("", help="Por dónde cortar: 1-3,4-8 (un PDF por tramo). Vacío: uno por página.", show_default=False),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Parte un PDF: uno por página, o uno por cada tramo (1-3,4-8,9-)."""
    ruta = uno(archivo)
    try:
        lector = abrir(ruta)
        total = len(lector.pages)
        tramos = [leer_paginas(t, total) for t in paginas.split(",")] if paginas.strip() else [[i] for i in range(total)]
    except NavajaError as error:
        fallar(error)
    reservados: set[str] = set()
    tareas = []
    for tramo in tramos:
        destino = al_lado(ruta, f"-{nombre_paginas(tramo)}", reservados=reservados)
        tareas.append(Tarea(ruta, destino, lambda t=tramo, d=destino: escribir([lector.pages[i] for i in t], d)))
    ejecutar(tareas, f"Separar en {cuantos(len(tareas), 'PDF', 'PDF')}", simular, si, hilos=1)


def gira(
    archivo: Path = ARCHIVO,
    grados: int = typer.Option(90, "--grados", "-g", help="90 (a la derecha), 180 o 270 (a la izquierda).", rich_help_panel=AJUSTE),
    paginas: str = typer.Option("", "--paginas", "-p", help="Solo estas (1-3,7); por defecto, todas.", rich_help_panel=AJUSTE, show_default=False),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
) -> None:
    """Gira páginas (las escaneadas del revés, las apaisadas…)."""
    if grados % 90 or grados % 360 == 0:
        fallar(NavajaError("Los grados tienen que ser 90, 180 o 270."))
    ruta = uno(archivo)
    try:
        lector = abrir(ruta)
        elegidas = set(leer_paginas(paginas, len(lector.pages))) if paginas.strip() else set(range(len(lector.pages)))
    except NavajaError as error:
        fallar(error)
    destino = al_lado(ruta, "-girado")

    def hacer() -> None:
        hojas = []
        for numero, pagina in enumerate(lector.pages):
            if numero in elegidas:
                pagina.rotate(grados)
            hojas.append(pagina)
        escribir(hojas, destino)

    ejecutar([Tarea(ruta, destino, hacer)], f"Girar {cuantos(len(elegidas), 'página')} {grados}°", simular, si)


def comprime(archivo: Path = ARCHIVO, simular: bool = OPCION_SIMULAR, si: bool = OPCION_SI) -> None:
    """Un PDF que ocupa menos (sin perder calidad: comprime el texto y quita lo repetido)."""
    ruta = uno(archivo)
    try:
        lector = abrir(ruta)
    except NavajaError as error:
        fallar(error)
    destino = al_lado(ruta, "-comprimido")
    ejecutar([Tarea(ruta, destino, lambda: escribir(list(lector.pages), destino, comprimir=True))], "Comprimir", simular, si)
    if destino.exists():
        antes, despues = ruta.stat().st_size, destino.stat().st_size
        if despues < antes:
            console.print(f"[pista]{tamano_legible(antes)} → {tamano_legible(despues)} ({100 - round(despues * 100 / antes)} % menos).[/]")
        else:
            console.print("[pista]Ya estaba comprimido: casi no ha cambiado (las fotos de dentro no se tocan).[/]")


def pedir_clave(texto: str, repetir: bool = False) -> str:
    clave = pedir_secreto(texto)
    if not clave:
        fallar(NavajaError("La contraseña no puede estar vacía."))
    if repetir and pedir_secreto("Otra vez, para comprobarla") != clave:
        fallar(NavajaError("Las dos contraseñas no son iguales."))
    return clave


def protege(archivo: Path = ARCHIVO, si: bool = OPCION_SI) -> None:
    """Un PDF nuevo con contraseña para abrirlo (AES-256). La escribes sin que se vea."""
    ruta = uno(archivo)
    try:
        lector = abrir(ruta)
    except NavajaError as error:
        fallar(error)
    clave = pedir_clave("Contraseña nueva", repetir=True)
    destino = al_lado(ruta, "-con-clave")
    ejecutar([Tarea(ruta, destino, lambda: escribir(list(lector.pages), destino, clave=clave))], "Poner contraseña", False, si)


def desprotege(archivo: Path = ARCHIVO, si: bool = OPCION_SI) -> None:
    """Un PDF nuevo sin contraseña (hace falta saberla)."""
    ruta = uno(archivo)
    try:
        lector = abrir(ruta)
    except NavajaError:
        lector = None
    if lector is not None:
        console.print("[aviso]Este PDF no tiene contraseña.[/]")
        return
    clave = pedir_clave("Contraseña del PDF")
    try:
        lector = abrir(ruta, clave)
    except NavajaError as error:
        fallar(error)
    destino = al_lado(ruta, "-sin-clave")
    ejecutar([Tarea(ruta, destino, lambda: escribir(list(lector.pages), destino))], "Quitar la contraseña", False, si)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(help="Unir, separar, sacar o quitar páginas, girar, comprimir y contraseñas.", no_args_is_help=True)
    sub.command("info", help="Páginas, tamaño y si tiene contraseña.")(info)
    sub.command("une", help="Junta varios PDF en uno.")(une)
    sub.command("separa", help="Un PDF por página o por tramos.")(separa)
    sub.command("saca", help="Un PDF nuevo solo con esas páginas.")(saca)
    sub.command("quita", help="Un PDF nuevo sin esas páginas.")(quita)
    sub.command("gira", help="Gira páginas 90, 180 o 270 grados.")(gira)
    sub.command("comprime", help="Que ocupe menos, sin perder calidad.")(comprime)
    sub.command("protege", help="Le pone contraseña para abrirlo.")(protege)
    sub.command("desprotege", help="Le quita la contraseña (hace falta saberla).")(desprotege)
    app.add_typer(sub, name="pdf", rich_help_panel=DOCUMENTOS)
