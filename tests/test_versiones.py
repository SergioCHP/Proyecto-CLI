"""«acciones versiones»: las versiones viejas que sustituye copiar con el-mas-nuevo."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from navaja import interactivo, versiones
from navaja.app import app
from navaja.comandos.ayuda import subcomandos

runner = CliRunner()


def plano(texto: str) -> str:
    return " ".join(texto.split())


def ordenes(*argumentos: str, entrada: str = "s\n"):
    return runner.invoke(app, list(argumentos), input=entrada)


def crear(ruta: Path, texto: str, hace_dias: float = 0) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    marca = (datetime.now() - timedelta(days=hace_dias)).timestamp()
    os.utime(ruta, (marca, marca))
    return ruta


@pytest.fixture
def sustituidas(tmp_path):
    """Dos archivos del USB sustituidos por versiones más nuevas del PC (pc-a-usb)."""
    pc, usb = tmp_path / "PC", tmp_path / "USB"
    for nombre in ("a.txt", "b.txt"):
        crear(usb / nombre, f"{nombre} viejo", hace_dias=1)
        crear(pc / nombre, f"{nombre} nuevo, de casa")
    config = tmp_path / "acciones.json"
    config.write_text(json.dumps({"version": 1, "acciones": [
        {"nombre": "pc-a-usb", "descripcion": "PC → USB", "tipo": "copiar", "carpeta": str(pc),
         "destino": str(usb), "si_cambia": "el-mas-nuevo"},
    ]}), encoding="utf-8")
    resultado = ordenes("acciones", "ejecutar", "pc-a-usb", "--si", "--config", str(config))
    assert resultado.exit_code == 0, resultado.output
    return usb


def test_ver_sin_versiones():
    resultado = ordenes("acciones", "versiones", "ver")
    assert resultado.exit_code == 0
    assert "No hay versiones viejas guardadas" in resultado.output


def test_ver_lista_lo_sustituido_con_su_accion(sustituidas):
    texto = plano(ordenes("acciones", "versiones", "ver").output)
    assert "a.txt" in texto and "b.txt" in texto and "pc-a-usb" in texto
    assert "2 versiones" in texto and "hoy" in texto


def test_recuperar_no_pisa_lo_que_hay_y_deja_la_vieja_al_lado(sustituidas):
    numero = next(n for n, v in enumerate(versiones.cargar(), 1) if v.sitio.name == "a.txt")
    resultado = ordenes("acciones", "versiones", "recuperar", str(numero))
    assert resultado.exit_code == 0, resultado.output
    assert (sustituidas / "a.txt").read_text(encoding="utf-8") == "a.txt nuevo, de casa"
    assert (sustituidas / "a (1).txt").read_text(encoding="utf-8") == "a.txt viejo"
    assert "como «a (1).txt»" in plano(resultado.output)
    assert [v.sitio.name for v in versiones.cargar()] == ["b.txt"]  # ya no está guardada


def test_recuperar_vuelve_a_su_sitio_si_esta_libre(sustituidas):
    (sustituidas / "b.txt").unlink()
    numero = next(n for n, v in enumerate(versiones.cargar(), 1) if v.sitio.name == "b.txt")
    assert ordenes("acciones", "versiones", "recuperar", str(numero)).exit_code == 0
    assert (sustituidas / "b.txt").read_text(encoding="utf-8") == "b.txt viejo"


def test_recuperar_un_numero_que_no_existe(sustituidas):
    resultado = ordenes("acciones", "versiones", "recuperar", "9")
    assert resultado.exit_code == 1
    assert "No hay ninguna versión con el número 9" in plano(resultado.output)
    assert "Traceback" not in resultado.output


def test_borrar_una_y_despues_todas(sustituidas):
    assert ordenes("acciones", "versiones", "borrar", "1").exit_code == 0
    assert len(versiones.cargar()) == 1
    resultado = ordenes("acciones", "versiones", "borrar")
    assert "Borradas 1 versión" in plano(resultado.output)
    assert versiones.cargar() == []
    guardadas = versiones.carpeta_versiones()
    assert [p.name for p in guardadas.rglob("*") if p.is_file()] == [versiones.INDICE]


def test_borrar_hasta_una_fecha_respeta_las_recientes(sustituidas):
    resultado = ordenes("acciones", "versiones", "borrar", "--hasta", "hace 30 días")
    assert "Ninguna versión es de hasta «hace 30 días»" in plano(resultado.output)
    assert len(versiones.cargar()) == 2
    malo = ordenes("acciones", "versiones", "borrar", "--hasta", "el mes que viene")
    assert malo.exit_code == 1 and "Traceback" not in malo.output


def test_borrar_pregunta_y_no_hace_nada_si_dices_que_no(sustituidas):
    resultado = ordenes("acciones", "versiones", "borrar", entrada="n\n")
    assert "No se podrá deshacer" in plano(resultado.output)
    assert len(versiones.cargar()) == 2


def test_un_indice_roto_no_pierde_los_archivos(sustituidas):
    (versiones.carpeta_versiones() / versiones.INDICE).write_text("{ roto", encoding="utf-8")
    assert "No hay versiones viejas guardadas" in ordenes("acciones", "versiones", "ver").output
    guardados = [p for p in versiones.carpeta_versiones().rglob("*.txt")]
    assert len(guardados) == 2  # siguen ahí


def test_dentro_de_navaja_por_numeros(sustituidas, capsys):
    raiz = typer.main.get_command(app)
    nombres = [n for n, _ in subcomandos(raiz)]
    de_acciones = [n for n, _ in subcomandos(raiz.commands["acciones"])]
    de_versiones = [n for n, _ in subcomandos(raiz.commands["acciones"].commands["versiones"])]
    lineas = iter([
        str(nombres.index("acciones") + 1),
        str(de_acciones.index("versiones") + 1),
        str(de_versiones.index("ver") + 1),
    ])

    def leer(prompt):
        try:
            return next(lineas)
        except StopIteration:
            raise EOFError from None

    interactivo.iniciar(app, leer)
    texto = plano(capsys.readouterr().out)
    assert "a.txt" in texto and "2 versiones" in texto
