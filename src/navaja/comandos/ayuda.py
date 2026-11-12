"""Ayuda de navaja: la corta de cada comando y la orden «manual» con todo.

La parte de los comandos se genera a partir de los propios comandos de Typer
(descripción, argumentos, opciones y valores por defecto), así que nunca se
queda desfasada. Lo que no está en el código (modo interactivo, seguridad,
datos, códigos de salida) va escrito aquí.
"""

from __future__ import annotations

import difflib
import re
from enum import Enum
from pathlib import Path
from typing import Any

import typer
from rich.console import Group
from rich.markup import escape
from rich.padding import Padding
from rich.table import Table

from .. import __version__
from ..comun import NAVAJA, SECCIONES, TEMAS, console, directorio_datos, error_console
from .ocupa import BASURA_ARCHIVOS, BASURA_DIRS, BASURA_EN_PROYECTOS, BASURA_PATRONES
from ..filtros import EJEMPLOS_FECHA, NOMBRES

# ── Lectura de los comandos ────────────────────────────────────────────────


def valor_texto(valor: Any) -> str:
    return str(valor.value if isinstance(valor, Enum) else valor)


def es_grupo(comando: Any) -> bool:
    return hasattr(comando, "commands")


def subcomandos(grupo: Any) -> list[tuple[str, Any]]:
    """Subcomandos visibles en el orden en que se registraron, con «manual» al final.

    Typer pone primero los comandos sueltos y después los grupos; sin mover «manual»
    al final, quedaría en mitad del menú y cambiaría los números de los grupos.
    """
    nombres = [
        n for n in grupo.list_commands(None) if not getattr(grupo.commands[n], "hidden", False)
    ]
    nombres.sort(key=lambda n: n == "manual")
    return [(n, grupo.commands[n]) for n in nombres]


def por_secciones(grupo: Any) -> list[tuple[str, list[tuple[str, Any]]]]:
    """Los ``subcomandos`` repartidos por su sección (``rich_help_panel``).

    Se corta cada vez que cambia la sección, sin reordenar nada: así el número de cada
    comando en el menú sigue siendo su posición en ``subcomandos``. Los comandos sin
    sección (los de un submenú) van en una sin título: «».
    """
    secciones: list[tuple[str, list[tuple[str, Any]]]] = []
    for nombre, comando in subcomandos(grupo):
        seccion_ = getattr(comando, "rich_help_panel", None) or ""
        if not secciones or secciones[-1][0] != seccion_:
            secciones.append((seccion_, []))
        secciones[-1][1].append((nombre, comando))
    return secciones


def titulo_seccion(seccion_: str) -> str:
    """«Herramientas — Se usan al momento…», con markup."""
    texto = SECCIONES.get(seccion_, "")
    return f"[titulo]{escape(seccion_)}[/]" + (f" [pista]— {escape(texto)}[/]" if texto else "")


def tabla_secciones(grupo: Any, ancho: int = 90) -> Group:
    """Nombre y ayuda corta de cada comando, con el título de cada sección encima.

    Una tabla por sección, todas con la primera columna igual de ancha para que las
    ayudas queden alineadas.
    """
    secciones = por_secciones(grupo)
    columna = max((len(n) for _, comandos in secciones for n, _ in comandos), default=0)
    partes: list[Any] = []
    for posicion, (seccion_, comandos) in enumerate(secciones):
        if seccion_:
            partes.append(("\n" if posicion else "") + titulo_seccion(seccion_))
        tabla = Table.grid(padding=(0, 2))
        tabla.add_column(style="acento", no_wrap=True, min_width=columna)
        tabla.add_column()
        for nombre, comando in comandos:
            tabla.add_row(nombre, escape(comando.get_short_help_str(ancho)))
        partes.append(Padding(tabla, (0, 0, 0, 2)) if seccion_ else tabla)
    return Group(*partes)


def argumentos(comando: Any) -> list[Any]:
    return [p for p in comando.params if p.param_type_name == "argument"]


def opciones_visibles(comando: Any) -> list[Any]:
    return [
        p
        for p in comando.params
        if p.param_type_name == "option" and not getattr(p, "hidden", False)
    ]


def resolver(grupo: Any, palabras: list[str]) -> tuple[Any, list[str]]:
    """Baja por los grupos mientras las palabras sean nombres de comando."""
    comando, nombres = grupo, []
    for palabra in palabras:
        if not es_grupo(comando) or palabra not in comando.commands:
            break
        comando = comando.commands[palabra]
        nombres.append(palabra)
    return comando, nombres


def todos(grupo: Any, camino: list[str] | None = None) -> list[tuple[list[str], Any]]:
    """Todos los comandos y subcomandos, en orden, con su camino (``["ordena", "fecha"]``)."""
    camino = camino or []
    lista: list[tuple[list[str], Any]] = []
    for nombre, comando in subcomandos(grupo):
        lista.append((camino + [nombre], comando))
        if es_grupo(comando):
            lista += todos(comando, camino + [nombre])
    return lista


def uso(nombres: list[str], comando: Any) -> str:
    """``ocupa [RUTA] [opciones]``: <> obligatorio, [] opcional."""
    partes = list(nombres)
    if es_grupo(comando):
        return " ".join(partes + ["<subcomando>" if partes else "<comando>"])
    for param in argumentos(comando):
        nombre = (param.name or "").upper()
        if getattr(param, "nargs", 1) == -1:
            nombre += "…"
        partes.append(f"<{nombre}>" if param.required else f"[{nombre}]")
    if opciones_visibles(comando):
        partes.append("[opciones]")
    return " ".join(partes)


