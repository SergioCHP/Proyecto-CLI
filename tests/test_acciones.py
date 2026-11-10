import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from navaja import esquema, interactivo
from navaja.acciones import Accion, AccionDeArchivos, Copiar, Mover, Renombrar, Resultado, Rutina
from navaja.app import app
from navaja.comandos.ayuda import subcomandos
from navaja.comun import directorio_datos
from navaja.errores import AccionNoValida, ConfigError, NavajaError
from navaja.motor import Motor

runner = CliRunner()
REPO = Path(__file__).resolve().parents[1]


def crear(ruta: Path, texto: str = "x", dias: int = 0) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    if dias:
        marca = (datetime.now() - timedelta(days=dias)).timestamp()
        os.utime(ruta, (marca, marca))
    return ruta


def archivo_de_acciones(tmp_path: Path, *acciones: dict) -> Path:
    ruta = tmp_path / "acciones.json"
    ruta.write_text(
        json.dumps({"version": 1, "acciones": list(acciones)}, ensure_ascii=False), encoding="utf-8"
    )
    return ruta


def accion(nombre: str, tipo: str, **campos) -> dict:
    return {"nombre": nombre, "descripcion": f"Prueba {nombre}", "tipo": tipo, **campos}


def acciones(*argumentos: str, config: Path | None = None, entrada: str = "s\ns\ns\n"):
    extra = ["--config", str(config)] if config else []
    return runner.invoke(app, ["acciones", *argumentos, *extra], input=entrada)


def relativos(carpeta: Path) -> set[str]:
    return {p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()}


def plano(texto: str) -> str:
    return " ".join(texto.split())


@pytest.fixture
def descargas(tmp_path):
    carpeta = tmp_path / "Descargas"
    crear(carpeta / "factura.pdf")
    crear(carpeta / "apuntes de redes.docx")
    crear(carpeta / "FOTO1.JPG")
    crear(carpeta / "cumpleaños 2.png")
    crear(carpeta / "Gemini_Generated_Image_1.png")
    crear(carpeta / "setup.exe")
    crear(carpeta / "viejo.msi", dias=40)
    return carpeta


# ── El archivo del repo ────────────────────────────────────────────────────


@pytest.mark.parametrize("nombre", ["acciones.json", "pruebas/acciones-prueba.json"])
def test_los_archivos_del_repo_son_validos(nombre):
    cargadas = esquema.cargar(REPO / nombre)
    assert len(cargadas) >= 5
    assert {a["tipo"] for a in cargadas} >= {"mover", "ordenar", "renombrar", "borrar", "rutina"}
    assert all(not campo.startswith("_") for a in cargadas for campo in a)  # las notas no pasan


@pytest.mark.parametrize(
    ("nombre", "dice"),
    [
        ("roto-coma.json", "sobra una coma"),
        ("roto-tipo.json", "«tipo»"),
        ("roto-repetido.json", "está repetido"),
        ("roto-regex.json", "filtro.patron"),
    ],
)
def test_los_json_rotos_de_pruebas_salen_con_3_y_sin_traza(nombre, dice):
    resultado = runner.invoke(app, ["acciones", "validar", "--config", str(REPO / "pruebas" / nombre)])
    assert resultado.exit_code == 3
    assert dice in plano(resultado.output)
    assert "Traceback" not in resultado.output


def test_el_de_pruebas_solo_toca_pruebas_navaja():
    for a in esquema.cargar(REPO / "pruebas" / "acciones-prueba.json"):
        for campo in ("carpeta", "destino"):
            if campo in a:
                assert a[campo].startswith("~/pruebas-navaja/"), a


# ── Comprobar el esquema ───────────────────────────────────────────────────

BUENA = accion("ordenar-descargas", "ordenar", carpeta="~/Downloads", por="tipo")


def validar_con(*cambios: dict, raiz: dict | None = None):
    lista = [dict(BUENA)]
    for cambio in cambios:
        lista.append(cambio)
    return esquema.validar({"version": 1, "acciones": lista, **(raiz or {})})


