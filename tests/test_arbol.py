from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.arbol import como_markdown, como_texto, dibujar

runner = CliRunner()


def proyecto(tmp_path):
    raiz = tmp_path / "proyecto"
    for ruta in ("src/app/main.py", "src/app/__init__.py", "README.md", ".venv/x", "src/__pycache__/a.pyc"):
        (raiz / ruta).parent.mkdir(parents=True, exist_ok=True)
        (raiz / ruta).write_text("x")
    return raiz


def test_dibujo_con_ramas_carpetas_primero(tmp_path):
    raiz = proyecto(tmp_path)
    dibujo = dibujar(raiz)
    assert como_texto(raiz, dibujo).splitlines() == [
        "proyecto/",
        "├── src/",
        "│   └── app/",
        "│       ├── __init__.py",
        "│       └── main.py",
        "└── README.md",
    ]
    assert (dibujo.carpetas, dibujo.archivos, dibujo.ignorados) == (2, 3, 2)


def test_profundidad_solo_carpetas_y_todo(tmp_path):
    raiz = proyecto(tmp_path)
    assert como_texto(raiz, dibujar(raiz, profundidad=1)).splitlines()[1:] == ["├── src/", "└── README.md", "… y 1 más"]
    assert "README.md" not in como_texto(raiz, dibujar(raiz, solo_carpetas=True))
    assert ".venv/" in como_texto(raiz, dibujar(raiz, todo=True))


def test_se_corta_si_es_enorme(tmp_path):
    for numero in range(30):
        (tmp_path / f"{numero:02}.txt").write_text("x")
    dibujo = dibujar(tmp_path, maximo=10)
    assert len(dibujo.lineas) == 10 and dibujo.sin_ver == 20


def test_guardar_en_markdown_sin_pisar(tmp_path):
    raiz = proyecto(tmp_path)
    destino = tmp_path / "arbol.md"
    destino.write_text("lo mío")
    salida = runner.invoke(app, ["arbol", str(raiz), "--guardar", str(destino)])
    assert salida.exit_code == 0 and destino.read_text() == "lo mío"
    nuevo = tmp_path / "arbol (1).md"
    assert nuevo.read_text(encoding="utf-8") == como_markdown(raiz, dibujar(raiz))
    assert nuevo.read_text(encoding="utf-8").startswith("```text\nproyecto/")


def test_carpeta_que_no_existe(tmp_path):
    assert runner.invoke(app, ["arbol", str(tmp_path / "no")]).exit_code == 1
