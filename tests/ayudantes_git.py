"""Ayudas para los tests que usan git de verdad (nuevo y hoy)."""

import os
import shutil
import subprocess

import pytest

hay_git = pytest.mark.skipif(shutil.which("git") is None, reason="hace falta git")


@pytest.fixture
def git_aislado(tmp_path, monkeypatch):
    """Un git con su propia configuración global (no la tuya): Ana <ana@clase.es>."""
    config = tmp_path / "gitconfig"
    config.write_text(
        "[user]\n\tname = Ana\n\temail = ana@clase.es\n[init]\n\tdefaultBranch = main\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for variable in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
                     "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.delenv(variable, raising=False)
    return config


def git(carpeta, *argumentos, entorno=None):
    return subprocess.run(
        ["git", *argumentos], cwd=carpeta, check=True, capture_output=True, text=True,
        env={**os.environ, **(entorno or {})},
    ).stdout


def repo_con_commits(carpeta, mensajes, autor=None, fecha=None):
    """Crea (si hace falta) un repo en ``carpeta`` y hace un commit por mensaje."""
    carpeta.mkdir(parents=True, exist_ok=True)
    if not (carpeta / ".git").exists():
        git(carpeta, "init", "-q")
    entorno = {}
    if autor:
        entorno |= {"GIT_AUTHOR_NAME": autor[0], "GIT_AUTHOR_EMAIL": autor[1],
                    "GIT_COMMITTER_NAME": autor[0], "GIT_COMMITTER_EMAIL": autor[1]}
    if fecha:
        entorno |= {"GIT_AUTHOR_DATE": fecha, "GIT_COMMITTER_DATE": fecha}
    for numero, mensaje in enumerate(mensajes):
        archivo = carpeta / f"{len(list(carpeta.iterdir()))}-{numero}.txt"
        archivo.write_text(mensaje, encoding="utf-8")
        git(carpeta, "add", "-A")
        git(carpeta, "commit", "-q", "-m", mensaje, entorno=entorno)
    return carpeta
