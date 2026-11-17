import subprocess
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import hoy
from navaja.errores import NavajaError

from ayudantes_git import git_aislado, hay_git, repo_con_commits  # noqa: F401 (fixture)

runner = CliRunner()
HOY = date(2026, 11, 17)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("hoy", HOY),
        ("Ayer", HOY - timedelta(days=1)),
        ("-7", HOY - timedelta(days=7)),
        ("2026-11-10", date(2026, 11, 10)),
        ("10/11/2026", date(2026, 11, 10)),
        ("10/11", date(2026, 11, 10)),
        ("20/12", date(2025, 12, 20)),  # aún no ha llegado este año: la última
        ("17/11", HOY),
    ],
)
def test_formas_de_decir_desde_cuando(texto, esperado):
    assert hoy.leer_desde(texto, HOY) == esperado


@pytest.mark.parametrize("texto", ["", "mañana", "+3", "31/02/2026", "32/01", "anteayer"])
def test_fechas_que_no_valen(texto):
    with pytest.raises(NavajaError):
        hoy.leer_desde(texto, HOY)


def test_busca_repos_sin_entrar_en_venv_ni_dentro_de_otro_repo(tmp_path):
    for ruta in ("a", "clase/b", "clase/b/sub", ".venv/c", "node_modules/d", "uno/dos/tres/cuatro"):
        (tmp_path / ruta / ".git").mkdir(parents=True)
    (tmp_path / "vacia").mkdir()
    encontrados = [p.relative_to(tmp_path).as_posix() for p in hoy.buscar_repos(tmp_path)]
    assert encontrados == ["a", "clase/b"]  # «cuatro» está a 4 niveles: demasiado hondo
    (tmp_path / ".git").mkdir()
    assert hoy.buscar_repos(tmp_path) == [tmp_path]  # la carpeta ya es un repo


@hay_git
def test_tus_commits_de_hoy_en_varios_repos(tmp_path, git_aislado):
    repo_con_commits(tmp_path / "navaja", ["Añade foco", "Arregla entregas"])
    repo_con_commits(tmp_path / "navaja", ["Commit de Luis"], autor=("Luis", "luis@clase.es"))
    repo_con_commits(tmp_path / "web", ["Portada nueva"])
    repo_con_commits(tmp_path / "viejo", ["Hace mucho"], fecha="2020-01-01T10:00:00")
    resultado = runner.invoke(app, ["hoy", str(tmp_path)])
    assert resultado.exit_code == 0, resultado.output
    texto = resultado.output
    assert "Añade foco" in texto and "Arregla entregas" in texto and "Portada nueva" in texto
    assert "Commit de Luis" not in texto  # no es tuyo
    assert "Hace mucho" not in texto
    assert "3 commits hoy" in texto and "(y 1 sin nada)" in texto

    todos = runner.invoke(app, ["hoy", str(tmp_path), "--todos"]).output
    assert "Commit de Luis" in todos


@hay_git
def test_desde_un_dia_y_en_markdown(tmp_path, git_aislado):
    antes = (date.today() - timedelta(days=3)).isoformat() + "T12:00:00"
    repo_con_commits(tmp_path / "navaja", ["Del martes"], fecha=antes)
    repo_con_commits(tmp_path / "navaja", ["De hoy"])
    assert "Del martes" not in runner.invoke(app, ["hoy", str(tmp_path)]).output
    resultado = runner.invoke(app, ["hoy", str(tmp_path), "--desde", "-3", "--md"])
    assert resultado.exit_code == 0, resultado.output
    assert resultado.output.startswith("## Commits desde el ")
    assert "### navaja" in resultado.output
    assert "- Del martes (`" in resultado.output and "- De hoy (`" in resultado.output
    assert "\x1b[" not in resultado.output  # sin colores


@hay_git
def test_sin_commits_y_repo_vacio(tmp_path, git_aislado):
    (tmp_path / "vacio").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path / "vacio", check=True)
    resultado = runner.invoke(app, ["hoy", str(tmp_path)])
    assert resultado.exit_code == 0, resultado.output
    assert "Sin commits hoy en 1 repositorio" in resultado.output
    assert "Sin commits hoy." in runner.invoke(app, ["hoy", str(tmp_path), "--md"]).output


def test_errores_sin_traza(tmp_path, monkeypatch):
    sin_repos = runner.invoke(app, ["hoy", str(tmp_path)])
    assert sin_repos.exit_code == 1 and "No hay ningún repositorio git" in sin_repos.output
    no_existe = runner.invoke(app, ["hoy", str(tmp_path / "nada")])
    assert no_existe.exit_code == 1 and "No existe la carpeta" in no_existe.output
    mala = runner.invoke(app, ["hoy", str(tmp_path), "--desde", "pronto"])
    assert mala.exit_code == 1 and "No entiendo la fecha" in mala.output
    monkeypatch.setattr(hoy.shutil, "which", lambda programa: None)
    sin_git = runner.invoke(app, ["hoy", str(tmp_path)])
    assert sin_git.exit_code == 1 and "No encuentro git" in sin_git.output
    assert "Traceback" not in sin_repos.output + no_existe.output + mala.output + sin_git.output
