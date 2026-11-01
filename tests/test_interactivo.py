import os
from datetime import datetime
from pathlib import Path

import pytest
import typer

from navaja import interactivo
from navaja.app import app
from navaja.comandos.ayuda import subcomandos
from navaja.comun import cargar_config


def lector(*lineas):
    """Simula lo que escribe la persona; al acabarse, es como pulsar Ctrl+D."""
    pendientes = iter(lineas)

    def leer(_prompt):
        try:
            return next(pendientes)
        except StopIteration:
            raise EOFError from None

    return leer


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    (tmp_path / "apuntes.pdf").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "dentro.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def salida(capsys):
    capturado = capsys.readouterr()
    return capturado.out + capturado.err


def numero_de(nombre):
    """Número con el que sale en el menú (el mismo orden que ve la persona)."""
    nombres = [n for n, _ in subcomandos(typer.main.get_command(app))]
    return str(nombres.index(nombre) + 1)


def test_dividir_respeta_comillas_y_barras_de_windows():
    assert interactivo.dividir(r'listar "C:\Users\ana\Mis cosas"') == [
        "listar",
        r"C:\Users\ana\Mis cosas",
    ]
    assert interactivo.dividir(r"renombra previsualizar . 'IMG_(\d+)' 'foto_\1'") == [
        "renombra",
        "previsualizar",
        ".",
        r"IMG_(\d+)",
        r"foto_\1",
    ]
    assert interactivo.dividir("listar ~") == ["listar", os.path.expanduser("~")]
    with pytest.raises(ValueError):
        interactivo.dividir('listar "sin cerrar')


def test_salir_vuelve_a_la_carpeta_de_inicio(carpeta, capsys):
    interactivo.iniciar(app, lector("cd sub", "listar", "salir"))
    texto = salida(capsys)
    assert "dentro.txt" in texto
    assert "Hasta luego" in texto
    assert Path.cwd() == carpeta
    assert interactivo.activo is False


def test_cd_a_una_carpeta_que_no_existe(carpeta, capsys):
    interactivo.iniciar(app, lector("cd no-existe", "pwd"))
    texto = salida(capsys)
    assert "No existe la carpeta" in texto
    assert str(carpeta) in texto


def test_numero_ejecuta_en_la_carpeta_actual_sin_preguntar(carpeta, capsys):
    interactivo.iniciar(app, lector(numero_de("listar")))
    texto = salida(capsys)
    assert "apuntes.pdf" in texto
    assert "→ navaja" not in texto  # no ha hecho falta preguntar nada
    assert "Más opciones: --ocultos" in texto


def test_un_error_no_cierra_navaja(carpeta, capsys):
    interactivo.iniciar(app, lector("ocupa no-existe", "listar", "0"))
    texto = salida(capsys)
    assert "La ruta no existe" in texto
    assert "apuntes.pdf" in texto
    assert "Hasta luego" in texto


def test_grupo_abre_submenu_e_intro_vuelve(carpeta, capsys):
    interactivo.iniciar(app, lector("ordena", "", "listar"))
    texto = salida(capsys)
    assert "tramo" in texto and "volver" in texto
    assert "apuntes.pdf" in texto


def test_submenu_sigue_abierto_despues_de_ejecutar(carpeta, capsys):
    # config → 1 (ver) → 2 (nombre): el «2» es de config, no «ocupa» del menú principal
    interactivo.iniciar(app, lector(numero_de("config"), "1", "2", "Lucía"))
    texto = salida(capsys)
    assert "Uso de disco" not in texto
    assert cargar_config()["nombre"] == "Lucía"


def test_numero_fuera_de_rango_en_submenu(carpeta, capsys):
    interactivo.iniciar(app, lector("config", "7"))
    assert "Elige un número del 1 al 2 (0 para volver)." in salida(capsys)


@pytest.mark.parametrize("linea", ["listar", "ls", "navaja listar"])
def test_comando_del_menu_principal_desde_un_submenu(carpeta, capsys, linea):
    interactivo.iniciar(app, lector("config", linea))
    texto = salida(capsys)
    assert "apuntes.pdf" in texto
    assert "No conozco" not in texto


