import os

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
