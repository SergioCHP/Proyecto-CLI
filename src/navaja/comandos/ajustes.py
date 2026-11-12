"""tema y config: colores y datos personales de navaja."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import typer
from rich.markup import escape
from rich.theme import Theme

from ..comun import (
    NAVAJA,
    TEMAS,
    aplicar_tema,
    cargar_config,
    como_se_escribe,
    console,
    directorio_datos,
    error_console,
    guardar_config,
    usuario_del_sistema,
)


def muestra_tema(nombre: str, actual: bool = False) -> str:
    """Línea de ejemplo con todos los estilos del tema."""
    marca = "[ok]✔[/]" if actual else " "
    return (
        f"{marca} [titulo]{nombre:<9}[/] [ok]hecho[/]  [aviso]ojo[/]  "
        f"[error]fallo[/]  [acento]acento[/]  [logro]1.2 GB[/]  [pista]pista[/]"
    )


def ver() -> None:
    """Muestra los temas con una muestra de sus colores; ✔ el que tienes."""
    actual = cargar_config()["tema"]
    for nombre, estilos in TEMAS.items():
        with console.use_theme(Theme(estilos)):
            console.print(muestra_tema(nombre, nombre == actual))
    console.print(f"\n[pista]Para cambiarlo: {como_se_escribe('tema elegir')} <nombre>[/]")


def elegir(
    nombre: str = typer.Argument(
        ..., help=f"Qué tema: {', '.join(TEMAS)} (los ves con «tema ver»)."
    ),
) -> None:
    """Cambia los colores de navaja."""
    nombre = nombre.strip().lower()
    if nombre not in TEMAS:
        error_console.print(
            f"[error]No hay ningún tema «{escape(nombre)}».[/] "
            f"Elige uno de estos: {', '.join(TEMAS)}."
        )
        raise typer.Exit(1)
    config = cargar_config()
    config["tema"] = nombre
    guardar_config(config)
    aplicar_tema(nombre)
    console.print(muestra_tema(nombre, actual=True))
    console.print(f"[ok]Tema cambiado a[/] [titulo]{nombre}[/].")


def ver_config() -> None:
    """Muestra tu nombre, tu tema y dónde guarda navaja tus datos."""
    config = cargar_config()
    if config["nombre"]:
        console.print(f"Nombre: [acento]{escape(config['nombre'])}[/]")
    else:
        console.print(
            f"Nombre: [acento]{escape(usuario_del_sistema() or '(ninguno)')}[/] "
            f"[pista](tu usuario del sistema; para cambiarlo: {como_se_escribe('config nombre')})[/]",
            soft_wrap=True,
        )
    console.print(f"Tema:   [acento]{config['tema']}[/]")
    console.print(
        f"Datos:  [acento]{escape(str(directorio_datos()))}[/] "
        "[pista](configuración, notas, lo de deshacer y la papelera)[/]",
        soft_wrap=True,
    )


def preguntar_nombre(leer: Callable[[str], str] | None = None) -> str:
    """La primera vez que se abre el menú: cómo quieres que te llame. Se guarda para siempre.

    Intro = tu usuario del sistema. Si se cancela (Ctrl+C), se usa el usuario sin
    guardarlo, y la próxima vez lo vuelve a preguntar.
    """
    leer = leer or console.input
    usuario = usuario_del_sistema()
    console.print("[titulo]¡Hola! Es la primera vez que abres navaja.[/]")
    pista = f" [pista](Intro = {escape(usuario)}, tu usuario)[/]" if usuario else ""
    try:
        elegido = leer(f"¿Cómo quieres que te llame?{pista}: ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print()
        return usuario
    elegido = elegido or usuario
    if elegido:
        config = cargar_config()
        config["nombre"] = elegido
        guardar_config(config)
        console.print(
            f"[pista]Te llamaré {escape(elegido)}. Para cambiarlo, en el menú: config → nombre.[/]\n"
        )
    return elegido


def nombre(
    nuevo: str = typer.Argument(..., help="Cómo quieres que te salude navaja."),
) -> None:
    """Cambia el nombre con el que te saluda (se guarda para siempre)."""
    nuevo = nuevo.strip()
    if not nuevo:
        error_console.print("[error]El nombre no puede estar vacío.[/]")
        raise typer.Exit(1)
    config = cargar_config()
    config["nombre"] = nuevo
    guardar_config(config)
    console.print(f"[ok]A partir de ahora te saludo como[/] [acento]{escape(nuevo)}[/].")


MARCA = "# navaja: autocompletar con Tab"
SHELLS = ("powershell", "bash")


def script_autocompletar(shell: str) -> str:
    """Las líneas que hay que añadir al perfil de la terminal, para navaja y para nav."""
    from typer.completion import get_completion_script

    script = get_completion_script(
        prog_name="navaja", complete_var="_NAVAJA_COMPLETE", shell=shell
    )
    if shell == "powershell":
        script = script.replace("-CommandName navaja ", "-CommandName navaja, nav ")
    else:
        script += "\ncomplete -o default -F _navaja_completion nav"
    return f"{MARCA}\n{script}\n{MARCA} (fin)\n"


def autocompletar(
    perfil: Path | None = typer.Argument(
        None,
        help="El perfil de tu terminal, donde se añade: en PowerShell, $PROFILE; en bash, "
        "~/.bashrc. Sin él, solo enseña lo que habría que añadir.",
        show_default=False,
    ),
    shell: str = typer.Option(
        "powershell" if os.name == "nt" else "bash",
        "--shell",
        help="Para qué terminal: powershell o bash.",
    ),
) -> None:
    """Tab en la terminal normal: navaja ord⇥ → navaja ordena (y lo mismo con nav)."""
    shell = shell.strip().lower()
    if shell not in SHELLS:
        error_console.print(
            f"[error]No sé hacerlo para «{escape(shell)}».[/] Elige {' o '.join(SHELLS)}."
        )
        raise typer.Exit(1)
    script = script_autocompletar(shell)
    if perfil is None:
        console.print(script, markup=False, highlight=False, soft_wrap=True)
        donde = "$PROFILE" if shell == "powershell" else "~/.bashrc"
        console.print(
            f"[pista]Para añadirlo tú solo: {como_se_escribe('config autocompletar')} {donde}[/]",
            soft_wrap=True,
        )
        return

    perfil = perfil.expanduser()
    actual = perfil.read_bytes() if perfil.is_file() else b""
    if actual.startswith((b"\xff\xfe", b"\xfe\xff")):
        error_console.print(
            f"[error]{escape(str(perfil))} está guardado en UTF-16 y no lo toco para no "
            "estropearlo.[/] Guárdalo como UTF-8 (en el Bloc de notas: Guardar como → "
            "Codificación) y vuelve a probar.",
            soft_wrap=True,
        )
        raise typer.Exit(1)
    if MARCA.encode() in actual:
        console.print(f"[ok]Ya estaba en {escape(str(perfil))}.[/] [pista]Nada que hacer.[/]", soft_wrap=True)
        return
    try:
        perfil.parent.mkdir(parents=True, exist_ok=True)
        with perfil.open("a", encoding="utf-8", newline="") as archivo:
            if actual and not actual.endswith(b"\n"):
                archivo.write("\n")
            archivo.write("\n" + script)
    except OSError as exc:
        error_console.print(
            f"[error]No puedo escribir en {escape(str(perfil))}: {escape(exc.strerror or str(exc))}[/]",
            soft_wrap=True,
        )
        raise typer.Exit(1)
    console.print(f"[ok]Añadido a {escape(str(perfil))}.[/]", soft_wrap=True)
    console.print("[pista]Abre una terminal nueva y prueba: navaja ord y Tab.[/]")
    if shell == "powershell":
        console.print(
            "[pista]Si al abrirla dice que la ejecución de scripts está deshabilitada: "
            "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned[/]",
            soft_wrap=True,
        )


def registrar(app: typer.Typer) -> None:
    tema = typer.Typer(help="Elige los colores de navaja.", no_args_is_help=True)
    tema.command("ver", help="Muestra los temas con una muestra de sus colores.")(ver)
    tema.command("elegir", help="Cambia los colores de navaja.")(elegir)
    app.add_typer(tema, name="tema", rich_help_panel=NAVAJA)

    config = typer.Typer(
        help="Tu nombre para el saludo y dónde guarda navaja tus datos.", no_args_is_help=True
    )
    config.command("ver", help="Muestra tu nombre, tu tema y dónde están tus datos.")(ver_config)
    config.command("nombre", help="Cambia el nombre con el que te saluda (para siempre).")(nombre)
    config.command(
        "autocompletar", help="Tab en PowerShell o bash: navaja ord⇥ → navaja ordena."
    )(autocompletar)
    app.add_typer(config, name="config", rich_help_panel=NAVAJA)
