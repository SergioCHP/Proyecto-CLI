"""navaja clave: contraseñas seguras, frases de contraseña y cómo de fuerte es una.

Todo con ``secrets`` (el azar para criptografía de Python). La contraseña que se comprueba
se escribe sin que se vea y no se guarda en ningún sitio.
"""

from __future__ import annotations

import math
import secrets
import string
import sys
from dataclasses import dataclass, field

import typer
from rich.markup import escape
from rich.text import Text

from ..comun import AJUSTE, PROGRAMACION, console, recuadro, resumen

SIMBOLOS = "!@#$%&*-_=+?"
PALABRAS = sorted(set("""
abeja abrigo aceite acera agosto agua aguila ahora aire ajedrez alambre alba albergue alegre
alfombra algodon almendra almohada altura amarillo amigo ancla angulo anillo antena anzuelo
arbol arena armario arroz arte asiento atlas aurora avena avion azucar azul bahia balcon
ballena banco bandera barco barro basura bateria baul bello beso biblioteca bicicleta bigote
blanco bloque boca bolsa bombero bosque bota botella brazo brisa broma brujula buho burbuja
caballo cabeza cable cactus cadena cafe caja calcetin calle calor cama camino campana campo
canal cancion canoa cantera capitan cara carbon cardo carpeta carta casa castillo cebolla
cereza cesta chaleco chispa chocolate cielo cine circo ciudad clavo cobre coche cohete cola
collar colina color cometa cometa concha cordero corona corral cosecha costa cristal cuaderno
cuchara cuerda cueva cumbre dado delfin desierto diamante diente disco dragon ducha duende
eco eclipse eje elefante enano enero escalera escoba espejo espiga estrella estufa faro feria
fideo fiesta flecha flor foca fresa frio fruta fuego fuente galleta gallo ganso garaje gato
gigante girasol globo golondrina goma gorila gorro grano granja grillo guante guitarra
hacha harina helado hielo hierba hilo hoja hongo horno huerto hueso huevo humo iglu imagen
isla jabon jardin jarra jirafa joya juego jungla ladrillo lago lampara lana lapiz largo lata
laurel leche lechuga lemur leon letra libro lima limon linterna llave lluvia lobo loro luna
madera maleta mango manta manzana mapa mar marea mariposa martillo mascara medalla melon
mesa miel molino moneda montana motor muelle mundo museo musica naranja nariz nave niebla
nido nieve noche norte nube nuez oasis ola oliva olmo onda oro oso otono oveja pajaro pala
paloma pan panda papel paraguas parque pasillo pastel patata pato peine pelota pera perro
pez piano piedra pimienta pino pinza pirata planeta plata playa pluma polo puente puerta
pulpo queso radio rana rayo reloj remo rio roble roca rosa rueda sal salto sandia selva
semilla silla sirena sol sombra sopa tambor taza techo tejado telar tigre tijera tinta
tomate torre tortuga trigo trompeta trueno tulipan uva vaca valle vapor vela ventana verano
viento violin volcan yate yogur zanahoria zapato zorro
""".split()))
"""Palabras fáciles de escribir (sin tildes ni ñ) para las frases de contraseña."""

COMUNES = {
    "123456", "1234567", "12345678", "123456789", "1234567890", "password", "contraseña",
    "contrasena", "qwerty", "qwerty123", "abc123", "111111", "000000", "123123", "iloveyou",
    "admin", "admin123", "welcome", "letmein", "monkey", "dragon", "football", "futbol",
    "barcelona", "realmadrid", "princesa", "tequiero", "hola", "hola123", "1q2w3e4r",
    "asdfgh", "zxcvbn", "passw0rd", "p@ssw0rd", "sergio", "superman", "batman", "654321",
}
"""Algunas de las contraseñas más usadas: son lo primero que se prueba."""

FILAS_TECLADO = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890")
INTENTOS_POR_SEGUNDO = 10_000_000_000
"""Lo que prueba un ordenador con buena tarjeta gráfica contra una contraseña robada."""

NIVELES = [
    (28, "muy débil", "error"),
    (36, "débil", "error"),
    (60, "regular", "aviso"),
    (80, "fuerte", "ok"),
    (math.inf, "muy fuerte", "logro"),
]


# ── Crear ──────────────────────────────────────────────────────────────────


def nueva(largo: int = 16, simbolos: bool = True) -> str:
    """Una contraseña al azar con al menos una minúscula, una mayúscula, un número y
    (si se quieren) un símbolo."""
    grupos = [string.ascii_lowercase, string.ascii_uppercase, string.digits]
    if simbolos:
        grupos.append(SIMBOLOS)
    todos = "".join(grupos)
    while True:
        clave = "".join(secrets.choice(todos) for _ in range(largo))
        if largo < len(grupos) or all(any(c in grupo for c in clave) for grupo in grupos):
            return clave


