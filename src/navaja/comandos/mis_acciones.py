"""«acciones»: tus tareas guardadas en acciones.json, con nombre, para lanzarlas cuando quieras.

Aquí solo hay órdenes y salida. Leer y comprobar el archivo es cosa de ``esquema``;
elegir archivos, de ``Motor``; y qué le pasa a cada archivo, de cada clase de
``acciones``. Todos los errores previsibles son ``NavajaError``: se capturan una vez
y se sale con su código (1 al ejecutar, 3 si acciones.json está mal).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import NoReturn

import typer
from rich.markup import escape
from rich.panel import Panel

from .. import esquema
from ..acciones import Accion, AccionDeArchivos, Resultado, Rutina, relativa
from ..comun import (
    abrir_en_editor,
    cargar_acciones,
    como_se_escribe,
    confirmar,
    console,
    crear_tabla,
    cuantos,
    error_console,
    guardar_acciones,
    limpiar_acciones,
    ruta_libre,
)
from ..errores import ConfigError, NavajaError
from ..filtros import OPCION_SI, OPCION_SIMULAR
from ..motor import Motor

OPCION_CONFIG = typer.Option(
    None,
    "--config",
    help="Usar este archivo de acciones (si no, acciones.json de la carpeta actual o de tus datos).",
    show_default=False,
)


def fallar(error: NavajaError, ruta: Path | None = None) -> NoReturn:
    """Un error previsible: el mensaje en rojo (sin traza) y su código de salida."""
    error_console.print(f"[error]✘ {escape(str(error))}[/]", soft_wrap=True)
    if ruta is not None and isinstance(error, ConfigError):
        error_console.print(f"[pista]En {escape(str(ruta))}[/]", soft_wrap=True)
    raise typer.Exit(error.codigo_salida)


def cargar(config: Path | None) -> tuple[Path, Motor]:
    ruta = None
    try:
        ruta = esquema.buscar(config)
        return ruta, Motor(esquema.cargar(ruta))
    except NavajaError as error:
        fallar(error, ruta)


def bonita(ruta: Path) -> str:
    """Con ~ en vez de la carpeta personal: ~/Pictures/Imagenes IA."""
    try:
        return str(Path("~") / ruta.relative_to(Path.home()))
    except ValueError:
        return str(ruta)


def donde(accion: Accion) -> str:
    if isinstance(accion, Rutina):
        return " → ".join(accion.pasos)
    assert isinstance(accion, AccionDeArchivos)
    return accion.datos.get("carpeta", "(la carpeta actual)")


# ── ver y validar ──────────────────────────────────────────────────────────


def ver(config: Path | None = OPCION_CONFIG) -> None:
    """Lista tus acciones: número, nombre, tipo y qué hace."""
    ruta, motor = cargar(config)
    tabla = crear_tabla(["#", "Nombre", "Tipo", "Qué hace", "Dónde"])
    for numero, (nombre, accion) in enumerate(motor.acciones.items(), start=1):
        tabla.add_row(
            str(numero),
            f"[acento]{escape(nombre)}[/]",
            accion.tipo,
            escape(accion.descripcion),
            f"[pista]{escape(donde(accion))}[/]",
        )
    console.print(tabla)
    console.print(f"[pista]Archivo: {escape(str(ruta))}[/]", soft_wrap=True)
    console.print(
        f"[pista]Para hacer una: {escape(como_se_escribe('acciones ejecutar <nombre o número>'))} "
        "(con --simular, solo mira)[/]",
        soft_wrap=True,
    )


def comprobar_y_contar(ruta: Path) -> None:
    """Lo que dicen «validar» y «editar» al acabar: ✔ y cuántas, o el error (código 3)."""
    try:
        acciones = esquema.cargar(ruta)
    except ConfigError as error:
        fallar(error, ruta)
    console.print(
        f"[ok]✔ {cuantos(len(acciones), 'acción válida', 'acciones válidas')}[/] "
        f"[pista]en {escape(str(ruta))}[/]",
        soft_wrap=True,
    )
    for aviso in esquema.avisos(acciones):
        console.print(f"[aviso]Ojo: {escape(aviso)}[/]", soft_wrap=True)


def validar(config: Path | None = OPCION_CONFIG) -> None:
    """Comprueba que acciones.json está bien escrito, sin tocar ningún archivo."""
    try:
        ruta = esquema.buscar(config)
    except ConfigError as error:
        fallar(error)
    comprobar_y_contar(ruta)


# ── ejecutar ───────────────────────────────────────────────────────────────


def mostrar_plan(accion: AccionDeArchivos, carpeta: Path, plan: list[Resultado]) -> None:
    pendientes = [r for r in plan if r.estado == "pendiente"]
    saltados = [r for r in plan if r.estado == "saltado"]
    resumen = (
        f"[pista]{escape(accion.descripcion)}[/]\n"
        f"[pista]En[/] {escape(bonita(carpeta.resolve()))}\n"
        f"[bold]{cuantos(len(pendientes), 'archivo')}[/] {accion.para}"
    )
    if saltados:
        resumen += f" · [aviso]{len(saltados)} no se {'toca' if len(saltados) == 1 else 'tocan'}[/]"
    console.print(Panel(resumen, title=escape(accion.nombre), border_style="marco", expand=False))
    if not plan:
        return

    tabla = crear_tabla(["Archivo", accion.columna] + (["Por qué no"] if saltados else []))
    limite = 100
    for resultado in (pendientes + saltados)[:limite]:
        if resultado.destino is None:
            va_a = "papelera de navaja"
        elif accion.columna == "Nombre nuevo":
            va_a = resultado.destino.name
        else:
            try:
                va_a = str(resultado.destino.relative_to(carpeta))
            except ValueError:
                va_a = bonita(resultado.destino)
        estilo = "ok" if resultado.estado == "pendiente" else "pista"
        fila = [escape(str(relativa(resultado.origen, carpeta))), f"[{estilo}]{escape(va_a)}[/]"]
        if saltados:
            fila.append(f"[aviso]{escape(resultado.motivo)}[/]" if resultado.estado == "saltado" else "")
        tabla.add_row(*fila)
    console.print(tabla)
    if len(plan) > limite:
        console.print(f"[pista]Mostrando {limite} de {len(plan)}.[/]")


def ejecutar(
    nombre: str = typer.Argument(
        ..., help="Nombre de la acción, o su número en «acciones ver»."
    ),
    carpeta: Path | None = typer.Argument(
        None,
        help="Hacerla en esta carpeta en vez de en la suya (en una rutina, en todos los pasos).",
        show_default=False,
    ),
    simular: bool = OPCION_SIMULAR,
    si: bool = OPCION_SI,
    config: Path | None = OPCION_CONFIG,
) -> None:
    """Hace una de tus acciones: enseña qué va a pasar y pregunta [s/n]."""
    _, motor = cargar(config)
    try:
        accion = motor.buscar(nombre)
    except NavajaError as error:
        fallar(error)
    pasos = motor.pasos(accion)
    if isinstance(accion, Rutina):
        console.print(
            Panel(
                f"[pista]{escape(accion.descripcion)}[/]\n"
                + " → ".join(f"[acento]{escape(p)}[/]" for p in accion.pasos),
                title=f"Rutina {escape(accion.nombre)}",
                border_style="marco",
                expand=False,
            )
        )

    para_deshacer: list[dict[str, str]] = []
    fallos = 0
    for numero, paso in enumerate(pasos, start=1):
        if len(pasos) > 1:
            console.rule(
                f"[titulo]Paso {numero} de {len(pasos)}: {escape(paso.nombre)}[/]",
                style="borde",
                align="left",
            )
        try:
            base, plan = motor.planificar(paso, carpeta)
        except NavajaError as error:
            if para_deshacer:  # los pasos de antes sí se hicieron
                console.print(f"[pista]Para deshacer lo hecho: {como_se_escribe('acciones deshacer')}[/]")
            fallar(error)
        mostrar_plan(paso, base, plan)
        pendientes = sum(r.estado == "pendiente" for r in plan)
        if not pendientes:
            detalle = "ningún archivo cumple el filtro" if not plan else "todo está ya hecho"
            console.print(f"[aviso]Nada que hacer: {detalle}.[/]")
            continue
        if simular:
            continue
        if not confirmar(paso.pregunta(pendientes), saltar=si, por_defecto=False):
            restan = len(pasos) - numero
            extra = (
                "" if not restan
                else " No se hace el paso que queda." if restan == 1
                else f" No se hacen los {restan} pasos que quedan."
            )
            console.print(f"[aviso]Cancelado.{extra}[/]")
            break

        paso.ejecutar(plan)
        hechos = [r for r in plan if r.estado == "hecho"]
        malos = [r for r in plan if r.estado == "fallo"]
        for resultado in malos:
            error_console.print(
                f"[error]No se pudo con[/] {escape(resultado.origen.name)}: {escape(resultado.motivo)}",
                soft_wrap=True,
            )
        fallos += len(malos)
        if hechos:
            para_deshacer += [paso.para_deshacer(r) for r in hechos]
            guardar_acciones("acciones", para_deshacer)  # después de cada paso, por si se cancela
            console.print(f"[ok]{paso.hecho(len(hechos)).capitalize()}.[/]")

    if simular:
        console.print("[pista]Simulación: no se ha tocado nada. Sin --simular, lo hace.[/]")
        if len(pasos) > 1:
            console.print(
                "[pista]En una rutina simulada, cada paso se calcula con la carpeta como está "
                "ahora, sin lo que cambiarían los pasos de antes.[/]"
            )
    if para_deshacer:
        console.print(f"[pista]Para deshacerlo: {como_se_escribe('acciones deshacer')}[/]")
    if fallos:
        console.print(f"[aviso]No se pudo con {cuantos(fallos, 'archivo')}.[/]")
        raise typer.Exit(1)


# ── deshacer y editar ──────────────────────────────────────────────────────


def deshacer(si: bool = OPCION_SI) -> None:
    """Deja los archivos como estaban antes de la última acción (también una rutina entera)."""
    registros = cargar_acciones("acciones")
    if not registros:
        console.print("[aviso]No hay ninguna acción que deshacer.[/]")
        return
    copias = sum(r.get("como") == "copiado" for r in registros)
    movidos = len(registros) - copias
    partes = []
    if movidos:
        partes.append(f"se devolverían {cuantos(movidos, 'archivo')} a su sitio")
    if copias:
        partes.append(f"se quitarían {cuantos(copias, 'copia', 'copias')}")
    console.print(" y ".join(partes).capitalize() + ".")
    if not confirmar("¿Deshacer la última acción?", saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return

    hechos = errores = 0
    carpetas: set[Path] = set()
    origenes: set[Path] = set()
    for registro in reversed(registros):
        origen, destino = Path(registro["origen"]), Path(registro["destino"])
        origenes.add(origen.parent)
        if not destino.exists():
            continue
        try:
            if registro.get("como") == "copiado":
                if not origen.exists():  # sin el original, la copia es lo único que queda
                    continue
                destino.unlink()
            elif str(origen).lower() == str(destino).lower():  # solo cambió de mayúsculas
                destino.rename(origen)
            else:
                origen.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destino), str(ruta_libre(origen)))
            hechos += 1
            carpetas.update([destino.parent, destino.parent.parent])
        except OSError as exc:
            errores += 1
            error_console.print(
                f"[error]No se pudo deshacer[/] {escape(str(destino))}: {escape(exc.strerror or str(exc))}",
                soft_wrap=True,
            )

    # las carpetas que creó la acción y han quedado vacías (nunca una de origen)
    for carpeta in sorted(carpetas, key=lambda c: len(c.parts), reverse=True):
        if any(o == carpeta or carpeta in o.parents for o in origenes):
            continue
        try:
            carpeta.rmdir()
        except OSError:
            pass

    limpiar_acciones("acciones")
    console.print(f"[ok]Deshecho: {cuantos(hechos, 'archivo')}.[/]")
    if errores:
        console.print(f"[aviso]No se pudo deshacer: {cuantos(errores, 'archivo')}.[/]")
        raise typer.Exit(1)


def editar(config: Path | None = OPCION_CONFIG) -> None:
    """Abre acciones.json en tu editor y, al cerrarlo, comprueba que está bien."""
    if config is not None:
        ruta = config.expanduser()
    else:
        try:
            ruta = esquema.buscar()
        except ConfigError:
            ruta = esquema.en_datos()
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(esquema.PLANTILLA_INICIAL, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        console.print(f"[ok]He creado {escape(str(ruta))} con una acción de ejemplo.[/]", soft_wrap=True)
    console.print(
        f"[pista]Abriendo {escape(str(ruta))}… Guarda y cierra el editor para seguir.[/]",
        soft_wrap=True,
    )
    try:
        abrir_en_editor(ruta)
    except (RuntimeError, OSError) as exc:
        error_console.print(f"[error]✘ {escape(str(exc))}[/]", soft_wrap=True)
        raise typer.Exit(1)
    comprobar_y_contar(ruta)


def registrar(app: typer.Typer) -> None:
    sub = typer.Typer(
        help="Tus acciones guardadas en acciones.json: verlas, comprobarlas y hacerlas.",
        no_args_is_help=True,
    )
    sub.command("ver", help="Lista tus acciones: nombre, tipo y qué hace.")(ver)
    sub.command("ejecutar", help="Hace una acción (o una rutina): enseña el plan y pregunta.")(ejecutar)
    sub.command("validar", help="Comprueba que acciones.json está bien escrito, sin tocar nada.")(validar)
    sub.command("editar", help="Abre acciones.json en tu editor y lo comprueba al cerrar.")(editar)
    sub.command("deshacer", help="Deshace la última acción que hiciste.")(deshacer)
    app.add_typer(sub, name="acciones")
