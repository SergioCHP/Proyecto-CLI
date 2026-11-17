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
    """Antes, con el índice roto no se listaba nada (ni caducaba), y el siguiente «apuntar»
    dejaba las de antes sin índice para siempre. Ahora se encuentran en la carpeta."""
    indice = versiones.carpeta_versiones() / versiones.INDICE
    indice.write_text("{ roto", encoding="utf-8")
    ver = ordenes("acciones", "versiones", "ver")
    texto = plano(ver.output)
    assert ver.exit_code == 0 and "a.txt" in texto and "b.txt" in texto and "(no se sabe)" in texto
    recuperar = ordenes("acciones", "versiones", "recuperar", "1", "--si")
    assert recuperar.exit_code == 1 and "No se sabe de dónde salió" in plano(recuperar.output)
    assert len(list(versiones.carpeta_versiones().rglob("*.txt"))) == 2  # siguen ahí
    # el siguiente que escribe el índice lo arregla, y guarda el roto aparte
    nueva = versiones.carpeta_versiones() / "20991231-235959" / "c.txt"
    crear(nueva, "c viejo")
    versiones.apuntar([versiones.Version(nueva, sustituidas / "c.txt", "pc-a-usb", datetime.now())])
    assert (versiones.carpeta_versiones() / "indice.roto.json").read_text(encoding="utf-8") == "{ roto"
    lista = versiones.cargar()
    assert sorted(v.guardada.name for v in lista) == ["a.txt", "b.txt", "c.txt"]  # sin repetir
    assert json.loads(indice.read_text(encoding="utf-8"))  # ya se lee
    assert ordenes("acciones", "versiones", "borrar", "--si").exit_code == 0  # y se borran todas
    assert versiones.cargar() == []


def test_sin_indice_caducan_con_la_fecha_de_su_carpeta(sustituidas):
    (versiones.carpeta_versiones() / versiones.INDICE).unlink()
    antigua = versiones.carpeta_versiones() / "20200101-120000" / "z.txt"
    crear(antigua, "muy viejo")
    assert any(v.cuando == datetime(2020, 1, 1, 12) for v in versiones.cargar())
    assert versiones.caducar(30) == (1, len("muy viejo"))  # solo esa: las otras son de hoy
    assert not antigua.exists()


def test_apuntar_no_repite_las_que_ya_estaban_en_la_carpeta(sustituidas):
    """Mientras se copia, la vieja ya está en la carpeta y aún no en el índice."""
    nueva = versiones.carpeta_versiones() / "20991231-235959" / "c.txt"
    crear(nueva, "c viejo")
    assert len(versiones.cargar()) == 3  # la ve «sin índice»
    versiones.apuntar([versiones.Version(nueva, sustituidas / "c.txt", "pc-a-usb", datetime.now())])
    assert len(versiones.cargar()) == 3 and all(v.sitio_conocido for v in versiones.cargar())