def frase(palabras: int = 5, separador: str = "-") -> str:
    """Palabras al azar de la lista y un número al final: «nube-cobre-faro-pinza-tigre-47»."""
    elegidas = [secrets.choice(PALABRAS) for _ in range(palabras)]
    return separador.join(elegidas + [str(secrets.randbelow(90) + 10)])


def bits_de_frase(palabras: int) -> float:
    return palabras * math.log2(len(PALABRAS)) + math.log2(90)


# ── Medir ──────────────────────────────────────────────────────────────────


@dataclass
class Fuerza:
    bits: float
    nivel: str
    estilo: str
    tiempo: str
    consejos: list[str] = field(default_factory=list)


def tamano_alfabeto(clave: str) -> int:
    tamano = 0
    if any(c.islower() for c in clave):
        tamano += 26
    if any(c.isupper() for c in clave):
        tamano += 26
    if any(c.isdigit() for c in clave):
        tamano += 10
    if any(not c.isalnum() and c.isascii() for c in clave):
        tamano += 33
    if any(not c.isascii() for c in clave):
        tamano += 20  # ñ, tildes…
    return max(tamano, 1)


def sigue_patron(anterior: str, actual: str) -> bool:
    """¿Es la misma letra, la siguiente (abc, 123) o la de al lado en el teclado (qwe)?"""
    a, b = anterior.lower(), actual.lower()
    if a == b or abs(ord(a) - ord(b)) == 1:
        return True
    return any(a + b in fila or b + a in fila for fila in FILAS_TECLADO)


def largo_util(clave: str) -> tuple[int, list[str]]:
    """Los caracteres que de verdad cuentan: «aaaa», «1234» y «qwerty» valen casi como uno,
    y una palabra del diccionario, como una sola letra. Devuelve también qué se ha visto."""
    vistos: list[str] = []
    minuscula = clave.lower()
    for palabra in sorted(PALABRAS, key=len, reverse=True):
        if len(palabra) >= 4 and palabra in minuscula:
            minuscula = minuscula.replace(palabra, "\0")
            if "palabra" not in vistos:
                vistos.append("palabra")
    utiles = 0
    seguidos = 0
    for posicion, caracter in enumerate(minuscula):
        if posicion and caracter != "\0" and minuscula[posicion - 1] != "\0" and sigue_patron(minuscula[posicion - 1], caracter):
            seguidos += 1
            if seguidos == 2 and "patron" not in vistos:
                vistos.append("patron")
            continue
        seguidos = 0
        utiles += 1
    return utiles, vistos


def tiempo_para(bits: float) -> str:
    """Lo que se tarda de media en adivinarla probando todas (la mitad de las posibles)."""
    segundos = 2 ** bits / 2 / INTENTOS_POR_SEGUNDO
    for limite, nombre, plural in (
        (60, "segundo", "segundos"),
        (3600, "minuto", "minutos"),
        (86400, "hora", "horas"),
        (86400 * 365, "día", "días"),
    ):
        if segundos < limite:
            divisor = {"segundo": 1, "minuto": 60, "hora": 3600, "día": 86400}[nombre]
            cantidad = segundos / divisor
            if nombre == "segundo" and cantidad < 1:
                return "al momento"
            cantidad = round(cantidad)
            return f"{cantidad} {nombre if cantidad == 1 else plural}"
    anios = segundos / (86400 * 365)
    if anios < 1000:
        anios = round(anios)
        return f"{anios} año" + ("" if anios == 1 else "s")
    if anios < 1_000_000:
        return f"{round(anios / 1000)} mil años"
    if anios < 1_000_000_000:
        return f"{round(anios / 1_000_000)} millones de años"
    return "más de mil millones de años"


