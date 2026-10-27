from navaja.comun import ruta_libre, tamano_legible


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
