from pathlib import Path

# Atajos que PowerShell trae de serie y que se adelantarían a un programa con el mismo nombre.
ALIAS_DE_POWERSHELL = {
    "ac", "cat", "cd", "clc", "clear", "cls", "copy", "cp", "del", "dir", "echo", "gc",
    "gci", "gcm", "gi", "gl", "gm", "gp", "gps", "gv", "h", "ii", "kill", "ls", "md",
    "mi", "mv", "ni", "nv", "ps", "pwd", "r", "rd", "ren", "ri", "rm", "rv", "sc", "si",
    "sl", "sleep", "sort", "sp", "sv", "type", "where",
}


def ordenes_instaladas():
    """Nombres de [project.scripts] en pyproject.toml (sin tomllib, que no está en 3.10)."""
    texto = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    seccion = texto.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
    return {linea.split("=")[0].strip() for linea in seccion.splitlines() if "=" in linea}


def test_se_instalan_navaja_y_nav():
    assert ordenes_instaladas() == {"navaja", "nav"}


def test_ningun_comando_choca_con_un_alias_de_powershell():
    assert not ordenes_instaladas() & ALIAS_DE_POWERSHELL
