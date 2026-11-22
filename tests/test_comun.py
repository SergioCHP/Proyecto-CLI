import os
from pathlib import Path

import pytest
from rich.prompt import InvalidResponse

from navaja.comun import Confirmar, ruta_libre, tamano_legible


def test_tamano_legible():
    assert tamano_legible(0) == "0 B"
    assert tamano_legible(1023) == "1023 B"
    assert tamano_legible(1024) == "1.0 KB"
    assert tamano_legible(1536) == "1.5 KB"
    assert tamano_legible(1024**3) == "1.0 GB"


def test_ruta_libre(tmp_path):
    original = tmp_path / "informe.txt"
    assert ruta_libre(original) == original

    original.write_text("x")
    assert ruta_libre(original).name == "informe (1).txt"

    (tmp_path / "informe (1).txt").write_text("x")
    assert ruta_libre(original).name == "informe (2).txt"


def test_confirmar_en_castellano():
    pregunta = Confirmar("¿Seguro?")
    for si in ("s", "S", "sí", "si", "y"):
        assert pregunta.process_response(si) is True
    for no in ("n", "No"):
        assert pregunta.process_response(no) is False
    with pytest.raises(InvalidResponse):
        pregunta.process_response("quizá")


def test_preparar_salida_en_git_bash_pasa_a_utf8():
    import io

    from navaja.comun import preparar_salida

    crudo = io.BytesIO()
    flujo = io.TextIOWrapper(crudo, encoding="cp1252")
    preparar_salida(flujo, {"MSYSTEM": "MINGW64"})
    flujo.write("✔ acción → …")
    flujo.flush()
    assert crudo.getvalue().decode("utf-8") == "✔ acción → …"


def test_preparar_salida_redirigida_no_rompe_y_conserva_las_tildes():
    import io

    from navaja.comun import preparar_salida

    crudo = io.BytesIO()
    flujo = io.TextIOWrapper(crudo, encoding="cp1252")
    preparar_salida(flujo, {})
    flujo.write("✔ acción")  # antes: UnicodeEncodeError
    flujo.flush()
    assert crudo.getvalue().decode("cp1252") == "? acción"


def test_preparar_salida_no_toca_lo_que_ya_es_utf8_ni_lo_que_no_se_puede_cambiar():
    import io

    from navaja.comun import preparar_salida

    flujo = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    preparar_salida(flujo, {"MSYSTEM": "MINGW64"})
    assert flujo.encoding == "utf-8" and flujo.errors == "strict"
    preparar_salida(object(), {})  # sin reconfigure: no pasa nada


def test_crear_carpetas_dice_cuales_son_nuevas(tmp_path):
    from navaja.comun import carpetas_creadas, carpetas_supuestas, crear_carpetas, quitar_vacias

    (tmp_path / "ya").mkdir()
    nuevas = crear_carpetas(tmp_path / "ya" / "a" / "b")
    assert nuevas == [tmp_path / "ya" / "a", tmp_path / "ya" / "a" / "b"]
    assert crear_carpetas(tmp_path / "ya" / "a" / "b") == []  # ya existen
    (tmp_path / "ya" / "a" / "f.txt").write_text("x")
    quitar_vacias(nuevas)  # «b» vacía fuera; «a» tiene un archivo: se queda
    assert (tmp_path / "ya" / "a").is_dir() and not (tmp_path / "ya" / "a" / "b").exists()
    (tmp_path / "es-archivo").write_text("x")
    with pytest.raises(OSError):
        crear_carpetas(tmp_path / "es-archivo" / "dentro")  # no se puede: OSError, sin traza
    destino = tmp_path / "x" / "y" / "f.txt"
    assert carpetas_creadas({"creadas": []}, destino) == []
    assert carpetas_creadas({"creadas": [str(tmp_path / "x")]}, destino) == [tmp_path / "x"]
    assert carpetas_creadas({"creadas": None}, destino) == [] and carpetas_creadas({"creadas": "C:/"}, destino) == []
    assert carpetas_creadas({}, destino) is None  # registro de antes de apuntarlas
    assert carpetas_supuestas(destino) == [tmp_path / "x" / "y", tmp_path / "x"]


