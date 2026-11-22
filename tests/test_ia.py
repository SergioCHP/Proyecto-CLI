"""La capa de IA: el proveedor (Gemini), la clave en .env, el modo sin red y las acciones
renombrar-ia y resumir-ia.

Nunca se habla con Gemini de verdad: las acciones usan ``Falso`` (un proveedor que contesta
lo que le digamos) y los errores de red se simulan cambiando ``urlopen``. Todo pasa en
carpetas temporales (``tmp_path``) y ``conftest.py`` borra la clave y los .env reales.
"""

import io
import json
import ssl
import urllib.error
from pathlib import Path

import pytest
from typer.testing import CliRunner

from navaja import esquema, proveedor_ia
from navaja.acciones import Accion, RenombrarIA, ResumirIA, limpiar_nombre
from navaja.app import app
from navaja.errores import AccionNoValida, IANoDisponible, NavajaError, RespuestaIARara
from navaja.proveedor_ia import Gemini, ProveedorIA, Servidor, leer_env

runner = CliRunner()


# ── Ayudantes ──────────────────────────────────────────────────────────────


class Falso(ProveedorIA):
    """Un proveedor de mentira: contesta con ``responder(prompt)`` y apunta cada pregunta."""

    nombre = "Falso"

    def __init__(self, responder=lambda prompt: "respuesta") -> None:
        super().__init__("modelo-de-prueba")
        self.responder = responder
        self.preguntas: list[str] = []

    def _pedir(self, prompt: str) -> str:
        self.preguntas.append(prompt)
        return self.responder(prompt)


@pytest.fixture
def falso(monkeypatch):
    """Las acciones con IA usan este proveedor en vez de Gemini."""
    proveedor = Falso()
    monkeypatch.setattr(ProveedorIA, "desde_entorno", staticmethod(lambda entorno=None: proveedor))
    return proveedor


def escribir(ruta: Path, texto: str) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def config(tmp_path: Path, *acciones: dict) -> Path:
    ruta = tmp_path / "acciones.json"
    ruta.write_text(json.dumps({"version": 1, "acciones": list(acciones)}, ensure_ascii=False), encoding="utf-8")
    return ruta


def accion(nombre: str, tipo: str, carpeta: Path, **campos) -> dict:
    return {"nombre": nombre, "descripcion": f"Prueba {nombre}", "tipo": tipo, "carpeta": str(carpeta), **campos}


def ejecutar(ruta: Path, *argumentos: str, entrada: str = "s\ns\ns\n"):
    return runner.invoke(app, ["acciones", "ejecutar", *argumentos, "--config", str(ruta)], input=entrada)


def plano(texto: str) -> str:
    return " ".join(texto.split())


@pytest.fixture
def descargas(tmp_path):
    """Dos documentos con texto y un instalador (que la IA no sabe leer)."""
    carpeta = tmp_path / "Descargas"
    escribir(carpeta / "documento (3).txt", "Factura de Movistar del mes de octubre de 2026. Total: 30 euros.")
    escribir(carpeta / "Tema5.md", "# Subredes\nVLSM sirve para repartir una red en subredes de distinto tamaño.")
    escribir(carpeta / "setup.exe", "binario")
    return carpeta


# ── La clave y el .env ─────────────────────────────────────────────────────


def test_leer_env_entiende_comentarios_comillas_y_export(tmp_path):
    ruta = escribir(
        tmp_path / ".env",
        "# mi clave\n\nGEMINI_API_KEY=\"abc 123\"\nexport NAVAJA_MODELO=gemini-x  # el rápido\nroto\n",
    )
    assert leer_env(ruta) == {"GEMINI_API_KEY": "abc 123", "NAVAJA_MODELO": "gemini-x"}
    assert leer_env(tmp_path / "no-existe.env") == {}  # sin .env no pasa nada


def test_la_clave_sale_del_env_y_la_variable_gana(tmp_path, monkeypatch):
    escribir(tmp_path / ".env", "GEMINI_API_KEY=del-archivo-1234\n")
    monkeypatch.setattr(proveedor_ia, "archivos_env", lambda: [tmp_path / ".env"])
    datos = proveedor_ia.configuracion({})
    assert (datos.clave, datos.origen) == ("del-archivo-1234", str(tmp_path / ".env"))
    assert datos.modelo == proveedor_ia.MODELO_POR_DEFECTO
    datos = proveedor_ia.configuracion({"GEMINI_API_KEY": "de-la-variable"})
    assert (datos.clave, datos.origen) == ("de-la-variable", "la variable GEMINI_API_KEY")
    proveedor = ProveedorIA.desde_entorno({})
    assert isinstance(proveedor, Gemini)