def medir(clave: str) -> Fuerza:
    """Cuántos bits de azar tiene de verdad, cuánto se tarda en adivinarla y qué mejorar."""
    consejos: list[str] = []
    if clave.lower() in COMUNES or clave.lower().rstrip("0123456789!.") in COMUNES:
        bits = 10.0
        consejos.append("Es de las contraseñas más usadas: es lo primero que se prueba.")
    else:
        utiles, vistos = largo_util(clave)
        bits = utiles * math.log2(tamano_alfabeto(clave))
        if "palabra" in vistos:
            consejos.append("Lleva palabras del diccionario: mejor varias al azar que una.")
        if "patron" in vistos:
            consejos.append("Lleva letras repetidas o seguidas (aaa, 123, qwerty): casi no suman.")
    if len(clave) < 12:
        consejos.append("Usa al menos 12 caracteres: el largo es lo que más cuenta.")
    tipos = [
        (any(c.isupper() for c in clave), "mayúsculas"),
        (any(c.isdigit() for c in clave), "números"),
        (any(not c.isalnum() for c in clave), "símbolos"),
    ]
    faltan = [nombre for tiene, nombre in tipos if not tiene]
    if faltan and len(clave) < 20:
        consejos.append("Añade " + (" y ".join(faltan) if len(faltan) < 3 else "mayúsculas, números y símbolos") + ".")
    for limite, nivel, estilo in NIVELES:
        if bits < limite:
            break
    return Fuerza(bits, nivel, estilo, tiempo_para(bits), consejos)


# ── Órdenes ────────────────────────────────────────────────────────────────


def nueva_orden(
    largo: int = typer.Option(16, "--largo", "-l", min=4, max=256, help="Cuántos caracteres.", rich_help_panel=AJUSTE),
    sin_simbolos: bool = typer.Option(
        False, "--sin-simbolos", help="Solo letras y números (para webs que no aceptan símbolos).", rich_help_panel=AJUSTE
    ),
    cuantas: int = typer.Option(1, "--cuantas", "-n", min=1, max=100, help="Cuántas contraseñas."),
) -> None:
    """Una contraseña segura al azar, con mayúsculas, minúsculas, números y símbolos."""
    claves = [nueva(largo, not sin_simbolos) for _ in range(cuantas)]
    for clave in claves:
        console.print(Text(clave), highlight=False)
    if console.is_terminal:
        fuerza = medir(claves[0])
        console.print(f"[pista]{fuerza.nivel.capitalize()}: adivinarla llevaría {fuerza.tiempo}.[/]")


def frase_orden(
    palabras: int = typer.Option(5, "--palabras", "-p", min=3, max=20, help="Cuántas palabras.", rich_help_panel=AJUSTE),
    separador: str = typer.Option("-", "--separador", help="Lo que va entre las palabras.", rich_help_panel=AJUSTE),
) -> None:
    """Una frase de contraseña: palabras al azar, fácil de recordar y difícil de adivinar."""
    console.print(Text(frase(palabras, separador)), highlight=False)
    if console.is_terminal:
        bits = bits_de_frase(palabras)
        console.print(
            f"[pista]{len(PALABRAS)} palabras posibles en cada hueco: unos {round(bits)} bits; "
            f"adivinarla llevaría {tiempo_para(bits)}.[/]"
        )


def fuerza_orden() -> None:
    """Cómo de fuerte es una contraseña. Se escribe sin que se vea y no se guarda."""
    try:
        if sys.stdin.isatty():
            clave = console.input("[pista]Escribe la contraseña (no se ve ni se guarda):[/] ", password=True)
        else:  # «… | navaja clave fuerza»: se lee la primera línea
            clave = sys.stdin.readline().rstrip("\r\n")
    except (KeyboardInterrupt, EOFError):
        console.print()
        return
    if not clave:
        console.print("[aviso]No has escrito nada.[/]")
        return
    fuerza = medir(clave)
    filas = [
        ("Nivel", f"[{fuerza.estilo}]{fuerza.nivel}[/]"),
        ("Largo", str(len(clave))),
        ("Azar", f"unos {round(fuerza.bits)} bits"),
        ("Adivinarla", escape(fuerza.tiempo)),
    ]
    partes: list = [resumen(filas)]
    if fuerza.consejos:
        partes.append(
            Text.from_markup("\n".join(f"[aviso]·[/] {escape(c)}" for c in fuerza.consejos))
        )
    partes.append(
        Text.from_markup(
            f"[pista]Con un ordenador que prueba {INTENTOS_POR_SEGUNDO:,} contraseñas por segundo. "
            "Para recordarla mejor: navaja clave frase.[/]".replace(",", ".")
        )
    )
    console.print(recuadro("Fuerza de la contraseña", *partes))


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(help="Contraseñas seguras y cómo de fuerte es la tuya.", no_args_is_help=True)
    sub.command("nueva", help="Una contraseña segura al azar.")(nueva_orden)
    sub.command("frase", help="Una frase de contraseña: palabras al azar, fácil de recordar.")(frase_orden)
    sub.command("fuerza", help="Cómo de fuerte es una contraseña (sin que se vea).")(fuerza_orden)
    app.add_typer(sub, name="clave", rich_help_panel=PROGRAMACION)
