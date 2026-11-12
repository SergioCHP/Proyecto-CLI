import os
import time
from pathlib import Path

from typer.testing import CliRunner

from navaja.app import app

runner = CliRunner()


def crear(ruta: Path, texto: str = "x") -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def relativos(carpeta: Path) -> set[str]:
    return {p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()}


def plano(texto: str) -> str:
    return " ".join(texto.split())


def copia(*argumentos: str, entrada: str = "s\n"):
    return runner.invoke(app, ["copia", *argumentos], input=entrada)


def test_copia_con_subcarpetas_y_deja_los_originales(tmp_path):
    clase, casa = tmp_path / "USB", tmp_path / "PC"
    crear(clase / "tema1" / "apuntes.md")
    crear(clase / "horario.txt")
    resultado = copia("a", str(casa), "--carpeta", str(clase), "-r")
    assert resultado.exit_code == 0, resultado.output
    assert "2 archivos copiados" in resultado.output
    assert "navaja copia deshacer" in resultado.output
    assert relativos(casa) == {"tema1/apuntes.md", "horario.txt"}
    assert relativos(clase) == {"tema1/apuntes.md", "horario.txt"}  # los originales siguen

    otra = copia("a", str(casa), "--carpeta", str(clase), "-r")
    assert "todo está ya copiado" in plano(otra.output)


def test_simular_no_crea_ni_copia_nada(tmp_path):
    crear(tmp_path / "USB" / "a.txt")
    destino = tmp_path / "PC"
    resultado = copia("a", str(destino), "--carpeta", str(tmp_path / "USB"), "--simular")
    assert resultado.exit_code == 0, resultado.output
    assert "1 archivo para copiar" in resultado.output
    assert not destino.exists()


def test_el_filtro_elige_que_se_copia(tmp_path):
    origen = tmp_path / "Descargas"
    crear(origen / "factura.pdf")
    crear(origen / "foto.jpg")
    resultado = copia("a", str(tmp_path / "Copia"), "--carpeta", str(origen), "--solo", "pdf")
    assert resultado.exit_code == 0, resultado.output
    assert relativos(tmp_path / "Copia") == {"factura.pdf"}


def test_si_ya_hay_otro_distinto_guarda_una_copia_aparte(tmp_path):
    crear(tmp_path / "USB" / "a.txt", "nuevo")
    crear(tmp_path / "PC" / "a.txt", "mío")
    copia("a", str(tmp_path / "PC"), "--carpeta", str(tmp_path / "USB"))
    assert (tmp_path / "PC" / "a.txt").read_text(encoding="utf-8") == "mío"  # no se pisa
    assert (tmp_path / "PC" / "a (1).txt").read_text(encoding="utf-8") == "nuevo"


def test_el_mas_nuevo_sustituye_y_deshacer_trae_la_vieja(tmp_path):
    viejo = crear(tmp_path / "PC" / "a.txt", "viejo")
    hace_un_dia = time.time() - 86400
    os.utime(viejo, (hace_un_dia, hace_un_dia))
    crear(tmp_path / "USB" / "a.txt", "nuevo")
    resultado = copia(
        "a", str(tmp_path / "PC"), "--carpeta", str(tmp_path / "USB"), "--si-cambia", "el-mas-nuevo"
    )
    assert resultado.exit_code == 0, resultado.output
    assert viejo.read_text(encoding="utf-8") == "nuevo"
    assert copia("deshacer").exit_code == 0
    assert viejo.read_text(encoding="utf-8") == "viejo"


def test_deshacer_quita_las_copias_y_no_toca_el_de_acciones(tmp_path):
    crear(tmp_path / "USB" / "a.txt")
    copia("a", str(tmp_path / "PC"), "--carpeta", str(tmp_path / "USB"))
    assert "No hay ninguna acción que deshacer" in runner.invoke(app, ["acciones", "deshacer"]).output
    resultado = copia("deshacer")
    assert resultado.exit_code == 0, resultado.output
    assert "¿Deshacer la última copia?" in resultado.output
    assert relativos(tmp_path / "PC") == set()
    assert (tmp_path / "USB" / "a.txt").exists()
    assert "No hay ninguna copia que deshacer" in copia("deshacer").output


