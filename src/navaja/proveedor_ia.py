"""El proveedor de IA: la única parte de navaja que habla con un modelo.

Las acciones con IA (``renombrar-ia`` y ``resumir-ia``) no saben a quién preguntan: piden
el proveedor a ``ProveedorIA.desde_entorno()`` y le llaman ``preguntar``. Hay dos:

- ``Gemini`` (Google), con ``GEMINI_API_KEY``: el de por defecto.
- ``Servidor``: cualquier servidor compatible con la API de OpenAI (Ollama, LM Studio, el
  servidor de modelos del centro…), si se pone su dirección en ``NAVAJA_IA_URL`` (y su clave
  en ``NAVAJA_IA_CLAVE``, si la pide).

Las claves nunca están en el código ni en el repositorio. Se leen, por este orden, de las
variables de entorno, del archivo ``.env`` de la carpeta actual o del ``.env`` de tus datos
de navaja. Git ignora ``.env``; ``.env.example`` dice qué poner.

Sin clave, sin internet, con una clave mala o sin cupo, se lanza ``IANoDisponible`` con
un mensaje en castellano: quien llama lo enseña en una línea y el resto de navaja sigue
funcionando. Si la IA contesta algo que no sirve, ``RespuestaIARara`` (solo para ese
archivo).
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from .comun import directorio_datos
from .errores import IANoDisponible, RespuestaIARara

ENV_CLAVE = "GEMINI_API_KEY"
ENV_MODELO = "NAVAJA_MODELO"
ENV_SIN_IA = "NAVAJA_SIN_IA"
ENV_URL = "NAVAJA_IA_URL"
"""La dirección de un servidor compatible con OpenAI. Si está, se usa en vez de Gemini."""
ENV_CLAVE_SERVIDOR = "NAVAJA_IA_CLAVE"
"""La clave de ese servidor, si la pide (Ollama en tu PC no pide ninguna)."""
MODELO_SERVIDOR = "llama3.2"
"""El modelo del servidor si no se dice otro: el de los ejemplos de clase con Ollama."""
MODELO_POR_DEFECTO = "gemini-flash-lite-latest"
"""Un alias de Google que apunta siempre al Flash-Lite más reciente: así no caduca. Es el
rápido (contesta en un segundo); el Flash normal «piensa» antes y a veces pasaba de 60 s."""

DONDE_SACAR_CLAVE = "https://aistudio.google.com/apikey"


# ── La configuración: clave y modelo ───────────────────────────────────────


def leer_env(ruta: Path) -> dict[str, str]:
    """Las variables de un archivo .env: ``CLAVE=valor`` por línea.

    Admite comentarios (#), líneas en blanco, ``export`` delante y el valor entre
    comillas. Lo que no se entiende se salta: un .env mal escrito no rompe navaja.
    """
    try:
        texto = ruta.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return {}
    variables: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        elif " #" in valor:  # comentario al final: CLAVE=valor  # lo que sea
            valor = valor.split(" #", 1)[0].rstrip()
        if clave:
            variables[clave] = valor
    return variables


def archivos_env() -> list[Path]:
    """Dónde se busca .env: en la carpeta actual y en la de tus datos de navaja."""
    return [Path.cwd() / ".env", directorio_datos() / ".env"]


@dataclass
class Configuracion:
    clave: str
    """La del proveedor que toca: ``GEMINI_API_KEY`` o, con servidor, ``NAVAJA_IA_CLAVE``."""
    modelo: str
    """El que se usará: el de ``NAVAJA_MODELO`` o el de por defecto de ese proveedor."""
    origen: str
    """De dónde salió la clave, para «comprobar-ia»: «la variable GEMINI_API_KEY» o la
    ruta del .env. Vacío si no hay clave."""
    apagada: bool = False
    """``NAVAJA_SIN_IA``: la IA está apagada a propósito."""
    url: str = ""
    """``NAVAJA_IA_URL``: con ella, un servidor compatible con OpenAI en vez de Gemini."""

    @property
    def con_servidor(self) -> bool:
        return bool(self.url)


def configuracion(entorno: Mapping[str, str] | None = None) -> Configuracion:
    """Clave y modelo. La variable de entorno gana al .env; el .env de la carpeta actual,
    al de tus datos (el más cercano es el más concreto)."""
    entorno = os.environ if entorno is None else entorno
    valores: dict[str, str] = {}
    origenes: dict[str, str] = {}
    for ruta in reversed(archivos_env()):  # el de la carpeta actual, el último: gana
        for clave, valor in leer_env(ruta).items():
            if valor:
                valores[clave], origenes[clave] = valor, str(ruta)
    for clave in (ENV_CLAVE, ENV_MODELO, ENV_SIN_IA, ENV_URL, ENV_CLAVE_SERVIDOR):
        if entorno.get(clave):
            valores[clave], origenes[clave] = entorno[clave], f"la variable {clave}"
    url = valores.get(ENV_URL, "").strip()
    nombre_clave = ENV_CLAVE_SERVIDOR if url else ENV_CLAVE
    clave = valores.get(nombre_clave, "").strip()
    return Configuracion(
        clave=clave,
        modelo=valores.get(ENV_MODELO, "").strip() or (MODELO_SERVIDOR if url else MODELO_POR_DEFECTO),
        origen=origenes.get(nombre_clave, "") if clave else "",
        apagada=valores.get(ENV_SIN_IA, "").strip().lower() not in ("", "0", "no", "false"),
        url=url,
    )


def hay_clave() -> bool:
    """¿Se podría usar la IA? (sin preguntar a nadie: hay clave de Gemini o un servidor)."""
    datos = configuracion()
    return (datos.con_servidor or bool(datos.clave)) and not datos.apagada


def sin_clave() -> IANoDisponible:
    return IANoDisponible(
        f"Las acciones con IA necesitan una clave de Gemini y no la encuentro. Sácala gratis en "
        f"{DONDE_SACAR_CLAVE} y ponla en un archivo .env (copia .env.example): "
        f"{ENV_CLAVE}=tu-clave. Si tienes un servidor de IA (Ollama, el del centro…), pon su "
        f"dirección en {ENV_URL}. Lo demás de navaja funciona sin ella."
    )


def oculta(clave: str) -> str:
    """Solo las 4 últimas letras: lo justo para saber cuál es, sin enseñarla."""
    return f"…{clave[-4:]}" if len(clave) > 8 else "…"


# ── El proveedor ───────────────────────────────────────────────────────────


class ProveedorIA(ABC):
    """A quién se le pregunta. Las subclases solo saben hacer la llamada (``_pedir``)."""

    nombre: ClassVar[str] = ""

    def __init__(self, modelo: str) -> None:
        self.modelo = modelo

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.modelo!r})"

    @staticmethod
    def desde_entorno(entorno: Mapping[str, str] | None = None) -> ProveedorIA:
        """Fábrica: el proveedor que toca según la configuración. ``IANoDisponible`` si la IA
        está apagada (``NAVAJA_SIN_IA``) o no hay clave."""
        datos = configuracion(entorno)
        if datos.apagada:
            raise IANoDisponible(
                f"La IA está apagada ({ENV_SIN_IA}). Quítalo para usar las acciones con IA; "
                "lo demás de navaja funciona igual."
            )
        if datos.con_servidor:
            return Servidor(datos.url, datos.modelo, datos.clave)
        if not datos.clave:
            raise sin_clave()
        return Gemini(datos.clave, datos.modelo)

    def preguntar(self, instrucciones: str, texto: str = "") -> str:
        """La respuesta de la IA, sin espacios de sobra. ``RespuestaIARara`` si viene vacía."""
        prompt = instrucciones.strip()
        if texto:
            prompt += f"\n\n<<<TEXTO\n{texto.strip()}\nTEXTO>>>"
        respuesta = self._pedir(prompt).strip()
        if not respuesta:
            raise RespuestaIARara(f"{self.nombre} ha contestado en blanco.")
        return respuesta

    def comprobar(self) -> str:
        """Una pregunta mínima para ver que responde (lo usa «comprobar-ia»)."""
        return self.preguntar("Responde solo con la palabra: ok")

    @abstractmethod
    def _pedir(self, prompt: str) -> str:
        """Le manda el texto al modelo y devuelve lo que contesta. Lanza ``IANoDisponible``
        o ``RespuestaIARara``; nunca una excepción de la red."""

    ESPERA: ClassVar[int] = 60
    """Segundos como mucho por respuesta."""

    def llamar(self, peticion: urllib.request.Request) -> Any:
        """Hace la petición y devuelve el JSON. Cada fallo, traducido por la subclase
        (``error_http`` y ``error_de_red``): nunca sale una excepción de la red."""
        try:
            with urllib.request.urlopen(peticion, timeout=self.ESPERA) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise self.error_http(error.code, self.mensaje_de(error)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise self.error_de_red(error) from None
        except (ValueError, UnicodeDecodeError):
            raise RespuestaIARara(f"{self.nombre} ha contestado algo que no es JSON.") from None

    @staticmethod
    def mensaje_de(error: urllib.error.HTTPError) -> str:
        """El «message» que viene en el cuerpo del error (Google y OpenAI lo mandan en
        ``{"error": {"message": …}}``; Ollama, a veces, en ``{"error": "…"}``)."""
        try:
            cuerpo = json.loads(error.read().decode("utf-8"))
            detalle = cuerpo.get("error", "")
            return str(detalle.get("message", "") if isinstance(detalle, dict) else detalle)
        except (ValueError, OSError, AttributeError):
            return ""

    def error_http(self, codigo: int, mensaje: str) -> IANoDisponible | RespuestaIARara:
        """El error HTTP ``codigo``, en castellano. Cada proveedor lo afina con qué hacer."""
        detalle = f": {mensaje}" if mensaje else ""
        if codigo in (401, 403, 404, 429) or codigo >= 500:
            return IANoDisponible(f"{self.nombre} no se puede usar ahora (error {codigo}{detalle}).")
        return RespuestaIARara(f"{self.nombre} no ha aceptado la petición (error {codigo}){detalle}")

    def error_de_red(self, error: OSError) -> IANoDisponible:
        """Por qué no se llega al modelo. Cada proveedor lo afina con qué hacer."""
        return IANoDisponible(f"No hay conexión con {self.nombre}. Detalle: {self.motivo_de_red(error)[1]}")

    @staticmethod
    def motivo_de_red(error: OSError) -> tuple[str, Any]:
        """«certificado», «espera» u «otro», y el motivo de verdad (para el «Detalle»)."""
        motivo = getattr(error, "reason", error)
        if isinstance(motivo, ssl.SSLError) or "CERTIFICATE" in str(motivo).upper():
            return "certificado", motivo
        if isinstance(motivo, TimeoutError) or "timed out" in str(motivo).lower():
            return "espera", motivo
        return "otro", motivo


class Gemini(ProveedorIA):
    """Gemini de Google por su API REST, con la librería estándar (sin dependencias)."""

    nombre = "Gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

    def __init__(self, clave: str, modelo: str = MODELO_POR_DEFECTO) -> None:
        super().__init__(modelo)
        self._clave = clave  # privada: nunca se enseña ni se escribe en ningún sitio

    def peticion(self, prompt: str) -> urllib.request.Request:
        """La petición HTTP. La clave va en una cabecera, no en la URL: así no sale en
        ningún registro ni mensaje de error."""
        cuerpo = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        return urllib.request.Request(
            self.URL.format(modelo=self.modelo),
            data=json.dumps(cuerpo).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._clave},
            method="POST",
        )

    def _pedir(self, prompt: str) -> str:
        return self.texto_de(self.llamar(self.peticion(prompt)))

    def error_de_red(self, error: OSError) -> IANoDisponible:
        """Por qué no se llega a Gemini, con el motivo de verdad al final (no siempre es que
        no haya internet: un antivirus que revisa HTTPS, un certificado, que tarde mucho…)."""
        tipo, motivo = self.motivo_de_red(error)
        if tipo == "certificado":
            return IANoDisponible(
                "No se puede comprobar el certificado de Gemini (HTTPS). Suele ser un antivirus o "
                "un proxy que revisa las conexiones seguras, o la fecha del PC mal puesta. "
                f"Detalle: {motivo}"
            )
        if tipo == "espera":
            return IANoDisponible(
                f"Gemini no ha contestado en {self.ESPERA} segundos. Prueba otra vez en un rato"
                + (f" o quita {ENV_MODELO} del .env para usar el rápido ({MODELO_POR_DEFECTO})."
                   if self.modelo != MODELO_POR_DEFECTO else ".")
            )
        return IANoDisponible(
            "No hay conexión con Gemini: ¿tienes internet? Las acciones sin IA funcionan igual; "
            f"vuelve a probar cuando tengas red (navaja comprobar-ia). Detalle: {motivo}"
        )

    def error_http(self, codigo: int, mensaje: str) -> IANoDisponible | RespuestaIARara:
        """Cada error de Google, en castellano y con qué hacer. Sin ``mensaje`` (el cuerpo no
        es el JSON de Google), quien contesta no es Gemini: un proxy o el cortafuegos de la red
        (el del instituto, por ejemplo)."""
        if codigo in (401, 403, 407) and not mensaje:
            return IANoDisponible(
                f"La red no deja llegar a Gemini (error {codigo}: un proxy o cortafuegos lo "
                "bloquea). Prueba desde otra red; las acciones sin IA funcionan igual."
            )
        if (codigo == 400 and "api key" in mensaje.lower()) or codigo in (401, 403):
            return IANoDisponible(
                f"Gemini no acepta la clave ({ENV_CLAVE}): ¿está bien copiada? Saca otra en "
                f"{DONDE_SACAR_CLAVE}."
            )
        if codigo == 404:
            return IANoDisponible(
                f"El modelo «{self.modelo}» no existe en Gemini. Quita {ENV_MODELO} del .env "
                f"para usar el de siempre ({MODELO_POR_DEFECTO})."
            )
        if codigo == 429:
            return IANoDisponible(
                "Se ha gastado el cupo gratis de Gemini por ahora (demasiadas peticiones seguidas "
                "o por hoy). Espera un poco y vuelve a probar."
            )
        if codigo >= 500:
            return IANoDisponible(f"Gemini no funciona bien ahora mismo (error {codigo}). Prueba más tarde.")
        detalle = f": {mensaje}" if mensaje else ""
        return RespuestaIARara(f"Gemini no ha aceptado la petición (error {codigo}){detalle}")

    @staticmethod
    def texto_de(datos: Any) -> str:
        """El texto de la respuesta (sin las partes de «pensar»). ``RespuestaIARara`` si
        Google la ha bloqueado o no trae nada."""
        candidatos = datos.get("candidates") if isinstance(datos, dict) else None
        if not candidatos:
            motivo = (datos.get("promptFeedback") or {}).get("blockReason") if isinstance(datos, dict) else None
            if motivo:
                raise RespuestaIARara(f"Gemini no ha querido contestar (bloqueado: {motivo}).")
            raise RespuestaIARara("Gemini no ha devuelto ninguna respuesta.")
        partes = (candidatos[0].get("content") or {}).get("parts") or []
        texto = "".join(
            parte.get("text", "") for parte in partes if isinstance(parte, dict) and not parte.get("thought")
        )
        if not texto.strip():
            motivo = candidatos[0].get("finishReason", "")
            extra = f" ({motivo})" if motivo and motivo != "STOP" else ""
            raise RespuestaIARara(f"Gemini ha contestado en blanco{extra}.")
        return texto


class Servidor(ProveedorIA):
    """Un servidor compatible con la API de OpenAI (``POST …/chat/completions``): Ollama
    (``http://localhost:11434/v1``), LM Studio, vLLM o el servidor de modelos del centro.

    Con ``NAVAJA_IA_URL`` en el .env se usa este en vez de Gemini; la clave
    (``NAVAJA_IA_CLAVE``) solo si el servidor la pide, y va en la cabecera
    ``Authorization``, nunca en la URL.
    """

    nombre = "el servidor de IA"
    ESPERA = 120  # un modelo en tu PC o en el del centro puede ir más despacio que Gemini

    def __init__(self, url: str, modelo: str = MODELO_SERVIDOR, clave: str = "") -> None:
        super().__init__(modelo)
        if not url.lower().startswith(("http://", "https://")):
            raise IANoDisponible(
                f"{ENV_URL} no parece una dirección: «{url}». Tiene que empezar por http:// o "
                "https://, por ejemplo http://localhost:11434/v1 para Ollama."
            )
        self.url = url.rstrip("/")
        self._clave = clave  # privada: nunca se enseña ni se escribe en ningún sitio

    def __repr__(self) -> str:
        return f"Servidor({self.url!r}, {self.modelo!r})"

    def peticion(self, prompt: str) -> urllib.request.Request:
        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "stream": False,
        }
        cabeceras = {"Content-Type": "application/json"}
        if self._clave:
            cabeceras["Authorization"] = f"Bearer {self._clave}"
        return urllib.request.Request(
            f"{self.url}/chat/completions",
            data=json.dumps(cuerpo).encode("utf-8"),
            headers=cabeceras,
            method="POST",
        )

    def _pedir(self, prompt: str) -> str:
        return self.texto_de(self.llamar(self.peticion(prompt)))

    def error_de_red(self, error: OSError) -> IANoDisponible:
        tipo, motivo = self.motivo_de_red(error)
        if tipo == "certificado":
            return IANoDisponible(
                f"No se puede comprobar el certificado HTTPS de {self.url}. Si es un servidor del "
                f"centro con certificado propio, pide la dirección con http://. Detalle: {motivo}"
            )
        if tipo == "espera":
            return IANoDisponible(
                f"El servidor de IA no ha contestado en {self.ESPERA} segundos. Puede que el modelo "
                f"«{self.modelo}» sea muy grande para ese equipo: prueba otro más pequeño con {ENV_MODELO}."
            )
        return IANoDisponible(
            f"No hay conexión con el servidor de IA ({self.url}): ¿está encendido (Ollama) o estás "
            f"en la red del centro? Las acciones sin IA funcionan igual. Detalle: {motivo}"
        )

    def error_http(self, codigo: int, mensaje: str) -> IANoDisponible | RespuestaIARara:
        detalle = f": {mensaje}" if mensaje else ""
        if codigo in (401, 403):
            return IANoDisponible(
                f"El servidor de IA no acepta la clave (error {codigo}): pon la buena en "
                f"{ENV_CLAVE_SERVIDOR} en el .env{detalle}"
            )
        if codigo == 404:
            return IANoDisponible(
                f"El servidor de IA no encuentra «{self.url}/chat/completions» o el modelo "
                f"«{self.modelo}» (error 404{detalle}). Comprueba {ENV_URL} (en Ollama acaba en /v1) "
                f"y {ENV_MODELO} (en Ollama, «ollama list» dice cuáles tienes)."
            )
        if codigo == 429:
            return IANoDisponible("El servidor de IA está saturado (demasiadas peticiones). Prueba en un rato.")
        if codigo >= 500:
            return IANoDisponible(f"El servidor de IA ha fallado (error {codigo}{detalle}). Prueba más tarde.")
        return RespuestaIARara(f"El servidor de IA no ha aceptado la petición (error {codigo}){detalle}")

    @staticmethod
    def texto_de(datos: Any) -> str:
        """El texto de ``choices[0].message.content``. ``RespuestaIARara`` si no viene."""
        try:
            texto = datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RespuestaIARara("El servidor de IA no ha devuelto ninguna respuesta.") from None
        if not isinstance(texto, str) or not texto.strip():
            raise RespuestaIARara("El servidor de IA ha contestado en blanco.")
        # algunos modelos (deepseek-r1, qwen3…) «piensan» en voz alta entre <think> y </think>
        if "</think>" in texto:
            texto = texto.split("</think>", 1)[1]
        return texto