def tipo_texto(param: Any) -> str:
    tipo = getattr(param, "type", None)
    choices = getattr(tipo, "choices", None)
    if choices:
        return " | ".join(valor_texto(c) for c in choices)
    nombre = getattr(tipo, "name", "")
    return {
        "int": "número",
        "integer": "número",
        "float": "número",
        "path": "ruta",
        "str": "texto",
        "text": "texto",
        "bool": "sí/no",
        "boolean": "sí/no",
    }.get(nombre, "texto")


def valor_de(param: Any) -> str:
    """Columna «Valor»: si es obligatorio, qué tipo de dato lleva y su valor por defecto."""
    defecto = param.default
    if param.param_type_name == "argument":
        if param.required:
            return "obligatorio"
        if getattr(param, "nargs", 1) == -1:
            return "opcional · uno o varios"
        if defecto is None:
            return "opcional"
        if valor_texto(defecto) == ".":
            return "opcional · por defecto: . (la carpeta actual)"
        if valor_texto(defecto) == "":
            return "opcional · si no lo pones, vacío"
        return f"opcional · por defecto: {valor_texto(defecto)}"
    if getattr(param, "is_flag", False):
        return "interruptor (sin valor)"
    texto = tipo_texto(param)
    vacio = defecto is None or defecto == "" or (isinstance(defecto, (list, tuple)) and not defecto)
    if not vacio:
        texto += f" · por defecto: {valor_texto(defecto)}"
    if getattr(param, "multiple", False):
        texto += " · se puede repetir"
    return texto


def tabla_parametros(comando: Any) -> Table | None:
    filas = argumentos(comando) + opciones_visibles(comando)
    if not filas:
        return None
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", no_wrap=True)
    tabla.add_column()
    tabla.add_column(style="pista")
    for param in filas:
        if param.param_type_name == "argument":
            nombre = (param.name or "").upper()
        else:
            nombre = ", ".join(sorted(param.opts, key=len))
        ayuda = getattr(param, "help", None) or ""
        tabla.add_row(escape(nombre), escape(ayuda), escape(valor_de(param)))
    return tabla


# ── Notas que no salen del código de Typer ────────────────────────────────

