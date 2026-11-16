import pytest

from navaja import lotes
from navaja.errores import NavajaError
from navaja.lotes import FaltaAlgo, Tarea, al_lado, expandir, hacer_todo, libreria, programa


def test_expandir_rutas_y_comodines(tmp_path):
    for nombre in ("b.jpg", "a.jpg", "c.png"):
        (tmp_path / nombre).write_text("x")
    assert [p.name for p in expandir([str(tmp_path / "*.jpg")])] == ["a.jpg", "b.jpg"]
    juntos = expandir([str(tmp_path / "c.png"), str(tmp_path / "*.png"), str(tmp_path / "a.jpg")])
    assert [p.name for p in juntos] == ["c.png", "a.jpg"]  # sin repetir, en el orden escrito
    for malo in (str(tmp_path / "*.gif"), str(tmp_path / "no.jpg"), str(tmp_path)):
        with pytest.raises(NavajaError):
            expandir([malo])


def test_al_lado_sin_pisar_ni_repetir(tmp_path):
    foto = tmp_path / "foto.heic"
    (tmp_path / "foto.jpg").write_text("ya estaba")
    reservados: set[str] = set()
    assert al_lado(foto, "", ".jpg", reservados).name == "foto (1).jpg"
    assert al_lado(foto, "", ".jpg", reservados).name == "foto (2).jpg"
    assert al_lado(foto, "-sin-fondo", ".png").name == "foto-sin-fondo.png"


def test_si_una_falla_las_demas_siguen(tmp_path):
    def mal():
        (tmp_path / "b.out").write_text("a medias")
        raise NavajaError("rota")

    tareas = [
        Tarea(tmp_path / "a", tmp_path / "a.out", lambda: (tmp_path / "a.out").write_text("ok")),
        Tarea(tmp_path / "b", tmp_path / "b.out", mal),
        Tarea(tmp_path / "c", tmp_path / "c.out", lambda: 1 / 0),
    ]
    fallos = hacer_todo(tareas)
    assert sorted(f.origen.name for f in fallos) == ["b", "c"]
    assert (tmp_path / "a.out").exists() and not (tmp_path / "b.out").exists()  # lo roto se quita


def test_falta_libreria_o_programa(monkeypatch):
    with pytest.raises(FaltaAlgo, match=r'uv tool install --editable "\.\[todo\]"'):
        libreria("no_existe_xyz", "noexiste", "cosa", "probar")
    # siempre todos juntos: instalar solo uno quitaría los demás
    assert lotes.como_instalar("fondo") == 'uv tool install --editable ".[todo,fondo]"'
    monkeypatch.setattr(lotes, "buscar_programa", lambda *e: None)
    monkeypatch.setattr(lotes, "WINDOWS", True)
    with pytest.raises(FaltaAlgo, match="winget install Gyan.FFmpeg"):
        programa("ffmpeg", "convertir vídeo")
