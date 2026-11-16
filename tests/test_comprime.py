import tarfile
import zipfile

from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.comprime import Formato, destino_por_defecto, nombre_dentro, que_meter

runner = CliRunner()


def proyecto(tmp_path):
    raiz = tmp_path / "practica"
    for ruta in ("src/main.py", "README.md", ".git/HEAD", ".venv/x", "src/__pycache__/a.pyc", "notas.log"):
        (raiz / ruta).parent.mkdir(parents=True, exist_ok=True)
        (raiz / ruta).write_text("contenido " * 50)
    return raiz


def test_que_meter_sin_lo_que_sobra(tmp_path):
    raiz = proyecto(tmp_path)
    archivos, fuera = que_meter(raiz, False, ("*.log",))
    assert sorted(a.relative_to(raiz).as_posix() for a in archivos) == ["README.md", "src/main.py"]
    assert set(fuera) == {".git/", ".venv/", "__pycache__/", "notas.log"}
    assert len(que_meter(raiz, True, ())[0]) == 6


def test_nombres(tmp_path):
    raiz = proyecto(tmp_path)
    assert destino_por_defecto(raiz, Formato.zip) == tmp_path / "practica.zip"
    assert destino_por_defecto(raiz / "README.md", Formato.targz) == raiz / "README.tar.gz"
    assert nombre_dentro(raiz, raiz / "src" / "main.py") == "practica/src/main.py"


def test_simular_no_crea_nada(tmp_path):
    raiz = proyecto(tmp_path)
    salida = runner.invoke(app, ["comprime", str(raiz), "--simular"])
    assert salida.exit_code == 0 and not (tmp_path / "practica.zip").exists()


def test_zip_con_su_carpeta_dentro_y_sin_pisar(tmp_path):
    raiz = proyecto(tmp_path)
    (tmp_path / "practica.zip").write_text("el de antes")
    salida = runner.invoke(app, ["comprime", str(raiz), "--si"])
    assert salida.exit_code == 0
    assert (tmp_path / "practica.zip").read_text() == "el de antes"
    with zipfile.ZipFile(tmp_path / "practica (1).zip") as z:
        assert sorted(z.namelist()) == ["practica/README.md", "practica/notas.log", "practica/src/main.py"]
    assert not list(tmp_path.glob(".*parcial"))


def test_tar_gz_y_destino(tmp_path):
    raiz = proyecto(tmp_path)
    salida = runner.invoke(app, ["comprime", str(raiz), "--si", "-f", "tar.gz", "--destino", str(tmp_path / "entregas")])
    assert salida.exit_code == 0
    with tarfile.open(tmp_path / "entregas" / "practica.tar.gz") as tar:
        assert "practica/src/main.py" in tar.getnames()


def test_respuesta_no(tmp_path):
    raiz = proyecto(tmp_path)
    salida = runner.invoke(app, ["comprime", str(raiz)], input="n\n")
    assert salida.exit_code == 0 and not (tmp_path / "practica.zip").exists()