@pytest.mark.parametrize(
    "mala, esperado",
    [
        (accion("x", "mober", destino="a"), "Acción «x», campo «tipo»: «mober» no existe; usa uno de: mover, copiar"),
        (accion("x", "mober", destino="a"), "¿Querías decir «mover»?"),
        (accion("ordenar-descargas", "mover", destino="a"), "campo «nombre»: está repetido"),
        (accion("Mis Fotos", "mover", destino="a"), "campo «nombre»: solo minúsculas"),
        (accion("x", "mover"), "campo «destino»: es obligatorio en acciones de tipo mover"),
        (accion("x", "renombrar"), "campo «plantilla»: es obligatorio en acciones de tipo renombrar"),
        (accion("x", "mover", destino="a", fitro={}), "campo «fitro»: no existe"),
        (accion("x", "mover", destino="a", fitro={}), "¿Querías decir «filtro»?"),
        (accion("x", "mover", destino="a", descripción="y"), "¿Querías decir «descripcion»?"),
        (accion("x", "mover", destino="a", plantilla="{n}{ext}"), "no se usa en acciones de tipo mover"),
        (accion("x", "borrar"), "campo «filtro»: una acción de borrar necesita un filtro"),
        (accion("x", "mover", destino="a", filtro={"patron": "*.tmp"}), "campo «filtro.patron»: expresión regular rota"),
        (accion("x", "mover", destino="a", filtro={"hasta": "hace un mes"}), "campo «filtro.hasta»: No entiendo la fecha"),
        (accion("x", "mover", destino="a", filtro={"recursivo": "true"}), "tiene que ser true o false"),
        (accion("x", "mover", destino="a", filtro={"extensiones": [".pdf"]}), "¿Querías decir «solo»?"),
        (accion("x", "mover", destino="a", filtro={"mayor_que": "mucho"}), "campo «filtro.mayor_que»"),
        (accion("x", "copiar", destino="a", filtro={"excluir": "proyectos/build"}), "«proyectos/build» no es un nombre de carpeta"),
        (accion("x", "copiar", destino="a", filtro={"excluir": "C:"}), "«C:» no es un nombre de carpeta"),
        (accion("x", "copiar", destino="a", filtro={"excluir": "*.egg-info"}), "sin rutas, unidades ni comodines"),
        (accion("x", "copiar", destino="a", filtro={"excluir": " , ,"}), "campo «filtro.excluir»: está vacío"),
        (accion("x", "copiar", destino="a", filtro={"excluir": []}), "campo «filtro.excluir»: está vacío"),
        (accion("x", "copiar", destino="a", si_cambia="sobrescribir"), "campo «si_cambia»: «sobrescribir» no vale"),
        (accion("x", "mover", destino="a", si_cambia="el-mas-nuevo"), "no se usa en acciones de tipo mover"),
        (accion("x", "copiar", destino="a", filtro={"excluir": ["build", 3]}), "campo «filtro.excluir»: tiene que ser una lista"),
        (accion("x", "mover", destino="C:\new\temp"), "campo «destino»: tiene un salto de línea o un tabulador"),
        (accion("x", "ordenar", por="semana"), "«semana» no vale; usa tipo, mes, año, día o letra"),
        (accion("x", "renombrar", plantilla="{dia}{ext}"), "el hueco {dia} no existe"),
        (accion("x", "renombrar", plantilla="{fecha:%d/%m}{ext}"), "no puede llevar /"),
        (accion("x", "renombrar", plantilla="{nombre}"), "perderían la extensión"),
        (accion("x", "renombrar", plantilla="{n}{ext}", orden="tamaño"), "campo «orden»"),
        (accion("x", "rutina", pasos=[]), "campo «pasos»: tiene que ser una lista"),
        (accion("x", "rutina", pasos=["ordenar-descarga"]), "no hay ninguna acción «ordenar-descarga». ¿Querías decir «ordenar-descargas»?"),
        (accion("x", "rutina", pasos=["x"]), "no puede llamarse a sí misma"),
        (accion("x", "rutina", pasos=["ordenar-descargas"], carpeta="~"), "campo «carpeta»: no se usa en acciones de tipo rutina"),
    ],
)
def test_cada_error_dice_que_accion_y_que_campo(mala, esperado):
    with pytest.raises(ConfigError) as error:
        validar_con(mala)
    assert esperado in str(error.value)
    assert error.value.codigo_salida == 3


def test_una_rutina_no_puede_llevar_otra_rutina():
    with pytest.raises(AccionNoValida, match="es otra rutina"):
        validar_con(
            accion("a", "rutina", pasos=["ordenar-descargas"]),
            accion("b", "rutina", pasos=["a"]),
        )


@pytest.mark.parametrize(
    "datos, esperado",
    [
        ([], "tiene que empezar por {"),
        ({"acciones": [BUENA]}, "Falta «version»"),
        ({"version": 2, "acciones": [BUENA]}, "esta navaja lee la versión 1"),
        ({"version": True, "acciones": [BUENA]}, "lee la versión 1"),
        ({"version": 1}, "Falta la lista «acciones» o está vacía"),
        ({"version": 1, "acciones": []}, "está vacía"),
        ({"version": 1, "acciones": [BUENA], "accion": []}, "Sobra «accion»"),
        ({"version": 1, "acciones": ["hola"]}, "La acción nº 1 no es un objeto"),
    ],
)
def test_errores_del_archivo_entero(datos, esperado):
    with pytest.raises(ConfigError, match=esperado):
        esquema.validar(datos)


def test_lo_que_empieza_por_guion_bajo_es_una_nota():
    cargadas = validar_con(
        accion("x", "mover", destino="a", _nota="hola", filtro={"_porque": "sí", "solo": "pdf"}),
        raiz={"_ayuda": "notas para mí"},
    )
    assert "_nota" not in cargadas[1]


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ('{"version": 1, "acciones": [{"nombre": "a"},]}', "no es JSON válido: línea 1, columna"),
        ('{"version": 1,\n "acciones": [\n {"carpeta": "C:\\Users\\yo"}]}', "barra invertida"),
        ('{"version": 1,\n "acciones": [\n {"nombre": "a" "tipo": "mover"}]}', "falta una coma"),
        ("{'version': 1}", "comillas dobles"),
    ],
)
def test_json_roto_explica_donde_y_que(tmp_path, texto, esperado):
    ruta = tmp_path / "roto.json"
    ruta.write_text(texto, encoding="utf-8")
    with pytest.raises(ConfigError) as error:
        esquema.cargar(ruta)
    assert esperado in str(error.value)
    assert "Expecting" not in str(error.value)


def test_json_con_bom_del_bloc_de_notas(tmp_path):
    ruta = tmp_path / "acciones.json"
    ruta.write_text(json.dumps({"version": 1, "acciones": [BUENA]}), encoding="utf-8-sig")
    assert esquema.cargar(ruta)[0]["nombre"] == "ordenar-descargas"


def test_json_que_no_es_utf8(tmp_path):
    ruta = tmp_path / "acciones.json"
    ruta.write_bytes(json.dumps({"version": 1, "acciones": [BUENA]}, ensure_ascii=False).replace("Prueba", "Preuba ñ").encode("cp1252"))
    with pytest.raises(ConfigError, match="UTF-8"):
        esquema.cargar(ruta)


# ── Dónde está ─────────────────────────────────────────────────────────────


