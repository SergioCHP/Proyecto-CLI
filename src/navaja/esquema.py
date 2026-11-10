"""acciones.json: dónde está, leerlo y comprobarlo entero antes de tocar un solo archivo.

Cada error dice qué acción y qué campo fallan («Acción «x», campo «tipo»: …»), en
castellano, y sale con el código 3. Lo propio de cada tipo (que «renombrar» lleve
plantilla…) lo comprueba su clase en ``acciones.py``.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any

from .acciones import Accion
from .comandos.duplicados import a_bytes
from .comandos.renombra import error_de_regex
from .comun import directorio_datos
from .errores import AccionNoValida, ConfigError
from .filtros import periodo, rango

ARCHIVO = "acciones.json"
VERSION = 1

COMUNES = ("nombre", "descripcion", "tipo")
DE_ARCHIVOS = ("carpeta", "filtro")
FILTRO: dict[str, type | tuple[type, ...]] = {
    "solo": (str, list),
    "contiene": str,
    "patron": str,
    "desde": str,
    "hasta": str,
    "mayor_que": str,
    "recursivo": bool,
    "ocultos": bool,
    "excluir": (str, list),
}
RUTAS = ("carpeta", "destino")
NOMBRE = re.compile(r"[a-z0-9ñ]+(?:[-_][a-z0-9ñ]+)*")

# Lo que explican el manual y el README (una sola vez, aquí).
DOC_CAMPOS = [
    ("version", "obligatorio", "Siempre 1, al principio. Si un día cambia el formato, sube a 2."),
    ("acciones", "obligatorio", "La lista de acciones."),
    ("nombre", "obligatorio", "Con el que la ejecutas: minúsculas, números y guiones, sin "
     "espacios (ordenar-descargas). No se puede repetir."),
    ("descripcion", "obligatorio", "Qué hace, en una frase. Sale en «acciones ver»."),
    ("tipo", "obligatorio", "mover, copiar, ordenar, renombrar, borrar o rutina."),
    ("carpeta", "opcional", "Dónde trabaja (~/Downloads). Sin ella, en la carpeta actual. "
     "Al ejecutar puedes darle otra."),
    ("filtro", "opcional", "Qué archivos de la carpeta se tocan (abajo). Sin filtro, todos."),
    ("destino", "mover, copiar", "A qué carpeta van. Si no existe, se crea. En «ordenar» es "
     "opcional: dónde se crean las subcarpetas. Al ejecutar puedes darle otro (--destino)."),
    ("si_cambia", "copiar, opcional", "Si allí ya hay uno distinto con el mismo nombre: "
     "copia-aparte (por defecto: guarda «nombre (1)» al lado) o el-mas-nuevo (se queda el más "
     "reciente; el viejo se guarda y «acciones versiones» lo devuelve o lo borra)."),
    ("por", "ordenar", "tipo, mes, año, día o letra."),
    ("plantilla", "renombrar", "El nombre nuevo con huecos: {fecha:%Y-%m-%d}, {n:03}, {nombre} "
     "y {ext}."),
    ("orden", "renombrar", "En qué orden se cuenta {n}: nombre (por defecto) o fecha."),
    ("pasos", "rutina", "Las acciones que hace, en orden: [\"ordenar-descargas\", \"…\"]."),
    ("_lo-que-sea", "opcional", "Lo que empieza por _ es una nota para ti: navaja no lo lee."),
]
DOC_FILTRO = [
    ("solo", "\"imagenes\", \"documentos\", \"ejecutables\"… o extensiones: \"jpg,png\" "
     "(también una lista). FOTO.JPG cuenta como jpg."),
    ("contiene", "Un texto que lleva el nombre, sin mirar mayúsculas: \"gemini\"."),
    ("patron", "Expresión regular sobre el nombre, sin mirar mayúsculas: \"^(IMG|PXL)_\". "
     "En JSON la barra invertida va doble: \"\\\\d\"."),
    ("desde · hasta", "Fechas de modificación como en ordena: \"hace 30 días\", "
     "\"septiembre 2026\", \"1/9/2026\". «hasta: hace 30 días» = los de hace más de un mes."),
    ("mayor_que", "Solo los que ocupan al menos eso: \"100MB\", \"1GB\"."),
    ("recursivo", "true para mirar también en las subcarpetas."),
    ("ocultos", "true para incluir ocultos y de sistema (desktop.ini…)."),
    ("excluir", "Con recursivo, carpetas en las que no entra, se llamen así donde estén: "
     "\"node_modules, __pycache__\" (también una lista), sin mirar mayúsculas. Nombres, no rutas "
     "ni comodines. Sin recursivo no hace nada (validar lo avisa)."),
]

PLANTILLA_INICIAL = {
    "version": 1,
    "acciones": [
        {
            "nombre": "ordenar-descargas",
            "descripcion": "Mete cada archivo de Descargas en su carpeta: Imagenes, Documentos…",
            "tipo": "ordenar",
            "carpeta": "~/Downloads",
            "por": "tipo",
        }
    ],
}
"""Lo que escribe «acciones editar» si todavía no tienes acciones.json."""


# ── Dónde está ─────────────────────────────────────────────────────────────


def en_datos() -> Path:
    return directorio_datos() / ARCHIVO


def buscar(config: Path | None = None) -> Path:
    """El de ``--config``; si no, el de la carpeta actual; si no, el de tus datos."""
    if config is not None:
        ruta = config.expanduser()
        if not ruta.is_file():
            raise ConfigError(f"No encuentro {ruta}.")
        return ruta
    for ruta in (Path.cwd() / ARCHIVO, en_datos()):
        if ruta.is_file():
            return ruta
    raise ConfigError(
        f"No encuentro {ARCHIVO}: ni en esta carpeta ({Path.cwd()}) ni en tus datos "
        f"({en_datos()}). Créalo con: navaja acciones editar"
    )


# ── Leerlo ─────────────────────────────────────────────────────────────────

ERRORES_JSON = [
    ("Illegal trailing comma", "sobra una coma antes de cerrar"),
    ("Expecting ',' delimiter", "falta una coma entre dos elementos"),
    ("Expecting ':' delimiter", "faltan los dos puntos (:) entre el campo y su valor"),
    ("Expecting property name enclosed in double quotes",
     "esperaba un campo entre comillas dobles (¿sobra una coma antes de «}», o usaste "
     "comillas simples?)"),
    ("Expecting value", "falta un valor (¿sobra una coma antes de «]», o hay un texto sin comillas?)"),
    ("Extra data", "sobra algo después del final"),
    ("Unterminated string", "faltan cerrar unas comillas"),
    ("Invalid \\escape", "hay una barra invertida \\ suelta: en JSON se escribe doble "
     "(C:\\\\Users) o, mejor, usa / (C:/Users o ~/Downloads)"),
    ("Invalid control character", "hay un salto de línea dentro de un texto entre comillas"),
]


def leer(ruta: Path) -> Any:
    """El contenido del archivo, o ``ConfigError`` con línea, columna y qué pasa."""
    try:
        texto = ruta.read_text(encoding="utf-8-sig")  # -sig: el Bloc de notas a veces pone BOM
    except UnicodeDecodeError:
        raise ConfigError(
            f"{ruta.name} no está guardado en UTF-8. En el Bloc de notas: Archivo → Guardar "
            "como → Codificación: UTF-8."
        ) from None
    except OSError as exc:
        raise ConfigError(f"No puedo leer {ruta}: {exc.strerror or exc}") from None
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        motivo = next((es for en, es in ERRORES_JSON if exc.msg.startswith(en)), exc.msg)
        lineas = texto.splitlines()
        linea = lineas[exc.lineno - 1].strip() if 0 < exc.lineno <= len(lineas) else ""
        detalle = f"\n    {exc.lineno} │ {linea}" if linea else ""
        raise ConfigError(
            f"{ruta.name} no es JSON válido: línea {exc.lineno}, columna {exc.colno}: "
            f"{motivo}.{detalle}"
        ) from None


def cargar(ruta: Path) -> list[dict[str, Any]]:
    """Lee y comprueba acciones.json. Devuelve las acciones listas para el motor."""
    return validar(leer(ruta))


# ── Comprobarlo ────────────────────────────────────────────────────────────


def es_nota(campo: str) -> bool:
    return campo.startswith(("_", "$"))


SINONIMOS = {
    "descripción": "descripcion",
    "origen": "carpeta",
    "extensiones": "solo",
    "extension": "solo",
    "patrón": "patron",
    "mas_antiguo_que_dias": "hasta",
    "mayor_que_mb": "mayor_que",
}
"""Lo que es fácil escribir en vez del campo bueno (con tilde, o como en otros esquemas)."""


def parecido(palabra: str, posibles: list[str]) -> str:
    if SINONIMOS.get(palabra) in posibles:
        return f" ¿Querías decir «{SINONIMOS[palabra]}»?"
    cerca = difflib.get_close_matches(palabra, posibles, n=1)
    return f" ¿Querías decir «{cerca[0]}»?" if cerca else ""


def validar(datos: Any) -> list[dict[str, Any]]:
    """Comprueba todo el archivo. ``ConfigError`` (o ``AccionNoValida``) con el primer fallo."""
    if not isinstance(datos, dict):
        raise ConfigError('El archivo tiene que empezar por { con "version" y "acciones" dentro.')
    if "version" not in datos:
        raise ConfigError('Falta «version». Empieza el archivo con: {"version": 1, "acciones": [ … ]}')
    if datos["version"] != VERSION or isinstance(datos["version"], bool):
        raise ConfigError(
            f"«version» es {json.dumps(datos['version'], ensure_ascii=False)}, pero esta navaja "
            f"lee la versión {VERSION}."
        )
    for campo in datos:
        if campo not in ("version", "acciones") and not es_nota(campo):
            raise ConfigError(
                f"Sobra «{campo}» al principio del archivo: ahí solo van version y acciones."
                + parecido(campo, ["version", "acciones"])
            )
    acciones = datos.get("acciones")
    if not isinstance(acciones, list) or not acciones:
        raise ConfigError('Falta la lista «acciones» o está vacía: "acciones": [ { … } ]')

    vistos: set[str] = set()
    limpias = []
    for numero, accion in enumerate(acciones, start=1):
        limpias.append(comprobar_accion(accion, numero, vistos))
    comprobar_rutinas(limpias)
    return limpias


def comprobar_accion(accion: Any, numero: int, vistos: set[str]) -> dict[str, Any]:
    if not isinstance(accion, dict):
        raise ConfigError(f"La acción nº {numero} no es un objeto {{ … }} con sus campos.")
    nombre = accion.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        raise AccionNoValida(f"nº {numero}", "nombre", "es obligatorio")
    if not NOMBRE.fullmatch(nombre) or nombre.isdigit():
        raise AccionNoValida(
            nombre, "nombre",
            "solo minúsculas, números y guiones, sin espacios ni tildes (ej.: ordenar-descargas)",
        )
    if nombre in vistos:
        raise AccionNoValida(nombre, "nombre", "está repetido: cada acción necesita uno distinto")
    vistos.add(nombre)

    for campo in ("descripcion", "tipo"):
        if not isinstance(accion.get(campo), str) or not accion[campo].strip():
            raise AccionNoValida(nombre, campo, "es obligatorio")
    tipos = Accion.tipos()
    clase = tipos.get(accion["tipo"])
    if clase is None:
        raise AccionNoValida(
            nombre, "tipo",
            f"«{accion['tipo']}» no existe; usa uno de: {', '.join(tipos)}."
            + parecido(accion["tipo"], list(tipos)),
        )

    permitidos = list(COMUNES) + list(clase.campos)
    if clase.usa_archivos:
        permitidos += list(DE_ARCHIVOS)
    for campo in accion:
        if campo in permitidos or es_nota(campo):
            continue
        de_otro = [t for t, c in tipos.items() if campo in c.campos or (campo in DE_ARCHIVOS and c.usa_archivos)]
        if de_otro:
            motivo = f"no se usa en acciones de tipo {clase.tipo} (es de {', '.join(de_otro)})"
        else:
            motivo = f"no existe; aquí valen: {', '.join(permitidos)}." + parecido(campo, permitidos)
        raise AccionNoValida(nombre, campo, motivo)

    for campo in RUTAS:
        if campo in accion:
            comprobar_ruta(nombre, campo, accion[campo])
    if "filtro" in accion:
        comprobar_filtro(nombre, accion["filtro"])
    clase.comprobar(accion)
    return {campo: valor for campo, valor in accion.items() if not es_nota(campo)}


def comprobar_ruta(nombre: str, campo: str, valor: Any) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise AccionNoValida(nombre, campo, 'tiene que ser una ruta entre comillas: "~/Downloads"')
    if any(c in valor for c in "\n\r\t\b\f"):
        raise AccionNoValida(
            nombre, campo,
            "tiene un salto de línea o un tabulador: en JSON, \\n y \\t de una ruta de Windows "
            "no son barras. Usa / (C:/Users/…) o ~/…",
        )


NO_VALEN_EN_NOMBRE = set('<>:"/\\|?*')
"""Lo que no puede llevar un nombre de carpeta en Windows (y delata una ruta o un comodín)."""


def carpetas_excluidas(excluir: str | list[str]) -> tuple[str, ...]:
    """«node_modules, build» o ["node_modules", "build"] → ("node_modules", "build").

    En la lista también se parte por comas: ["node_modules, build"] vale lo mismo.
    """
    textos = [excluir] if isinstance(excluir, str) else excluir
    return tuple(parte.strip() for texto in textos for parte in texto.split(",") if parte.strip())


def comprobar_filtro(nombre: str, filtro: Any) -> None:
    if not isinstance(filtro, dict):
        raise AccionNoValida(nombre, "filtro", 'tiene que ser un objeto: {"solo": "imagenes"}')
    for campo, valor in filtro.items():
        if es_nota(campo):
            continue
        if campo not in FILTRO:
            raise AccionNoValida(
                nombre, f"filtro.{campo}",
                f"no existe; en el filtro valen: {', '.join(FILTRO)}." + parecido(campo, list(FILTRO)),
            )
        esperado = FILTRO[campo]
        if esperado is bool and not isinstance(valor, bool):
            raise AccionNoValida(nombre, f"filtro.{campo}", "tiene que ser true o false (sin comillas)")
        if not isinstance(valor, esperado) or (esperado is str and not valor.strip()):
            raise AccionNoValida(nombre, f"filtro.{campo}", "tiene que ser un texto entre comillas")
    solo = filtro.get("solo")
    if isinstance(solo, list) and not all(isinstance(s, str) and s.strip() for s in solo):
        raise AccionNoValida(nombre, "filtro.solo", 'tiene que ser una lista de textos: ["jpg", "png"]')
    if "excluir" in filtro:
        excluir = filtro["excluir"]
        if isinstance(excluir, list) and not all(isinstance(e, str) and e.strip() for e in excluir):
            raise AccionNoValida(
                nombre, "filtro.excluir", 'tiene que ser una lista de textos: ["node_modules", "build"]'
            )
        carpetas = carpetas_excluidas(excluir)
        if not carpetas:
            raise AccionNoValida(
                nombre, "filtro.excluir", 'está vacío; pon nombres de carpeta: ["node_modules"]'
            )
        for carpeta in carpetas:
            if any(letra in NO_VALEN_EN_NOMBRE for letra in carpeta) or carpeta in (".", ".."):
                raise AccionNoValida(
                    nombre, "filtro.excluir",
                    f"«{carpeta}» no es un nombre de carpeta; pon solo el nombre, sin rutas, "
                    "unidades ni comodines (node_modules)",
                )
    if "patron" in filtro:
        try:
            re.compile(filtro["patron"])
        except re.error as exc:
            raise AccionNoValida(
                nombre, "filtro.patron", f"expresión regular rota: {error_de_regex(exc)}"
            ) from None
    for clave in ("desde", "hasta"):
        if clave in filtro:
            try:
                periodo(filtro[clave])
            except ValueError as exc:
                raise AccionNoValida(nombre, f"filtro.{clave}", str(exc).rstrip(".")) from None
    try:
        rango(filtro.get("desde", ""), filtro.get("hasta", ""))
    except ValueError as exc:  # desde después de hasta
        raise AccionNoValida(nombre, "filtro.desde", str(exc).rstrip(".")) from None
    if "mayor_que" in filtro:
        try:
            a_bytes(filtro["mayor_que"])
        except ValueError as exc:
            raise AccionNoValida(nombre, "filtro.mayor_que", str(exc).rstrip(".")) from None


def comprobar_rutinas(acciones: list[dict[str, Any]]) -> None:
    """Los pasos de una rutina tienen que ser acciones que existen y no otras rutinas."""
    por_nombre = {a["nombre"]: a for a in acciones}
    for accion in acciones:
        if accion["tipo"] != "rutina":
            continue
        for paso in accion["pasos"]:
            if paso == accion["nombre"]:
                raise AccionNoValida(accion["nombre"], "pasos", "una rutina no puede llamarse a sí misma")
            if paso not in por_nombre:
                raise AccionNoValida(
                    accion["nombre"], "pasos",
                    f"no hay ninguna acción «{paso}»." + parecido(paso, list(por_nombre)),
                )
            if por_nombre[paso]["tipo"] == "rutina":
                raise AccionNoValida(
                    accion["nombre"], "pasos",
                    f"«{paso}» es otra rutina; los pasos tienen que ser acciones sueltas",
                )


def avisos(acciones: list[dict[str, Any]]) -> list[str]:
    """Lo que no es un error pero conviene saber: carpetas o unidades que ahora mismo no
    existen y un «excluir» que no hace nada porque falta «recursivo»."""
    mensajes = []
    for accion in acciones:
        nombre = accion["nombre"]
        carpeta = accion.get("carpeta")
        if carpeta and not Path(carpeta).expanduser().is_dir():
            mensajes.append(f"«{nombre}»: la carpeta {carpeta} no existe ahora mismo.")
        destino = accion.get("destino")
        unidad = Path(destino).expanduser().anchor if isinstance(destino, str) else ""
        if unidad and not Path(unidad).exists():
            mensajes.append(
                f"«{nombre}»: el destino {destino} está en una unidad que no existe ahora mismo "
                "(¿el USB sin conectar?)."
            )
        filtro = accion.get("filtro") or {}
        if "excluir" in filtro and not filtro.get("recursivo"):
            mensajes.append(
                f"«{nombre}»: «excluir» solo sirve con \"recursivo\": true; sin él no entra en "
                "ninguna subcarpeta."
            )
    return mensajes
