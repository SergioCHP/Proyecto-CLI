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
