"""El instalador de una línea: instalar.ps1 (Windows) e instalar.sh (Linux y macOS).

Aquí no se instala nada de verdad (eso lo hace GitHub Actions en el trabajo «instalador»):
se comprueba que los dos instalan la misma versión que dice navaja, desde el .zip de
GitHub (sin git), y el camino de instalar.sh con un «uv» de mentira que apunta lo que le
piden.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import navaja
from navaja import lotes

RAIZ = Path(__file__).resolve().parent.parent
PS1 = RAIZ / "instalar.ps1"
SH = RAIZ / "instalar.sh"
SIN_SH = pytest.mark.skipif(os.name == "nt" or shutil.which("sh") is None, reason="hace falta sh (Linux o macOS)")


def version_de(script: Path) -> str:
    """La versión que instala por defecto: «1.2.0» en ${NAVAJA_VERSION:-1.2.0} o en el else de PowerShell."""
    texto = script.read_text(encoding="utf-8")
    encontrada = re.search(r'NAVAJA_VERSION:-([\d.]+)\}', texto) or re.search(r'else \{ "([\d.]+)" \}', texto)
    assert encontrada, f"no encuentro la versión en {script.name}"
    return encontrada.group(1)


@pytest.mark.parametrize("script", [PS1, SH], ids=["instalar.ps1", "instalar.sh"])
def test_el_instalador_instala_la_version_de_navaja(script):
    """Al sacar una versión hay que cambiarla también aquí: si se olvida, este test falla."""
    assert version_de(script) == navaja.__version__


@pytest.mark.parametrize("script", [PS1, SH], ids=["instalar.ps1", "instalar.sh"])
def test_el_instalador_baja_el_zip_de_github_sin_git(script):
    texto = script.read_text(encoding="utf-8")
    assert f'"{lotes.REPO}"' in texto  # el mismo repositorio que usa «doctor»
    assert "/archive/refs/tags/v$Version.zip" in texto or "/archive/refs/tags/v$VERSION.zip" in texto
    assert "git+" not in texto  # sin git: muchos Windows no lo tienen
    assert "--force" in texto  # reinstalar o actualizar encima de la que haya


def test_el_powershell_no_usa_exit():
    """Con «irm … | iex», un exit cerraría la ventana de PowerShell del que lo instala."""
    codigo = [linea for linea in PS1.read_text(encoding="utf-8").splitlines() if not linea.lstrip().startswith("#")]
    assert not any(re.search(r"\bexit\b", linea) for linea in codigo)


@SIN_SH
def test_instalar_sh_no_tiene_errores_de_sintaxis():
    assert subprocess.run(["sh", "-n", str(SH)], capture_output=True).returncode == 0


def uv_de_mentira(tmp_path: Path, falla: bool = False) -> tuple[Path, Path]:
    """Un «uv» que apunta cada llamada en uv.log; «tool dir --bin» dice una carpeta con un
    «navaja» que solo contesta a --version. Con ``falla``, «tool install» sale con 2."""
    bin_uv, bin_tools = tmp_path / "uv-bin", tmp_path / "tools-bin"
    bin_uv.mkdir()
    bin_tools.mkdir()
    log = tmp_path / "uv.log"
    uv = bin_uv / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> "{log}"\n'
        f'if [ "$1 $2" = "tool dir" ]; then echo "{bin_tools}"; fi\n'
        + ('if [ "$1 $2" = "tool install" ]; then exit 2; fi\n' if falla else "")
        + "exit 0\n",
        encoding="utf-8",
    )
    navaja_falso = bin_tools / "navaja"
    navaja_falso.write_text('#!/bin/sh\necho "navaja de prueba"\n', encoding="utf-8")
    for archivo in (uv, navaja_falso):
        archivo.chmod(0o755)
    return bin_uv, log


def correr_sh(tmp_path: Path, bin_uv: Path, **entorno: str) -> subprocess.CompletedProcess:
    variables = {
        "PATH": f"{bin_uv}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(tmp_path / "casa"),  # para que no encuentre el uv de verdad
        **entorno,
    }
    return subprocess.run(["sh", str(SH)], capture_output=True, text=True, env=variables, timeout=30)


@SIN_SH
def test_instalar_sh_con_uv_ya_instalado_instala_navaja_y_lo_comprueba(tmp_path):
    bin_uv, log = uv_de_mentira(tmp_path)
    resultado = correr_sh(tmp_path, bin_uv)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    llamadas = log.read_text(encoding="utf-8").splitlines()
    assert llamadas[0] == f"tool install --force navaja[todo] @ {lotes.zip_de_version()}"
    assert "tool update-shell" in llamadas  # para que «navaja» se encuentre en terminales nuevas
    assert "uv ya está" in resultado.stdout  # no intenta instalar uv otra vez
    assert "navaja de prueba" in resultado.stdout and "Listo" in resultado.stdout


@SIN_SH
def test_instalar_sh_con_otra_version_y_extras(tmp_path):
    bin_uv, log = uv_de_mentira(tmp_path)
    resultado = correr_sh(tmp_path, bin_uv, NAVAJA_VERSION="1.0.0", NAVAJA_EXTRAS="todo,fondo")
    assert resultado.returncode == 0, resultado.stderr
    assert log.read_text(encoding="utf-8").splitlines()[0] == (
        f"tool install --force navaja[todo,fondo] @ {lotes.zip_de_version('1.0.0')}"
    )


@SIN_SH
def test_instalar_sh_si_uv_falla_lo_dice_y_sale_con_error(tmp_path):
    bin_uv, _ = uv_de_mentira(tmp_path, falla=True)
    resultado = correr_sh(tmp_path, bin_uv)
    assert resultado.returncode == 1
    assert "No se pudo instalar navaja" in resultado.stderr
    assert "Listo" not in resultado.stdout
