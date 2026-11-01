"""Ayuda de navaja: la corta de cada comando y la orden «manual» con todo.

La parte de los comandos se genera a partir de los propios comandos de Typer
(descripción, argumentos, opciones y valores por defecto), así que nunca se
queda desfasada. Lo que no está en el código (modo interactivo, seguridad,
datos, códigos de salida) va escrito aquí.
"""

from __future__ import annotations

import difflib
from enum import Enum
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape
from rich.padding import Padding
from rich.table import Table

from .. import __version__
from ..comun import TEMAS, console, directorio_datos, error_console
from .ocupa import BASURA_ARCHIVOS, BASURA_DIRS, BASURA_PATRONES
from .ordena import NOMBRES

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
    """Todos los comandos y subcomandos, en orden, con su camino (``["ordena", "aplicar"]``)."""
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
        return " ".join(partes + ["<subcomando>"])
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
        if valor_texto(defecto) == ".":
            return "opcional · por defecto: . (la carpeta actual)"
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
        "Considera basura las carpetas "
        + ", ".join(sorted(BASURA_DIRS))
        + "; los archivos "
        + ", ".join(sorted(BASURA_ARCHIVOS))
        + "; y los que encajan con "
        + ", ".join(sorted(BASURA_PATRONES))
        + "."
    ),
    "ordena": (
        "Por extensión, cada archivo va a una carpeta según su tipo: "
        + ", ".join(NOMBRES.values())
        + ". Por fecha, a AÑO/MES (por ejemplo 2026/10). Si ya hay un archivo con ese "
        "nombre, añade (1), (2)… Solo se puede deshacer la última organización."
    ),
    "ordena categorias": "Enseña qué extensiones van a cada carpeta.",
    "renombra": (
        "El patrón es una expresión regular de Python. Sin --completo solo cambia el "
        "nombre y la extensión se queda igual. Ejemplo: IMG_(\\d+) → foto_\\1 convierte "
        "IMG_1234.jpg en foto_1234.jpg. Si dos archivos acabarían con el mismo nombre, o "
        "el nombre nuevo ya existe, lo marca como conflicto y no lo toca."
    ),
    "duplicados": (
        "Compara el contenido de los archivos (SHA-256), no el nombre: dos archivos son "
        "duplicados aunque se llamen distinto. Los enlaces duros no cuentan dos veces."
    ),
    "duplicados borrar": "No borra: mueve las copias a la papelera de navaja.",
    "duplicados vaciar": "Esto sí borra para siempre; no se puede deshacer.",
    "notas": (
        "Una nota con --url es un enlace: «notas abrir» lo abre en el navegador. Sin "
        "--texto ni --url, «notas agregar» abre tu editor (Bloc de notas en Windows, o "
        "el de la variable EDITOR)."
    ),
    "tema": "Temas disponibles: " + ", ".join(TEMAS) + ".",
    "manual": "Sin nada, este manual entero. Con un comando, solo su parte.",
}


# ── Pintar ─────────────────────────────────────────────────────────────────