EXTRA: dict[str, str] = {
    "listar": "Primero las carpetas y luego los archivos, por orden alfabético.",
    "ocupa": "Suma el tamaño de cada carpeta con todo lo que tiene dentro.",
    "limpia": (
        "Borra solo lo que se vuelve a crear solo: las carpetas "
        + ", ".join(sorted(BASURA_DIRS))
        + "; "
        + ", ".join(sorted(BASURA_EN_PROYECTOS))
        + " solo dentro de un proyecto de programación (si al lado hay un package.json, "
        "pyproject.toml, Cargo.toml…; fuera pueden ser carpetas tuyas); los archivos "
        + ", ".join(sorted(BASURA_ARCHIVOS))
        + "; y los que encajan con "
        + ", ".join(sorted(BASURA_PATRONES))
        + ". No toca .git ni los entornos virtuales (venv). Lo borrado no va a la papelera."
    ),
    "ordena": (
        "Todas las opciones trabajan en la carpeta actual (o la de --carpeta), enseñan "
        "«archivo → carpeta» y preguntan [s/n] antes de mover nada; con --simular solo "
        "miran. Las carpetas se crean dentro de la misma carpeta (o en --destino). Nunca "
        "se sobrescribe: si ya hay un archivo con ese nombre, añade (1), (2)… La fecha es "
        "la de modificación, la que ves en el explorador. Se saltan los archivos ocultos "
        "y de sistema (desktop.ini…). Filtros: --solo imagenes (o jpg,png), --contiene "
        "texto, --desde y --hasta."
    ),
    "ordena tipo": "Carpetas: " + ", ".join(NOMBRES.values()) + ". «ordena tipos» dice qué va en cada una.",
    "ordena fecha": "Por mes: «2026/10 octubre». Por año: «2026». Por día: «2026-10-26».",
    "ordena tramo": (
        f"Fechas: {EJEMPLOS_FECHA}. Un mes o un año valen enteros: «septiembre 2026» "
        "como desde es el 1 de septiembre y como hasta, el 30. La carpeta se llama «del "
        "2026-09-01 al 2026-09-30» salvo que le pongas --nombre."
    ),
    "ordena nombre": (
        "Sin mirar mayúsculas: «factura» junta factura_enero.pdf y Factura luz.pdf en la "
        "carpeta «factura» (o la que digas con --nombre). Los demás no se tocan, así que en "
        "el menú no pregunta «¿Con qué archivos?». Para un "
        "texto con espacios, entre comillas: nombre \"mi viaje\"."
    ),
    "ordena letra": (
        "Activitat.pdf → A · Boletin.pdf → B · Ñandú.jpg → Ñ · 2024 notas.txt → 0-9. Las "
        "tildes no cuentan (Álbum va a A) ni los signos del principio (_borrador va a B); "
        "sin letras ni números, a Otros."
    ),
    "ordena tipos": "Los nombres de tipo también valen en --solo: --solo imagenes.",
    "renombra": (
        "Todas las opciones trabajan en la carpeta actual (o la de --carpeta), enseñan "
        "«antes → después» y preguntan [s/n] antes de cambiar nada; con --simular solo "
        "miran. Cambian el nombre y dejan la extensión como estaba (salvo arreglar y "
        "plantilla). Filtros: --solo imagenes (o jpg,png), --contiene Gemini, --desde y "
        "--hasta (fechas como en ordena). Si dos archivos acabarían "
        "con el mismo nombre, el nombre ya existe o no vale en Windows, lo marca y no lo "
        "toca. Para un texto con espacios, entre comillas: cambiar \" (1)\" \"\"."
    ),
    "renombra cambiar": (
        "Solo cambian los archivos que llevan ese texto; los demás se quedan igual (por eso "
        "en el menú no pregunta «¿Con qué archivos?»). No mira mayúsculas: «gemini» encuentra "
        "«Gemini_…». Vale el nombre entero, con o sin extensión: cambiar informe.pdf final "
        "deja final.pdf. El texto va tal cual (sin regex): «(1)» o «.» son texto normal."
    ),
    "renombra numerar": (
        "Cuenta por separado en cada carpeta. Con --orden fecha, la más antigua es la 001."
    ),
    "renombra fecha": "Si un archivo ya empieza por su fecha, no la repite.",
    "renombra arreglar": (
        "Pasa a minúsculas, quita tildes y eñes (año → ano) y cambia espacios y símbolos "
        "por guiones: «Foto Año (1).JPG» → «foto-ano-1.jpg»."
    ),
    "renombra plantilla": (
        "Huecos: {nombre} (el nombre sin extensión), {ext} (la extensión con punto, en "
        "minúsculas), {n} (contador; {n:03} → 001) y {fecha} (fecha de modificación; "
        "{fecha:%Y-%m-%d} → 2026-10-26). Pon {ext} para no perder la extensión."
    ),
    "renombra avanzado": (
        "El patrón es una expresión regular de Python. Ejemplo: IMG_(\\d+) → foto_\\1 "
        "convierte IMG_1234.jpg en foto_1234.jpg. Sin --completo solo cambia el nombre, "
        "no la extensión."
    ),
    "duplicados": (
        "Compara el contenido de los archivos (SHA-256), no el nombre: dos archivos son "
        "duplicados aunque se llamen distinto. Los enlaces duros no cuentan dos veces."
    ),
    "duplicados buscar": "Al acabar te dice la orden exacta para quitar esas copias.",
    "duplicados borrar": "No borra: mueve las copias a la papelera de navaja.",
    "duplicados vaciar": "Esto sí borra para siempre; no se puede deshacer.",
    "notas": (
        "Si lo que guardas empieza por https:// o www., es un enlace: «notas abrir» lo abre "
        "en el navegador. Si no escribes el texto, «notas agregar» abre tu editor (Bloc de "
        "notas en Windows, o el de la variable EDITOR). Cada nota tiene un número (ID): es "
        "el que piden abrir y borrar."
    ),
    "tema": "Temas disponibles: " + ", ".join(TEMAS) + ".",
    "config": (
        "La primera vez que abres navaja te pregunta cómo quieres que te llame (Intro = tu "
        "usuario de Windows). Lo que pongas en «config nombre» se guarda y te llama así siempre. "
        "«config autocompletar $PROFILE» añade a PowerShell el Tab de navaja (y de nav), que "
        "completa también los nombres de tus acciones (acciones ejecutar us⇥ → usb-a-pc); "
        "abre una terminal nueva para que funcione."
    ),
    "acciones": (
        "Una acción es una tarea que repites, guardada con un nombre en acciones.json "
        "(ordenar-descargas, imagenes-ia…): la escribes una vez y la haces cuando quieras. "
        "navaja usa el acciones.json de la carpeta actual y, si no hay, el de tus datos (o el "
        "que digas con --config, antes o después de la orden: «acciones --config X ver» o "
        "«acciones ver --config X»). Antes de hacer nada comprueba el archivo entero; si algo está "
        "mal, dice qué acción y qué campo y sale con el código 3. Cómo se escribe el archivo: "
        "«manual acciones»."
    ),
    "acciones ejecutar": (
        "Enseña «archivo → dónde va» y pregunta [s/n]; con --simular solo mira. Nunca "
        "sobrescribe: si el nombre ya existe, añade (1), (2)… Solo «copiar» con «si_cambia»: "
        "«el-mas-nuevo» sustituye uno más viejo, y el viejo se guarda (acciones versiones). Lo que "
        "ya está copiado igual se salta, así que puedes repetirla (USB ↔ PC) sin duplicar. Si "
        "el destino está en una unidad que no existe (el USB sin conectar), no empieza. Con "
        "CARPETA y --destino cambias, solo esa vez, de dónde salen y a dónde van (si el USB "
        "sale con otra letra: acciones ejecutar pc-a-usb --destino E:/DAM). Una "
        "rutina hace sus pasos en "
        "orden y pregunta en cada uno; si dices que no, no hace los que quedan. Prueba "
        "primero en una carpeta de pruebas: acciones ejecutar ordenar-descargas "
        "~/pruebas --simular."
    ),
    "acciones deshacer": (
        "Devuelve a su sitio lo movido, renombrado u ordenado, saca de la papelera lo borrado "
        "y quita las copias (a la papelera de navaja; solo si el original sigue ahí y la copia "
        "no ha cambiado: si la editaste después, la deja y avisa). Si una copia sustituyó a otra "
        "más vieja, devuelve la vieja, mientras siga guardada. Solo deshace la última "
        "acción; si algo falla, lo guarda para volver a intentarlo. En una rutina, la deshace "
        "entera."
    ),
    "acciones versiones": (
        "Cuando «copiar» con «si_cambia: el-mas-nuevo» sustituye un archivo, el viejo no se "
        "borra: se guarda en tus datos (no en la papelera de duplicados, así que «duplicados "
        "vaciar» no lo toca). Aquí lo ves, lo recuperas aunque hayas hecho otras acciones "
        "después, y borras lo que ya no necesitas."
    ),
    "acciones versiones recuperar": (
        "Lo devuelve a donde estaba. Si allí ya hay un archivo (la versión nueva), no lo pisa: "
        "deja la vieja al lado como «nombre (1)» para que elijas tú."
    ),
    "acciones versiones borrar": (
        "Sin números, todas; con números, esas; con --hasta \"hace 30 días\", las sustituidas "
        "hasta esa fecha. Enseña cuáles y cuánto ocupan y pregunta: no se puede deshacer."
    ),
    "acciones editar": (
        "Usa el Bloc de notas en Windows (o el editor de la variable EDITOR). Si no tienes "
        "acciones.json, lo crea en tus datos con una acción de ejemplo."
    ),
    "manual": "Sin nada, este manual entero. Con un comando, solo su parte.",
}