def test_errores_sin_traza(tmp_path):
    resultado = copia("a", str(tmp_path / "PC"), "--carpeta", str(tmp_path / "no-esta"))
    assert resultado.exit_code == 1
    assert "no existe" in resultado.output and "Traceback" not in resultado.output

    crear(tmp_path / "USB" / "a.txt")
    resultado = copia("a", str(tmp_path / "PC"), "--carpeta", str(tmp_path / "USB"), "--desde", "ayer no")
    assert resultado.exit_code == 2
    assert "Traceback" not in resultado.output
    assert not (tmp_path / "PC").exists()


def test_decir_que_no_no_copia_y_sale_con_1(tmp_path):
    crear(tmp_path / "USB" / "a.txt")
    resultado = copia("a", str(tmp_path / "PC"), "--carpeta", str(tmp_path / "USB"), entrada="n\n")
    assert resultado.exit_code == 1
    assert "Cancelado" in resultado.output
    assert not (tmp_path / "PC").exists()


def por_menu(tmp_path, monkeypatch, *respuestas, confirmar="s", crear_pc=True):
    """Abre navaja en tmp_path, escribe «copia a» y contesta; devuelve las preguntas."""
    from navaja import interactivo

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: confirmar)  # a «¿Copiar…? [s/n]»
    if crear_pc:
        (tmp_path / "PC").mkdir(exist_ok=True)  # el destino ya existe: no pregunta si crearlo
    preguntas = []
    pendientes = iter(["copia a", *respuestas])

    def leer(prompt):
        preguntas.append(prompt)
        try:
            return next(pendientes)
        except StopIteration:
            raise EOFError from None

    interactivo.iniciar(app, leer)
    return preguntas


def test_por_menu_una_carpeta_con_filtro(tmp_path, capsys, monkeypatch):
    crear(tmp_path / "USB" / "a.txt")
    crear(tmp_path / "USB" / "b.pdf")
    # qué (Intro = carpeta) · carpeta · destino · si cambia · ¿con qué? 2 tipo · pdf
    por_menu(tmp_path, monkeypatch, "", "USB", "PC", "", "", "2", "pdf")
    assert "→ navaja copia a" in plano(capsys.readouterr().out)
    assert relativos(tmp_path / "PC") == {"b.pdf"}


def test_por_menu_eliges_los_archivos_de_una_lista(tmp_path, capsys, monkeypatch):
    for nombre in ("apuntes.md", "b.txt", "c.txt", "horario.pdf"):
        crear(tmp_path / "USB" / nombre)
    # qué: 2 archivos · carpeta · cuáles · destino · si cambia (no pregunta «¿con qué?»)
    preguntas = por_menu(tmp_path, monkeypatch, "2", "USB", "1 3-4", "PC", "", "")
    texto = plano(capsys.readouterr().out)
    assert "horario.pdf" in texto  # la lista
    assert f"→ navaja copia a --carpeta USB {tmp_path / 'PC'} apuntes.md c.txt horario.pdf" in texto
    assert relativos(tmp_path / "PC") == {"apuntes.md", "c.txt", "horario.pdf"}
    assert not any("¿Con qué archivos?" in p for p in preguntas)


def test_por_menu_numero_que_no_esta_se_vuelve_a_preguntar(tmp_path, capsys, monkeypatch):
    crear(tmp_path / "USB" / "a.txt")
    por_menu(tmp_path, monkeypatch, "2", "USB", "7", "1", "PC", "", "")
    texto = plano(capsys.readouterr().out)
    assert "No hay ningún 7: elige entre 1 y 1." in texto
    assert relativos(tmp_path / "PC") == {"a.txt"}


