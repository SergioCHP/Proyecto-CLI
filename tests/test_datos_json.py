import json

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos.datos_json import (
    ErrorDeFormato,
    Leido,
    arbol_de,
    compactar,
    elementos,
    formatear,
    leer,
    profundidad,
)

runner = CliRunner()


def escribir(tmp_path, nombre, texto):
    ruta = tmp_path / nombre
    ruta.write_text(texto, encoding="utf-8")
    return ruta


@pytest.mark.parametrize(
    "texto, linea, dice",
    [
        ('{"a": 1,\n "b": 2,\n}', 3, "sobra una coma"),
        ('{"a": 1\n "b": 2}', 2, "falta una coma"),
        ("{'a': 1}", 1, "comillas dobles"),
        ('{"a" 1}', 1, "dos puntos"),
        ('{"ruta": "C:\\Users"}', 1, "barra invertida"),
    ],
)
def test_errores_en_castellano_con_la_linea(tmp_path, texto, linea, dice):
    with pytest.raises(ErrorDeFormato) as error:
        leer(escribir(tmp_path, "malo.json", texto))
    assert error.value.linea == linea and dice in error.value.motivo


def test_bom_y_claves_repetidas(tmp_path):
    ruta = tmp_path / "bom.json"
    ruta.write_bytes('\ufeff{"a": 1, "a": 2}'.encode("utf-8"))
    leido = leer(ruta)
    assert leido.datos == {"a": 2} and leido.repetidas == ["a"]


def test_yaml(tmp_path):
    pytest.importorskip("yaml")
    leido = leer(escribir(tmp_path, "c.yaml", "a: 1\nb:\n  - x\n"))
    assert leido.yaml and leido.datos == {"a": 1, "b": ["x"]}
    with pytest.raises(ErrorDeFormato) as error:
        leer(escribir(tmp_path, "mal.yml", "a: [1, 2\nb: 3\n"))
    assert error.value.linea >= 2


def test_describir():
    datos = {"a": 1, "b": [1, {"c": None}]}
    assert profundidad(datos) == 3 and elementos(datos) == 5
    assert profundidad(5) == 0


def test_formatear_y_compactar():
    leido = Leido({"b": 1, "a": "ñ"}, yaml=False)
    assert formatear(leido, 2, ordenar=True) == '{\n  "a": "ñ",\n  "b": 1\n}\n'
    assert compactar(leido) == '{"b":1,"a":"ñ"}\n'


def test_arbol_corta_las_listas_largas():
    arbol = arbol_de({"lista": list(range(80))}, "x.json")
    lista = arbol.children[0]
    assert len(lista.children) == 51  # 50 y «… y 30 más»


def test_ordenes(tmp_path):
    bueno = escribir(tmp_path, "bueno.json", '{"nombre": "navaja", "lista": [1, 2]}')
    salida = runner.invoke(app, ["json", "comprueba", str(bueno)])
    assert salida.exit_code == 0 and "bien escrito" in salida.output
    malo = escribir(tmp_path, "malo.json", '{"a": 1,}')
    salida = runner.invoke(app, ["json", "comprueba", str(malo)])
    assert salida.exit_code == 1 and "Línea 1" in salida.output and "Traceback" not in salida.output
    salida = runner.invoke(app, ["json", "compacta", str(bueno)])
    assert salida.output.strip() == '{"nombre":"navaja","lista":[1,2]}'
    salida = runner.invoke(app, ["json", "formatea", str(bueno), "--guardar"])
    nuevo = tmp_path / "bueno-formateado.json"
    assert salida.exit_code == 0 and json.loads(nuevo.read_text(encoding="utf-8")) == {"nombre": "navaja", "lista": [1, 2]}
    assert bueno.read_text(encoding="utf-8") == '{"nombre": "navaja", "lista": [1, 2]}'  # el original igual
    runner.invoke(app, ["json", "formatea", str(bueno), "--guardar"])
    assert (tmp_path / "bueno-formateado (1).json").exists()  # nunca se pisa
    assert "nombre" in runner.invoke(app, ["json", "arbol", str(bueno)]).output
