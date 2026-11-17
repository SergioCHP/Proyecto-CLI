import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import chuleta
from navaja.errores import NavajaError

runner = CliRunner()


def test_vienen_git_linux_y_powershell():
    temas = chuleta.de_navaja()
    assert {"git", "linux", "powershell"} <= set(temas)
    for nombre, hoja in temas.items():
        assert hoja.texto.startswith("# "), nombre
        assert hoja.titulo != nombre, nombre  # el título dice de qué va


def test_sin_tema_ensena_la_lista():
    resultado = runner.invoke(app, ["chuleta"])
    assert resultado.exit_code == 0, resultado.output
    for tema in ("git", "linux", "powershell"):
        assert tema in resultado.output
    assert "--editar" in resultado.output


def test_ensena_la_chuleta_entera():
    resultado = runner.invoke(app, ["chuleta", "Git.md"])
    assert resultado.exit_code == 0, resultado.output
    assert "git reset --soft HEAD~1" in resultado.output
    assert "Deshacer" in resultado.output


def test_un_tema_que_no_hay_sugiere_el_parecido():
    resultado = runner.invoke(app, ["chuleta", "gti"])
    assert resultado.exit_code == 1
    assert "¿Querías decir git?" in resultado.output
    assert "Traceback" not in resultado.output


@pytest.mark.parametrize("tema", ["../fuera", "a/b", "con", "dos palabras", ""])
def test_nombres_que_no_valen(tema):
    with pytest.raises(NavajaError):
        chuleta.nombre_del_tema(tema)


def test_editar_una_de_navaja_crea_tu_copia_y_gana_la_tuya(monkeypatch):
    abiertas = []
    monkeypatch.setattr(chuleta, "abrir_en_editor", abiertas.append)
    resultado = runner.invoke(app, ["chuleta", "git", "--editar"])
    assert resultado.exit_code == 0, resultado.output
    ruta = chuleta.carpeta_tuyas() / "git.md"
    assert abiertas == [ruta]
    assert ruta.read_text(encoding="utf-8") == chuleta.de_navaja()["git"].texto

    ruta.write_text("# git a mi manera\n\n- `git lg` — mi alias\n", encoding="utf-8")
    resultado = runner.invoke(app, ["chuleta", "git"])
    assert "git lg" in resultado.output
    assert "Es tuya" in resultado.output
    lista = runner.invoke(app, ["chuleta"]).output
    assert "git a mi manera" in lista and "tuya" in lista


def test_editar_una_nueva_usa_la_plantilla_y_no_pisa_la_que_ya_hay(monkeypatch):
    monkeypatch.setattr(chuleta, "abrir_en_editor", lambda ruta: None)
    assert runner.invoke(app, ["chuleta", "sql", "--editar"]).exit_code == 0
    ruta = chuleta.carpeta_tuyas() / "sql.md"
    assert ruta.read_text(encoding="utf-8").startswith("# sql")
    ruta.write_text("# SQL\n", encoding="utf-8")
    assert runner.invoke(app, ["chuleta", "sql", "--editar"]).exit_code == 0
    assert ruta.read_text(encoding="utf-8") == "# SQL\n"


def test_sin_editor_dice_donde_esta_sin_traza(monkeypatch):
    def sin_editor(ruta):
        raise RuntimeError("No se encontró el editor 'nada'. Define la variable EDITOR.")

    monkeypatch.setattr(chuleta, "abrir_en_editor", sin_editor)
    resultado = runner.invoke(app, ["chuleta", "git", "--editar"])
    assert resultado.exit_code == 1
    assert "Ábrela tú" in resultado.output
    assert "Traceback" not in resultado.output


def test_una_tuya_que_no_es_utf8_no_rompe_la_lista():
    carpeta = chuleta.carpeta_tuyas()
    carpeta.mkdir(parents=True)
    (carpeta / "rota.md").write_bytes(b"# mal \xff\xfe")
    resultado = runner.invoke(app, ["chuleta"])
    assert resultado.exit_code == 0, resultado.output
    assert "rota" not in resultado.output


def test_tab_sugiere_los_temas():
    assert [n for n, _ in chuleta.temas_para_tab("po")] == ["powershell"]