# ── Pintar ─────────────────────────────────────────────────────────────────


def describir(nombres: list[str], comando: Any, sangria: int = 0, prefijo: str = "") -> None:
    """Un comando con su uso, parámetros y notas; si es un grupo, también sus subcomandos.

    ``prefijo`` va delante del uso: «navaja » en la terminal.
    """
    clave = " ".join(nombres)

    def imprimir(cosa: Any, extra: int = 0) -> None:
        console.print(Padding(cosa, (0, 0, 0, sangria + extra)))

    ayuda = escape((comando.help or "").strip())
    imprimir(f"[titulo]{escape(clave)}[/] [pista]—[/] {ayuda}")
    imprimir(f"Uso: [acento]{escape(prefijo + uso(nombres, comando))}[/]", 2)
    tabla = tabla_parametros(comando)
    if tabla is not None:
        imprimir(tabla, 4)
    if clave in EXTRA:
        imprimir(f"[pista]{escape(EXTRA[clave])}[/]", 2)
    console.print()
    if es_grupo(comando):
        for nombre, sub in subcomandos(comando):
            describir(nombres + [nombre], sub, sangria + 2, prefijo)


def seccion(titulo: str) -> None:
    console.print()
    console.rule(f"[titulo]{titulo}[/]", style="borde", align="left")
    console.print()


def tabla_dos(filas: list[tuple[str, str]]) -> Table:
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", no_wrap=True)
    tabla.add_column()
    for clave, texto in filas:
        tabla.add_row(escape(clave), escape(texto))
    return tabla


MODO_INTERACTIVO = [
    ("1, 2, 3…", "Elige una opción del menú. Si es un grupo (ordena, notas…) abre su "
     "submenú; si no, lo ejecuta en la carpeta actual y pregunta lo que hace falta y los "
     "ajustes que importan (en renombra numerar: separador, cifras y orden), con Intro para "
     "dejarlos como están. Lo que cambia archivos (ordena, renombra, limpia y duplicados "
     "borrar) pregunta primero «¿En qué carpeta?» (Intro = la actual; vale una ruta "
     "completa, ~\\Documents o arrastrar la carpeta desde el explorador). En ordena y "
     "renombra pregunta al final «¿Con qué archivos?»: todos, de un tipo, los que llevan un "
     "texto o los de unas fechas (no en renombra cambiar y avanzado ni en ordena nombre, "
     "donde el texto ya dice qué archivos). El plan dice en qué carpeta va a trabajar. Debajo del "
     "resultado te dice qué más opciones tiene."),
    ("un comando", "Igual que en la terminal pero sin «navaja» delante: ocupa -n 5, "
     "ordena tipo --solo imagenes. Si le falta algo obligatorio, lo pregunta."),
    ("ayuda · ?", "Explica lo que puedes hacer donde estás: en el menú principal, todas las "
     "opciones; dentro de una opción (config, ordena…), esa opción con las suyas. "
     "También vale help."),
    ("menu · menú", "Vuelve a enseñar el menú (dentro de un submenú, el de ese grupo)."),
    ("ayuda ocupa · ocupa ? · ? 2", "Ayuda corta de un comando: qué hace, cómo se escribe y "
     "sus opciones (también «ayuda ordena fecha»)."),
    ("manual", "Este manual entero. «manual ocupa» enseña solo la parte de ese comando."),
    ("cd RUTA · cd .. · cd", "Cambia de carpeta; «cd» solo dice dónde estás. Al salir vuelves "
     "a la carpeta desde la que entraste."),
    ("pwd", "Dice en qué carpeta estás."),
    ("ls · dir", "Atajos de «listar»."),
    ("navaja … · nav …", "También valen: «navaja ocupa» es lo mismo que «ocupa»."),
    ("cls · clear", "Limpia la pantalla."),
    ("Intro · 0 · volver", "En un submenú, vuelve al menú principal."),
    ("volver · atrás", "En medio de las preguntas de una opción, repite la anterior; en la "
     "primera, vuelve al menú sin hacer nada. En las listas numeradas («¿Con qué "
     "archivos?», «¿Qué tipo?») también vale 0. Al confirmar ([s/n]), «n» no hace "
     "nada y vuelves al menú. Atrás vale con o sin tilde (atras). Entre comillas "
     "(«\"volver\"») es el texto volver. En una pregunta, «salir» cancela y te deja en el "
     "menú sin hacer nada."),
    ("salir · exit · quit · 0", "Termina y vuelve a la terminal normal (0 solo en el menú principal)."),
    ("Ctrl+C", "Cancela las preguntas o la orden en curso; en el menú principal, sale."),
    ("Tab", "Completa lo que escribes: comandos, subcomandos, opciones (escribe - y Tab), "
     "rutas (después de cd, de listar o de una opción como --carpeta) y los nombres de tus "
     "acciones (después de acciones ejecutar, también al preguntártelo). Si hay varias, las "
     "enseña en una lista."),
    ("↑ ↓", "Recuperan lo que escribiste antes, también de otras veces (se guarda en "
     "historial.txt)."),
]