def test_por_menu_volver_salta_lo_que_no_toca(tmp_path, capsys, monkeypatch):
    crear(tmp_path / "USB" / "a.txt")
    crear(tmp_path / "Otra" / "z.txt")
    # carpeta entera: en el destino, «volver» va a la carpeta (no a la lista, que no tocaba)
    por_menu(tmp_path, monkeypatch, "1", "USB", "volver", "Otra", "PC", "", "", "", "")
    assert relativos(tmp_path / "PC") == {"z.txt"}


def test_por_menu_carpeta_sin_archivos_vuelve_a_la_carpeta(tmp_path, capsys, monkeypatch):
    (tmp_path / "Vacia" / "sub").mkdir(parents=True)
    crear(tmp_path / "USB" / "a.txt")
    por_menu(tmp_path, monkeypatch, "2", "Vacia", "USB", "1", "PC", "", "")
    assert "no hay archivos" in plano(capsys.readouterr().out)
    assert relativos(tmp_path / "PC") == {"a.txt"}


def test_por_menu_quedarse_con_el_mas_reciente(tmp_path, capsys, monkeypatch):
    viejo = crear(tmp_path / "PC" / "a.txt", "viejo")
    os.utime(viejo, (time.time() - 86400, time.time() - 86400))
    crear(tmp_path / "USB" / "a.txt", "nuevo")
    por_menu(tmp_path, monkeypatch, "2", "USB", "1", "PC", "", "2")
    assert "--si-cambia el-mas-nuevo" in plano(capsys.readouterr().out)
    assert viejo.read_text(encoding="utf-8") == "nuevo"


def test_por_menu_destino_de_la_lista_y_bajando_por_carpetas(tmp_path, capsys, monkeypatch):
    casa = tmp_path / "casa"
    (casa / "Documents" / "ESTUDIO" / "DAM").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: casa)
    crear(tmp_path / "trabajo" / "apuntes.md")
    # archivos · carpeta trabajo · 1 · destino: 1 (Documentos) → 1 (ESTUDIO) → .. → ESTUDIO
    # (escrito) → 1 (DAM) → Intro, aquí · si cambia Intro
    por_menu(
        tmp_path, monkeypatch, "2", "trabajo", "1", "1", "1", "..", "ESTUDIO", "1", "", "",
        crear_pc=False,
    )
    texto = plano(capsys.readouterr().out)
    assert "¿A qué carpeta van las copias?" in texto
    assert "1 Documentos" in texto
    assert relativos(casa / "Documents" / "ESTUDIO" / "DAM") == {"apuntes.md"}


def test_por_menu_documentos_escrito_y_carpeta_nueva(tmp_path, capsys, monkeypatch):
    casa = tmp_path / "casa"
    (casa / "Documents" / "ESTUDIO").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: casa)
    crear(tmp_path / "trabajo" / "apuntes.md")
    # «documentos\ESTUDIO» escrito (en castellano y minúsculas) → + carpeta nueva «copias»
    por_menu(
        tmp_path, monkeypatch, "2", "trabajo", "1", r"documentos\ESTUDIO", "+", "copias", "",
        crear_pc=False,
    )
    assert relativos(casa / "Documents" / "ESTUDIO" / "copias") == {"apuntes.md"}


def test_por_menu_destino_que_no_existe_pregunta_antes(tmp_path, capsys, monkeypatch):
    crear(tmp_path / "Documents" / "factura.pdf")
    monkeypatch.chdir(tmp_path / "Documents")
    # «sergi/Cosas» relativa: avisa con la ruta entera; 2 = escribir otra; luego crearla
    por_menu(
        tmp_path / "Documents", monkeypatch, "2", "", "1", "sergi/Cosas", "2",
        str(tmp_path / "Copia"), "1", "", crear_pc=False,
    )
    texto = plano(capsys.readouterr().out)
    assert f"La carpeta {tmp_path / 'Documents' / 'sergi' / 'Cosas'} no existe" in texto
    assert not (tmp_path / "Documents" / "sergi").exists()
    assert relativos(tmp_path / "Copia") == {"factura.pdf"}


