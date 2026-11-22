import os

import pytest

import navaja
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


def instalada_desde(monkeypatch, origen: dict) -> None:
    """Hace como si navaja se hubiera instalado así (lo que uv deja en direct_url.json)."""
    monkeypatch.setattr(lotes, "origen_instalacion", lambda: origen)


EDITABLE = {"url": "file:///C:/Users/ana/Proyecto-CLI", "dir_info": {"editable": True}}


def test_falta_libreria_o_programa(monkeypatch):
    instalada_desde(monkeypatch, EDITABLE)
    with pytest.raises(FaltaAlgo, match=r'Desde la carpeta de navaja: uv tool install --editable "\.\[todo\]"'):
        libreria("no_existe_xyz", "noexiste", "cosa", "probar")
    # siempre todos juntos: instalar solo uno quitaría los demás
    assert lotes.como_instalar("fondo") == 'uv tool install --editable ".[todo,fondo]"'
    monkeypatch.setattr(lotes, "buscar_programa", lambda *e: None)
    monkeypatch.setattr(lotes, "WINDOWS", True)
    with pytest.raises(FaltaAlgo, match="winget install Gyan.FFmpeg"):
        programa("ffmpeg", "convertir vídeo")


def test_instalada_desde_github_dice_la_orden_de_github_con_su_version(monkeypatch):
    """Quien la instaló con la orden del README no tiene la carpeta: --editable no le vale."""
    instalada_desde(monkeypatch, {
        "url": "https://github.com/SergioCHP/Proyecto-CLI",
        "vcs_info": {"vcs": "git", "requested_revision": "v1.0.0", "commit_id": "eb0ff90"},
    })
    assert lotes.como_instalar("fondo") == (
        'uv tool install --force "navaja[todo,fondo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.0.0"'
    )
    with pytest.raises(FaltaAlgo, match="Instálalo con: uv tool install --force") as error:
        libreria("no_existe_xyz", "noexiste", "cosa", "probar")
    assert "--editable" not in str(error.value) and "carpeta de navaja" not in str(error.value)


def test_desde_github_sin_version_o_sin_saber_de_donde_usa_main(monkeypatch):
    instalada_desde(monkeypatch, {"url": "https://github.com/SergioCHP/Proyecto-CLI", "vcs_info": {"vcs": "git"}})
    assert lotes.como_instalar() == 'uv tool install --force "navaja[todo] @ git+https://github.com/SergioCHP/Proyecto-CLI"'
    instalada_desde(monkeypatch, {})  # ni editable ni de git: el .zip de esta versión (sin git)
    assert lotes.como_instalar() == (
        f'uv tool install --force "navaja[todo] @ {lotes.REPO}/archive/refs/tags/v{navaja.__version__}.zip"'
    )


def test_instalada_con_el_instalador_dice_la_orden_con_su_zip(monkeypatch):
    """El instalador (instalar.ps1 / instalar.sh) instala desde el .zip de la versión: el
    arreglo de «doctor» tiene que usar ese mismo .zip, no git (que quizá no tiene)."""
    zip_ = "https://github.com/SergioCHP/Proyecto-CLI/archive/refs/tags/v1.2.0.zip"
    instalada_desde(monkeypatch, {"url": zip_, "archive_info": {}})
    assert lotes.como_instalar("fondo") == f'uv tool install --force "navaja[todo,fondo] @ {zip_}"'
    assert "git+" not in lotes.como_instalar()


def test_doctor_sugiere_la_orden_segun_como_se_instalo(monkeypatch):
    from navaja.comandos import doctor

    monkeypatch.setattr(doctor, "version_de", lambda paquete: None)  # falta todo
    instalada_desde(monkeypatch, {"url": "https://github.com/SergioCHP/Proyecto-CLI", "vcs_info": {"vcs": "git"}})
    arreglos = {r.arreglo for r in doctor.revisar_librerias()}
    assert all("git+https://github.com/SergioCHP/Proyecto-CLI" in a for a in arreglos)
    instalada_desde(monkeypatch, EDITABLE)
    assert all("--editable" in r.arreglo for r in doctor.revisar_librerias())


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


