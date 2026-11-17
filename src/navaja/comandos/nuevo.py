"""navaja nuevo: crea un proyecto listo para trabajar.

Carpetas, README, el ``.gitignore`` del lenguaje (Python, Java o web), ``git init`` y el
primer commit. Enseña antes lo que va a crear y pregunta ``[s/n]``; nunca pisa nada: si la
carpeta ya existe, crea «nombre (1)».
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import date
from enum import Enum
from pathlib import Path

import typer
from rich.markup import escape

from ..comun import (
    AJUSTE,
    PROGRAMACION,
    bonita,
    confirmar,
    console,
    problema_del_nombre,
    ruta_libre,
    tabla_ligera,
)
from ..errores import NavajaError
from ..lotes import fallar


class Lenguaje(str, Enum):
    python = "python"
    java = "java"
    web = "web"


GITIGNORE_COMUN = """# Sistema y editores
.DS_Store
Thumbs.db
desktop.ini
.vscode/
.idea/
*.swp
"""

GITIGNORE = {
    Lenguaje.python: """# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
dist/
build/
.pytest_cache/
.env
""",
    Lenguaje.java: """# Java
*.class
*.jar
out/
bin/
target/
build/
.gradle/
*.iml
""",
    Lenguaje.web: """# Web
node_modules/
dist/
.cache/
*.log
.env
""",
}

INSTRUCCIONES = {
    Lenguaje.python: "```bash\npython src/main.py\n```",
    Lenguaje.java: "```bash\njavac -d out src/Main.java\njava -cp out Main\n```",
    Lenguaje.web: "Abre `index.html` en el navegador.",
}


def archivos_de(nombre: str, lenguaje: Lenguaje) -> dict[str, str]:
    """Ruta relativa → contenido de cada archivo del proyecto nuevo."""
    readme = (
        f"# {nombre}\n\n"
        "Qué hace este proyecto, en una o dos frases.\n\n"
        f"## Cómo se usa\n\n{INSTRUCCIONES[lenguaje]}\n\n"
        f"Creado el {date.today().strftime('%d/%m/%Y')} con `navaja nuevo`.\n"
    )
    archivos = {
        "README.md": readme,
        ".gitignore": GITIGNORE[lenguaje] + "\n" + GITIGNORE_COMUN,
    }
    if lenguaje is Lenguaje.python:
        archivos |= {
            "src/main.py": (
                f'"""{nombre}: punto de entrada."""\n\n\n'
                "def main() -> None:\n"
                f'    print("Hola desde {nombre}")\n\n\n'
                'if __name__ == "__main__":\n'
                "    main()\n"
            ),
            "tests/.gitkeep": "",
        }
    elif lenguaje is Lenguaje.java:
        archivos |= {
            "src/Main.java": (
                "public class Main {\n"
                "    public static void main(String[] args) {\n"
                f'        System.out.println("Hola desde {nombre}");\n'
                "    }\n"
                "}\n"
            ),
            "lib/.gitkeep": "",
        }
    else:
        archivos |= {
            "index.html": (
                "<!DOCTYPE html>\n"
                '<html lang="es">\n'
                "<head>\n"
                '  <meta charset="utf-8">\n'
                '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
                f"  <title>{nombre}</title>\n"
                '  <link rel="stylesheet" href="css/estilos.css">\n'
                "</head>\n"
                "<body>\n"
                f"  <h1>{nombre}</h1>\n"
                '  <script src="js/main.js"></script>\n'
                "</body>\n"
                "</html>\n"
            ),
            "css/estilos.css": "body {\n  font-family: system-ui, sans-serif;\n  margin: 2rem;\n}\n",
            "js/main.js": f'console.log("Hola desde {nombre}");\n',
            "img/.gitkeep": "",
        }
    return archivos


def git(*argumentos: str, carpeta: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *argumentos],
        cwd=carpeta,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def iniciar_git(carpeta: Path) -> str | None:
    """``git init`` y el primer commit. Devuelve None si fue bien, o qué pasó."""
    if git("init", "-b", "main", carpeta=carpeta).returncode != 0:  # git anterior a 2.28
        if git("init", carpeta=carpeta).returncode != 0:
            return "git init falló."
    git("add", "-A", carpeta=carpeta)
    commit = git("commit", "-m", "Primer commit: estructura del proyecto", carpeta=carpeta)
    if commit.returncode != 0:
        if "user.email" in commit.stderr or "user.name" in commit.stderr or "identity" in commit.stderr:
            return (
                "El repositorio está creado, pero git no sabe quién eres y no hizo el commit. "
                'Díselo una vez: git config --global user.name "Tu Nombre" y '
                'git config --global user.email "tu@correo.com"; luego: git commit -m "Primer commit"'
            )
        return f"El repositorio está creado, pero el commit falló: {commit.stderr.strip() or commit.stdout.strip()}"
    return None


def nuevo(
    nombre: str = typer.Argument(..., help="Nombre del proyecto (será el de la carpeta)."),
    lenguaje: Lenguaje = typer.Option(
        Lenguaje.python, "--lenguaje", "-l", help="python, java o web: elige la plantilla y el .gitignore.",
        rich_help_panel=AJUSTE,
    ),
    carpeta: Path = typer.Option(
        Path("."), "--carpeta", "-c", help="Dónde crearlo (por defecto, aquí).", show_default=False,
        rich_help_panel=AJUSTE,
    ),
    sin_git: bool = typer.Option(
        False, "--sin-git", help="Solo los archivos, sin git init ni commit.", rich_help_panel=AJUSTE
    ),
    simular: bool = typer.Option(
        False, "--simular", help="Enseña lo que crearía sin crear nada.", rich_help_panel=AJUSTE
    ),
    si: bool = typer.Option(False, "--si", "-s", help="No pide confirmación."),
) -> None:
    """Crea un proyecto: carpetas, README, .gitignore del lenguaje, git init y primer commit."""
    try:
        nombre = nombre.strip()
        problema = problema_del_nombre(nombre)
        if problema:
            raise NavajaError(problema)
        base = carpeta.expanduser()
        if not base.is_dir():
            raise NavajaError(f"No existe la carpeta {bonita(base)}.")
        destino = ruta_libre(base.resolve() / nombre)
        con_git = not sin_git and shutil.which("git") is not None
        archivos = archivos_de(destino.name, lenguaje)

        tabla = tabla_ligera()
        tabla.add_column("Se crea")
        for ruta in archivos:
            tabla.add_row(escape(ruta))
        console.print(f"[titulo]Proyecto {escape(lenguaje.value)} en {escape(bonita(destino))}[/]", soft_wrap=True)
        if destino.name != nombre:
            console.print(f"[aviso]Ya había una carpeta «{escape(nombre)}»: se usa «{escape(destino.name)}».[/]")
        console.print(tabla)
        if sin_git:
            console.print("[pista]Sin git (--sin-git).[/]")
        elif con_git:
            console.print("[pista]Y luego: git init y el primer commit.[/]")
        else:
            console.print(
                "[aviso]No encuentro git: se crean los archivos sin repositorio.[/] "
                "[pista]Instálalo con: winget install Git.Git (Windows) o sudo apt install git (Linux).[/]"
            )

        if simular:
            console.print("[aviso]Simulado:[/] no se creó nada.")
            return
        if not confirmar("¿Crear el proyecto?", saltar=si, por_defecto=True):
            console.print("[aviso]Cancelado.[/]")
            return

        try:
            for ruta, contenido in archivos.items():
                archivo = destino / ruta
                archivo.parent.mkdir(parents=True, exist_ok=True)
                archivo.write_text(contenido, encoding="utf-8")
        except OSError as error:
            raise NavajaError(f"No se pudo crear {bonita(destino)}: {error.strerror or error}") from error

        console.print(f"[ok]✔ Creado {escape(bonita(destino))}[/]", soft_wrap=True)
        if con_git:
            try:
                problema_git = iniciar_git(destino)
            except (OSError, subprocess.TimeoutExpired) as error:
                problema_git = f"git no respondió: {error}"
            if problema_git:
                console.print(f"[aviso]{escape(problema_git)}[/]", soft_wrap=True)
            else:
                console.print("[ok]✔ git init y primer commit hechos[/] [pista](rama main)[/]")
        console.print(f"[pista]Para entrar: cd \"{escape(str(destino))}\"[/]", soft_wrap=True)
    except NavajaError as error:
        fallar(error)


def registrar(app: typer.Typer) -> None:
    app.command(
        "nuevo", help="Crea un proyecto listo: README, .gitignore, git init y primer commit.",
        rich_help_panel=PROGRAMACION,
    )(nuevo)