def test_por_menu_descargas_propone_la_de_verdad(tmp_path, capsys, monkeypatch):
    casa = tmp_path / "casa"
    (casa / "Downloads").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: casa)
    crear(tmp_path / "factura.pdf")
    por_menu(tmp_path, monkeypatch, "2", "", "1", "sergi/Descargas", "1", "", crear_pc=False)
    texto = plano(capsys.readouterr().out)
    assert f"Usar {casa / 'Downloads'} (es tu Descargas)" in texto
    assert relativos(casa / "Downloads") == {"factura.pdf"}
    assert not (tmp_path / "sergi").exists()


def test_el_plan_dice_a_donde_entero_y_si_se_creara(tmp_path, monkeypatch):
    crear(tmp_path / "a.txt")
    monkeypatch.chdir(tmp_path)
    resultado = copia("a", "sergi/Descargas", "--simular")
    assert resultado.exit_code == 0, resultado.output
    sin_bordes = " ".join(resultado.output.replace("│", " ").split())  # el recuadro la parte
    assert "(no existe: se creará)" in sin_bordes
    assert not (tmp_path / "sergi").exists()


# ── Archivos concretos ─────────────────────────────────────────────────────


def test_copia_solo_los_archivos_que_dices(tmp_path):
    origen = crear(tmp_path / "Descargas" / "horario.pdf").parent
    crear(origen / "apuntes tema 3.docx")
    crear(origen / "otro.pdf")
    resultado = copia("a", str(tmp_path / "USB"), "horario.pdf", "apuntes tema 3.docx", "-c", str(origen))
    assert resultado.exit_code == 0, resultado.output
    assert relativos(tmp_path / "USB") == {"horario.pdf", "apuntes tema 3.docx"}


def test_comodin_se_busca_en_la_carpeta_de_c(tmp_path, monkeypatch):
    origen = tmp_path / "Descargas"
    crear(origen / "a.pdf")
    crear(origen / "b.pdf")
    crear(origen / "c.txt")
    crear(tmp_path / "aqui.pdf")  # en la carpeta actual: no debe entrar
    monkeypatch.chdir(tmp_path)
    resultado = copia("a", str(tmp_path / "USB"), "*.pdf", "a.pdf", "-c", str(origen))
    assert resultado.exit_code == 0, resultado.output
    assert relativos(tmp_path / "USB") == {"a.pdf", "b.pdf"}  # a.pdf, una sola vez


def test_de_subcarpetas_van_sin_subcarpeta_y_se_deshace(tmp_path):
    dam = tmp_path / "DAM"
    crear(dam / "Entornos" / "dudas.txt")
    crear(dam / "Sistemas" / "horario.txt")
    resultado = copia(
        "a", str(tmp_path / "USB"), "Entornos/dudas.txt", "Entornos/../Sistemas/horario.txt",
        "-c", str(dam),
    )
    assert resultado.exit_code == 0, resultado.output
    assert relativos(tmp_path / "USB") == {"dudas.txt", "horario.txt"}
    assert copia("deshacer").exit_code == 0
    assert relativos(tmp_path / "USB") == set()


def test_archivos_con_errores_claros(tmp_path):
    dam = tmp_path / "DAM"
    crear(dam / "a" / "x.txt")
    crear(dam / "b" / "x.txt")
    casos = [
        (["no-esta.pdf"], "No encuentro «no-esta.pdf»"),
        (["*.pdf"], "Ningún archivo coincide con «*.pdf»"),
        (["a"], "«a» es una carpeta"),
        (["a/x.txt", "b/x.txt"], "Hay dos archivos que se llaman «x.txt»"),
        (["a/x.txt", "--solo", "txt"], "Con archivos concretos no se usan filtros"),
    ]
    for argumentos, mensaje in casos:
        resultado = copia("a", str(tmp_path / "USB"), *argumentos, "-c", str(dam))
        assert resultado.exit_code != 0, argumentos
        assert mensaje in plano(resultado.output), (argumentos, resultado.output)
        assert "Traceback" not in resultado.output
    assert not (tmp_path / "USB").exists()