def test_guardar_acciones_cortado_deja_el_registro_de_antes(monkeypatch):
    from navaja import comun

    comun.guardar_acciones("prueba", [{"origen": "a", "destino": "b"}])
    reemplazar = os.replace  # el de verdad, antes de cambiarlo (comun.os es este mismo módulo)

    def corta(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr(comun.os, "replace", corta)
    with pytest.raises(KeyboardInterrupt):
        comun.guardar_acciones("prueba", [{"origen": "x", "destino": "y"}])
    monkeypatch.setattr(comun.os, "replace", reemplazar)  # solo esto (undo() quitaría NAVAJA_DATOS)
    assert comun.cargar_acciones("prueba") == [{"origen": "a", "destino": "b"}]
    assert not list(comun.directorio_datos().glob("*.navaja"))  # sin temporales sueltos
    comun.guardar_acciones("prueba", [{"origen": "x", "destino": "y"}])  # y ya vuelve a guardar
    assert comun.cargar_acciones("prueba") == [{"origen": "x", "destino": "y"}]


@pytest.fixture
def otra_unidad(monkeypatch):
    """Como si el destino estuviera en otra unidad (un USB): mover es copiar y borrar."""
    from navaja import comun

    monkeypatch.setattr(comun, "misma_unidad", lambda a, b: False)


def test_mover_seguro_a_otra_unidad(tmp_path, otra_unidad):
    from navaja.comun import mover_seguro

    origen = tmp_path / "a.txt"
    origen.write_text("apuntes", encoding="utf-8")
    (tmp_path / "USB").mkdir()
    mover_seguro(origen, tmp_path / "USB" / "a.txt")
    assert not origen.exists() and (tmp_path / "USB" / "a.txt").read_text(encoding="utf-8") == "apuntes"
    assert [p.name for p in (tmp_path / "USB").iterdir()] == ["a.txt"]  # sin temporal


def test_mover_seguro_cortado_copiando_no_deja_nada_a_medias(tmp_path, otra_unidad, monkeypatch):
    import shutil

    from navaja.comun import mover_seguro

    origen = tmp_path / "a.txt"
    origen.write_text("apuntes", encoding="utf-8")
    (tmp_path / "USB").mkdir()

    def copia_a_medias(de, a, *_, **__):
        Path(a).write_text("apun", encoding="utf-8")
        raise KeyboardInterrupt

    copiar = shutil.copy2
    monkeypatch.setattr(shutil, "copy2", copia_a_medias)
    with pytest.raises(KeyboardInterrupt):
        mover_seguro(origen, tmp_path / "USB" / "a.txt")
    monkeypatch.setattr(shutil, "copy2", copiar)  # solo esto (undo() quitaría NAVAJA_DATOS)
    assert origen.read_text(encoding="utf-8") == "apuntes" and list((tmp_path / "USB").iterdir()) == []


def test_mover_seguro_cortado_al_borrar_el_original_no_duplica(tmp_path, otra_unidad, monkeypatch):
    from pathlib import Path as P

    from navaja.comun import mover_seguro

    origen = tmp_path / "a.txt"
    origen.write_text("apuntes", encoding="utf-8")
    (tmp_path / "USB").mkdir()
    borrar = P.unlink

    def no_deja_borrar_el_original(self, *a, **k):
        if self == origen:
            raise KeyboardInterrupt  # copiado entero; justo antes de quitar el original
        return borrar(self, *a, **k)

    monkeypatch.setattr(P, "unlink", no_deja_borrar_el_original)
    with pytest.raises(KeyboardInterrupt):
        mover_seguro(origen, tmp_path / "USB" / "a.txt")
    monkeypatch.setattr(P, "unlink", borrar)
    assert origen.exists() and list((tmp_path / "USB").iterdir()) == []  # en un solo sitio


def test_mover_seguro_cortado_justo_despues_de_borrar_el_original_no_lo_pierde(tmp_path, otra_unidad, monkeypatch):
    """El Ctrl+C llega justo al volver de borrar el original: el archivo está movido y la
    limpieza no debe quitar la copia (antes se perdía de los dos sitios)."""
    from navaja.comun import mover_seguro

    origen = tmp_path / "a.txt"
    origen.write_text("apuntes", encoding="utf-8")
    (tmp_path / "USB").mkdir()
    borrar = Path.unlink

    def borra_y_corta(self, *a, **k):
        borrar(self, *a, **k)
        if self == origen:
            raise KeyboardInterrupt

    monkeypatch.setattr(Path, "unlink", borra_y_corta)
    with pytest.raises(KeyboardInterrupt):
        mover_seguro(origen, tmp_path / "USB" / "a.txt")
    monkeypatch.setattr(Path, "unlink", borrar)
    assert not origen.exists() and (tmp_path / "USB" / "a.txt").read_text(encoding="utf-8") == "apuntes"


def test_mover_seguro_nunca_pisa(tmp_path):
    from navaja.comun import mover_seguro

    (tmp_path / "a.txt").write_text("nuevo", encoding="utf-8")
    (tmp_path / "b.txt").write_text("tuyo", encoding="utf-8")
    with pytest.raises(FileExistsError):
        mover_seguro(tmp_path / "a.txt", tmp_path / "b.txt")
    assert (tmp_path / "a.txt").exists() and (tmp_path / "b.txt").read_text(encoding="utf-8") == "tuyo"


def test_mover_seguro_en_el_mismo_disco_no_copia_si_no_puede_renombrar(tmp_path, monkeypatch):
    """Abierto en Word: renombrar falla, y shutil.move lo copiaba y lo dejaba en dos sitios."""
    from navaja.comun import misma_unidad, mover_seguro

    origen = tmp_path / "a.docx"
    origen.write_text("trabajo", encoding="utf-8")
    assert misma_unidad(origen, tmp_path / "Nueva" / "Sub")  # sube hasta una carpeta que exista
    (tmp_path / "Nueva").mkdir()
    renombrar = os.rename

    def abierto_en_word(*_):
        raise PermissionError(32, "El proceso no tiene acceso al archivo")

    monkeypatch.setattr(os, "rename", abierto_en_word)
    with pytest.raises(PermissionError):
        mover_seguro(origen, tmp_path / "Nueva" / "a.docx")
    monkeypatch.setattr(os, "rename", renombrar)
    assert origen.exists() and list((tmp_path / "Nueva").iterdir()) == []


def _ubuntu_en_espanol(tmp_path, monkeypatch):
    """Una carpeta personal como la de un Ubuntu en español: Descargas, y su user-dirs.dirs."""
    casa = tmp_path / "casa"
    (casa / "Descargas").mkdir(parents=True)
    (casa / ".config").mkdir()
    (casa / ".config" / "user-dirs.dirs").write_text(
        '# comentario\nXDG_DOWNLOAD_DIR="$HOME/Descargas"\nXDG_DESKTOP_DIR="$HOME/"\n', encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: casa))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return casa


