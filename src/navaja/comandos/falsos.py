"""navaja falsos: datos de prueba realistas en español, para rellenar la base de datos de un
proyecto en segundos.

Nombres, apellidos, emails, DNI (con su letra bien calculada), teléfonos, direcciones…
en una tabla, en CSV, en JSON o como ``INSERT`` de SQL. Usa Faker con el idioma
``es_ES`` (extra opcional ``falsos``). Con ``--semilla`` salen siempre los mismos.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import typer
from rich.markup import escape

from ..comun import AJUSTE, PROGRAMACION, bonita, console, crear_tabla, ruta_libre
from ..errores import NavajaError
from ..filtros import sin_tildes
from ..lotes import fallar, libreria

LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"
MAXIMO = 10_000
POR_DEFECTO = ["id", "nombre", "apellidos", "email", "dni", "telefono", "ciudad"]
NOMBRE_TABLA = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class Formato(str, Enum):
    tabla = "tabla"
    csv = "csv"
    json = "json"
    sql = "sql"


def letra_dni(numero: int) -> str:
    """La letra del DNI: el número módulo 23, en la tabla oficial."""
    return LETRAS_DNI[numero % 23]


def dni_valido(dni: str) -> bool:
    coincide = re.fullmatch(r"(\d{8})([A-Z])", dni.strip().upper())
    return bool(coincide) and letra_dni(int(coincide[1])) == coincide[2]


def _usuario(nombre: str, apellidos: str) -> str:
    """«María José», «Gómez Ruiz» → «mariajose.gomez» (sin tildes, eñes ni espacios)."""
    limpio = lambda texto: re.sub(r"[^a-z]", "", sin_tildes(texto).lower())  # noqa: E731
    return f"{limpio(nombre)}.{limpio(apellidos.split()[0])}"


def generador(semilla: int | None) -> Any:
    faker = libreria("faker", "Faker", "falsos", "generar datos de prueba")
    falso = faker.Faker("es_ES")
    if semilla is not None:
        falso.seed_instance(semilla)
    return falso


def campos_disponibles() -> dict[str, tuple[str, str]]:
    """campo → (tipo SQL, descripción)."""
    return {
        "id": ("INTEGER PRIMARY KEY", "1, 2, 3…"),
        "nombre": ("TEXT", "Lucía, Javier…"),
        "apellidos": ("TEXT", "dos apellidos"),
        "email": ("TEXT", "sacado del nombre, sin repetir"),
        "usuario": ("TEXT", "lucia.garcia"),
        "dni": ("TEXT", "con la letra bien calculada"),
        "telefono": ("TEXT", "móvil de 9 cifras"),
        "direccion": ("TEXT", "calle y número"),
        "ciudad": ("TEXT", "una ciudad española"),
        "cp": ("TEXT", "código postal"),
        "provincia": ("TEXT", "una provincia"),
        "nacimiento": ("TEXT", "fecha AAAA-MM-DD, de 18 a 80 años"),
        "empresa": ("TEXT", "nombre de empresa"),
        "puesto": ("TEXT", "trabajo"),
        "sueldo": ("INTEGER", "euros al año"),
        "alta": ("TEXT", "fecha de los últimos 3 años"),
        "activo": ("INTEGER", "1 o 0"),
    }


def leer_campos(texto: str | None) -> list[str]:
    if not texto:
        return list(POR_DEFECTO)
    disponibles = campos_disponibles()
    campos: list[str] = []
    for parte in texto.split(","):
        campo = sin_tildes(parte.strip().lower())
        if not campo:
            continue
        if campo not in disponibles:
            raise NavajaError(
                f"No hay campo «{parte.strip()}». Los que hay: {', '.join(disponibles)}."
            )
        if campo not in campos:
            campos.append(campo)
    if not campos:
        raise NavajaError("Di al menos un campo: --campos nombre,email")
    return campos


def generar(cantidad: int, campos: list[str], semilla: int | None) -> list[dict[str, Any]]:
    falso = generador(semilla)
    filas: list[dict[str, Any]] = []
    emails: set[str] = set()
    dnis: set[int] = set()
    for numero in range(1, cantidad + 1):
        nombre = falso.first_name()
        apellidos = f"{falso.last_name()} {falso.last_name()}"
        usuario = _usuario(nombre, apellidos)
        valores: dict[str, Callable[[], Any]] = {
            "id": lambda: numero,
            "nombre": lambda: nombre,
            "apellidos": lambda: apellidos,
            "usuario": lambda: usuario,
            "telefono": lambda: f"6{falso.random_number(digits=8, fix_len=True)}",
            "direccion": falso.street_address,
            "ciudad": falso.city,
            "cp": falso.postcode,
            "provincia": falso.state,
            "nacimiento": lambda: falso.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
            "empresa": falso.company,
            "puesto": falso.job,
            "sueldo": lambda: falso.random_int(16, 60) * 1000,
            "alta": lambda: falso.date_between(start_date="-3y", end_date="today").isoformat(),
            "activo": lambda: int(falso.boolean(chance_of_getting_true=80)),
        }
        fila: dict[str, Any] = {}
        for campo in campos:
            if campo == "email":
                base, dominio = usuario, falso.free_email_domain()
                email, extra = f"{base}@{dominio}", 2
                while email in emails:
                    email, extra = f"{base}{extra}@{dominio}", extra + 1
                emails.add(email)
                fila[campo] = email
            elif campo == "dni":
                cifras = falso.random_number(digits=8, fix_len=True)
                while cifras in dnis:
                    cifras = falso.random_number(digits=8, fix_len=True)
                dnis.add(cifras)
                fila[campo] = f"{cifras:08d}{letra_dni(cifras)}"
            else:
                fila[campo] = valores[campo]()
        filas.append(fila)
    return filas


def a_csv(filas: list[dict[str, Any]], campos: list[str], separador: str) -> str:
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=campos, delimiter=separador, lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(filas)
    return salida.getvalue()


def a_json(filas: list[dict[str, Any]]) -> str:
    return json.dumps(filas, ensure_ascii=False, indent=2) + "\n"


def literal_sql(valor: Any) -> str:
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def a_sql(filas: list[dict[str, Any]], campos: list[str], tabla: str) -> str:
    tipos = campos_disponibles()
    columnas = ",\n".join(f"    {campo} {tipos[campo][0]}" for campo in campos)
    lineas = [
        f"-- Datos de prueba de navaja falsos ({date.today().isoformat()})",
        f"CREATE TABLE IF NOT EXISTS {tabla} (\n{columnas}\n);",
        "",
    ]
    lista = ", ".join(campos)
    for fila in filas:
        valores = ", ".join(literal_sql(fila[c]) for c in campos)
        lineas.append(f"INSERT INTO {tabla} ({lista}) VALUES ({valores});")
    return "\n".join(lineas) + "\n"


def falsos(
    cantidad: int = typer.Option(
        10, "--cantidad", "-n", min=1, max=MAXIMO, help="Cuántas filas.", rich_help_panel=AJUSTE
    ),
    campos: str | None = typer.Option(
        None, "--campos", "-c",
        help="Qué columnas, separadas por comas (nombre,email,dni…). Con --lista, todas las que hay.",
        rich_help_panel=AJUSTE,
    ),
    formato: Formato = typer.Option(
        Formato.tabla, "--formato", "-f", help="tabla (para ver), csv, json o sql (INSERT).",
        rich_help_panel=AJUSTE,
    ),
    guardar: Path | None = typer.Option(
        None, "--guardar", "-g", help="Lo guarda en este archivo (nunca pisa uno que ya existe).",
        rich_help_panel=AJUSTE,
    ),
    tabla: str = typer.Option(
        "personas", "--tabla", "-t", help="Nombre de la tabla en el SQL.", rich_help_panel=AJUSTE
    ),
    separador: str = typer.Option(
        ";", "--separador", help="Separador del CSV: ; (Excel en español) o ,", rich_help_panel=AJUSTE
    ),
    semilla: int | None = typer.Option(
        None, "--semilla", help="Con el mismo número salen siempre los mismos datos.",
        rich_help_panel=AJUSTE,
    ),
    lista: bool = typer.Option(False, "--lista", help="Enseña los campos que se pueden pedir."),
    simular: bool = typer.Option(
        False, "--simular", help="Con --guardar, dice dónde lo guardaría sin guardar nada.",
        rich_help_panel=AJUSTE,
    ),
) -> None:
    """Datos de prueba en español (nombres, DNI, emails…) en tabla, CSV, JSON o INSERT de SQL."""
    try:
        if lista:
            resultado = crear_tabla(["Campo", "Qué sale"])
            for campo, (_, descripcion) in campos_disponibles().items():
                marca = " [pista](por defecto)[/]" if campo in POR_DEFECTO else ""
                resultado.add_row(campo + marca, descripcion)
            console.print(resultado)
            return
        elegidos = leer_campos(campos)
        if not NOMBRE_TABLA.fullmatch(tabla):
            raise NavajaError(f"«{tabla}» no vale como nombre de tabla: letras, números y _, sin empezar por número.")
        if len(separador) != 1:
            raise NavajaError("El separador tiene que ser un solo carácter: ; o ,")
        if guardar and formato is Formato.tabla:
            formato = {".csv": Formato.csv, ".json": Formato.json, ".sql": Formato.sql}.get(
                guardar.suffix.lower(), Formato.csv
            )

        filas = generar(cantidad, elegidos, semilla)

        if formato is Formato.tabla:
            resultado = crear_tabla(elegidos)
            for fila in filas[:50]:
                resultado.add_row(*(escape(str(fila[c])) for c in elegidos))
            console.print(resultado)
            if len(filas) > 50:
                console.print(f"[pista]… y {len(filas) - 50} más. Para todas: -f csv, -f json o -f sql (o --guardar).[/]")
            return

        texto = {
            Formato.csv: lambda: a_csv(filas, elegidos, separador),
            Formato.json: lambda: a_json(filas),
            Formato.sql: lambda: a_sql(filas, elegidos, tabla),
        }[formato]()

        if guardar is None:
            typer.echo(texto, nl=False)
            return
        destino = ruta_libre(guardar.expanduser())
        if not destino.parent.is_dir():
            raise NavajaError(f"No existe la carpeta {bonita(destino.parent)}.")
        if simular:
            console.print(f"[aviso]Simulado:[/] se guardarían {len(filas)} filas en {escape(bonita(destino))} ({formato.value}).", soft_wrap=True)
            return
        try:
            # CSV con BOM: Excel en Windows reconoce las tildes
            destino.write_text(texto, encoding="utf-8-sig" if formato is Formato.csv else "utf-8")
        except OSError as error:
            raise NavajaError(f"No se pudo guardar {bonita(destino)}: {error.strerror or error}") from error
        console.print(f"[ok]✔ {len(filas)} filas en {escape(bonita(destino))}[/] [pista]({formato.value})[/]", soft_wrap=True)
        if formato is Formato.sql:
            console.print(f"[pista]Para meterlas en una base: navaja sql clase.db --archivo \"{escape(str(destino))}\" --crear[/]", soft_wrap=True)
    except NavajaError as error:
        fallar(error)


def registrar(app: typer.Typer) -> None:
    app.command(
        "falsos", help="Datos de prueba en español: CSV, JSON o INSERT.",
        rich_help_panel=PROGRAMACION,
    )(falsos)