def manual(raiz: Any) -> None:
    console.rule(f"[titulo]Manual de navaja {__version__}[/]", style="marco")
    console.print(
        "\nCaja de herramientas de terminal con utilidades cotidianas, todo en castellano. "
        "Este manual explica cómo se usa, todos los comandos con sus opciones, los "
        "atajos, la seguridad y dónde se guardan los datos."
    )

    seccion("1. Cómo se usa")
    console.print("Hay dos formas de usar navaja:\n")
    console.print(
        tabla_dos(
            [
                ("navaja", "Abre el modo interactivo: un menú que se queda esperando órdenes "
                 "hasta que escribes «salir»."),
                ("navaja ocupa ~/Descargas", "Ejecuta un comando directamente y vuelve a la "
                 "terminal. Sirve cualquier comando de este manual."),
                ("nav", "Es un alias de navaja: «nav ocupa» = «navaja ocupa». (No es «nv»: en "
                 "PowerShell, nv ya es New-Variable.)"),
            ]
        )
    )
    console.print("\nCómo leer el «Uso» de cada comando:\n")
    console.print(
        tabla_dos(
            [
                ("<TEXTO>", "Obligatorio: hay que escribirlo."),
                ("[RUTA]", "Opcional: si no lo escribes, usa su valor por defecto "
                 "(en las rutas, la carpeta actual)."),
                ("[opciones]", "Empiezan por - o --. Muchas tienen forma corta y larga "
                 "(-n = --mayores). Los interruptores (--si, -r) no llevan valor; "
                 "las demás sí: -n 5."),
                (". · .. · ~", "La carpeta actual, la de arriba y tu carpeta personal."),
                ('"Mis apuntes"', "Las rutas con espacios van entre comillas."),
            ]
        )
    )

    seccion("2. Modo interactivo")
    console.print(
        "Escribe [acento]navaja[/] sin nada más. El prompt dice en qué carpeta estás "
        "([acento]Descargas>[/]) y, dentro de un submenú, en cuál "
        "([acento]Descargas/ordena>[/]). Un error enseña el mensaje y sigues dentro. Si "
        "navaja no se ejecuta en una terminal (por ejemplo, en un script), no abre el menú.\n"
    )
    console.print(tabla_dos(MODO_INTERACTIVO))

    seccion("3. Comandos")
    console.print(
        "Resumen. Debajo, cada comando con su uso, sus argumentos y opciones "
        "(con el valor por defecto) y lo que conviene saber.\n"
    )
    resumen = Table.grid(padding=(0, 2))
    resumen.add_column(style="acento", no_wrap=True)
    resumen.add_column()
    for nombres, comando in todos(raiz):
        sangria = "  " * (len(nombres) - 1)
        resumen.add_row(
            f"{sangria}{escape(' '.join(nombres))}",
            escape(comando.get_short_help_str(90)),
        )
    console.print(resumen)
    console.print()
    for nombre, comando in subcomandos(raiz):
        describir([nombre], comando)

    manual_acciones()

    seccion("5. Seguridad")
    console.print(
        tabla_dos(
            [
                ("[s/n]", "Nada se borra ni se mueve sin enseñarte antes qué va a pasar y "
                 "preguntarte. Vale s, sí, n o no. Con --si no pregunta."),
                ("--simular", "En ordena, renombra, limpia y acciones ejecutar enseña lo que "
                 "haría sin tocar nada."),
                ("deshacer", "ordena, renombra y acciones revierten su última operación."),

                ("papelera", "duplicados borrar y las acciones de tipo borrar mueven los archivos "
                 "a la papelera de navaja; duplicados restaurar y acciones deshacer los "
                 "devuelven; duplicados vaciar la borra para siempre."),
                ("sin sobrescribir", "ordena, duplicados y acciones añaden (1), (2)… si el nombre "
                 "ya existe; renombra marca esos casos como conflicto y no los toca."),
            ]
        )
    )

    seccion("6. Dónde guarda sus datos")
    console.print(
        f"En [acento]{escape(str(directorio_datos()))}[/]. Se puede cambiar con la "
        "variable de entorno [acento]NAVAJA_DATOS[/]. navaja nunca guarda nada en tus "
        "carpetas.\n"
    )
    console.print(
        tabla_dos(
            [
                ("config.json", "Tu nombre para el saludo y el tema."),
                ("notas.db", "Las notas y enlaces (base de datos SQLite)."),
                ("historial.txt", "Lo que escribes en el modo interactivo, para ↑ ↓."),
                ("ordena_deshacer.json", "La última organización, para deshacerla."),
                ("renombra_deshacer.json", "El último renombrado, para deshacerlo."),
                ("duplicados_deshacer.json", "De dónde salió cada copia de la papelera, "
                 "para restaurarla."),
                ("acciones.json", "Tus acciones, si no hay uno en la carpeta en la que estás "
                 "(lo crea «acciones editar»)."),
                ("acciones_deshacer.json", "La última acción que hiciste, para deshacerla."),
                ("papelera/", "Lo que quitan duplicados borrar y las acciones de tipo borrar."),
            ]
        )
    )

    seccion("7. Para scripts")
    console.print(
        tabla_dos(
            [
                ("código 0", "Todo bien (también si respondes «n» a una confirmación)."),
                ("código 1", "Algo ha fallado: una ruta que no existe, un tema que no existe…"),
                ("código 2", "Uso incorrecto: falta un argumento, una opción no existe o la "
                 "expresión regular no es válida."),
                ("código 3", "acciones.json no existe o está mal escrito (el mensaje dice qué "
                 "acción y qué campo)."),
                ("version · -v · --version", "Muestra la versión: navaja version (o navaja --version)."),
                ("-h · --help", "En cualquier comando, su ayuda: navaja ocupa --help (lo mismo "
                 "que «manual ocupa»)."),
                ("navaja manual > manual.txt", "Guarda este manual en un archivo de texto."),
            ]
        )
    )
    console.print(
        "\n[pista]Ayuda corta de un comando dentro de navaja: [/][acento]ayuda ocupa[/][pista]. "
        "Su parte de este manual: [/][acento]manual ocupa[/][pista] "
        "(o [/][acento]navaja manual ocupa[/][pista] desde la terminal).[/]"
    )