def test_comando_con_obligatorios_sin_argumentos_pregunta(carpeta, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "n")  # a «¿Renombrar…? [s/n]»
    interactivo.iniciar(app, lector("renombra cambiar", "apuntes", "notas", ""))
    texto = salida(capsys)
    assert "→ navaja renombra cambiar apuntes notas" in texto
    assert "notas.pdf" in texto
    assert "Cancelado" in texto
    assert (carpeta / "apuntes.pdf").exists()


def test_texto_opcional_se_pregunta_y_vacio_borra(carpeta, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    (carpeta / "informe (1).pdf").write_text("x")
    # renombra → 1 (cambiar) → buscar « (1)» (con comillas, para el espacio) → Intro (nada)
    interactivo.iniciar(app, lector("renombra", "1", '" (1)"', "", ""))
    salida(capsys)
    assert (carpeta / "informe.pdf").exists()


def test_renombrar_las_imagenes_de_gemini_desde_el_menu(carpeta, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    for codigo in ("4ll5w74ll5w74ll5", "jx2wlfjx2wlfjx2w", "yz08iryz08iryz08"):
        (carpeta / f"Gemini_Generated_Image_{codigo}.png").write_text("x")
    # renombra → 4 (numerar) → nombre → separador (un espacio) → cifras → orden (mal y bien)
    # → ¿con qué archivos? 3 (los que llevan un texto) → gemini
    interactivo.iniciar(
        app, lector("renombra", "4", "gemini", " ", "1", "por tamaño", "", "3", "gemini")
    )
    texto = salida(capsys)
    assert "Escribe nombre o fecha" in texto
    assert '→ navaja renombra numerar gemini --separador " " --cifras 1 --contiene gemini' in texto
    archivos = {p.name for p in carpeta.iterdir() if p.is_file()}
    assert {"gemini 1.png", "gemini 2.png", "gemini 3.png", "apuntes.pdf"} <= archivos
    assert not any(n.startswith("Gemini_") for n in archivos)


def test_ordenar_un_tramo_de_fechas_desde_el_menu(carpeta, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    for nombre, dia in (("septiembre.pdf", 10), ("octubre.pdf", 40)):
        archivo = carpeta / nombre
        archivo.write_text("x")
        marca = datetime(2026, 9, 1).timestamp() + dia * 86400
        os.utime(archivo, (marca, marca))
    # ordena → 3 (tramo) → desde (mal y bien) → hasta → nombre (Intro) → ¿con qué archivos?
    # → 2 (de un tipo) → 2 (Documentos)
    interactivo.iniciar(
        app,
        lector("ordena", "3", "mañana", "septiembre 2026", "septiembre 2026", "", "2", "2"),
    )
    texto = salida(capsys)
    assert "No entiendo la fecha «mañana»" in texto
    assert "¿Con qué archivos?" in texto
    assert (carpeta / "del 2026-09-01 al 2026-09-30" / "septiembre.pdf").exists()
    assert (carpeta / "octubre.pdf").exists()


def test_filtro_de_fechas_desde_el_menu(carpeta, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    # ordena → 1 (tipo) → ¿con qué archivos? 4 (fechas) → desde → hasta (antes que desde) → otra vez
    interactivo.iniciar(
        app, lector("ordena", "1", "4", "1/10/2026", "1/9/2026", "1/9/2026", "hoy")
    )
    texto = salida(capsys)
    assert "posterior" in texto
    assert "--desde 1/9/2026 --hasta hoy" in texto


def test_ordenar_por_nombre_desde_el_menu(carpeta, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    for nombre in ("factura_enero.pdf", "Factura luz.pdf"):
        (carpeta / nombre).write_text("x")
    # ordena → 4 (nombre) → texto (vacío y bien) → carpeta (Intro) → ¿con qué archivos? (Intro)
    interactivo.iniciar(app, lector("ordena", "4", "", "factura", "", ""))
    texto = salida(capsys)
    assert "Hace falta un valor" in texto
    assert "Los que llevan un texto" not in texto  # el texto ya lo ha dicho
    assert {p.name for p in (carpeta / "factura").iterdir()} == {"factura_enero.pdf", "Factura luz.pdf"}
    assert (carpeta / "apuntes.pdf").exists()


def test_ordenar_por_letra_desde_el_menu(carpeta, capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "s")
    (carpeta / "boletin.pdf").write_text("x")
    # ordena → 5 (letra) → ¿con qué archivos? 2 (de un tipo) → 2 (Documentos)
    interactivo.iniciar(app, lector("ordena", "5", "2", "2"))
    salida(capsys)
    assert (carpeta / "A" / "apuntes.pdf").exists()
    assert (carpeta / "B" / "boletin.pdf").exists()
    assert (carpeta / "sub" / "dentro.txt").exists()


@pytest.mark.parametrize("pedido", ["ayuda ocupa", "ocupa ?", "? 2"])
def test_ayuda_de_un_comando(carpeta, capsys, pedido):
    if pedido == "? 2":
        pedido = f"? {numero_de('ocupa')}"
    interactivo.iniciar(app, lector(pedido))
    texto = salida(capsys)
    assert "Uso: ocupa [RUTA] [opciones]" in texto
    assert "--mayores" in texto and "por defecto: 15" in texto


def test_ayuda_de_un_grupo_muestra_sus_opciones(carpeta, capsys):
    interactivo.iniciar(app, lector("ayuda ordena", "ayuda ordena fecha"))
    texto = salida(capsys)
    assert "tramo" in texto
    assert "Uso: ordena fecha [opciones]" in texto
    assert "por defecto: mes" in texto  # valor del Enum, sin «Agrupar.»


def test_menu_vuelve_a_ensenar_el_menu(carpeta, capsys):
    interactivo.iniciar(app, lector("menu"))
    texto = salida(capsys)
    assert texto.count("Muestra qué hay en una carpeta") == 2  # al entrar y al pedirlo
    assert "Aquí puedes" not in texto

    interactivo.iniciar(app, lector("ordena", "menu"))
    texto = salida(capsys)
    assert texto.count("Junta en una carpeta los archivos de unas fechas") == 2


@pytest.mark.parametrize("pedido", ["ayuda", "?", "help"])
def test_ayuda_en_el_menu_principal_explica_todas_las_opciones(carpeta, capsys, pedido):
    interactivo.iniciar(app, lector(pedido))
    texto = salida(capsys)
    assert "Menú principal" in texto and str(carpeta) in texto
    assert "Aquí puedes" in texto
    assert "Dentro: tipo · fecha · tramo · nombre · letra · tipos · deshacer" in texto
    assert "Manual de navaja" not in texto


def test_ayuda_dentro_de_una_opcion_explica_esa_opcion(carpeta, capsys):
    interactivo.iniciar(app, lector(numero_de("config"), "ayuda"))
    texto = salida(capsys)
    assert "Menú principal" not in texto
    assert "Uso: nombre <NUEVO>" in texto
    assert "Cómo quieres que te salude navaja" in texto
    assert "Vuelve al menú principal" in texto

    interactivo.iniciar(app, lector("ordena", "ayuda", "fecha ?"))
    texto = salida(capsys)
    # dentro del submenú se escribe «fecha», no «ordena fecha»: en las dos ayudas
    assert texto.count("Uso: fecha [opciones]") == 2
    assert "Uso: ordena fecha" not in texto


def test_manual_es_otra_orden(carpeta, capsys):
    interactivo.iniciar(app, lector("manual"))
    assert "Manual de navaja" in salida(capsys)

    interactivo.iniciar(app, lector(numero_de("manual")))
    assert "Manual de navaja" in salida(capsys)


def test_comando_desconocido_sugiere(carpeta, capsys):
    interactivo.iniciar(app, lector("ocpa", "navaja ls"))
    texto = salida(capsys)
    assert "No conozco «ocpa»" in texto
    assert "ocupa" in texto
    assert "apuntes.pdf" in texto


def test_sin_terminal_no_se_abre():
    # Bajo pytest la entrada no es una terminal: navaja enseña la bienvenida y sale.
    assert interactivo.puede_iniciar() is False
