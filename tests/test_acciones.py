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
    assert "5 acciones válidas" in plano(resultado.output)