EJEMPLO_ACCIONES = """{
  "version": 1,
  "acciones": [
    {
      "nombre": "instaladores-viejos",
      "descripcion": "Manda a la papelera los instaladores de hace más de un mes",
      "tipo": "borrar",
      "carpeta": "~/Downloads",
      "filtro": { "solo": "ejecutables", "hasta": "hace 30 días" }
    }
  ]
}"""


def manual_acciones() -> None:
    """La sección del manual que explica cómo se escribe acciones.json."""
    from ..acciones import Accion
    from ..esquema import DOC_CAMPOS, DOC_FILTRO

    seccion("4. acciones.json")
    console.print(
        "Tus acciones se escriben en un archivo de texto, acciones.json. Así añades una nueva "
        "sin tocar el programa: [acento]acciones editar[/] lo abre y lo comprueba al cerrar, y "
        "[acento]acciones validar[/] lo comprueba sin hacer nada. Por ejemplo:\n"
    )
    console.print(Padding(escape(EJEMPLO_ACCIONES), (0, 0, 0, 2)), highlight=False)
    console.print("\nCampos de cada acción:\n")
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", no_wrap=True)
    tabla.add_column(style="pista", no_wrap=True)
    tabla.add_column()
    for campo, cuando, texto in DOC_CAMPOS:
        tabla.add_row(escape(campo), escape(cuando), escape(texto))
    console.print(tabla)
    console.print("\nTipos:\n")
    console.print(tabla_dos([(tipo, clase.explicacion) for tipo, clase in Accion.tipos().items()]))
    console.print("\nFiltro (si pones varios, el archivo tiene que cumplirlos todos):\n")
    console.print(tabla_dos(DOC_FILTRO))
    console.print(
        "\n[pista]Rutas: ~ es tu carpeta personal y en Windows se escriben con / "
        "(~/Downloads, C:/Users/…). Una ruta relativa se cuenta desde la carpeta de la acción.[/]"
    )


# ── Ayuda corta (la de «ayuda ocupa» en el modo interactivo) ───────────────


def tabla_opciones(opciones: list[Any]) -> Table:
    tabla = Table.grid(padding=(0, 2))
    tabla.add_column(style="acento", no_wrap=True)
    tabla.add_column()
    for opcion in opciones:
        nombres = ", ".join(sorted(opcion.opts, key=len))
        texto = escape(getattr(opcion, "help", None) or "")
        defecto = opcion.default
        vacio = defecto is None or defecto == "" or (
            isinstance(defecto, (list, tuple)) and not defecto
        )
        if not getattr(opcion, "is_flag", False) and not vacio:
            texto += f" [pista](por defecto: {escape(valor_texto(defecto))})[/]"
        tabla.add_row(nombres, texto)
    return tabla


def ayuda_corta(nombres: list[str], comando: Any, escribir: list[str] | None = None) -> None:
    """Qué hace un comando, cómo se escribe y sus opciones.

    ``escribir`` es lo que se teclea donde estás: dentro del submenú de ordena,
    «fecha» y no «ordena fecha».
    """
    console.print(
        f"[titulo]{escape(' '.join(nombres))}[/]  "
        f"[pista]{escape(comando.get_short_help_str(80))}[/]",
        soft_wrap=True,
    )
    console.print(
        f"Uso: [acento]{escape(uso(escribir or nombres, comando))}[/]", soft_wrap=True
    )
    opciones = opciones_visibles(comando)
    if opciones:
        console.print(tabla_opciones(opciones))


# ── «ayuda» sola en el modo interactivo: lo que puedes hacer donde estás ────

AQUI_PRINCIPAL = [
    ("1, 2, 3…", "Elige una opción. Si tiene submenú lo abre; si no, la ejecuta aquí mismo "
     "y solo pregunta lo obligatorio. En las preguntas, «volver» va a la anterior."),
    ("ocupa -n 5", "Escribe un comando con sus opciones, como en la terminal pero sin «navaja»."),
    ("ayuda ocupa · ocupa ? · ? 2", "La ayuda de una opción concreta."),
    ("menu", "Vuelve a enseñar el menú."),
    ("cd RUTA · cd ..", "Cambia de carpeta; «pwd» dice dónde estás."),
    ("manual", "El manual completo, con todo explicado."),
    ("salir · 0", "Vuelve a la terminal."),
]


def aqui_submenu(grupo: Any) -> list[tuple[str, str]]:
    ejemplo = subcomandos(grupo)[0][0] if subcomandos(grupo) else "opcion"
    return [
        ("1, 2…", "Ejecuta esa opción aquí mismo; si le falta algo obligatorio, lo pregunta. "
         "Sigues en este submenú hasta que vuelvas."),
        ("volver", "En medio de las preguntas, repite la anterior; en la primera, vuelves "
         "aquí. Al confirmar ([s/n]), «n» no hace nada y vuelves aquí."),
        (f"{ejemplo} …", "Escribe la opción con sus argumentos y opciones."),
        (f"ayuda {ejemplo} · ? 1", "La ayuda de una opción concreta."),
        ("menu", "Vuelve a enseñar este submenú."),
        ("Intro · 0 · volver", "Vuelve al menú principal."),
        ("salir", "Vuelve a la terminal."),
    ]


