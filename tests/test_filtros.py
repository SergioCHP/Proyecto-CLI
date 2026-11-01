from datetime import date, datetime

import pytest

from navaja.comun import es_oculto
from navaja.filtros import extensiones, periodo, rango

HOY = date(2026, 11, 1)


@pytest.mark.parametrize(
    "texto, inicio, fin",
    [
        ("hoy", date(2026, 11, 1), date(2026, 11, 1)),
        ("ayer", date(2026, 10, 31), date(2026, 10, 31)),
        ("hace 30 días", date(2026, 10, 2), date(2026, 10, 2)),
        ("hace 2 semanas", date(2026, 10, 18), date(2026, 10, 18)),
        ("hace 3 meses", date(2026, 8, 1), date(2026, 8, 1)),
        ("1/9/2026", date(2026, 9, 1), date(2026, 9, 1)),
        ("01-09-26", date(2026, 9, 1), date(2026, 9, 1)),
        ("1/9", date(2026, 9, 1), date(2026, 9, 1)),
        ("2026-09-15", date(2026, 9, 15), date(2026, 9, 15)),
        ("septiembre 2026", date(2026, 9, 1), date(2026, 9, 30)),
        ("Febrero de 2028", date(2028, 2, 1), date(2028, 2, 29)),
        ("9/2026", date(2026, 9, 1), date(2026, 9, 30)),
        ("2026", date(2026, 1, 1), date(2026, 12, 31)),
    ],
)
def test_fechas_como_las_escribe_cualquiera(texto, inicio, fin):
    assert periodo(texto, HOY) == (inicio, fin)


@pytest.mark.parametrize("texto", ["mañana", "31/2/2026", "13/13/2026", "septiembrillo"])
def test_fechas_que_no_se_entienden(texto):
    with pytest.raises(ValueError, match="No entiendo la fecha"):
        periodo(texto, HOY)


def test_rango_va_del_primer_al_ultimo_segundo():
    inicio, fin = rango("septiembre 2026", "septiembre 2026")
    assert inicio == datetime(2026, 9, 1)
    assert fin.date() == date(2026, 9, 30) and fin.hour == 23
    assert rango("", "") == (None, None)
    with pytest.raises(ValueError, match="posterior"):
        rango("1/10/2026", "1/9/2026")


def test_tipos_y_extensiones():
    assert ".jpg" in extensiones("imágenes")
    assert ".jpg" in extensiones("fotos")
    assert extensiones("pdf, .TXT, *.md") == {".pdf", ".txt", ".md"}
    assert ".pdf" in extensiones("documentos") and ".png" in extensiones("imagenes, pdf")


def test_archivos_de_sistema_se_consideran_ocultos(tmp_path):
    for nombre in ("desktop.ini", "Thumbs.db", ".oculto", "normal.txt"):
        (tmp_path / nombre).write_text("x")
    assert es_oculto(tmp_path / "desktop.ini")
    assert es_oculto(tmp_path / "Thumbs.db")
    assert es_oculto(tmp_path / ".oculto")
    assert not es_oculto(tmp_path / "normal.txt")
