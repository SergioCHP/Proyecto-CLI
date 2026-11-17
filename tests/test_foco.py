import re
import sqlite3

import pytest
from typer.testing import CliRunner

from navaja.app import app
from navaja.comandos import foco
from navaja.comun import directorio_datos

runner = CliRunner()


def plano(texto):
    """Sin los bordes de las tablas ni los saltos de línea: «redes 2 1 h 15 min»."""
    return " ".join(re.sub(r"[│┃┏┓┡┩└┘┌┐├┤┼╇╈━─┳┻┬┴┠┨┯┷]", " ", texto).split())


@pytest.fixture
def reloj(monkeypatch):
    """Sin esperar de verdad: cada cuenta atrás se apunta y termina entera (o como se diga)."""
    llamadas = []
    sonidos = []
    resultado = {"parar_en": None}

    def falsa(segundos, titulo, detalle, estilo="acento"):
        llamadas.append((segundos, titulo, detalle))
        if resultado["parar_en"] is not None and len(llamadas) == resultado["parar_en"][0]:
            return resultado["parar_en"][1], False
        return segundos, True

    monkeypatch.setattr(foco, "cuenta_atras", falsa)
    monkeypatch.setattr(foco, "sonar", lambda: sonidos.append(1))
    return llamadas, sonidos, resultado


def sesiones():
    ruta = directorio_datos() / "foco.db"
    if not ruta.exists():
        return []
    with sqlite3.connect(ruta) as conexion:
        return conexion.execute("SELECT asignatura, segundos, completa FROM sesiones ORDER BY id").fetchall()


def test_formatos_de_tiempo():
    assert foco.mmss(0) == "00:00"
    assert foco.mmss(90) == "01:30"
    assert foco.mmss(1500) == "25:00"
    assert foco.mmss(3900) == "1:05:00"
    assert foco.mmss(-5) == "00:00"
    assert foco.tiempo_legible(0) == "0 min"
    assert foco.tiempo_legible(30) == "menos de 1 min"
    assert foco.tiempo_legible(600) == "10 min"
    assert foco.tiempo_legible(3600) == "1 h"
    assert foco.tiempo_legible(4500) == "1 h 15 min"


def test_numeros_grandes_miden_cinco_lineas_y_lo_mismo_de_ancho():
    dibujo = foco.numeros_grandes("25:00").splitlines()
    assert len(dibujo) == 5
    assert len({len(linea) for linea in dibujo}) == 1
    assert "#" in foco.numeros_grandes("25:00", "#") and "█" not in foco.numeros_grandes("25:00", "#")


def test_foco_a_secas_es_un_bloque_de_25_minutos(reloj):
    llamadas, sonidos, _ = reloj
    resultado = runner.invoke(app, ["foco"])
    assert resultado.exit_code == 0, resultado.output
    assert [c[0] for c in llamadas] == [25 * 60]  # un bloque, sin descanso al final
    assert len(sonidos) == 1
    assert sesiones() == [("", 1500, 1)]
    assert "Hoy llevas 25 min" in resultado.output


def test_varios_bloques_con_descanso_entre_ellos(reloj):
    llamadas, sonidos, _ = reloj
    resultado = runner.invoke(
        app, ["foco", "empieza", "-t", "50", "-d", "10", "-b", "2", "-a", "redes"]
    )
    assert resultado.exit_code == 0, resultado.output
    assert [c[:2] for c in llamadas] == [(3000, "A trabajar"), (600, "Descanso"), (3000, "A trabajar")]
    assert llamadas[0][2] == "bloque 1 de 2 · redes"
    assert len(sonidos) == 3
    assert sesiones() == [("redes", 3000, 1), ("redes", 3000, 1)]  # el descanso no cuenta


def test_sin_descanso(reloj):
    llamadas, _, _ = reloj
    runner.invoke(app, ["foco", "empieza", "-d", "0", "-b", "2"])
    assert [c[1] for c in llamadas] == ["A trabajar", "A trabajar"]


def test_simular_no_espera_ni_guarda(reloj):
    llamadas, sonidos, _ = reloj
    resultado = runner.invoke(app, ["foco", "empieza", "-b", "3", "--simular"])
    assert resultado.exit_code == 0, resultado.output
    assert "Plan" in resultado.output and "Simulado" in resultado.output
    assert llamadas == [] and sonidos == []
    assert sesiones() == []


def test_parar_a_medias_apunta_lo_que_llevabas_si_paso_un_minuto(reloj):
    _, sonidos, parar = reloj
    parar["parar_en"] = (1, 600)  # Ctrl+C a los 10 minutos del primer bloque
    resultado = runner.invoke(app, ["foco", "empieza", "-a", "bd", "-b", "2"])
    assert resultado.exit_code == 0, resultado.output
    assert "Parado a los 10 min" in resultado.output and "Apuntado" in resultado.output
    assert sesiones() == [("bd", 600, 0)]
    assert sonidos == []  # no suena si lo paraste tú


def test_parar_antes_de_un_minuto_no_se_apunta(reloj):
    _, _, parar = reloj
    parar["parar_en"] = (1, 30)
    resultado = runner.invoke(app, ["foco"])
    assert "No se apunta" in resultado.output
    assert sesiones() == []


def test_historial_por_asignatura(reloj):
    assert "No hay bloques apuntados" in runner.invoke(app, ["foco", "historial"]).output
    runner.invoke(app, ["foco", "empieza", "-t", "30", "-a", "redes"])
    runner.invoke(app, ["foco", "empieza", "-t", "45", "-a", "redes"])
    runner.invoke(app, ["foco", "empieza", "-t", "10"])
    texto = plano(runner.invoke(app, ["foco", "historial"]).output)
    assert "redes 2 1 h 15 min" in texto
    assert "sin asignatura 1 10 min" in texto
    assert "Total 3 1 h 25 min" in texto
    assert "Hoy: 1 h 25 min" in texto


@pytest.mark.parametrize("opcion", [["-t", "0"], ["-b", "0"], ["-d", "-1"], ["-t", "500"]])
def test_valores_fuera_de_rango_son_error_de_uso(opcion):
    resultado = runner.invoke(app, ["foco", "empieza", *opcion, "--simular"])
    assert resultado.exit_code == 2
    assert "Traceback" not in resultado.output


def test_la_cuenta_atras_de_verdad_llega_a_cero(monkeypatch):
    monkeypatch.setattr(foco.time, "sleep", lambda s: None)
    reloj = iter([0.0, 0.0, 0.5, 1.2, 1.2])  # inicio, fin = 1 s; luego va pasando el tiempo
    monkeypatch.setattr(foco.time, "monotonic", lambda: next(reloj))
    assert foco.cuenta_atras(1, "A trabajar", "bloque 1 de 1") == (1, True)


def test_ctrl_c_en_la_cuenta_atras_devuelve_lo_que_llevaba(monkeypatch):
    marcas = iter([0.0, 5.0, 130.0])  # inicio, un tic, y al parar (130 s después)

    def dormir(segundos):
        raise KeyboardInterrupt

    monkeypatch.setattr(foco.time, "sleep", dormir)
    monkeypatch.setattr(foco.time, "monotonic", lambda: next(marcas))
    assert foco.cuenta_atras(1500, "A trabajar", "bloque 1 de 1") == (130, False)