def test_sin_clave_lo_explica_sin_traza():
    with pytest.raises(IANoDisponible) as error:
        ProveedorIA.desde_entorno({})
    assert "GEMINI_API_KEY" in str(error.value) and ".env" in str(error.value)
    assert error.value.codigo_salida == 4


def test_navaja_sin_ia_la_apaga_aunque_haya_clave():
    with pytest.raises(IANoDisponible, match="apagada"):
        ProveedorIA.desde_entorno({"GEMINI_API_KEY": "una-clave-buena", "NAVAJA_SIN_IA": "1"})


def test_la_clave_nunca_se_ensena_entera():
    assert proveedor_ia.oculta("AIzaSyA-una-clave-muy-larga-WXYZ") == "…WXYZ"
    assert proveedor_ia.oculta("corta") == "…"


# ── Gemini: la llamada y sus errores (sin red de verdad) ──────────────────


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def con_urlopen(monkeypatch, hacer):
    monkeypatch.setattr(proveedor_ia.urllib.request, "urlopen", lambda peticion, timeout: hacer(peticion))


def error_http(codigo: int, cuerpo: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", codigo, "error", {}, io.BytesIO(cuerpo))


def test_gemini_manda_la_clave_en_cabecera_y_lee_el_texto(monkeypatch):
    vistas = []

    def contestar(peticion):
        vistas.append(peticion)
        datos = {"candidates": [{"content": {"parts": [{"text": "pensando…", "thought": True}, {"text": " hola "}]}}]}
        return Respuesta(json.dumps(datos).encode())

    con_urlopen(monkeypatch, contestar)
    assert Gemini("clave-secreta-1234", "gemini-x").preguntar("di hola") == "hola"
    peticion = vistas[0]
    assert "clave-secreta" not in peticion.full_url  # la clave no va en la URL
    assert peticion.get_header("X-goog-api-key") == "clave-secreta-1234"
    assert "gemini-x" in peticion.full_url


@pytest.mark.parametrize(
    ("fallo", "esperado"),
    [
        (urllib.error.URLError("sin red"), "internet"),
        (TimeoutError(), "no ha contestado"),
        (urllib.error.URLError(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED")), "certificado"),
        (error_http(429, b'{"error": {"message": "quota"}}'), "cupo"),
        (error_http(400, b'{"error": {"message": "API key not valid."}}'), "clave"),
        (error_http(404, b'{"error": {"message": "not found"}}'), "no existe"),
        (error_http(503, b'{"error": {"message": "overloaded"}}'), "más tarde"),
        (error_http(403, b"request blocked"), "proxy"),  # no es Google: un cortafuegos
    ],
)
def test_cada_error_de_red_es_ia_no_disponible_con_mensaje_humano(monkeypatch, fallo, esperado):
    def fallar(_):
        raise fallo

    con_urlopen(monkeypatch, fallar)
    with pytest.raises(IANoDisponible) as error:
        Gemini("clave-1234", "gemini-x").preguntar("hola")
    assert esperado in str(error.value)
    assert "clave-1234" not in str(error.value)


@pytest.mark.parametrize(
    "datos",
    [{"promptFeedback": {"blockReason": "SAFETY"}}, {"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]}],
)
def test_una_respuesta_bloqueada_o_vacia_es_rara(monkeypatch, datos):
    con_urlopen(monkeypatch, lambda _: Respuesta(json.dumps(datos).encode()))
    with pytest.raises(RespuestaIARara):
        Gemini("clave-1234").preguntar("hola")


# ── Un servidor compatible con OpenAI (Ollama, el del centro…) ─────────────


def respuesta_openai(texto: str) -> Respuesta:
    return Respuesta(json.dumps({"choices": [{"message": {"role": "assistant", "content": texto}}]}).encode())


def test_con_navaja_ia_url_se_usa_el_servidor_y_no_hace_falta_clave():
    proveedor = ProveedorIA.desde_entorno({"NAVAJA_IA_URL": "http://localhost:11434/v1"})
    assert isinstance(proveedor, Servidor)  # sin GEMINI_API_KEY y sin NAVAJA_IA_CLAVE
    assert proveedor.modelo == proveedor_ia.MODELO_SERVIDOR  # llama3.2 si no se dice otro
    datos = proveedor_ia.configuracion({"NAVAJA_IA_URL": "http://x/v1", "NAVAJA_MODELO": "qwen3",
                                        "NAVAJA_IA_CLAVE": "clave-del-centro", "GEMINI_API_KEY": "otra"})
    assert (datos.con_servidor, datos.modelo, datos.clave) == (True, "qwen3", "clave-del-centro")


def test_el_servidor_recibe_lo_que_espera_la_api_de_openai(monkeypatch):
    vistas = []

    def contestar(peticion):
        vistas.append(peticion)
        return respuesta_openai(" hola ")

    con_urlopen(monkeypatch, contestar)
    assert Servidor("http://centro:8000/v1/", "llama3", "clave-1234").preguntar("di hola") == "hola"
    peticion = vistas[0]
    assert peticion.full_url == "http://centro:8000/v1/chat/completions"  # sin la / repetida
    assert peticion.get_header("Authorization") == "Bearer clave-1234"  # la clave, en la cabecera
    cuerpo = json.loads(peticion.data)
    assert cuerpo["model"] == "llama3" and cuerpo["messages"][0]["content"] == "di hola"


def test_el_servidor_sin_clave_no_manda_authorization(monkeypatch):
    vistas = []
    con_urlopen(monkeypatch, lambda peticion: vistas.append(peticion) or respuesta_openai("ok"))
    Servidor("http://localhost:11434/v1").preguntar("hola")
    assert vistas[0].get_header("Authorization") is None


def test_el_servidor_quita_lo_que_el_modelo_piensa_en_voz_alta(monkeypatch):
    con_urlopen(monkeypatch, lambda _: respuesta_openai("<think>a ver…</think>\nfactura-movistar"))
    assert Servidor("http://localhost:11434/v1").preguntar("nombre") == "factura-movistar"


@pytest.mark.parametrize(
    ("fallo", "esperado"),
    [
        (urllib.error.URLError("connection refused"), "¿está encendido"),
        (TimeoutError(), "más pequeño"),
        (error_http(401, b'{"error": {"message": "bad key"}}'), "NAVAJA_IA_CLAVE"),
        (error_http(404, b'{"error": "model \'llama9\' not found"}'), "ollama list"),
        (error_http(500, b"{}"), "Prueba más tarde"),
    ],
)
def test_cada_fallo_del_servidor_dice_que_hacer(monkeypatch, fallo, esperado):
    def fallar(_):
        raise fallo

    con_urlopen(monkeypatch, fallar)
    with pytest.raises(IANoDisponible) as error:
        Servidor("http://localhost:11434/v1", "llama9", "clave-1234").preguntar("hola")
    assert esperado in str(error.value)
    assert "clave-1234" not in str(error.value)


def test_una_url_que_no_es_una_direccion_lo_dice():
    with pytest.raises(IANoDisponible, match="http://"):
        ProveedorIA.desde_entorno({"NAVAJA_IA_URL": "localhost:11434"})


def test_comprobar_ia_con_servidor_dice_cual_y_que_no_hace_falta_clave(monkeypatch):
    monkeypatch.setenv("NAVAJA_IA_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(Servidor, "_pedir", lambda self, prompt: "ok")
    resultado = runner.invoke(app, ["comprobar-ia"])
    assert resultado.exit_code == 0, resultado.output
    texto = plano(resultado.output)
    assert "localhost:11434" in texto and "llama3.2" in texto and "lista" in texto


# ── Validación en acciones.json ────────────────────────────────────────────


def test_los_tipos_con_ia_se_registran_solos():
    tipos = Accion.tipos()
    assert tipos["renombrar-ia"] is RenombrarIA and tipos["resumir-ia"] is ResumirIA
    assert RenombrarIA.usa_ia and not tipos["renombrar"].usa_ia


@pytest.mark.parametrize(
    ("campos", "campo"),
    [
        ({"instrucciones": 3}, "instrucciones"),
        ({"instrucciones": "  "}, "instrucciones"),
        ({"instrucciones": "x" * 501}, "instrucciones"),
        ({"plantilla": "{n}{ext}"}, "plantilla"),  # es de renombrar, no de renombrar-ia
    ],
)
def test_un_campo_mal_en_una_accion_con_ia_dice_cual(tmp_path, campos, campo):
    datos = {"version": 1, "acciones": [accion("nombres", "renombrar-ia", tmp_path, **campos)]}
    with pytest.raises(AccionNoValida) as error:
        esquema.validar(datos)
    assert error.value.campo == campo


def test_validar_avisa_si_hay_acciones_con_ia_y_no_hay_clave(tmp_path):
    ruta = config(tmp_path, accion("nombres", "renombrar-ia", tmp_path))
    resultado = runner.invoke(app, ["acciones", "validar", "--config", str(ruta)])
    assert resultado.exit_code == 0  # el archivo está bien: solo es un aviso
    assert "no hay clave de Gemini" in plano(resultado.output)


# ── renombrar-ia ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("respuesta", "nombre"),
    [
        ('"Factura Movistar – octubre 2026.pdf"', "factura-movistar-octubre-2026"),
        ("Nombre: apuntes-redes-tema5", "apuntes-redes-tema5"),
        ("**Ejercicios de VLSM**\nEs un documento sobre…", "ejercicios-de-vlsm"),
        ("Año académico: Programación", "ano-academico-programacion"),
    ],
)
def test_limpiar_nombre_deja_un_nombre_que_vale_en_cualquier_sistema(respuesta, nombre):
    assert limpiar_nombre(respuesta) == nombre


def test_limpiar_nombre_sin_nada_que_sirva_es_respuesta_rara():
    with pytest.raises(RespuestaIARara):
        limpiar_nombre("¿?¡!")


def nombres_por_contenido(prompt: str) -> str:
    return "Factura Movistar octubre 2026" if "Movistar" in prompt else "apuntes subredes vlsm"


def test_renombrar_ia_simulado_no_toca_nada(tmp_path, descargas, falso):
    falso.responder = nombres_por_contenido
    ruta = config(tmp_path, accion("nombres", "renombrar-ia", descargas))
    antes = sorted(p.name for p in descargas.iterdir())
    resultado = ejecutar(ruta, "nombres", "--simular")
    assert resultado.exit_code == 0, resultado.output
    texto = plano(resultado.output)
    assert "factura-movistar-octubre-2026.txt" in texto and "apuntes-subredes-vlsm.md" in texto
    assert "no sé leer los .exe" in texto  # el instalador se salta sin preguntar a la IA
    assert "papelera" not in texto  # saltarse no es borrar
    assert len(falso.preguntas) == 2
    assert sorted(p.name for p in descargas.iterdir()) == antes  # nada cambia de nombre


def test_renombrar_ia_renombra_y_deshacer_lo_devuelve(tmp_path, descargas, falso):
    falso.responder = nombres_por_contenido
    ruta = config(tmp_path, accion("nombres", "renombrar-ia", descargas, filtro={"solo": "txt,md"}))
    resultado = ejecutar(ruta, "nombres", "--si")
    assert resultado.exit_code == 0, resultado.output
    assert sorted(p.name for p in descargas.iterdir()) == [
        "apuntes-subredes-vlsm.md", "factura-movistar-octubre-2026.txt", "setup.exe"
    ]
    assert runner.invoke(app, ["acciones", "deshacer", "--si"]).exit_code == 0
    assert sorted(p.name for p in descargas.iterdir()) == ["Tema5.md", "documento (3).txt", "setup.exe"]


def test_renombrar_ia_no_pisa_nunca_un_archivo_que_ya_existe(tmp_path, descargas, falso):
    escribir(descargas / "factura-movistar-octubre-2026.txt", "la que ya estaba")
    falso.responder = nombres_por_contenido
    ruta = config(tmp_path, accion("nombres", "renombrar-ia", descargas, filtro={"contiene": "documento"}))
    assert ejecutar(ruta, "nombres", "--si").exit_code == 0
    assert (descargas / "factura-movistar-octubre-2026.txt").read_text(encoding="utf-8") == "la que ya estaba"
    assert (descargas / "factura-movistar-octubre-2026 (1).txt").exists()


def test_una_respuesta_rara_solo_salta_ese_archivo(tmp_path, descargas, falso):
    falso.responder = lambda prompt: "???" if "Movistar" in prompt else "apuntes subredes"
    ruta = config(tmp_path, accion("nombres", "renombrar-ia", descargas, filtro={"solo": "txt,md"}))
    resultado = ejecutar(ruta, "nombres", "--si")
    assert resultado.exit_code == 0, resultado.output
    assert "no ha propuesto un nombre que sirva" in plano(resultado.output)
    assert sorted(p.name for p in descargas.iterdir()) == ["apuntes-subredes.md", "documento (3).txt", "setup.exe"]


# ── resumir-ia ─────────────────────────────────────────────────────────────


def test_resumir_ia_escribe_el_resumen_al_lado_y_no_toca_el_original(tmp_path, descargas, falso):
    falso.responder = lambda prompt: "# Subredes\n\nVLSM reparte una red.\n\n- Máscaras distintas"
    ruta = config(tmp_path, accion("resumir", "resumir-ia", descargas, filtro={"solo": "md"},
                                   instrucciones="para estudiar"))
    original = (descargas / "Tema5.md").read_text(encoding="utf-8")
    resultado = ejecutar(ruta, "resumir", "--si")
    assert resultado.exit_code == 0, resultado.output
    resumen = (descargas / "Tema5.resumen.md").read_text(encoding="utf-8")
    assert resumen.startswith("# Subredes") and "hecho con IA" in resumen and "Tema5.md" in resumen
    assert (descargas / "Tema5.md").read_text(encoding="utf-8") == original
    assert "para estudiar" in falso.preguntas[0]  # las instrucciones del JSON llegan a la IA


def test_resumir_ia_la_segunda_vez_solo_resume_lo_nuevo(tmp_path, descargas, falso):
    ruta = config(tmp_path, accion("resumir", "resumir-ia", descargas, filtro={"solo": "md,txt"}))
    assert ejecutar(ruta, "resumir", "--si").exit_code == 0
    assert len(falso.preguntas) == 2
    resultado = ejecutar(ruta, "resumir", "--si")
    assert "ya tiene resumen" in plano(resultado.output)
    assert "Tema5.resumen.resumen.md" not in {p.name for p in descargas.iterdir()}  # un resumen no se resume
    assert len(falso.preguntas) == 2  # no se ha vuelto a preguntar


def test_resumir_ia_deshacer_manda_los_resumenes_a_la_papelera(tmp_path, descargas, falso):
    ruta = config(tmp_path, accion("resumir", "resumir-ia", descargas, filtro={"solo": "md"}))
    assert ejecutar(ruta, "resumir", "--si").exit_code == 0
    assert (descargas / "Tema5.resumen.md").exists()
    resultado = runner.invoke(app, ["acciones", "deshacer", "--si"])
    assert resultado.exit_code == 0, resultado.output
    assert not (descargas / "Tema5.resumen.md").exists()
    assert (descargas / "Tema5.md").exists()
    from navaja.comun import carpeta_papelera
    assert list(carpeta_papelera().rglob("Tema5.resumen.md"))  # en la papelera, no borrado


def test_resumir_ia_con_destino_los_junta_en_otra_carpeta(tmp_path, descargas, falso):
    ruta = config(tmp_path, accion("resumir", "resumir-ia", descargas, filtro={"solo": "md"}, destino="Resúmenes"))
    assert ejecutar(ruta, "resumir", "--si").exit_code == 0
    assert (descargas / "Resúmenes" / "Tema5.resumen.md").exists()


# ── Sin IA: se explica y lo demás sigue ────────────────────────────────────


def test_sin_clave_la_accion_con_ia_lo_dice_sin_traza_y_no_toca_nada(tmp_path, descargas):
    ruta = config(tmp_path, accion("nombres", "renombrar-ia", descargas))
    antes = sorted(p.name for p in descargas.iterdir())
    resultado = ejecutar(ruta, "nombres")
    assert resultado.exit_code == 4
    assert "GEMINI_API_KEY" in plano(resultado.output)
    assert "Traceback" not in resultado.output and not isinstance(resultado.exception, IANoDisponible)
    assert sorted(p.name for p in descargas.iterdir()) == antes


def test_una_rutina_sin_ia_se_salta_ese_paso_y_hace_los_demas(tmp_path, descargas):
    ruta = config(
        tmp_path,
        accion("nombres", "renombrar-ia", descargas),
        accion("instaladores", "mover", descargas, filtro={"solo": "exe"}, destino="Instaladores"),
        {"nombre": "todo", "descripcion": "Prueba todo", "tipo": "rutina", "pasos": ["nombres", "instaladores"]},
    )
    resultado = ejecutar(ruta, "todo", "--si")
    texto = plano(resultado.output)
    assert "necesita IA" in texto and "Sigo con los demás" in texto
    assert (descargas / "Instaladores" / "setup.exe").exists()  # el paso sin IA sí se hace
    assert resultado.exit_code == 1  # pero avisa de que no se hizo todo
    assert "Traceback" not in resultado.output


def test_si_se_va_la_red_a_medias_no_se_pregunta_mas_y_lo_hecho_se_queda(tmp_path, descargas, falso):
    def red_que_se_cae(prompt):
        if len(falso.preguntas) > 1:
            raise IANoDisponible("No hay conexión con Gemini: ¿tienes internet?")
        return "# Resumen"

    falso.responder = red_que_se_cae
    escribir(descargas / "Tema6.md", "# Enrutamiento\nLas rutas estáticas se configuran a mano en el router.")
    ruta = config(tmp_path, accion("resumir", "resumir-ia", descargas, filtro={"solo": "md,txt"}))
    resultado = ejecutar(ruta, "resumir", "--si")
    texto = plano(resultado.output)
    assert resultado.exit_code == 1
    assert len(falso.preguntas) == 2  # tras el fallo de red no se insiste con el tercero
    assert len(list(descargas.glob("*.resumen.md"))) == 1  # el primero sí se hizo
    assert "internet" in texto and "Traceback" not in resultado.output


def test_renombrar_ia_si_se_va_la_red_a_medias_hace_los_que_ya_tenia(tmp_path, descargas, falso):
    def red_que_se_cae(prompt):
        if len(falso.preguntas) > 1:
            raise IANoDisponible("No hay conexión con Gemini: ¿tienes internet?")
        return "primero"

    falso.responder = red_que_se_cae
    ruta = config(tmp_path, accion("nombres", "renombrar-ia", descargas, filtro={"solo": "txt,md"}))
    resultado = ejecutar(ruta, "nombres", "--si")
    assert resultado.exit_code == 0, resultado.output
    assert "internet" in plano(resultado.output)
    nombres = {p.name for p in descargas.iterdir()}
    assert len(nombres & {"primero.txt", "primero.md"}) == 1  # el primero sí se renombra
    assert len(nombres & {"documento (3).txt", "Tema5.md"}) == 1  # el otro, sin IA, se queda igual


# ── comprobar-ia ───────────────────────────────────────────────────────────


def test_comprobar_ia_sin_clave_explica_que_hacer_y_sale_con_4():
    resultado = runner.invoke(app, ["comprobar-ia"])
    assert resultado.exit_code == 4
    texto = plano(resultado.output)
    assert "no hay" in texto and ".env" in texto and "aistudio" in texto


def test_comprobar_ia_con_ia_dice_que_esta_lista(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba-ABCD")
    monkeypatch.setattr(Gemini, "_pedir", lambda self, prompt: "ok")
    resultado = runner.invoke(app, ["comprobar-ia"])
    assert resultado.exit_code == 0, resultado.output
    texto = plano(resultado.output)
    assert "lista" in texto and "…ABCD" in texto
    assert "clave-de-prueba" not in texto  # la clave no se enseña


def test_comprobar_ia_sin_red_no_tiene_traza(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba-ABCD")

    def sin_red(_):
        raise urllib.error.URLError("sin red")

    con_urlopen(monkeypatch, sin_red)
    resultado = runner.invoke(app, ["comprobar-ia"])
    assert resultado.exit_code == 4
    assert "internet" in plano(resultado.output) and "Traceback" not in resultado.output


def test_ningun_error_de_ia_es_una_traza():
    """Todos son NavajaError: las órdenes los enseñan en una línea."""
    assert issubclass(IANoDisponible, NavajaError) and issubclass(RespuestaIARara, NavajaError)