def test_expandir_corchetes_tal_cual_y_sin_ocultos(tmp_path):
    for nombre in ("tema1.pdf", "tema[1] v2.pdf", "apuntes [borrador].pdf", "desktop.ini", ".oculto.pdf"):
        (tmp_path / nombre).write_text("x")
    (tmp_path / "[2026] fotos").mkdir()
    (tmp_path / "[2026] fotos" / "a.jpg").write_text("x")
    nombres = lambda *p: [r.name for r in expandir([str(tmp_path / x) for x in p])]  # noqa: E731
    assert nombres("*") == ["apuntes [borrador].pdf", "tema1.pdf", "tema[1] v2.pdf"]  # sin ocultos
    assert nombres("*[borrador].pdf") == ["apuntes [borrador].pdf"]
    assert nombres("tema[1]*.pdf") == ["tema[1] v2.pdf"]  # no coge tema1.pdf
    assert nombres("[2026] fotos/*.jpg") == ["a.jpg"]  # corchetes también en la carpeta
    # «.oculto.pdf» cuenta como oculto (es_oculto): sin ver_ocultos, «.*» no lo daría
    assert nombres(".*") == [".oculto.pdf"]  # empezando por punto, se piden
    assert nombres("**.pdf") == ["apuntes [borrador].pdf", "tema1.pdf", "tema[1] v2.pdf"]  # como «*»
    assert nombres("desktop.ini") == ["desktop.ini"]  # por su nombre (sin comodín), sí
    with pytest.raises(NavajaError, match="No existe"):
        expandir([str(tmp_path / "tema[2].pdf")])  # sin * ni ?: un nombre, no un patrón


def test_convierte_con_asterisco_en_una_carpeta_de_windows(tmp_path):
    """Antes, desktop.ini entraba en el «*» y paraba todo: «No sé pasar .ini a .png»."""
    pytest.importorskip("PIL")
    from PIL import Image
    from typer.testing import CliRunner

    from navaja.app import app

    Image.new("RGB", (4, 4)).save(tmp_path / "foto.jpg")
    (tmp_path / "desktop.ini").write_text("[.ShellClassInfo]")
    salida = CliRunner().invoke(app, ["convierte", str(tmp_path / "*"), "a", "png", "--simular"])
    assert salida.exit_code == 0, salida.output
    assert "foto.png" in salida.output and "desktop" not in salida.output


@pytest.mark.skipif(os.name != "nt", reason="unidades (C:) y recursos de red (\\\\servidor): rutas de Windows")
def test_comodin_con_unidad_recurso_de_red_y_prefijo():
    from navaja.comun import patron_glob, tiene_comodin

    # el recurso de red se deja tal cual (glob ya lo toma así); lo de después, escapado
    assert patron_glob(r"\\servidor\apuntes[1]\*[b].pdf") == r"\\servidor\apuntes[1]\*[[]b[]].pdf"
    assert patron_glob(r"C:\a[1]\*.pdf") == r"C:\a[[]1[]]\*.pdf"
    assert not tiene_comodin(r"\\?\C:\x\foto.jpg")  # el «?» del prefijo no es un comodín
    assert tiene_comodin(r"\\?\C:\x\*.jpg") and tiene_comodin("fotos/tema?.md")


def test_expandir_un_patron_relativo(tmp_path, monkeypatch):
    (tmp_path / "a.pdf").write_text("x")
    monkeypatch.chdir(tmp_path)
    assert [r.name for r in expandir(["*.pdf"])] == ["a.pdf"]


@pytest.mark.skipif(os.name != "nt", reason="mayúsculas y atributo oculto: cosas de Windows")
def test_expandir_en_windows_mayusculas_y_atributo_oculto(tmp_path):
    import ctypes

    (tmp_path / "FOTO.JPG").write_text("x")
    secreto = tmp_path / "secreto.jpg"
    secreto.write_text("x")
    assert ctypes.windll.kernel32.SetFileAttributesW(str(secreto), 2)  # FILE_ATTRIBUTE_HIDDEN
    assert [r.name for r in expandir([str(tmp_path / "*.jpg")])] == ["FOTO.JPG"]  # sin el oculto
