import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import doctor

runner = CliRunner()


def test_python():
    assert doctor.revisar_python((3, 12)).estado == "ok"
    assert doctor.revisar_python((3, 10)).estado == "error"


def test_librerias_obligatorias_estan():
    revisiones = {r.nombre: r for r in doctor.revisar_librerias()}
    assert all(revisiones[nombre].estado == "ok" for nombre, _ in doctor.OBLIGATORIAS)


def test_opcional_que_falta_es_aviso(monkeypatch):
    monkeypatch.setattr(doctor, "version_de", lambda paquete: None)
    revisiones = doctor.revisar_librerias()
    assert {r.estado for r in revisiones} == {"error", "aviso"}
    assert all(r.arreglo for r in revisiones)


@pytest.mark.parametrize("windows", [False, True])
def test_programa_que_falta(monkeypatch, windows):
    monkeypatch.setattr(doctor, "WINDOWS", windows)
    monkeypatch.setattr(doctor, "buscar_programa", lambda nombre, ejecutables: None)
    revisiones = doctor.revisar_programas()
    assert all(r.estado == "aviso" for r in revisiones)
    assert all(r.arreglo for r in revisiones if r.nombre != "Word")  # Word no se instala con un comando
    assert ("winget" in {r.nombre for r in revisiones}) == windows
    arreglos = " ".join(r.arreglo for r in revisiones)
    assert ("winget install" in arreglos) == windows and ("apt install" in arreglos) != windows


def test_datos_que_no_se_pueden_escribir(tmp_path):
    archivo = tmp_path / "soy-un-archivo"
    archivo.write_text("x")
    assert doctor.revisar_datos(tmp_path).estado == "ok"
    assert doctor.revisar_datos(archivo / "datos").estado == "error"


def test_acciones(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert doctor.revisar_acciones().estado == "aviso"  # no hay
    (tmp_path / "acciones.json").write_text('{"acciones": [}', encoding="utf-8")
    assert doctor.revisar_acciones().estado == "error"


def test_orden(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    salida = runner.invoke(app, ["doctor"])
    assert salida.exit_code == 0 and "Python" in salida.output and "Traceback" not in salida.output
    monkeypatch.setattr(doctor, "revisar_python", lambda: doctor.Revision("Python", "Python", "error", "vieja"))
    assert runner.invoke(app, ["doctor"]).exit_code == 1
