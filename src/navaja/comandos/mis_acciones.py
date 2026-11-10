"""«acciones»: tus tareas guardadas en acciones.json, con nombre, para lanzarlas cuando quieras.

Aquí solo hay órdenes y salida. Leer y comprobar el archivo es cosa de ``esquema``;
elegir archivos, de ``Motor``; y qué le pasa a cada archivo, de cada clase de
``acciones``. Todos los errores previsibles son ``NavajaError``: se capturan una vez
y se sale con su código (1 al ejecutar, 3 si acciones.json está mal).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import typer
from rich.markup import escape
from rich.panel import Panel

from .. import esquema
from ..acciones import (
    Accion,
    AccionDeArchivos,
    Resultado,
    Rutina,
    apartar,
    misma_copia,
    relativa,
)
from ..comun import (
    abrir_en_editor,
    cargar_acciones,
    carpeta_papelera,
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


def elegir_config(ctx: typer.Context, config: Path | None) -> Path | None:
    """El --config de la orden y, si no hay, el del grupo (``navaja acciones --config X ver``),
    guardado en ``ctx.obj``. El de la orden gana porque es el más concreto."""
    if config is not None:
        return config
    datos = ctx.obj if isinstance(ctx.obj, dict) else {}
    return datos.get("config")


def grupo(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Usar este archivo de acciones en la orden que va detrás: "
        "navaja acciones --config pruebas/acciones-prueba.json ver.",
        show_default=False,
    ),
) -> None:
    """Guarda el --config escrito antes de la orden para que lo usen todas."""
    datos = ctx.ensure_object(dict)
    datos["config"] = config


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


def ver(ctx: typer.Context, config: Path | None = OPCION_CONFIG) -> None:
    """Lista tus acciones: número, nombre, tipo y qué hace."""
    ruta, motor = cargar(elegir_config(ctx, config))
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


def validar(ctx: typer.Context, config: Path | None = OPCION_CONFIG) -> None:
    """Comprueba que acciones.json está bien escrito, sin tocar ningún archivo."""
    try:
        ruta = esquema.buscar(elegir_config(ctx, config))
    except ConfigError as error:
        fallar(error)
    comprobar_y_contar(ruta)


# ── ejecutar ───────────────────────────────────────────────────────────────


def corta(texto: str, largo: int = 45) -> str:
    """La descripción en una línea corta: PowerShell lee cada línea como una sugerencia,
    así que una descripción que se parte en dos dejaría una sugerencia suelta."""
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[: largo - 1].rstrip(" ,;:") + "…"


def nombres_para_tab(ctx: typer.Context, incomplete: str) -> list[tuple[str, str]]:
    """Tab en el nombre de la acción (en PowerShell y dentro de navaja): los nombres de tus
    acciones con su descripción. Usa el --config que ya se haya escrito (en la orden o en el
    grupo) y no comprueba el archivo entero: si no se puede leer, simplemente no sugiere."""
    config = None
    actual: Any = ctx
    while actual is not None and config is None:
        config = (actual.params or {}).get("config")
        actual = actual.parent
    try:
        datos = esquema.leer(esquema.buscar(Path(config) if config else None))
    except NavajaError:
        return []
    acciones = datos.get("acciones") if isinstance(datos, dict) else None
    if not isinstance(acciones, list):
        return []
    return [
        (accion["nombre"], corta(str(accion.get("descripcion", ""))))
        for accion in acciones
        if isinstance(accion, dict)
        and isinstance(accion.get("nombre"), str)
        and accion["nombre"].lower().startswith(incomplete.lower())
    ]


def mostrar_plan(accion: AccionDeArchivos, carpeta: Path, plan: list[Resultado]) -> None:
    pendientes = [r for r in plan if r.estado == "pendiente"]
    saltados = [r for r in plan if r.estado == "saltado"]
    # Si todo va a una carpeta de fuera (el USB, otro disco…), se dice una vez arriba y la
    # columna solo lleva la ruta desde allí, en vez de repetirla entera en cada fila.
    destino = accion.destino_comun(carpeta)
    if destino is not None and destino.resolve().is_relative_to(carpeta.resolve()):
        destino = None  # dentro de la carpeta ya se ve corto: «PDF\factura.pdf»
    resumen = (
        f"[pista]{escape(accion.descripcion)}[/]\n"
        f"[pista]En[/] {escape(bonita(carpeta.resolve()))}\n"
        + (f"[pista]A[/] {escape(bonita(destino.resolve()))}\n" if destino is not None else "")
        + f"[bold]{cuantos(len(pendientes), 'archivo')}[/] {accion.para}"
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
            va_a = bonita(resultado.destino)
            for base in (destino, carpeta):
                if base is None:
                    continue
                try:
                    va_a = str(resultado.destino.relative_to(base))
                    break
                except ValueError:
                    continue
        estilo = "ok" if resultado.estado == "pendiente" else "pista"
        if resultado.sustituir:
            va_a += "  (sustituye a la versión vieja)"
        fila = [escape(str(relativa(resultado.origen, carpeta))), f"[{estilo}]{escape(va_a)}[/]"]
        if saltados:
            fila.append(f"[aviso]{escape(resultado.motivo)}[/]" if resultado.estado == "saltado" else "")
        tabla.add_row(*fila)
    console.print(tabla)
    if len(plan) > limite:
        console.print(f"[pista]Mostrando {limite} de {len(plan)}.[/]")


def ejecutar(
    ctx: typer.Context,
    nombre: str = typer.Argument(
        ...,
        help="Nombre de la acción, o su número en «acciones ver».",
        autocompletion=nombres_para_tab,
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
    _, motor = cargar(elegir_config(ctx, config))
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
    cancelado = False
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
            cancelado = True
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
    if fallos or cancelado:  # decir que no también sale con 1: un script sabe que no se hizo
        raise typer.Exit(1)


# ── deshacer y editar ──────────────────────────────────────────────────────


def deshacer(si: bool = OPCION_SI) -> None:
    """Deja los archivos como estaban antes de la última acción (también una rutina entera)."""
    registros = cargar_acciones("acciones")
    if not registros:
        console.print("[aviso]No hay ninguna acción que deshacer.[/]")
        return
    copias = sum(r.get("como") == "copiado" for r in registros)
    viejas = sum("apartado" in r and Path(r["apartado"]).exists() for r in registros)
    perdidas = sum("apartado" in r for r in registros) - viejas
    copias -= perdidas  # sin su versión vieja, esas copias se quedan (ver abajo)
    movidos = len(registros) - copias - perdidas
    partes = []
    if movidos:
        partes.append(f"se devolverían {cuantos(movidos, 'archivo')} a su sitio")
    if copias - viejas:
        partes.append(f"se quitarían {cuantos(copias - viejas, 'copia', 'copias')}")
    if viejas:
        partes.append(
            f"volvería {cuantos(viejas, 'versión vieja')} que se sustituyó" if viejas == 1
            else f"volverían {cuantos(viejas, 'versión vieja', 'versiones viejas')} que se sustituyeron"
        )
    if not partes:
        partes.append("no queda nada que se pueda deshacer sin perder algo")
    console.print(" y ".join(partes).capitalize() + ".")
    if perdidas:
        console.print(
            f"[aviso]{cuantos(perdidas, 'versión vieja', 'versiones viejas')} ya no "
            f"{'está' if perdidas == 1 else 'están'} en la papelera de navaja: esas copias se "
            "quedan como están.[/]",
            soft_wrap=True,
        )
    if not confirmar("¿Deshacer la última acción?", saltar=si, por_defecto=False):
        console.print("[aviso]Cancelado.[/]")
        return

    hechos = errores = 0
    pendientes: list[dict[str, str]] = []  # lo que falló: se guarda para poder reintentarlo
    papelera = carpeta_papelera() / datetime.now().strftime("deshacer-%Y%m%d-%H%M%S")
    carpetas: set[Path] = set()
    origenes: set[Path] = set()
    for registro in reversed(registros):
        origen, destino = Path(registro["origen"]), Path(registro["destino"])
        origenes.add(origen.parent)
        if not destino.exists():
            continue
        try:
            if registro.get("como") == "copiado":
                if not deshacer_copia(origen, destino, registro.get("apartado"), papelera):
                    continue
            elif str(origen).lower() == str(destino).lower():  # solo cambió de mayúsculas
                destino.rename(origen)
            else:
                origen.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destino), str(ruta_libre(origen)))
            hechos += 1
            carpetas.update([destino.parent, destino.parent.parent])
        except OSError as exc:
            errores += 1
            pendientes.append(registro)
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

    console.print(f"[ok]Deshecho: {cuantos(hechos, 'archivo')}.[/]")
    if errores:
        guardar_acciones("acciones", list(reversed(pendientes)))  # para volver a intentarlo
        console.print(
            f"[aviso]No se pudo deshacer: {cuantos(errores, 'archivo')}.[/] "
            f"[pista]Se guardan para probar otra vez con {como_se_escribe('acciones deshacer')}.[/]",
            soft_wrap=True,
        )
        raise typer.Exit(1)
    limpiar_acciones("acciones")


def deshacer_copia(origen: Path, destino: Path, apartado: str | None, papelera: Path) -> bool:
    """Quita una copia (a la papelera, nunca borrada) y, si sustituyó a otra, devuelve la
    vieja. Devuelve False si no la toca porque se perdería algo, y dice por qué."""
    if not origen.exists():  # sin el original, la copia es lo único que queda
        return False
    vieja = Path(apartado) if apartado else None
    if vieja is not None and not vieja.exists():
        return False  # se vació la papelera: la copia es lo único que queda (ya se avisó)
    if not misma_copia(origen, destino):
        console.print(
            f"[aviso]No toco[/] {escape(str(destino))}[aviso]: ha cambiado desde que se copió y "
            "perderías lo que hayas hecho.[/]",
            soft_wrap=True,
        )
        return False
    quitada = apartar(destino, papelera)
    if vieja is not None:
        try:
            shutil.move(str(vieja), str(destino))
        except OSError as exc:
            shutil.move(str(quitada), str(destino))  # vuelve la copia: queda como estaba
            raise OSError(
                exc.errno, f"no se pudo devolver la versión vieja; sigue en {vieja}"
            ) from None
    return True


def editar(ctx: typer.Context, config: Path | None = OPCION_CONFIG) -> None:
    """Abre acciones.json en tu editor y, al cerrarlo, comprueba que está bien."""
    config = elegir_config(ctx, config)
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
        callback=grupo,
    )
    sub.command("ver", help="Lista tus acciones: nombre, tipo y qué hace.")(ver)
    sub.command("ejecutar", help="Hace una acción (o una rutina): enseña el plan y pregunta.")(ejecutar)
    sub.command("validar", help="Comprueba que acciones.json está bien escrito, sin tocar nada.")(validar)
    sub.command("editar", help="Abre acciones.json en tu editor y lo comprueba al cerrar.")(editar)
    sub.command("deshacer", help="Deshace la última acción que hiciste.")(deshacer)
    app.add_typer(sub, name="acciones")