def test_carpeta_personal_downloads_es_descargas_en_ubuntu(tmp_path, monkeypatch):
    from navaja.comun import carpeta_personal

    casa = _ubuntu_en_espanol(tmp_path, monkeypatch)
    assert carpeta_personal(casa / "Downloads") == casa / "Descargas"
    assert carpeta_personal(casa / "Downloads" / "fotos") == casa / "Descargas" / "fotos"  # lo de dentro, igual


def test_carpeta_personal_deja_las_rutas_que_no_toca(tmp_path, monkeypatch):
    from navaja.comun import carpeta_personal

    casa = _ubuntu_en_espanol(tmp_path, monkeypatch)
    (casa / "Downloads").mkdir()
    assert carpeta_personal(casa / "Downloads") == casa / "Downloads"  # si existe, es esa
    assert carpeta_personal(casa / "Desktop") == casa / "Desktop"  # apunta a la casa entera: no
    assert carpeta_personal(casa / "Proyectos") == casa / "Proyectos"  # no es de las del sistema
    assert carpeta_personal(tmp_path / "fuera" / "Downloads") == tmp_path / "fuera" / "Downloads"
    assert carpeta_personal(Path("Downloads")) == Path("Downloads")  # relativa


def test_carpeta_personal_sin_user_dirs_la_deja_igual(tmp_path, monkeypatch):
    """Windows, macOS o un Linux sin ese archivo: la ruta tal cual (y luego «no existe»)."""
    from navaja.comun import carpeta_personal

    casa = _ubuntu_en_espanol(tmp_path, monkeypatch)
    (casa / ".config" / "user-dirs.dirs").unlink()
    assert carpeta_personal(casa / "Downloads") == casa / "Downloads"


def test_validar_y_ver_en_ubuntu_en_espanol_usan_descargas(tmp_path, monkeypatch):
    """En el Ubuntu de prueba, «validar» avisaba de que ~/Downloads no existe y «ver» decía
    ~/Downloads, aunque al ejecutar se usaba ~/Descargas."""
    from navaja import esquema
    from navaja.acciones import Accion
    from navaja.comandos.mis_acciones import donde

    casa = _ubuntu_en_espanol(tmp_path, monkeypatch)
    datos = {"nombre": "ordenar-descargas", "descripcion": "x", "tipo": "ordenar", "carpeta": "~/Downloads", "por": "tipo"}
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("USERPROFILE", str(casa))  # Windows: expanduser mira esta
    assert esquema.avisos([datos]) == []  # ya no avisa
    assert donde(Accion.tipos()["ordenar"](datos)) == str(Path("~") / "Descargas")
    sin_descargas = dict(datos, carpeta="~/Proyectos")
    assert esquema.avisos([sin_descargas]) == ["«ordenar-descargas»: la carpeta ~/Proyectos no existe ahora mismo."]