def ayuda_aqui(grupo: Any, camino: list[str]) -> None:
    """Lo que enseña «ayuda» en el modo interactivo, según dónde estés."""
    try:
        carpeta = str(Path.cwd())
    except OSError:
        carpeta = "?"
    opciones = subcomandos(grupo)

    if not camino:
        console.print(
            f"[titulo]Menú principal[/] [pista]— trabajas en[/] [acento]{escape(carpeta)}[/]",
            soft_wrap=True,
        )
        console.print("\nAquí puedes:\n")
        console.print(tabla_dos(AQUI_PRINCIPAL))
        console.print("\nQué hace cada opción:\n")
        tabla = Table.grid(padding=(0, 2))
        tabla.add_column(style="acento", justify="right")
        tabla.add_column(style="bold", no_wrap=True)
        tabla.add_column()
        for numero, (nombre, comando) in enumerate(opciones, start=1):
            texto = escape((comando.help or "").strip())
            if es_grupo(comando):
                dentro = " · ".join(n for n, _ in subcomandos(comando))
                texto += f"\n[pista]Dentro: {escape(dentro)}[/]"
            tabla.add_row(str(numero), nombre, texto)
        console.print(tabla)
        console.print()
        return

    clave = " ".join(camino)
    console.print(
        f"[titulo]{escape(clave)}[/] [pista]—[/] {escape((grupo.help or '').strip())}",
        soft_wrap=True,
    )
    if clave in EXTRA:
        console.print(f"[pista]{escape(EXTRA[clave])}[/]")
    console.print("\nAquí puedes:\n")
    console.print(tabla_dos(aqui_submenu(grupo)))
    console.print("\nQué hace cada opción:\n")
    for numero, (nombre, comando) in enumerate(opciones, start=1):
        console.print(
            f"[acento]{numero:>2}[/]  [bold]{escape(nombre)}[/]  "
            f"{escape((comando.help or '').strip())}",
            soft_wrap=True,
        )
        # dentro del submenú se escribe sin el nombre del grupo: «fecha», no «ordena fecha»
        console.print(Padding(f"Uso: [acento]{escape(uso([nombre], comando))}[/]", (0, 0, 0, 6)))
        tabla = tabla_parametros(comando)
        if tabla is not None:
            console.print(Padding(tabla, (0, 0, 0, 8)))
        extra = EXTRA.get(" ".join(camino + [nombre]))
        if extra:
            console.print(Padding(f"[pista]{escape(extra)}[/]", (0, 0, 0, 6)))
        console.print()


# ── La orden «manual» ──────────────────────────────────────────────────────


def manual_cmd(
    ctx: typer.Context,
    comando: list[str] | None = typer.Argument(
        None,
        help="Comando del que quieres solo su parte (ocupa, ordena fecha…). "
        "Sin nada, el manual entero.",
        show_default=False,
    ),
) -> None:
    """El manual completo: cómo se usa navaja, todos sus comandos, opciones y atajos."""
    raiz = ctx.find_root().command
    palabras = [p for p in (comando or []) if p.lower() not in ("navaja", "nav")]
    if not palabras:
        manual(raiz)
        return

    encontrado, nombres = resolver(raiz, palabras)
    if len(nombres) < len(palabras):
        pedido = " ".join(palabras)
        posibles = [" ".join(n) for n, _ in todos(raiz)]
        parecido = difflib.get_close_matches(pedido, posibles, n=1)
        pista = f" ¿Querías decir [acento]{parecido[0]}[/]?" if parecido else ""
        error_console.print(
            f"[error]No hay ningún comando «{escape(pedido)}».[/]{pista}", soft_wrap=True
        )
        raise typer.Exit(1)
    describir(nombres, encontrado)
    if nombres == ["acciones"]:  # y cómo se escribe acciones.json
        manual_acciones()


def registrar(app: typer.Typer) -> None:
    app.command(
        "manual",
        help="El manual completo: cómo se usa todo navaja, con opciones y atajos.",
        rich_help_panel=NAVAJA,
    )(manual_cmd)


# ── --help y errores en castellano ─────────────────────────────────────────
#
# Typer los escribe en inglés («Usage», «Missing argument»…). navaja cambia sus
# funciones por estas, que usan lo mismo que el manual. Se instalan en app.py.


def _prefijo() -> str:
    """En la terminal se escribe «navaja ocupa»; dentro del modo interactivo, «ocupa»."""
    from .. import interactivo

    return "" if interactivo.activo else "navaja "


def ayuda_terminal(obj: Any, ctx: Any, markup_mode: Any = None) -> None:
    """Lo que enseña ``--help``: lo mismo que el manual de ese comando."""
    nombres = ctx.command_path.split()[1:]
    prefijo = _prefijo()
    if not nombres:
        console.print(
            "[titulo]navaja[/] [pista]—[/] Caja de herramientas de terminal, en castellano."
        )
        console.print(
            "Uso: [acento]navaja[/] abre el menú · [acento]navaja <comando> \\[opciones][/] "
            "hace una cosa y vuelve a la terminal\n"
        )
        console.print(tabla_secciones(obj))
        console.print(
            "\n[pista]Ayuda de un comando: navaja ocupa --help · Todo explicado: navaja manual "
            "· Versión: navaja --version[/]"
        )
        return
    if es_grupo(obj):
        clave = " ".join(nombres)
        console.print(
            f"[titulo]{escape(clave)}[/] [pista]—[/] {escape((obj.help or '').strip())}",
            soft_wrap=True,
        )
        console.print(f"  Uso: [acento]{escape(prefijo + uso(nombres, obj))}[/]")
        if clave in EXTRA:
            console.print(Padding(f"[pista]{escape(EXTRA[clave])}[/]", (0, 0, 0, 2)))
        console.print()
        tabla = Table.grid(padding=(0, 2))
        tabla.add_column(style="acento", no_wrap=True)
        tabla.add_column()
        for nombre, comando in subcomandos(obj):
            tabla.add_row(nombre, escape(comando.get_short_help_str(90)))
        console.print(Padding(tabla, (0, 0, 0, 2)))
        primero = subcomandos(obj)[0][0] if subcomandos(obj) else "…"
        console.print(
            f"\n[pista]Ayuda de una: {escape(prefijo + clave)} {escape(primero)} --help[/]"
        )
        return
    describir(nombres, obj, prefijo=prefijo)


