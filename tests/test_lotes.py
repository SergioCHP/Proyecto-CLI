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


def test_ctrl_c_no_empieza_mas_y_no_deja_nada_a_medias(tmp_path, monkeypatch):
    """Sin depender del reloj: la tarea 2 se queda en marcha hasta que, tras el Ctrl+C, se
    cancela la cola y sale el aviso de «Cortando»; la 3 está en cola y no debe empezar."""
    import concurrent.futures
    import signal
    import threading

    import typer

    empezadas = []
    segunda_en_marcha, soltar_la_segunda = threading.Event(), threading.Event()
    avisos = []

    def tarea(numero, falla=False):
        destino = tmp_path / f"{numero}.txt"

        def hacer():
            empezadas.append(numero)
            destino.write_text("a medias")
            if falla:
                segunda_en_marcha.set()
                assert soltar_la_segunda.wait(5)
                raise OSError("cortado a medias")
            destino.write_text("hecho")

        return destino, hacer

    d1, h1 = tarea(1)
    d2, h2 = tarea(2, falla=True)
    d3, h3 = tarea(3)
    (tmp_path / "2b.txt").write_text("otra página a medias")
    (tmp_path / "2c.txt").mkdir()  # no se puede borrar como archivo: tiene que avisarse
    tareas = [
        Tarea(tmp_path / "o1", d1, h1),
        Tarea(tmp_path / "o2", d2, h2, mas_destinos=[tmp_path / "2b.txt", tmp_path / "2c.txt"]),
        Tarea(tmp_path / "o3", d3, h3),
    ]
    llamadas = []
    esperar_de_verdad = concurrent.futures.wait

    def wait_con_ctrl_c(pendientes, timeout, return_when):
        llamadas.append(1)
        if len(llamadas) == 1:  # con un hilo, la primera en acabar es la 1
            return esperar_de_verdad(pendientes, timeout=5, return_when=return_when)
        assert segunda_en_marcha.wait(5)
        raise KeyboardInterrupt

    class Consola:  # apunta los avisos y, con el de «Cortando» (la cola ya cancelada), suelta la 2
        def print(self, texto, **_):
            avisos.append(texto)
            soltar_la_segunda.set()

    monkeypatch.setattr(lotes, "wait", wait_con_ctrl_c)
    monkeypatch.setattr(lotes, "error_console", Consola())
    antes = signal.getsignal(signal.SIGINT)
    with pytest.raises(typer.Exit) as salida:
        hacer_todo(tareas, hilos=1)
    assert salida.value.exit_code == 130
    assert signal.getsignal(signal.SIGINT) is antes  # Ctrl+C vuelve a funcionar como antes
    assert d1.read_text() == "hecho"  # acabó bien: se queda
    assert not d2.exists() and not (tmp_path / "2b.txt").exists()  # falló: fuera lo que se pudo
    assert 3 not in empezadas and not d3.exists()  # en cola: ni se empieza
    todo = "\n".join(avisos)
    assert "o2:" in todo and "cortado a medias" in todo  # el fallo se dice
    assert "bórralo tú: 2c.txt" in todo and "No queda nada a medias" not in todo
    assert "Cortado: 1 archivo nuevo de 3" in todo
