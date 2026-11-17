from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import nuevo

from ayudantes_git import git, git_aislado, hay_git  # noqa: F401 (fixture)

runner = CliRunner()


def creados(carpeta):
    """Lo que hay en la carpeta, sin los datos de navaja de los tests."""
    return [p for p in carpeta.iterdir() if p.name != "datos_navaja"]


def crear(tmp_path, *extra, entrada="s\n"):
    return runner.invoke(app, ["nuevo", "practica", "-c", str(tmp_path), *extra], input=entrada)


@hay_git
def test_python_con_git_y_primer_commit(tmp_path, git_aislado):
    resultado = crear(tmp_path)
    assert resultado.exit_code == 0, resultado.output
    proyecto = tmp_path / "practica"
    assert (proyecto / "README.md").read_text(encoding="utf-8").startswith("# practica")
    assert "__pycache__/" in (proyecto / ".gitignore").read_text(encoding="utf-8")
    assert "Hola desde practica" in (proyecto / "src" / "main.py").read_text(encoding="utf-8")
    assert (proyecto / "tests" / ".gitkeep").exists()
    assert "primer commit hechos" in resultado.output
    assert git(proyecto, "log", "--format=%s").strip() == "Primer commit: estructura del proyecto"
    assert git(proyecto, "status", "--porcelain") == ""  # todo dentro del commit
    assert git(proyecto, "branch", "--show-current").strip() == "main"


def test_java_y_web_traen_su_plantilla(tmp_path):
    assert crear(tmp_path, "-l", "java", "--sin-git").exit_code == 0
    java = tmp_path / "practica"
    assert "class Main" in (java / "src" / "Main.java").read_text(encoding="utf-8")
    assert "*.class" in (java / ".gitignore").read_text(encoding="utf-8")
    assert not (java / ".git").exists()

    web = runner.invoke(app, ["nuevo", "web", "-l", "web", "-c", str(tmp_path), "--sin-git", "--si"])
    assert web.exit_code == 0, web.output
    carpeta = tmp_path / "web"
    assert 'href="css/estilos.css"' in (carpeta / "index.html").read_text(encoding="utf-8")
    assert (carpeta / "js" / "main.js").exists() and (carpeta / "img" / ".gitkeep").exists()


def test_enseña_el_plan_y_respeta_el_no(tmp_path):
    resultado = crear(tmp_path, "--sin-git", entrada="n\n")
    assert "README.md" in resultado.output and ".gitignore" in resultado.output
    assert "Cancelado" in resultado.output
    assert not (tmp_path / "practica").exists()


def test_simular_no_crea_nada(tmp_path):
    resultado = crear(tmp_path, "--simular", entrada="")
    assert resultado.exit_code == 0, resultado.output
    assert "Simulado" in resultado.output and "src/main.py" in resultado.output
    assert creados(tmp_path) == []


def test_si_la_carpeta_existe_no_la_pisa(tmp_path):
    (tmp_path / "practica").mkdir()
    (tmp_path / "practica" / "mio.txt").write_text("no tocar", encoding="utf-8")
    resultado = crear(tmp_path, "--sin-git", "--si")
    assert resultado.exit_code == 0, resultado.output
    assert "se usa «practica (1)»" in resultado.output
    assert (tmp_path / "practica (1)" / "README.md").read_text(encoding="utf-8").startswith("# practica (1)")
    assert sorted(p.name for p in (tmp_path / "practica").iterdir()) == ["mio.txt"]


def test_nombres_y_carpetas_que_no_valen_sin_traza(tmp_path):
    for nombre in ("a/b", "con", "malo:nombre", ""):
        resultado = runner.invoke(app, ["nuevo", nombre, "-c", str(tmp_path), "--si"])
        assert resultado.exit_code == 1, (nombre, resultado.output)
        assert "Traceback" not in resultado.output
    sin_carpeta = runner.invoke(app, ["nuevo", "x", "-c", str(tmp_path / "no-hay"), "--si"])
    assert sin_carpeta.exit_code == 1 and "No existe la carpeta" in sin_carpeta.output
    assert creados(tmp_path) == []


def test_sin_git_instalado_crea_los_archivos_y_dice_como_instalarlo(tmp_path, monkeypatch):
    monkeypatch.setattr(nuevo.shutil, "which", lambda programa: None)
    resultado = crear(tmp_path, "--si")
    assert resultado.exit_code == 0, resultado.output
    assert "No encuentro git" in resultado.output and "winget install Git.Git" in resultado.output
    assert (tmp_path / "practica" / "README.md").exists()
    assert not (tmp_path / "practica" / ".git").exists()


@hay_git
def test_si_git_no_sabe_quien_eres_lo_explica(tmp_path, git_aislado, monkeypatch):
    git_aislado.write_text("[init]\n\tdefaultBranch = main\n", encoding="utf-8")  # sin user
    monkeypatch.setenv("GIT_AUTHOR_NAME", "")
    monkeypatch.setenv("EMAIL", "")
    monkeypatch.setattr(
        nuevo, "git",
        lambda *a, carpeta: (
            nuevo.subprocess.CompletedProcess(a, 128, "", "Please tell me who you are. user.email")
            if a[0] == "commit" else nuevo.subprocess.CompletedProcess(a, 0, "", "")
        ),
    )
    resultado = crear(tmp_path, "--si")
    assert resultado.exit_code == 0, resultado.output
    assert "git no sabe quién eres" in resultado.output
    assert "git config --global user.name" in resultado.output
