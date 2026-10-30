import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from navaja import comun
from navaja.app import app
from navaja.comandos import duplicados
from navaja.comandos.duplicados import (
    MUESTRA,
    Conservar,
    Grupo,
    a_bytes,
    buscar_duplicados,
    ordenar_grupo,
)


def _crear(ruta: Path, nombre: str, contenido: bytes) -> Path:
    archivo = ruta / nombre
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_bytes(contenido)
    return archivo


def _todos(ruta: Path) -> list[Path]:
    return sorted(p for p in ruta.rglob("*") if p.is_file())


def test_a_bytes():
    assert a_bytes("0") == 0
    assert a_bytes("100") == 100
    assert a_bytes("500K") == 500 * 1024
    assert a_bytes("10 mb") == 10 * 1024**2
    assert a_bytes("1,5GB") == int(1.5 * 1024**3)
    for malo in ("diez", "5TB", "", "-3K"):
        with pytest.raises(ValueError):
            a_bytes(malo)


def test_encuentra_iguales_e_ignora_distintos(tmp_path):
    a = _crear(tmp_path, "a.txt", b"hola")
    b = _crear(tmp_path, "sub/b.txt", b"hola")
    _crear(tmp_path, "c.txt", b"adio")  # mismo tamaño, otro contenido
    _crear(tmp_path, "d.txt", b"otra cosa")

    grupos = buscar_duplicados(_todos(tmp_path))
    assert len(grupos) == 1
    assert set(grupos[0].archivos) == {a, b}


def test_vacios_solo_con_minimo_cero(tmp_path):
    _crear(tmp_path, "uno.txt", b"")
    _crear(tmp_path, "dos.txt", b"")

    assert buscar_duplicados(_todos(tmp_path)) == []
    assert len(buscar_duplicados(_todos(tmp_path), minimo=0)) == 1


def test_minimo_descarta_pequenos(tmp_path):
    _crear(tmp_path, "a.bin", b"x" * 10)
    _crear(tmp_path, "b.bin", b"x" * 10)

    assert buscar_duplicados(_todos(tmp_path), minimo=11) == []


def test_mismo_inicio_distinto_final(tmp_path):
    inicio = b"a" * MUESTRA
    _crear(tmp_path, "uno.bin", inicio + b"1")
    _crear(tmp_path, "dos.bin", inicio + b"2")
    assert buscar_duplicados(_todos(tmp_path)) == []

    _crear(tmp_path, "tres.bin", inicio + b"1")
    grupos = buscar_duplicados(_todos(tmp_path))
    assert [sorted(p.name for p in g.archivos) for g in grupos] == [
        ["tres.bin", "uno.bin"]
    ]


def test_enlaces_duros_no_son_duplicados(tmp_path):
    original = _crear(tmp_path, "original.txt", b"contenido")
    try:
        os.link(original, tmp_path / "enlace.txt")
    except (OSError, NotImplementedError):
        pytest.skip("El sistema de archivos no admite enlaces duros")

    assert buscar_duplicados(_todos(tmp_path)) == []


def test_desperdicio():
    grupo = Grupo(10, [Path("a"), Path("b"), Path("c")])
    assert grupo.original == Path("a")
    assert grupo.sobrantes == [Path("b"), Path("c")]
    assert grupo.desperdicio == 20


def test_ordenar_grupo(tmp_path):
    viejo = _crear(tmp_path, "carpeta/viejo.txt", b"x")
    nuevo = _crear(tmp_path, "nuevo.txt", b"x")
    os.utime(viejo, (1_600_000_000, 1_600_000_000))
    os.utime(nuevo, (1_700_000_000, 1_700_000_000))

    assert ordenar_grupo([nuevo, viejo], Conservar.antiguo)[0] == viejo
    assert ordenar_grupo([viejo, nuevo], Conservar.reciente)[0] == nuevo
    assert ordenar_grupo([viejo, nuevo], Conservar.corto)[0] == nuevo


@pytest.fixture
def datos_temporales(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    monkeypatch.setattr(comun, "directorio_datos", lambda: datos)
    monkeypatch.setattr(duplicados, "directorio_datos", lambda: datos)
    return datos


def test_borrar_restaurar_y_vaciar(tmp_path, datos_temporales):
    runner = CliRunner()
    carpeta = tmp_path / "fotos"
    original = _crear(carpeta, "foto.jpg", b"pixeles")
    copia = _crear(carpeta, "foto (1).jpg", b"pixeles")
    _crear(carpeta, "otra.jpg", b"distinta")
    os.utime(original, (1_600_000_000, 1_600_000_000))

    resultado = runner.invoke(app, ["duplicados", "borrar", str(carpeta), "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert original.exists() and not copia.exists()
    papelera = datos_temporales / "papelera"
    assert [p.name for p in _todos(papelera)] == ["foto (1).jpg"]

    resultado = runner.invoke(app, ["duplicados", "restaurar", "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert original.exists() and copia.exists()
    assert _todos(papelera) == []

    runner.invoke(app, ["duplicados", "borrar", str(carpeta), "--si"])
    resultado = runner.invoke(app, ["duplicados", "vaciar", "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert not papelera.exists()
    assert original.exists() and not copia.exists()


def test_carpeta_inexistente_sale_con_1(tmp_path, datos_temporales):
    resultado = CliRunner().invoke(
        app, ["duplicados", "buscar", str(tmp_path / "no-existe")]
    )
    assert resultado.exit_code == 1


def test_minimo_invalido_es_error_de_uso(tmp_path, datos_temporales):
    resultado = CliRunner().invoke(
        app, ["duplicados", "buscar", str(tmp_path), "--minimo", "diez"]
    )
    assert resultado.exit_code == 2