def _nombre_param(param: Any) -> str:
    if param.param_type_name == "argument":
        return (param.name or "").upper()
    return max(param.opts, key=len)


def _lista(cosas: list[str]) -> str:
    """«a», «a o b», «a, b o c»."""
    if len(cosas) < 2:
        return "".join(cosas)
    return f"{', '.join(cosas[:-1])} o {cosas[-1]}"


def _rango(texto: str) -> str:
    if m := re.fullmatch(r"x>=?(\S+)", texto):
        return f"tiene que ser {m[1]} o más"
    if m := re.fullmatch(r"x<=?(\S+)", texto):
        return f"tiene que ser {m[1]} o menos"
    if m := re.fullmatch(r"(\S+?)<=?x<=?(\S+)", texto):
        return f"tiene que estar entre {m[1]} y {m[2]}"
    return f"fuera de rango ({texto})"


def _traducir_valor(texto: str) -> str:
    if m := re.fullmatch(r"'(.*)' is not a valid (?:int|integer)(?: range)?\.", texto):
        return f"«{m[1]}» no es un número entero."
    if m := re.fullmatch(r"'(.*)' is not a valid float(?: range)?\.", texto):
        return f"«{m[1]}» no es un número."
    if m := re.fullmatch(r"'(.*)' is not one of (.*)\.", texto):
        opciones = re.findall(r"'([^']*)'", m[2])
        return f"«{m[1]}» no vale; elige {_lista(opciones)}."
    if m := re.fullmatch(r"(.*) is not in the range (.*)\.", texto):
        return f"{m[1]} no vale: {_rango(m[2])}."
    return texto


def mensaje_de_error(error: Any) -> str:
    """El mensaje de un error de uso de Typer, en castellano."""
    clase = type(error).__name__
    param = getattr(error, "param", None)
    texto = getattr(error, "message", "") or ""
    if clase == "MissingParameter":
        if param is None:
            return "Falta un valor obligatorio."
        if param.param_type_name == "argument":
            ayuda = (getattr(param, "help", None) or "").rstrip(".")
            return f"Falta {_nombre_param(param)}" + (f": {ayuda}." if ayuda else ".")
        return f"Falta la opción {_nombre_param(param)}."
    if clase == "NoSuchOption":
        mensaje = f"No existe la opción {error.option_name}."
        if error.possibilities:
            mensaje += f" ¿Querías decir {_lista(sorted(error.possibilities))}?"
        return mensaje
    if clase == "BadOptionUsage":
        if "does not take a value" in texto:
            return f"{error.option_name} no lleva valor: se pone o no se pone."
        if "requires" in texto:
            return f"Falta el valor de {error.option_name}."
        return texto
    if param is not None or clase == "BadParameter":
        detalle = _traducir_valor(texto)
        pista = getattr(error, "param_hint", None)
        if param is not None:
            return f"{_nombre_param(param)}: {detalle}"
        if pista:
            return f"{pista if isinstance(pista, str) else ' / '.join(pista)}: {detalle}"
        return detalle
    if m := re.fullmatch(r"Got unexpected extra arguments?(?:\(s\))? \((.*)\)", texto):
        return f"Sobra «{m[1]}». Si es un texto con espacios, ponlo entre comillas."
    if m := re.fullmatch(r"No such command '(.*?)'\.(?: Did you mean .*)?", texto):
        ctx = getattr(error, "ctx", None)
        posibles = list(ctx.command.list_commands(ctx)) if ctx is not None else []
        parecido = difflib.get_close_matches(m[1], posibles, n=1)
        return f"No existe «{m[1]}»." + (f" ¿Querías decir {parecido[0]}?" if parecido else "")
    if texto == "Missing command.":
        return "Falta elegir una opción."
    return texto


def error_terminal(error: Any) -> None:
    """Un error de uso: qué pasa, cómo se escribe y dónde está la ayuda."""
    if type(error).__name__ == "NoArgsIsHelpError":
        return  # ya se ha enseñado la ayuda
    error_console.print(f"[error]{escape(mensaje_de_error(error))}[/]", soft_wrap=True)
    ctx = getattr(error, "ctx", None)
    if ctx is None:
        return
    nombres = ctx.command_path.split()[1:]
    prefijo = _prefijo()
    ayuda = " ".join([*nombres, "--help"])
    error_console.print(
        f"[pista]Uso: {escape(prefijo + uso(nombres, ctx.command))} · "
        f"Ayuda: {escape(prefijo + ayuda)}[/]",
        soft_wrap=True,
    )


def cancelado() -> None:
    error_console.print("[aviso]Cancelado.[/]")


def instalar_en_castellano() -> None:
    """Cambia la ayuda y los errores de Typer (en inglés) por los de navaja."""
    from typer import rich_utils

    rich_utils.rich_format_help = ayuda_terminal
    rich_utils.rich_format_error = error_terminal
    rich_utils.rich_abort_error = cancelado