def test_guardar_el_indice_cortado_deja_el_de_antes(sustituidas, monkeypatch):
    indice = versiones.carpeta_versiones() / versiones.INDICE
    antes = indice.read_text(encoding="utf-8")
    reemplazar = os.replace

    def corta(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", corta)
    with pytest.raises(KeyboardInterrupt):
        versiones.guardar([])
    monkeypatch.setattr(os, "replace", reemplazar)  # solo esto (undo() quitaría NAVAJA_DATOS)
    assert indice.read_text(encoding="utf-8") == antes
    assert not list(versiones.carpeta_versiones().glob("*.navaja"))


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


def test_una_entrada_mala_no_tira_las_demas(sustituidas, tmp_path):
    indice = versiones.carpeta_versiones() / versiones.INDICE
    datos = json.loads(indice.read_text(encoding="utf-8"))
    fuera = crear(tmp_path / "mio.txt", "un archivo tuyo", hace_dias=100)
    datos += [
        {"guardada": None, "sitio": "x", "cuando": "2026-01-01T10:00:00"},  # mala
        {"guardada": str(fuera), "sitio": "x", "cuando": "2000-01-01T10:00:00"},  # fuera de versiones
        "ni siquiera es un objeto",
    ]
    datos[0]["cuando"] = "2026-11-17T10:00:00+01:00"  # con zona horaria
    datos[1]["accion"] = 5  # no es texto
    indice.write_text("﻿" + json.dumps(datos), encoding="utf-8")  # con BOM, como el Bloc de notas
    lista = versiones.cargar()
    assert len(lista) == 2 and all(v.sitio_conocido for v in lista)  # las buenas, con su sitio
    assert ordenes("acciones", "versiones", "ver").exit_code == 0
    versiones.caducar(30)
    assert fuera.exists()  # caducar nunca toca nada fuera de la carpeta de versiones


def test_indice_que_no_se_puede_leer_no_se_pisa(sustituidas, monkeypatch, tmp_path):
    bloqueado = tmp_path / "bloqueado"
    bloqueado.mkdir()  # leer una carpeta como archivo da OSError, como un archivo bloqueado
    monkeypatch.setattr(versiones, "_indice", lambda: bloqueado)
    assert len(versiones.cargar()) == 2  # se siguen viendo (por la carpeta)
    with pytest.raises(OSError):
        versiones.apuntar([versiones.Version(Path("x"), Path("y"), "z", datetime.now())])
    assert bloqueado.is_dir()  # no se ha escrito nada encima


def test_un_roto_anterior_no_se_pisa(sustituidas):
    raiz = versiones.carpeta_versiones()
    (raiz / "indice.roto.json").write_text("primero", encoding="utf-8")
    (raiz / versiones.INDICE).write_text("segundo { roto", encoding="utf-8")
    versiones.olvidar([])
    assert (raiz / "indice.roto.json").read_text(encoding="utf-8") == "primero"
    assert (raiz / "indice.roto (1).json").read_text(encoding="utf-8") == "segundo { roto"


def test_borrar_una_sin_indice_y_de_solo_lectura(sustituidas):
    import stat

    suelta = versiones.carpeta_versiones() / "20200101-120000" / "suelta.txt"
    crear(suelta, "vieja sin índice")
    os.chmod(suelta, stat.S_IREAD)
    numero = next(n for n, v in enumerate(versiones.cargar(), start=1) if v.guardada == suelta)
    resultado = ordenes("acciones", "versiones", "borrar", str(numero), "--si")
    assert resultado.exit_code == 0, resultado.output
    assert not suelta.exists()


def test_dos_navaja_a_la_vez_no_se_pisan_el_indice():
    """Antes, con dos apuntando a la vez, ganaba el último: las del otro se quedaban sin sitio."""
    import threading

    raiz = versiones.carpeta_versiones()

    def apunta(quien: str) -> None:
        for n in range(15):
            archivo = crear(raiz / f"20261117-1000{n:02}" / f"{quien}{n}.txt", "viejo")
            versiones.apuntar([versiones.Version(archivo, Path(f"C:/sitio/{quien}{n}.txt"), quien, datetime.now())])

    hilos = [threading.Thread(target=apunta, args=(q,)) for q in ("a", "b")]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    lista = versiones.cargar()
    assert len(lista) == 30 and all(v.sitio_conocido for v in lista)  # todas, y con su sitio
    assert not (raiz / versiones.CERROJO).exists()


def test_cerrojo_abandonado_y_ocupado():
    raiz = versiones.carpeta_versiones()
    raiz.mkdir(parents=True)
    cerrojo = raiz / versiones.CERROJO
    cerrojo.write_text("")
    hace_un_rato = datetime.now().timestamp() - 3600
    os.utime(cerrojo, (hace_un_rato, hace_un_rato))  # de un navaja que se cortó
    versiones.olvidar([])  # lo quita y sigue
    assert not cerrojo.exists()
    cerrojo.write_text("")  # ahora, de otro navaja que está trabajando
    with pytest.raises(OSError, match="otro navaja"):
        with versiones._cerrojo(espera=0.2):
            pass
    assert cerrojo.exists()  # el del otro no se toca


def test_cerrojo_con_ctrl_c_dentro_no_se_queda_puesto():
    cerrojo = versiones.carpeta_versiones() / versiones.CERROJO
    with pytest.raises(KeyboardInterrupt):
        with versiones._cerrojo():
            assert cerrojo.exists()
            raise KeyboardInterrupt
    assert not cerrojo.exists()


def test_cerrojo_espera_si_windows_dice_permiso_denegado(monkeypatch):
    """Con el cerrojo a medio borrar, Windows da PermissionError (no FileExistsError)."""
    abrir = os.open
    veces = []

    def ocupado_la_primera(*a, **k):
        veces.append(1)
        if len(veces) == 1:
            raise PermissionError(13, "Permiso denegado")
        return abrir(*a, **k)

    monkeypatch.setattr(os, "open", ocupado_la_primera)
    with versiones._cerrojo(espera=2):
        pass
    monkeypatch.setattr(os, "open", abrir)  # solo esto (undo() quitaría NAVAJA_DATOS)
    assert len(veces) == 2


def test_un_navaja_lento_no_quita_el_cerrojo_de_otro():
    cerrojo = versiones.carpeta_versiones() / versiones.CERROJO
    with versiones._cerrojo():
        cerrojo.write_text("otro-navaja 9999999999.0", encoding="utf-8")  # se lo quitaron y puso el suyo
    assert cerrojo.read_text(encoding="utf-8") == "otro-navaja 9999999999.0"  # el del otro, intacto