def test_busca_en_la_carpeta_actual_y_luego_en_tus_datos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigError, match="acciones editar"):
        esquema.buscar()
    en_datos = esquema.en_datos()
    en_datos.write_text("{}", encoding="utf-8")
    assert esquema.buscar() == en_datos
    aqui = tmp_path / "acciones.json"
    aqui.write_text("{}", encoding="utf-8")
    assert esquema.buscar() == aqui
    with pytest.raises(ConfigError, match="No encuentro"):
        esquema.buscar(tmp_path / "otro.json")


# ── Las clases ─────────────────────────────────────────────────────────────


def test_la_fabrica_elige_la_clase_por_el_tipo():
    assert isinstance(Accion.desde_config(accion("a", "mover", destino="x")), Mover)
    assert isinstance(Accion.desde_config(accion("a", "copiar", destino="x")), Copiar)
    assert isinstance(Accion.desde_config(accion("a", "rutina", pasos=["b"])), Rutina)
    with pytest.raises(AccionNoValida):
        Accion.desde_config(accion("a", "volar"))


def test_un_tipo_nuevo_es_solo_una_subclase(tmp_path):
    class Tocar(AccionDeArchivos):
        tipo = "tocar-prueba"
        explicacion = "Para la prueba."

        def planificar(self, archivos, carpeta):
            return [Resultado(a, a) for a in archivos]

        def aplicar(self, resultado):
            resultado.origen.touch()

    try:
        assert "tocar-prueba" in Accion.tipos()
        cargadas = validar_con(accion("t", "tocar-prueba", filtro={"solo": "pdf"}))
        assert isinstance(Motor(cargadas).acciones["t"], Tocar)
    finally:
        del Accion._registro["tocar-prueba"]


def test_motor_busca_por_nombre_numero_o_parecido():
    motor = Motor(validar_con(accion("imagenes-ia", "mover", destino="x")))
    assert motor.buscar("2").nombre == "imagenes-ia"
    assert motor.buscar("IMAGENES-IA").nombre == "imagenes-ia"
    with pytest.raises(NavajaError, match="¿Querías decir «imagenes-ia»?") as error:
        motor.buscar("imagenes")
    assert error.value.codigo_salida == 1


def test_motor_buscar_con_cifras_raras_no_revienta():
    motor = Motor(validar_con(accion("pdf", "mover", destino="x")))
    with pytest.raises(NavajaError, match="No hay ninguna acción «²»"):
        motor.buscar("²")


def test_sin_carpeta_trabaja_con_la_actual_en_absoluto(descargas, monkeypatch):
    monkeypatch.chdir(descargas)
    motor = Motor(validar_con(accion("pdf", "mover", destino=str(descargas), filtro={"solo": "pdf"})))
    base, plan = motor.planificar(motor.acciones["pdf"])
    assert base.is_absolute()
    assert plan == []  # ya están en su sitio: nada de «factura (1).pdf»


def test_destino_por_encima_de_la_carpeta_no_excluye_nada(descargas):
    escaneos = descargas / "Escaneos"
    crear(escaneos / "dni.pdf")
    assert [a.name for a in Motor.seleccionar(escaneos, {}, descargas)] == ["dni.pdf"]
    # el de dentro sí se sigue excluyendo
    assert Motor.seleccionar(descargas, {"recursivo": True, "solo": "pdf"}, escaneos) == [descargas / "factura.pdf"]


def test_seleccionar_cumple_todo_el_filtro(descargas):
    crear(descargas / "grande.png", "x" * 2048)
    elegir = lambda filtro: {a.name for a in Motor.seleccionar(descargas, filtro)}  # noqa: E731
    assert elegir({"solo": "jpg"}) == {"FOTO1.JPG"}  # mayúsculas en la extensión
    assert elegir({"solo": ["jpg", "png"], "contiene": "GEMINI"}) == {"Gemini_Generated_Image_1.png"}
    assert elegir({"patron": "^(foto|cumple)"}) == {"FOTO1.JPG", "cumpleaños 2.png"}
    assert elegir({"solo": "ejecutables", "hasta": "hace 30 días"}) == {"viejo.msi"}
    assert elegir({"mayor_que": "1K"}) == {"grande.png"}


# ── validar ────────────────────────────────────────────────────────────────


def test_validar_bien_y_mal(tmp_path):
    buena = archivo_de_acciones(tmp_path, BUENA)
    resultado = acciones("validar", config=buena)
    assert resultado.exit_code == 0
    assert "✔ 1 acción válida" in resultado.output

    mala = tmp_path / "roto.json"
    mala.write_text(json.dumps({"version": 1, "acciones": [accion("x", "mober")]}), encoding="utf-8")
    resultado = acciones("validar", config=mala)
    assert resultado.exit_code == 3
    assert "Acción «x», campo «tipo»" in plano(resultado.output)
    assert "Traceback" not in resultado.output


def test_validar_avisa_de_carpetas_que_no_existen(tmp_path):
    ruta = archivo_de_acciones(tmp_path, accion("x", "mover", carpeta=str(tmp_path / "no-hay"), destino="a"))
    resultado = acciones("validar", config=ruta)
    assert resultado.exit_code == 0
    assert "no existe ahora mismo" in plano(resultado.output)