def describir(nombres: list[str], comando: Any, sangria: int = 0) -> None:
    """Un comando con su uso, parámetros y notas; si es un grupo, también sus subcomandos."""
    clave = " ".join(nombres)

    def imprimir(cosa: Any, extra: int = 0) -> None:
        console.print(Padding(cosa, (0, 0, 0, sangria + extra)))

    ayuda = escape((comando.help or "").strip())
    imprimir(f"[titulo]{escape(clave)}[/] [pista]—[/] {ayuda}")
    imprimir(f"Uso: [acento]{escape(uso(nombres, comando))}[/]", 2)
    tabla = tabla_parametros(comando)
    if tabla is not None:
        imprimir(tabla, 4)
    if clave in EXTRA:
        imprimir(f"[pista]{escape(EXTRA[clave])}[/]", 2)
    console.print()
    if es_grupo(comando):
        for nombre, sub in subcomandos(comando):
            describir(nombres + [nombre], sub, sangria + 2)


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
     "submenú; si no, lo ejecuta en la carpeta actual y solo pregunta lo obligatorio. "
     "Debajo del resultado te dice qué opciones tiene."),
    ("un comando", "Igual que en la terminal pero sin «navaja» delante: ocupa -n 5, "
     "ordena aplicar ~/Descargas. Si le falta algo obligatorio, lo pregunta."),
    ("ayuda · ?", "Explica lo que puedes hacer donde estás: en el menú principal, todas las "
     "opciones; dentro de una opción (config, ordena…), esa opción con las suyas. "
     "También vale help."),
    ("menu · menú", "Vuelve a enseñar el menú (dentro de un submenú, el de ese grupo)."),
    ("ayuda ocupa · ocupa ? · ? 2", "Ayuda corta de un comando: qué hace, cómo se escribe y "
     "sus opciones (también «ayuda ordena aplicar»)."),
    ("manual", "Este manual entero. «manual ocupa» enseña solo la parte de ese comando."),
    ("cd RUTA · cd .. · cd", "Cambia de carpeta; «cd» solo dice dónde estás. Al salir vuelves "
     "a la carpeta desde la que entraste."),
    ("pwd", "Dice en qué carpeta estás."),
    ("ls · dir", "Atajos de «listar»."),
    ("navaja … · nav …", "También valen: «navaja ocupa» es lo mismo que «ocupa»."),
    ("cls · clear", "Limpia la pantalla."),
    ("Intro · 0 · volver", "En un submenú, vuelve al menú principal."),
    ("salir · exit · quit · 0", "Termina y vuelve a la terminal normal (0 solo en el menú principal)."),
    ("Ctrl+C", "Cancela la pregunta o la orden en curso; en el menú principal, sale."),
    ("↑ ↓", "Recuperan lo que escribiste antes."),
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

    seccion("4. Seguridad")
    console.print(
        tabla_dos(
            [
                ("[s/n]", "Nada se borra ni se mueve sin enseñarte antes qué va a pasar y "
                 "preguntarte. Vale s, sí, n o no. Con --si no pregunta."),
                ("previsualizar", "ordena y renombra lo tienen: enseñan el plan sin tocar nada."),
                ("deshacer", "ordena y renombra revierten su última operación."),
                ("--seco", "limpia solo enseña lo que borraría."),
                ("papelera", "duplicados borrar mueve las copias a la papelera de navaja; "
                 "duplicados restaurar las devuelve; duplicados vaciar las borra para siempre."),
                ("sin sobrescribir", "ordena y duplicados añaden (1), (2)… si el nombre ya "
                 "existe; renombra marca esos casos como conflicto y no los toca."),
            ]
        )
    )

    seccion("5. Dónde guarda sus datos")
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
                ("ordena_deshacer.json", "La última organización, para deshacerla."),
                ("renombra_deshacer.json", "El último renombrado, para deshacerlo."),
                ("duplicados_deshacer.json", "De dónde salió cada copia de la papelera, "
                 "para restaurarla."),
                ("papelera/", "Las copias que quita duplicados borrar."),
            ]
        )
    )

    seccion("6. Para scripts")
    console.print(
        tabla_dos(
            [
                ("código 0", "Todo bien (también si respondes «n» a una confirmación)."),
                ("código 1", "Algo ha fallado: una ruta que no existe, un tema que no existe…"),
                ("código 2", "Uso incorrecto: falta un argumento, una opción no existe o la "
                 "expresión regular no es válida."),
                ("-v · --version", "Muestra la versión: navaja --version."),
                ("--help", "En cualquier comando, la ayuda técnica en el formato estándar "
                 "de Typer: navaja ocupa --help."),
                ("navaja manual > manual.txt", "Guarda este manual en un archivo de texto."),
            ]
        )
    )
    console.print(
        "\n[pista]Ayuda corta de un comando dentro de navaja: [/][acento]ayuda ocupa[/][pista]. "
        "Su parte de este manual: [/][acento]manual ocupa[/][pista] "
        "(o [/][acento]navaja manual ocupa[/][pista] desde la terminal).[/]"
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
    «aplicar» y no «ordena aplicar».
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
     "y solo pregunta lo obligatorio."),
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
        # dentro del submenú se escribe sin el nombre del grupo: «aplicar», no «ordena aplicar»
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
        help="Comando del que quieres solo su parte (ocupa, ordena aplicar…). "
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


def registrar(app: typer.Typer) -> None:
    app.command(
        "manual", help="El manual completo: cómo se usa todo navaja, con opciones y atajos."
    )(manual_cmd)