def test_sin_archivo_sale_con_3(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resultado = acciones("ver")
    assert resultado.exit_code == 3
    assert "acciones editar" in plano(resultado.output)


def test_ver_lista_las_acciones(tmp_path):
    ruta = archivo_de_acciones(tmp_path, BUENA, accion("r", "rutina", pasos=["ordenar-descargas"]))
    texto = plano(acciones("ver", config=ruta).output)
    assert "ordenar-descargas" in texto and "rutina" in texto and "Prueba r" in texto


# ── ejecutar ───────────────────────────────────────────────────────────────


def test_simular_no_toca_nada(tmp_path, descargas):
    destino = tmp_path / "PDF"
    ruta = archivo_de_acciones(
        tmp_path, accion("pdfs", "mover", carpeta=str(descargas), destino=str(destino), filtro={"solo": "pdf"})
    )
    antes = relativos(descargas)
    resultado = acciones("ejecutar", "pdfs", "--simular", config=ruta)
    assert resultado.exit_code == 0, resultado.output
    assert "factura.pdf" in resultado.output and "Simulación" in resultado.output
    assert relativos(descargas) == antes
    assert not destino.exists()  # ni siquiera crea la carpeta


def test_mover_nunca_sobrescribe(tmp_path, descargas):
    destino = tmp_path / "PDF"
    crear(destino / "factura.pdf", "la de antes")
    ruta = archivo_de_acciones(
        tmp_path, accion("pdfs", "mover", carpeta=str(descargas), destino=str(destino), filtro={"solo": "pdf"})
    )
    resultado = acciones("ejecutar", "pdfs", config=ruta)
    assert resultado.exit_code == 0, resultado.output
    assert relativos(destino) == {"factura.pdf", "factura (1).pdf"}
    assert (destino / "factura.pdf").read_text() == "la de antes"
    # la segunda vez no hay nada que mover
    resultado = acciones("ejecutar", "pdfs", config=ruta)
    assert "Nada que hacer" in resultado.output


def test_decir_que_no_no_hace_nada(tmp_path, descargas):
    ruta = archivo_de_acciones(tmp_path, accion("todo", "ordenar", carpeta=str(descargas), por="tipo"))
    antes = relativos(descargas)
    resultado = acciones("ejecutar", "todo", config=ruta, entrada="n\n")
    assert resultado.exit_code == 1  # no se hizo: un script lo sabe
    assert "Cancelado" in resultado.output
    assert relativos(descargas) == antes


def test_ordenar_con_tildes_espacios_y_corchetes(tmp_path, descargas):
    crear(descargas / "[borrador].pdf")
    ruta = archivo_de_acciones(tmp_path, accion("orden", "ordenar", carpeta=str(descargas), por="tipo"))
    resultado = acciones("ejecutar", "orden", config=ruta)
    assert resultado.exit_code == 0, resultado.output
    assert "[borrador].pdf" in resultado.output
    assert {"Imagenes/cumpleaños 2.png", "Documentos/apuntes de redes.docx", "Documentos/[borrador].pdf",
            "Imagenes/FOTO1.JPG", "Ejecutables/setup.exe"} <= relativos(descargas)


def test_copiar_la_segunda_vez_no_copia_otra_vez(tmp_path):
    dam = tmp_path / "DAM"
    crear(dam / "tema1" / "apuntes.pdf")
    crear(dam / "viejo.pdf", dias=20)
    copia = tmp_path / "Copia"
    ruta = archivo_de_acciones(
        tmp_path,
        accion("copia", "copiar", carpeta=str(dam), destino=str(copia),
               filtro={"desde": "hace 7 días", "recursivo": True}),
    )
    assert acciones("ejecutar", "copia", config=ruta).exit_code == 0
    assert relativos(copia) == {"tema1/apuntes.pdf"}  # conserva la subcarpeta
    assert (dam / "tema1" / "apuntes.pdf").exists()  # el original se queda
    resultado = acciones("ejecutar", "copia", config=ruta)
    assert "ya está copiado" in resultado.output
    assert relativos(copia) == {"tema1/apuntes.pdf"}


def test_copiar_usb_y_pc_en_los_dos_sentidos_sin_entrar_en_excluidas(tmp_path):
    usb, pc = tmp_path / "USB" / "DAM", tmp_path / "PC" / "DAM"
    crear(usb / "Programación" / "tema3.pdf")
    crear(pc / "Programación" / "practica.py")
    crear(pc / "Proyecto" / "node_modules" / "lib.js")
    crear(pc / "Proyecto" / "src" / "__pycache__" / "app.pyc")
    crear(pc / "Proyecto" / "Build" / "app.exe")  # sin mirar mayúsculas
    filtro = {"recursivo": True, "excluir": "node_modules, __pycache__, build"}
    ruta = archivo_de_acciones(
        tmp_path,
        accion("usb-a-pc", "copiar", carpeta=str(usb), destino=str(pc), filtro=filtro),
        accion("pc-a-usb", "copiar", carpeta=str(pc), destino=str(usb), filtro=filtro),
    )
    assert acciones("ejecutar", "usb-a-pc", config=ruta).exit_code == 0
    assert acciones("ejecutar", "pc-a-usb", config=ruta).exit_code == 0
    esperado = {"Programación/tema3.pdf", "Programación/practica.py"}
    assert relativos(usb) == esperado
    assert esperado <= relativos(pc)
    vuelta = acciones("ejecutar", "usb-a-pc", config=ruta)  # ya está todo en los dos sitios
    assert "ya está copiado" in vuelta.output
    assert not any("(1)" in nombre for nombre in relativos(pc))


def fecha(archivo: Path, segundos: float) -> None:
    """Pone la fecha de modificación ``segundos`` antes de ahora."""
    marca = datetime.now().timestamp() - segundos
    os.utime(archivo, (marca, marca))


def test_copia_aparte_no_repite_la_copia_en_cada_ejecucion(tmp_path):
    pc, usb = tmp_path / "PC", tmp_path / "USB"
    crear(usb / "a.txt", "viejo")
    fecha(usb / "a.txt", 3 * 86400)
    crear(pc / "a.txt", "nuevo y más largo")
    ruta = archivo_de_acciones(
        tmp_path, accion("ida", "copiar", carpeta=str(pc), destino=str(usb))
    )
    for _ in range(3):
        assert acciones("ejecutar", "ida", config=ruta).exit_code == 0
    assert relativos(usb) == {"a.txt", "a (1).txt"}  # una sola «(1)», no una por vez
    assert "ya está copiado como «a (1).txt»" in plano(acciones("ejecutar", "ida", "--simular", config=ruta).output)


def test_el_mas_nuevo_sustituye_y_deshacer_devuelve_la_version_vieja(tmp_path):
    pc, usb = tmp_path / "PC" / "DAM", tmp_path / "USB" / "DAM"
    crear(usb / "tema1" / "apuntes.md", "versión de clase")
    fecha(usb / "tema1" / "apuntes.md", 86400)
    crear(pc / "tema1" / "apuntes.md", "versión de casa, editada después")
    ruta = archivo_de_acciones(
        tmp_path,
        accion("pc-a-usb", "copiar", carpeta=str(pc), destino=str(usb), si_cambia="el-mas-nuevo",
               filtro={"recursivo": True}),
        accion("usb-a-pc", "copiar", carpeta=str(usb), destino=str(pc), si_cambia="el-mas-nuevo",
               filtro={"recursivo": True}),
    )
    simulado = acciones("ejecutar", "pc-a-usb", "--simular", config=ruta)
    assert "sustituye a la versión vieja" in plano(simulado.output)

    assert acciones("ejecutar", "pc-a-usb", config=ruta).exit_code == 0
    assert (usb / "tema1" / "apuntes.md").read_text(encoding="utf-8") == "versión de casa, editada después"
    assert relativos(usb) == {"tema1/apuntes.md"}  # sin «(1)»
    viejas = list((directorio_datos() / "papelera").rglob("apuntes.md"))
    assert [v.read_text(encoding="utf-8") for v in viejas] == ["versión de clase"]

    vuelta = acciones("ejecutar", "usb-a-pc", config=ruta)  # ya son iguales: nada que hacer
    assert "ya está copiado" in vuelta.output
    assert relativos(pc) == {"tema1/apuntes.md"}


def test_el_mas_nuevo_deshacer_trae_la_version_vieja(tmp_path):
    pc, usb = tmp_path / "PC", tmp_path / "USB"
    crear(usb / "a.txt", "viejo")
    fecha(usb / "a.txt", 86400)
    crear(pc / "a.txt", "nuevo")
    ruta = archivo_de_acciones(
        tmp_path, accion("ida", "copiar", carpeta=str(pc), destino=str(usb), si_cambia="el-mas-nuevo")
    )
    assert acciones("ejecutar", "ida", config=ruta).exit_code == 0
    resultado = acciones("deshacer", entrada="s\n")
    assert "Volvería 1 versión vieja que se sustituyó" in plano(resultado.output)
    assert (usb / "a.txt").read_text(encoding="utf-8") == "viejo"
    assert (pc / "a.txt").read_text(encoding="utf-8") == "nuevo"  # el original no se toca


def test_el_plan_dice_el_destino_una_vez_y_la_columna_va_corta(tmp_path):
    usb, pc = tmp_path / "USB", tmp_path / "DESTINOPC"
    crear(usb / "tema1" / "apuntes.md")
    crear(usb / "tema2" / "practica.md")
    ruta = archivo_de_acciones(
        tmp_path,
        accion("traer", "copiar", carpeta=str(usb), destino=str(pc), filtro={"recursivo": True}),
    )
    salida = acciones("ejecutar", "traer", "--simular", config=ruta).output
    assert salida.count("DESTINOPC") == 1  # en el recuadro («A …»), no en cada fila
    assert "2 archivos para copiar" in salida


def usb_y_pc_con_cambio(tmp_path: Path) -> tuple[Path, Path, Path]:
    """PC/a.txt «nuevo» (de hoy) y USB/a.txt «viejo» (de ayer); acción «ida» PC → USB."""
    pc, usb = tmp_path / "PC", tmp_path / "USB"
    crear(usb / "a.txt", "viejo")
    fecha(usb / "a.txt", 86400)
    crear(pc / "a.txt", "nuevo")
    ruta = archivo_de_acciones(
        tmp_path, accion("ida", "copiar", carpeta=str(pc), destino=str(usb), si_cambia="el-mas-nuevo")
    )
    return pc, usb, ruta


def test_una_copia_cortada_a_medias_no_deja_nada_roto(tmp_path, monkeypatch):
    import navaja.acciones as modulo

    pc, usb, ruta = usb_y_pc_con_cambio(tmp_path)

    def copia_que_se_corta(origen, destino, *args, **kwargs):
        Path(destino).write_text("nu", encoding="utf-8")  # medio archivo y… USB lleno
        raise OSError(28, "No queda espacio en el dispositivo")

    monkeypatch.setattr(modulo.shutil, "copy2", copia_que_se_corta)
    resultado = acciones("ejecutar", "ida", config=ruta)
    assert resultado.exit_code == 1
    assert "No queda espacio" in plano(resultado.output)
    assert (usb / "a.txt").read_text(encoding="utf-8") == "viejo"  # intacto
    assert {p.name for p in usb.iterdir()} == {"a.txt"}  # ni temporal ni medio archivo


def test_si_falla_al_poner_el_nombre_vuelve_la_version_vieja(tmp_path, monkeypatch):
    import navaja.acciones as modulo

    pc, usb, ruta = usb_y_pc_con_cambio(tmp_path)

    def replace_que_falla(*args, **kwargs):
        raise OSError(13, "Acceso denegado")

    monkeypatch.setattr(modulo.os, "replace", replace_que_falla)
    resultado = acciones("ejecutar", "ida", config=ruta)
    assert resultado.exit_code == 1
    assert (usb / "a.txt").read_text(encoding="utf-8") == "viejo"
    assert {p.name for p in usb.iterdir()} == {"a.txt"}


def test_si_tampoco_vuelve_la_vieja_dice_donde_esta(tmp_path, monkeypatch):
    import navaja.acciones as modulo

    pc, usb, ruta = usb_y_pc_con_cambio(tmp_path)
    mover_de_verdad = modulo.shutil.move
    llamadas = []

    def replace_que_falla(*args, **kwargs):
        raise OSError(13, "Acceso denegado")

    def move_que_falla_al_devolver(origen, destino, *args, **kwargs):
        llamadas.append(origen)
        if len(llamadas) > 1:  # la 1.ª aparta la vieja; la 2.ª intenta devolverla
            raise OSError(13, "Acceso denegado")
        return mover_de_verdad(origen, destino)

    monkeypatch.setattr(modulo.os, "replace", replace_que_falla)
    monkeypatch.setattr(modulo.shutil, "move", move_que_falla_al_devolver)
    resultado = acciones("ejecutar", "ida", config=ruta)
    assert resultado.exit_code == 1
    texto = plano(resultado.output)
    assert "no se pudo copiar ni devolver la versión vieja: está en" in texto
    viejas = list((directorio_datos() / "papelera").rglob("a.txt"))
    assert [v.read_text(encoding="utf-8") for v in viejas] == ["viejo"]  # no se ha perdido


def test_deshacer_no_quita_una_copia_que_has_editado_despues(tmp_path):
    pc, usb, ruta = usb_y_pc_con_cambio(tmp_path)
    assert acciones("ejecutar", "ida", config=ruta).exit_code == 0
    (usb / "a.txt").write_text("nuevo y además lo que hice por la tarde", encoding="utf-8")
    resultado = acciones("deshacer", entrada="s\n")
    assert "ha cambiado desde que se copió" in plano(resultado.output)
    assert (usb / "a.txt").read_text(encoding="utf-8") == "nuevo y además lo que hice por la tarde"


def test_deshacer_con_la_papelera_vaciada_lo_dice_y_no_toca_la_copia(tmp_path):
    import shutil

    pc, usb, ruta = usb_y_pc_con_cambio(tmp_path)
    assert acciones("ejecutar", "ida", config=ruta).exit_code == 0
    shutil.rmtree(directorio_datos() / "papelera")  # como «duplicados vaciar»
    resultado = acciones("deshacer", entrada="s\n")
    texto = plano(resultado.output)
    assert "1 versión vieja ya no está en la papelera de navaja" in texto
    assert "Volvería" not in texto
    assert (usb / "a.txt").read_text(encoding="utf-8") == "nuevo"


def test_deshacer_que_falla_guarda_el_registro_para_reintentarlo(tmp_path, monkeypatch):
    import navaja.comandos.mis_acciones as modulo
    from navaja.comun import cargar_acciones

    pc, usb, ruta = usb_y_pc_con_cambio(tmp_path)
    assert acciones("ejecutar", "ida", config=ruta).exit_code == 0
    mover_de_verdad = modulo.shutil.move
    llamadas = []

    def move_que_falla_al_devolver(origen, destino, *args, **kwargs):
        llamadas.append(origen)
        if len(llamadas) == 2:  # 1.ª: la copia a la papelera; 2.ª: devolver la vieja
            raise OSError(13, "Acceso denegado")
        return mover_de_verdad(origen, destino)

    monkeypatch.setattr(modulo.shutil, "move", move_que_falla_al_devolver)
    resultado = acciones("deshacer", entrada="s\n")
    assert resultado.exit_code == 1
    assert "sigue en" in plano(resultado.output)
    assert (usb / "a.txt").read_text(encoding="utf-8") == "nuevo"  # queda como estaba
    assert cargar_acciones("acciones")  # el registro sigue: se puede volver a intentar
    monkeypatch.setattr(modulo.shutil, "move", mover_de_verdad)  # (undo() quitaría también NAVAJA_DATOS)
    otra_vez = acciones("deshacer", entrada="s\n")
    assert otra_vez.exit_code == 0, otra_vez.output
    assert (usb / "a.txt").read_text(encoding="utf-8") == "viejo", otra_vez.output


def test_el_mas_nuevo_no_toca_si_alli_es_mas_reciente(tmp_path):
    pc, usb = tmp_path / "PC", tmp_path / "USB"
    crear(pc / "a.txt", "viejo")
    fecha(pc / "a.txt", 86400)
    crear(usb / "a.txt", "editado en clase")
    ruta = archivo_de_acciones(
        tmp_path, accion("ida", "copiar", carpeta=str(pc), destino=str(usb), si_cambia="el-mas-nuevo")
    )
    resultado = acciones("ejecutar", "ida", config=ruta)
    assert "allí hay una versión más nueva" in plano(resultado.output)
    assert (usb / "a.txt").read_text(encoding="utf-8") == "editado en clase"
    assert relativos(usb) == {"a.txt"}


def test_misma_copia_aguanta_el_cambio_de_hora_de_fat32(tmp_path):
    from navaja.acciones import misma_copia

    original, copia = crear(tmp_path / "a.txt", "igual"), crear(tmp_path / "b.txt", "igual")
    fecha(original, 7200)
    fecha(copia, 7200 - 3601)  # una hora (y un segundo de redondeo de FAT32) después
    assert misma_copia(original, copia)
    fecha(copia, 7200 - 1800)  # media hora: es otro archivo
    assert not misma_copia(original, copia)


@pytest.mark.skipif(os.name != "nt", reason="las letras de unidad son de Windows")
def test_destino_en_una_unidad_que_no_existe_para_antes_de_empezar(tmp_path):
    libre = next(
        (f"{letra}:" for letra in "QRSTUVWXYZ" if not Path(f"{letra}:/").exists()), None
    )
    if libre is None:
        pytest.skip("no hay ninguna letra de unidad libre")
    crear(tmp_path / "a.txt")
    ruta = archivo_de_acciones(
        tmp_path, accion("al-usb", "copiar", carpeta=str(tmp_path), destino=f"{libre}/DAM")
    )
    validado = acciones("validar", config=ruta)
    assert "unidad que no existe" in plano(validado.output)
    resultado = acciones("ejecutar", "al-usb", config=ruta)
    assert resultado.exit_code == 1
    assert "¿Está conectado el USB?" in plano(resultado.output)
    assert "Traceback" not in resultado.output


def test_excluir_sin_recursivo_avisa(tmp_path):
    ruta = archivo_de_acciones(
        tmp_path, accion("x", "copiar", destino="a", filtro={"excluir": "build"})
    )
    resultado = acciones("validar", config=ruta)
    assert resultado.exit_code == 0
    assert "«excluir» solo sirve con" in plano(resultado.output)


def test_excluir_en_el_filtro_se_describe_y_admite_lista(tmp_path):
    from navaja.filtros import Filtro, seleccionar

    crear(tmp_path / "a" / "dist" / "x.js")
    crear(tmp_path / "a" / "y.js")
    filtro = Filtro(recursivo=True, excluir=("dist",))
    assert seleccionar(tmp_path, filtro) == [tmp_path / "a" / "y.js"]
    assert "sin entrar en dist" in filtro.describir()
    assert Motor.seleccionar(tmp_path, {"recursivo": True, "excluir": ["DIST"]}) == [tmp_path / "a" / "y.js"]
    assert esquema.carpetas_excluidas(["node_modules, build", " dist "]) == ("node_modules", "build", "dist")


def test_renombrar_y_volver_a_ejecutar_no_lo_repite(tmp_path):
    fotos = tmp_path / "Fotos"
    crear(fotos / "IMG_0001.jpg")
    crear(fotos / "PXL_0002.jpg")
    crear(fotos / "playa.jpg")
    ruta = archivo_de_acciones(
        tmp_path,
        accion("fecha", "renombrar", carpeta=str(fotos), filtro={"patron": "^(IMG|PXL)_"},
               plantilla="{fecha:%Y-%m-%d}_{nombre}{ext}"),
    )
    assert acciones("ejecutar", "fecha", config=ruta).exit_code == 0
    hoy = datetime.now().strftime("%Y-%m-%d")
    assert relativos(fotos) == {f"{hoy}_IMG_0001.jpg", f"{hoy}_PXL_0002.jpg", "playa.jpg"}
    assert "Nada que hacer" in acciones("ejecutar", "fecha", config=ruta).output
    assert relativos(fotos) == {f"{hoy}_IMG_0001.jpg", f"{hoy}_PXL_0002.jpg", "playa.jpg"}


def test_renombrar_marca_los_que_acabarian_igual(tmp_path):
    fotos = tmp_path / "Fotos"
    crear(fotos / "a.jpg")
    crear(fotos / "b.jpg")
    ruta = archivo_de_acciones(tmp_path, accion("mal", "renombrar", carpeta=str(fotos), plantilla="foto{ext}"))
    resultado = acciones("ejecutar", "mal", "--simular", config=ruta)
    assert "dos archivos acabarían igual" in plano(resultado.output)


def test_borrar_va_a_la_papelera_y_deshacer_lo_devuelve(tmp_path, descargas):
    ruta = archivo_de_acciones(
        tmp_path,
        accion("viejos", "borrar", carpeta=str(descargas), filtro={"solo": "ejecutables", "hasta": "hace 30 días"}),
    )
    resultado = acciones("ejecutar", "viejos", config=ruta)
    assert resultado.exit_code == 0, resultado.output
    assert "papelera de navaja" in resultado.output
    assert not (descargas / "viejo.msi").exists()
    assert (descargas / "setup.exe").exists()  # es nuevo: no se toca
    assert any(p.name == "viejo.msi" for p in (directorio_datos() / "papelera").rglob("*"))

    resultado = acciones("deshacer")
    assert resultado.exit_code == 0, resultado.output
    assert (descargas / "viejo.msi").exists()
    assert not list((directorio_datos() / "papelera").rglob("*.msi"))
    assert "No hay ninguna acción que deshacer" in acciones("deshacer").output


def test_deshacer_una_copia_quita_solo_la_copia(tmp_path, descargas):
    copia = tmp_path / "Copia"
    ruta = archivo_de_acciones(
        tmp_path, accion("c", "copiar", carpeta=str(descargas), destino=str(copia), filtro={"solo": "pdf"})
    )
    acciones("ejecutar", "c", config=ruta)
    assert (copia / "factura.pdf").exists()
    acciones("deshacer")
    assert not copia.exists()  # la carpeta que creó también se quita
    assert (descargas / "factura.pdf").exists()


def test_rutina_hace_los_pasos_en_orden_y_se_deshace_entera(tmp_path, descargas):
    ia = tmp_path / "Imagenes IA"
    ruta = archivo_de_acciones(
        tmp_path,
        accion("ia", "mover", carpeta=str(descargas), destino=str(ia), filtro={"contiene": "gemini"}),
        accion("orden", "ordenar", carpeta=str(descargas), por="tipo"),
        accion("domingo", "rutina", pasos=["ia", "orden"]),
    )
    antes = relativos(descargas)
    resultado = acciones("ejecutar", "domingo", config=ruta)
    assert resultado.exit_code == 0, resultado.output
    assert "Paso 1 de 2: ia" in resultado.output and "Paso 2 de 2: orden" in resultado.output
    assert relativos(ia) == {"Gemini_Generated_Image_1.png"}  # antes de ordenar, se fue a IA
    assert "Imagenes/FOTO1.JPG" in relativos(descargas)

    assert acciones("deshacer").exit_code == 0
    assert relativos(descargas) == antes
    assert not ia.exists() and not (descargas / "Imagenes").exists()


def test_rutina_decir_que_no_para_los_pasos_que_quedan(tmp_path, descargas):
    ruta = archivo_de_acciones(
        tmp_path,
        accion("pdf", "mover", carpeta=str(descargas), destino="PDF", filtro={"solo": "pdf"}),
        accion("orden", "ordenar", carpeta=str(descargas), por="tipo"),
        accion("domingo", "rutina", pasos=["pdf", "orden"]),
    )
    resultado = acciones("ejecutar", "domingo", config=ruta, entrada="s\nn\n")
    assert "No se hacen" not in resultado.output  # era el último
    assert (descargas / "PDF" / "factura.pdf").exists()
    assert not (descargas / "Imagenes").exists()

    crear(descargas / "otra.pdf")
    resultado = acciones("ejecutar", "domingo", config=ruta, entrada="n\n")
    assert "Cancelado. No se hace el paso que queda." in plano(resultado.output)
    assert (descargas / "otra.pdf").exists()


def test_destino_relativo_y_carpeta_desde_la_orden(tmp_path, descargas):
    otra = tmp_path / "Otra"
    crear(otra / "nota.pdf")
    ruta = archivo_de_acciones(
        tmp_path, accion("pdf", "mover", carpeta=str(descargas), destino="PDF", filtro={"solo": "pdf", "recursivo": True})
    )
    assert acciones("ejecutar", "pdf", str(otra), config=ruta).exit_code == 0
    assert relativos(otra) == {"PDF/nota.pdf"}  # relativo a la carpeta en la que trabaja
    assert (descargas / "factura.pdf").exists()  # la suya no se toca
    # con -r no vuelve a coger lo que ya está en el destino
    assert "Nada que hacer" in acciones("ejecutar", "pdf", str(otra), config=ruta).output


def test_errores_al_ejecutar_salen_con_1(tmp_path, descargas):
    ruta = archivo_de_acciones(tmp_path, accion("pdf", "mover", carpeta=str(tmp_path / "no-hay"), destino="x"))
    resultado = acciones("ejecutar", "pdf", config=ruta)
    assert resultado.exit_code == 1
    assert "no existe (acción «pdf»)" in plano(resultado.output)

    resultado = acciones("ejecutar", "pfd", config=ruta)
    assert resultado.exit_code == 1
    assert "¿Querías decir «pdf»?" in plano(resultado.output)
    assert "Traceback" not in resultado.output


def test_ejecutar_por_numero(tmp_path, descargas):
    ruta = archivo_de_acciones(
        tmp_path, BUENA, accion("pdf", "mover", carpeta=str(descargas), destino="PDF", filtro={"solo": "pdf"})
    )
    resultado = acciones("ejecutar", "2", "--simular", config=ruta)
    assert resultado.exit_code == 0
    assert "factura.pdf" in resultado.output


# ── editar y modo interactivo ──────────────────────────────────────────────


def test_editar_crea_el_archivo_en_tus_datos_y_lo_comprueba(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EDITOR", "true")  # un «editor» que no cambia nada
    monkeypatch.delenv("VISUAL", raising=False)
    if os.name == "nt":
        pytest.skip("en Windows no hay orden true")
    resultado = acciones("editar")
    assert resultado.exit_code == 0, resultado.output
    assert esquema.en_datos().is_file()
    assert "✔ 1 acción válida" in resultado.output


def test_acciones_en_el_menu_interactivo(tmp_path, descargas, monkeypatch, capsys):
    archivo_de_acciones(
        tmp_path, accion("pdf", "mover", carpeta=str(descargas), destino="PDF", filtro={"solo": "pdf"})
    )
    monkeypatch.chdir(tmp_path)  # usa el acciones.json de aquí
    nombres = [n for n, _ in subcomandos(typer.main.get_command(app))]
    numero = str(nombres.index("acciones") + 1)
    respuestas = iter([numero, "2", "pdf", "", "salir"])
    monkeypatch.setattr("builtins.input", lambda *_: "s")  # a «¿Mover 1 archivo? [s/n]»

    def leer(prompt):
        try:
            return next(respuestas)
        except StopIteration:
            raise EOFError from None

    interactivo.iniciar(app, leer)
    texto = capsys.readouterr().out
    assert "Prueba pdf" in texto  # enseña la lista antes de preguntar
    assert (descargas / "PDF" / "factura.pdf").exists()


@pytest.mark.parametrize(
    "orden",
    [
        ["acciones", "--config", str(REPO / "pruebas" / "roto-tipo.json"), "validar"],
        ["acciones", "validar", "--config", str(REPO / "pruebas" / "roto-tipo.json")],
    ],
)
def test_config_antes_o_despues_de_la_orden(orden):
    resultado = runner.invoke(app, orden)
    assert resultado.exit_code == 3
    assert "«tipo»" in plano(resultado.output)


def test_el_config_de_la_orden_gana_al_del_grupo():
    resultado = runner.invoke(
        app,
        [
            "acciones", "--config", str(REPO / "pruebas" / "roto-tipo.json"),
            "validar", "--config", str(REPO / "pruebas" / "acciones-prueba.json"),
        ],
    )
    assert resultado.exit_code == 0, resultado.output
    prueba = json.loads((REPO / "pruebas" / "acciones-prueba.json").read_text(encoding="utf-8"))
    assert f"{len(prueba['acciones'])} acciones válidas" in plano(resultado.output)
