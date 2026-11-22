"""Las acciones de acciones.json: una clase por tipo.

``Accion`` es la base de todas: nombre, descripción, el registro de tipos y la
fábrica ``desde_config``, que convierte un diccionario del JSON en el objeto de la
clase que toca. Cada subclase se apunta sola en el registro al definirse, así que
añadir un tipo nuevo es escribir una subclase más: ni el motor ni la validación
tienen un ``if tipo == …``.

Las que tocan archivos (``AccionDeArchivos``) siguen el mismo camino que ordena y
renombra: ``planificar`` calcula qué le pasaría a cada archivo sin tocar nada (eso
es lo que enseña --simular) y ``ejecutar`` lo hace de verdad. ``Rutina`` no toca
archivos: encadena otras acciones.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from .comandos import cuenta, ordena, renombra
from .comun import (
    carpeta_papelera, crear_carpetas, cuantos, destino_libre, hora_dudosa, mover_seguro, poner_solo_lectura,
    quitar_solo_lectura, quitar_vacias, ruta_libre,
)
from .errores import AccionNoValida, IANoDisponible, NavajaError, RespuestaIARara
from .filtros import sin_tildes
from .proveedor_ia import ProveedorIA
from .versiones import Version, apuntar, carpeta_versiones


Avance = Callable[[Path], None]
"""Aviso que ``ejecutar`` da antes de cada archivo, con su ruta: la barra de progreso de
``acciones ejecutar`` se cuelga de aquí sin que las acciones sepan nada de la pantalla."""


@dataclass
class Resultado:
    """Lo que le pasa (o le pasaría) a un archivo.

    ``estado``: «pendiente» (está en el plan), «saltado» (no se toca; ``motivo`` dice
    por qué), y después de ejecutar, «hecho» o «fallo».
    """

    origen: Path
    destino: Path | None
    estado: str = "pendiente"
    motivo: str = ""
    sustituir: bool = False
    """Copiar con «el-mas-nuevo»: el destino existe y es más viejo; se aparta y se copia."""
    apartado: Path | None = None
    """Dónde quedó (en «versiones» de los datos de navaja) la versión vieja sustituida."""
    creadas: list[Path] = field(default_factory=list)
    """Las carpetas que no existían y se crearon para este archivo (las únicas que deshacer quita)."""
    sin_guardar: bool = False
    """Sustituyó a la versión vieja sin guardarla (``guardar_viejas: false``): no hay vuelta atrás."""


def relativa(archivo: Path, carpeta: Path) -> Path:
    """La ruta del archivo desde la carpeta (solo el nombre si está fuera)."""
    try:
        return archivo.relative_to(carpeta)
    except ValueError:
        return Path(archivo.name)


class Accion(ABC):
    """Lo que tienen todas las acciones: nombre, descripción y tipo."""

    tipo: ClassVar[str] = ""
    explicacion: ClassVar[str] = ""
    """Qué hace este tipo, para «acciones ver», el manual y los errores."""
    campos: ClassVar[dict[str, bool]] = {}
    """Campos propios de este tipo → si son obligatorios."""
    usa_archivos: ClassVar[bool] = False
    """Si lleva «carpeta» y «filtro»."""
    usa_ia: ClassVar[bool] = False
    """Si necesita la IA (Gemini con su clave, o un servidor compatible con OpenAI)."""

    _registro: ClassVar[dict[str, type[Accion]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.tipo:  # las clases intermedias (sin tipo) no se apuntan
            Accion._registro[cls.tipo] = cls

    def __init__(self, datos: dict[str, Any]) -> None:
        self.datos = datos
        self.nombre: str = datos["nombre"]
        self.descripcion: str = datos["descripcion"]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.nombre!r})"

    # ── Registro y fábrica ─────────────────────────────────────────────────

    @staticmethod
    def tipos() -> dict[str, type[Accion]]:
        """Los tipos que existen, en el orden en que se definieron."""
        return dict(Accion._registro)

    @staticmethod
    def desde_config(datos: dict[str, Any]) -> Accion:
        """Fábrica: del diccionario del JSON al objeto de la clase que toca."""
        clase = Accion._registro.get(datos.get("tipo", ""))
        if clase is None:
            raise AccionNoValida(
                datos.get("nombre", "?"), "tipo", "no hay ninguna clase para ese tipo"
            )
        return clase(datos)

    # ── Validación de lo propio de cada tipo ───────────────────────────────

    @classmethod
    def comprobar(cls, datos: dict[str, Any]) -> None:
        """Comprueba los campos propios del tipo (los comunes los mira ``esquema``).

        Lanza ``AccionNoValida`` diciendo qué campo falla y por qué.
        """
        for campo, obligatorio in cls.campos.items():
            if obligatorio and campo not in datos:
                raise AccionNoValida(
                    datos["nombre"], campo, f"es obligatorio en acciones de tipo {cls.tipo}"
                )
        cls.comprobar_valores(datos)

    @classmethod
    def comprobar_valores(cls, datos: dict[str, Any]) -> None:
        """Lo que cada tipo quiera mirar además (valores permitidos, plantillas…)."""


class AccionDeArchivos(Accion):
    """Una acción que elige archivos de una carpeta y hace algo con cada uno."""

    usa_archivos = True
    destructiva: ClassVar[bool] = False
    verbo: ClassVar[str] = "Tocar"
    participio: ClassVar[tuple[str, str]] = ("tocado", "tocados")
    columna: ClassVar[str] = "Va a"
    para: ClassVar[str] = "para tocar"
    """Lo que se dice en el plan: «3 archivos para mover»."""
    como: ClassVar[str] = "movido"
    """Cómo se deshace: «movido» (se devuelve a su sitio) o «copiado» (se quita la copia)."""

    def __init__(self, datos: dict[str, Any]) -> None:
        super().__init__(datos)
        carpeta = datos.get("carpeta")
        self.carpeta: Path | None = Path(carpeta).expanduser() if carpeta else None
        self.filtro: dict[str, Any] = datos.get("filtro", {})

    @staticmethod
    def ruta(texto: str, carpeta: Path) -> Path:
        """Ruta de un campo: ``~`` es tu carpeta personal y una relativa se cuenta
        desde la carpeta de la acción."""
        ruta = Path(texto).expanduser()
        return ruta if ruta.is_absolute() else carpeta / ruta

    def excluir(self, carpeta: Path) -> Path | None:
        """Carpeta cuyos archivos no se eligen (el destino, si está dentro de la carpeta),
        para no volver a coger lo que ya se movió allí."""
        return None

    def comprobar_destino(self, carpeta: Path) -> None:
        """Antes del plan: ``NavajaError`` si el destino no puede existir (una unidad que
        no está, como un USB sin conectar)."""

    def destino_comun(self, carpeta: Path) -> Path | None:
        """La carpeta a la que va todo, si es una sola (para no repetirla en cada fila del plan)."""
        return None

    def con_destino(self, destino: Path) -> AccionDeArchivos:
        """La misma acción, pero llevando los archivos a ``destino`` («--destino» al
        ejecutar). ``NavajaError`` si este tipo no lleva destino."""
        if "destino" not in self.campos:
            raise NavajaError(
                f"La acción «{self.nombre}» es de tipo {self.tipo}, que no lleva destino: "
                "--destino no vale con ella."
            )
        return type(self)({**self.datos, "destino": str(destino)})

    def pregunta(self, n: int) -> str:
        return f"¿{self.verbo} {cuantos(n, 'archivo')}?"

    def hecho(self, n: int) -> str:
        return f"{cuantos(n, 'archivo')} {self.participio[0] if n == 1 else self.participio[1]}"

    @abstractmethod
    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        """Qué le pasaría a cada archivo. No toca el disco (ni crea carpetas)."""

    @abstractmethod
    def aplicar(self, resultado: Resultado) -> None:
        """Lo hace con un archivo. Lanza ``OSError`` si no puede."""

    def ejecutar(self, plan: list[Resultado], avance: Avance | None = None) -> list[Resultado]:
        """Hace lo pendiente del plan; cada archivo acaba «hecho» o «fallo».

        ``avance``, si se da, se llama con el origen justo antes de cada archivo.
        """
        for resultado in plan:
            if resultado.estado != "pendiente":
                continue
            if avance is not None:
                avance(resultado.origen)
            try:
                self.aplicar(resultado)
                resultado.estado = "hecho"
            except OSError as exc:
                resultado.estado, resultado.motivo = "fallo", exc.strerror or str(exc)
                # la carpeta que creó para él no se queda vacía (y sin apuntar): el siguiente
                # archivo la vuelve a crear y la apunta él
                quitar_vacias(resultado.creadas)
                resultado.creadas = []
            except BaseException:  # Ctrl+C: este archivo no se apunta, su carpeta tampoco
                quitar_vacias(resultado.creadas)
                raise
        return plan

    def para_deshacer(self, resultado: Resultado) -> dict[str, Any]:
        return {
            "origen": str(resultado.origen), "destino": str(resultado.destino), "como": self.como,
            "creadas": [str(c) for c in resultado.creadas],  # siempre, aunque vacía: ver carpetas_creadas
        }


def mover(resultado: Resultado) -> None:
    """Mueve sin sobrescribir nunca: si el destino ha aparecido después del plan, «(1)»."""
    assert resultado.destino is not None
    if resultado.destino.exists():
        resultado.destino = ruta_libre(resultado.destino)
    resultado.creadas = crear_carpetas(resultado.destino.parent)
    mover_seguro(resultado.origen, resultado.destino)  # a otra unidad, nunca a medias


TOLERANCIA = 2
"""Segundos de diferencia que no cuentan: FAT32 (muchos USB) guarda la hora de 2 en 2 s."""


def misma_copia(original: Path, copia: Path, dudosa: bool = True) -> bool:
    """Mismo tamaño y misma fecha (la copia conserva la fecha): ya está copiado.

    Con ``dudosa`` (algún lado en un USB FAT32, o no se sabe: ver ``hora_dudosa``), una hora
    justa de diferencia también cuenta como la misma fecha: tras el cambio de hora Windows ve
    todo lo del USB movido una hora. Entre dos discos NTFS, no: serían archivos distintos.
    """
    try:
        a, b = original.stat(), copia.stat()
    except OSError:
        return False
    diferencia = abs(a.st_mtime - b.st_mtime)
    return a.st_size == b.st_size and (
        diferencia <= TOLERANCIA or (dudosa and abs(diferencia - 3600) <= TOLERANCIA)
    )


def copia_igual_al_lado(original: Path, deseado: Path, dudosa: bool = True) -> Path | None:
    """Una «nombre (n).ext» junto a ``deseado`` que ya es copia de ``original``: así la
    segunda vez no se hace otra «(n)» con lo mismo."""
    indice = 1
    while True:
        candidato = deseado.with_name(f"{deseado.stem} ({indice}){deseado.suffix}")
        if not candidato.exists():
            return None
        if misma_copia(original, candidato, dudosa):
            return candidato
        indice += 1


def apartar(archivo: Path, papelera: Path) -> Path:
    """Lleva ``archivo`` a ``papelera`` (una carpeta de navaja) sin pisar nada y dice dónde
    ha quedado.

    Con ``mover_seguro``: de un USB a C: (copiar y borrar) también con el «solo lectura» (en
    Windows no se dejaba borrar y la copia entera fallaba), y si algo falla a medias no deja
    una copia suelta aquí (sin apuntar en el índice, nunca caducaría). Ni pisa nada: si el
    destino apareciera justo ahora, falla sin tocarlo.
    """
    papelera.mkdir(parents=True, exist_ok=True)
    destino = ruta_libre(papelera / archivo.name)
    mover_seguro(archivo, destino)
    return destino


# ── Los tipos ──────────────────────────────────────────────────────────────


class Mover(AccionDeArchivos):
    tipo = "mover"
    explicacion = "Lleva los archivos a otra carpeta (destino)."
    campos = {"destino": True}
    verbo = "Mover"
    participio = ("movido", "movidos")
    para = "para mover"

    def base(self, carpeta: Path) -> Path:
        return self.ruta(self.datos["destino"], carpeta)

    def excluir(self, carpeta: Path) -> Path | None:
        return self.base(carpeta)

    def destino_comun(self, carpeta: Path) -> Path | None:
        return self.base(carpeta)

    def comprobar_destino(self, carpeta: Path) -> None:
        unidad = self.base(carpeta).anchor  # «D:\» en Windows; «/» en Linux y macOS
        if unidad and not Path(unidad).exists():
            raise NavajaError(
                f"El destino {self.datos['destino']} está en una unidad que no existe ahora "
                f"mismo ({unidad.rstrip('/\\')}) (acción «{self.nombre}»). "
                "¿Está conectado el USB? Si ahora tiene otra letra, dásela al ejecutar: "
                "--destino E:/DAM."
            )

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        base = self.base(carpeta)
        reservados: set[str] = set()
        plan = []
        for archivo in archivos:
            deseado = base / relativa(archivo, carpeta)  # con -r, conserva las subcarpetas
            if deseado == archivo:
                continue
            plan.append(Resultado(archivo, destino_libre(deseado, reservados)))
        return plan

    def aplicar(self, resultado: Resultado) -> None:
        mover(resultado)


class Copiar(Mover):
    tipo = "copiar"
    explicacion = (
        "Copia los archivos a otra carpeta; el original se queda donde está. Si allí ya "
        "hay uno distinto con el mismo nombre, «si_cambia» decide: copia-aparte o el-mas-nuevo."
    )
    campos = {"destino": True, "si_cambia": False, "guardar_viejas": False}
    verbo = "Copiar"
    participio = ("copiado", "copiados")
    para = "para copiar"
    columna = "Copia en"
    como = "copiado"

    SI_CAMBIA = ("copia-aparte", "el-mas-nuevo")

    def __init__(self, datos: dict[str, Any]) -> None:
        super().__init__(datos)
        self._versiones: Path | None = None

    @classmethod
    def comprobar_valores(cls, datos: dict[str, Any]) -> None:
        si_cambia = datos.get("si_cambia", "copia-aparte")
        if si_cambia not in cls.SI_CAMBIA:
            raise AccionNoValida(
                datos["nombre"], "si_cambia",
                f"«{si_cambia}» no vale; usa copia-aparte (guarda «nombre (1)» al lado) o "
                "el-mas-nuevo (se queda la versión más reciente)",
            )
        if "guardar_viejas" in datos:
            if not isinstance(datos["guardar_viejas"], bool):
                raise AccionNoValida(
                    datos["nombre"], "guardar_viejas",
                    "tiene que ser true (guarda la versión vieja, por defecto) o false (no la guarda)",
                )
            if si_cambia != "el-mas-nuevo":
                raise AccionNoValida(
                    datos["nombre"], "guardar_viejas",
                    "solo se usa con «si_cambia»: «el-mas-nuevo» (con copia-aparte no se sustituye nada)",
                )

    @property
    def guardar_viejas(self) -> bool:
        return self.datos.get("guardar_viejas", True)

    @staticmethod
    def cual_gana(archivo: Path, deseado: Path, dudosa: bool = True) -> Resultado:
        """«el-mas-nuevo» y allí hay otro distinto: si el de aquí es más reciente, lo
        sustituye; si no, no se toca.

        Con ``dudosa`` (un USB FAT32 de por medio), las fechas pueden ir movidas una hora:
        con menos de una hora de diferencia no se sabe cuál es más nuevo, y antes podía
        ganar el viejo. Entonces no se toca y se dice: míralo tú.
        """
        try:
            aqui, alli = archivo.stat().st_mtime, deseado.stat().st_mtime
        except OSError:
            return Resultado(archivo, deseado, "saltado", "no puedo leer su fecha")
        diferencia = abs(aqui - alli)
        if diferencia <= TOLERANCIA:
            return Resultado(archivo, deseado, "saltado", "distinto pero con la misma fecha: míralo tú")
        if dudosa and diferencia <= 3600 + TOLERANCIA:
            return Resultado(
                archivo, deseado, "saltado",
                "distinto y con menos de una hora de diferencia; en un USB la hora puede ir "
                "movida por el cambio de hora: míralo tú",
            )
        if aqui > alli:
            return Resultado(archivo, deseado, sustituir=True)
        return Resultado(archivo, deseado, "saltado", "allí hay una versión más nueva")

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        base = self.base(carpeta)
        el_mas_nuevo = self.datos.get("si_cambia") == "el-mas-nuevo"
        dudosa = hora_dudosa(carpeta, base)  # una vez por carpeta, no por archivo
        reservados: set[str] = set()
        plan = []
        for archivo in archivos:
            deseado = base / relativa(archivo, carpeta)
            if deseado == archivo:
                continue
            if misma_copia(archivo, deseado, dudosa):  # la segunda vez no se copia otra vez
                plan.append(Resultado(archivo, deseado, "saltado", "ya está copiado"))
                continue
            if el_mas_nuevo and deseado.is_file():
                plan.append(self.cual_gana(archivo, deseado, dudosa))
                continue
            igual = copia_igual_al_lado(archivo, deseado, dudosa)
            if igual is not None:
                plan.append(Resultado(archivo, igual, "saltado", f"ya está copiado como «{igual.name}»"))
                continue
            plan.append(Resultado(archivo, destino_libre(deseado, reservados)))
        return plan

    def ejecutar(self, plan: list[Resultado], avance: Avance | None = None) -> list[Resultado]:
        # las versiones viejas que se sustituyan van juntas a una carpeta con fecha de
        # «versiones» (no a la papelera común: así «duplicados vaciar» no las borra)
        cuando = datetime.now()
        self._versiones = carpeta_versiones() / cuando.strftime("%Y%m%d-%H%M%S")
        try:
            super().ejecutar(plan, avance)
        finally:
            # también con Ctrl+C a medias, y las de un fallo que no se pudieron devolver:
            # así «acciones versiones» las lista y se recuperan. Si el índice no se puede
            # escribir, no para nada: «acciones versiones» las encuentra igual en la carpeta
            # (sin saber de dónde salieron), así que no se pierden.
            with contextlib.suppress(OSError):
                apuntar([
                    Version(r.apartado, r.destino, self.nombre, cuando)
                    for r in plan
                    if r.apartado is not None and r.destino is not None
                ])
        return plan

    def aplicar(self, resultado: Resultado) -> None:
        """Copia a un temporal oculto junto al destino y, solo cuando está entero, le pone
        el nombre bueno: si el USB se llena o se desconecta a medias, en el destino no
        queda un archivo roto con fecha de ahora (que «el-mas-nuevo» tomaría por bueno)."""
        assert resultado.destino is not None
        if not resultado.sustituir and resultado.destino.exists():
            resultado.destino = ruta_libre(resultado.destino)
        destino = resultado.destino
        resultado.creadas = crear_carpetas(destino.parent)
        temporal = destino.with_name(f".{destino.name}.navaja-copiando")
        destino_era_solo_lectura = False
        try:
            shutil.copy2(resultado.origen, temporal)  # copy2 conserva la fecha
            if resultado.sustituir and destino.exists():
                if self.guardar_viejas:
                    assert self._versiones is not None
                    resultado.apartado = apartar(destino, self._versiones)
                else:  # os.replace la sustituye de golpe; de solo lectura, no se deja
                    destino_era_solo_lectura = quitar_solo_lectura(destino)
                    resultado.sin_guardar = True
            os.replace(temporal, destino)
        except BaseException as error:  # también Ctrl+C: que no quede el temporal
            if resultado.sin_guardar and destino_era_solo_lectura:
                poner_solo_lectura(destino)  # la vieja sigue ahí: tal como estaba
            resultado.sin_guardar = False  # si falla, la vieja sigue ahí
            quitar_solo_lectura(temporal)  # el original era de solo lectura: el temporal también
            with contextlib.suppress(OSError):
                temporal.unlink(missing_ok=True)
            if isinstance(error, OSError):
                self.devolver_apartado(resultado)
            else:
                # Con Ctrl+C se corta igual: si la vieja no se puede devolver, se queda
                # apartada (y apuntada en «versiones»), y un OSError aquí taparía el corte
                with contextlib.suppress(OSError):
                    self.devolver_apartado(resultado)
            raise

    @staticmethod
    def devolver_apartado(resultado: Resultado) -> None:
        """Tras un fallo, deja la versión vieja donde estaba. Si ni eso se puede, el error
        dice dónde ha quedado (y «acciones versiones» la lista), para que no se pierda."""
        apartado = resultado.apartado
        if apartado is None:
            return
        assert resultado.destino is not None
        try:
            mover_seguro(apartado, resultado.destino)  # nunca pisa ni deja a medias
        except OSError as exc:
            raise OSError(
                exc.errno,
                f"no se pudo copiar ni devolver la versión vieja: está en {apartado}",
            ) from None
        resultado.apartado = None

    def para_deshacer(self, resultado: Resultado) -> dict[str, Any]:
        registro = super().para_deshacer(resultado)
        if resultado.apartado is not None:
            registro["apartado"] = str(resultado.apartado)
        if resultado.sin_guardar:
            registro["sin_guardar"] = True  # deshacer no la quita: dejaría el sitio vacío
        return registro


class Ordenar(AccionDeArchivos):
    tipo = "ordenar"
    explicacion = (
        "Mete cada archivo en una subcarpeta según «por»: tipo (Imagenes, Documentos…), "
        "mes, año, día o letra. Como «ordena»."
    )
    campos = {"por": True, "destino": False}
    verbo = "Mover"
    participio = ("ordenado", "ordenados")
    para = "para ordenar"

    POR = {"tipo", "mes", "año", "dia", "letra"}

    @staticmethod
    def normalizar(por: str) -> str:
        """«Día», «dia» y «día» son lo mismo; «ano» es «año»."""
        limpio = sin_tildes(str(por).strip().lower())
        return {"ano": "año"}.get(limpio, limpio)

    @classmethod
    def comprobar_valores(cls, datos: dict[str, Any]) -> None:
        if not isinstance(datos["por"], str) or cls.normalizar(datos["por"]) not in cls.POR:
            raise AccionNoValida(
                datos["nombre"], "por", f"«{datos['por']}» no vale; usa tipo, mes, año, día o letra"
            )

    def base(self, carpeta: Path) -> Path:
        destino = self.datos.get("destino")
        return self.ruta(destino, carpeta) if destino else carpeta

    def excluir(self, carpeta: Path) -> Path | None:
        return self.base(carpeta) if self.datos.get("destino") else None

    def carpeta_de(self) -> ordena.Carpeta:
        por = self.normalizar(self.datos["por"])
        if por == "tipo":
            return ordena.carpeta_por_tipo
        if por == "letra":
            return ordena.carpeta_por_letra
        return ordena.carpeta_por_fecha(
            {"mes": ordena.Agrupar.mes, "año": ordena.Agrupar.año, "dia": ordena.Agrupar.día}[por]
        )

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        movimientos = ordena.planificar(archivos, self.base(carpeta), self.carpeta_de())
        return [Resultado(Path(m["origen"]), Path(m["destino"])) for m in movimientos]

    def aplicar(self, resultado: Resultado) -> None:
        mover(resultado)


class Renombrar(AccionDeArchivos):
    tipo = "renombrar"
    explicacion = (
        "Cambia el nombre de cada archivo según una «plantilla» con huecos: "
        "{fecha:%Y-%m-%d}, {n:03}, {nombre} y {ext}. Como «renombra plantilla»."
    )
    campos = {"plantilla": True, "orden": False}
    verbo = "Renombrar"
    participio = ("renombrado", "renombrados")
    para = "para renombrar"
    columna = "Nombre nuevo"

    @classmethod
    def comprobar_valores(cls, datos: dict[str, Any]) -> None:
        nombre, plantilla = datos["nombre"], datos["plantilla"]
        if not isinstance(plantilla, str) or not plantilla.strip():
            raise AccionNoValida(nombre, "plantilla", "tiene que ser un texto con huecos")
        try:
            ejemplo = plantilla.format(
                fecha=datetime(2026, 10, 26, 18, 30), n=1, ext=".jpg", nombre="IMG_1234"
            )
        except KeyError as exc:
            raise AccionNoValida(
                nombre, "plantilla",
                f"el hueco {{{exc.args[0]}}} no existe; usa {renombra.HUECOS}",
            ) from None
        except (ValueError, IndexError, AttributeError) as exc:
            raise AccionNoValida(nombre, "plantilla", f"no es válida ({exc})") from None
        if not renombra.nombre_valido(ejemplo) or Path(ejemplo).name != ejemplo:
            raise AccionNoValida(
                nombre, "plantilla",
                f"saldrían nombres como «{ejemplo}», que no valen: {renombra.motivo_invalido(ejemplo)}",
            )
        if not Path(ejemplo).suffix:
            raise AccionNoValida(
                nombre, "plantilla", "los archivos perderían la extensión: añade {ext} al final"
            )
        orden = datos.get("orden", "nombre")
        if orden not in ("nombre", "fecha"):
            raise AccionNoValida(nombre, "orden", f"«{orden}» no vale; usa nombre o fecha")

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        plantilla = self.datos["plantilla"]
        orden = renombra.Orden(self.datos.get("orden", "nombre"))
        movimientos = renombra.planificar(
            renombra.ordenados(archivos, orden),
            lambda archivo, n: renombra.formatear_plantilla(plantilla, archivo, n),
        )
        plan = []
        for m in movimientos:
            if m["estado"] == "igual":
                continue  # ya se llama así
            estado = "pendiente" if m["estado"] == "ok" else "saltado"
            plan.append(Resultado(Path(m["origen"]), Path(m["destino"]), estado, m["motivo"]))
        return plan

    def aplicar(self, resultado: Resultado) -> None:
        cambiar_nombre(resultado)


def cambiar_nombre(resultado: Resultado) -> None:
    """Le pone el nombre nuevo sin pisar nunca otro archivo (sí deja cambiar solo mayúsculas)."""
    assert resultado.destino is not None
    origen, destino = resultado.origen, resultado.destino
    solo_mayusculas = str(origen).lower() == str(destino).lower()
    if destino.exists() and not (solo_mayusculas and destino.samefile(origen)):
        raise FileExistsError(17, "ya existe un archivo con ese nombre")
    origen.rename(destino)


class Borrar(AccionDeArchivos):
    tipo = "borrar"
    explicacion = (
        "Manda los archivos a la papelera de navaja (se recuperan con «acciones deshacer»). "
        "Necesita un filtro."
    )
    destructiva = True
    verbo = "Mandar"
    participio = ("a la papelera", "a la papelera")
    para = "para la papelera de navaja"

    def __init__(self, datos: dict[str, Any]) -> None:
        super().__init__(datos)
        self._papelera: Path | None = None

    @classmethod
    def comprobar_valores(cls, datos: dict[str, Any]) -> None:
        if not datos.get("filtro"):
            raise AccionNoValida(
                datos["nombre"], "filtro",
                "una acción de borrar necesita un filtro; sin él mandaría a la papelera "
                "toda la carpeta",
            )

    def pregunta(self, n: int) -> str:
        return f"¿Mandar {cuantos(n, 'archivo')} a la papelera de navaja?"

    def hecho(self, n: int) -> str:
        return f"{cuantos(n, 'archivo')} a la papelera de navaja"

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        return [Resultado(archivo, None) for archivo in archivos]

    def ejecutar(self, plan: list[Resultado], avance: Avance | None = None) -> list[Resultado]:
        # una carpeta por vez, como hace «duplicados borrar»
        self._papelera = carpeta_papelera() / datetime.now().strftime("%Y%m%d-%H%M%S")
        return super().ejecutar(plan, avance)

    def aplicar(self, resultado: Resultado) -> None:
        assert self._papelera is not None
        resultado.creadas = crear_carpetas(self._papelera)  # la de esta vez: deshacer la quita vacía
        resultado.destino = ruta_libre(self._papelera / resultado.origen.name)
        mover_seguro(resultado.origen, resultado.destino)  # desde un USB, la papelera está en C:


class Rutina(Accion):
    tipo = "rutina"
    explicacion = "Hace varias acciones seguidas, en orden («pasos»)."
    campos = {"pasos": True}

    @classmethod
    def comprobar_valores(cls, datos: dict[str, Any]) -> None:
        pasos = datos["pasos"]
        if (
            not isinstance(pasos, list)
            or not pasos
            or not all(isinstance(p, str) and p.strip() for p in pasos)
        ):
            raise AccionNoValida(
                datos["nombre"], "pasos",
                'tiene que ser una lista de nombres de acciones: ["ordenar-descargas", "…"]',
            )

    @property
    def pasos(self) -> list[str]:
        return list(self.datos["pasos"])


# ── Los tipos con IA ───────────────────────────────────────────────────────


def limpiar_nombre(respuesta: str) -> str:
    """De lo que contesta la IA a un nombre de archivo que vale en Windows, Linux y macOS:
    «"Factura Movistar – octubre 2026.pdf"» → «factura-movistar-octubre-2026».

    Minúsculas, sin tildes, palabras con guiones y como mucho 60 letras (cortando entre
    palabras). ``RespuestaIARara`` si no queda nada.
    """
    linea = next((l for l in respuesta.splitlines() if l.strip()), "")
    linea = linea.strip().strip("`\"'«»“”*").strip()
    linea = linea.split(":", 1)[1] if linea.lower().startswith("nombre:") else linea
    base = Path(linea).stem if Path(linea).suffix.lower() in cuenta.LEIBLES else linea
    texto = sin_tildes(base).lower()
    palabras = [p for p in "".join(c if c.isalnum() else " " for c in texto).split() if p.isascii()]
    nombre = ""
    for palabra in palabras:
        siguiente = f"{nombre}-{palabra}" if nombre else palabra
        if len(siguiente) > 60:
            break
        nombre = siguiente
    if not nombre:
        raise RespuestaIARara(f"la IA no ha propuesto un nombre que sirva («{respuesta.strip()[:40]}»)")
    return nombre


class AccionConIA(AccionDeArchivos):
    """Una acción que le pide algo a la IA por cada archivo.

    El proveedor (Gemini o un servidor) se pide la primera vez que hace falta, así que «acciones ver» y
    «validar» funcionan sin clave. Si la IA deja de estar disponible a medias (se va
    internet, se acaba el cupo), no se le vuelve a preguntar: lo que queda sale como «sin
    IA» y lo ya hecho se queda hecho (y se puede deshacer).
    """

    usa_ia = True
    MAXIMO_TEXTO: ClassVar[int] = 12000
    """Letras del documento que se le mandan como mucho (el principio, que es lo que más dice)."""

    def __init__(self, datos: dict[str, Any]) -> None:
        super().__init__(datos)
        self._proveedor: ProveedorIA | None = None
        self._sin_ia = ""
        """Por qué ya no se puede usar la IA en esta ejecución (vacío si se puede)."""

    @property
    def proveedor(self) -> ProveedorIA:
        """El de ``ProveedorIA.desde_entorno``. ``IANoDisponible`` si no hay clave."""
        if self._proveedor is None:
            self._proveedor = ProveedorIA.desde_entorno()
        return self._proveedor

    def asegurar_ia(self) -> None:
        """Antes del plan: si no hay clave (o la IA está apagada), ``IANoDisponible`` ya, en
        vez de un error por cada archivo."""
        self.proveedor  # noqa: B018 (pedirlo es lo que lo comprueba)

    @classmethod
    def comprobar_valores(cls, datos: dict[str, Any]) -> None:
        if "instrucciones" in datos:
            instrucciones = datos["instrucciones"]
            if not isinstance(instrucciones, str) or not instrucciones.strip():
                raise AccionNoValida(
                    datos["nombre"], "instrucciones",
                    'tiene que ser un texto para la IA: "pon la asignatura delante"',
                )
            if len(instrucciones) > 500:
                raise AccionNoValida(
                    datos["nombre"], "instrucciones",
                    f"es muy larga ({len(instrucciones)} letras); como mucho 500",
                )

    @property
    def instrucciones(self) -> str:
        extra = self.datos.get("instrucciones", "").strip()
        return f"\nAdemás: {extra}" if extra else ""

    def texto(self, archivo: Path) -> str:
        """El texto del documento (el principio). ``NavajaError`` si no se sabe leer o está
        vacío: ese archivo se salta, sin preguntar a la IA."""
        if archivo.suffix.lower() not in cuenta.LEIBLES:
            raise NavajaError(f"no sé leer los {archivo.suffix.lower() or 'archivos sin extensión'}")
        try:
            texto = " ".join(cuenta.texto_de(archivo).split())
        except NavajaError as error:
            raise NavajaError(str(error).rstrip(".")) from None
        except OSError as exc:
            raise NavajaError(f"no se puede leer: {exc.strerror or exc}") from None
        if len(texto) < 20:
            raise NavajaError("no tiene texto (¿un PDF escaneado?)")
        return texto[: self.MAXIMO_TEXTO]

    def pedir(self, instrucciones: str, texto: str) -> str:
        """Le pregunta a la IA; si ya se sabe que no está, ni lo intenta."""
        if self._sin_ia:  # el motivo entero ya salió con el primero
            raise IANoDisponible("sin IA: no se le ha preguntado (mira el motivo en el primero)")
        try:
            return self.proveedor.preguntar(instrucciones, texto)
        except IANoDisponible as error:
            self._sin_ia = str(error)
            raise


class RenombrarIA(AccionConIA):
    tipo = "renombrar-ia"
    explicacion = (
        "La IA lee el principio de cada documento (PDF, Word, ODT, texto) y le pone un nombre "
        "que dice lo que es: factura-movistar-octubre-2026.pdf. Necesita IA (Gemini o tu servidor)."
    )
    campos = {"instrucciones": False}
    verbo = "Renombrar"
    participio = ("renombrado", "renombrados")
    para = "para renombrar"
    columna = "Nombre nuevo"
    MAXIMO_TEXTO = 3000  # para el nombre basta con el principio

    PETICION = (
        "Propón un nombre de archivo corto que diga qué es este documento, según su contenido. "
        "En castellano, de 2 a 6 palabras, empezando por lo más importante (qué es y de qué o "
        "de quién). Si tiene una fecha clara, ponla al final como 2026-10-26 o 2026-10. "
        "Responde SOLO con el nombre, sin extensión, sin comillas y sin explicar nada."
    )

    def proponer(self, archivo: Path) -> str:
        texto = self.texto(archivo)
        peticion = f"{self.PETICION}{self.instrucciones}\nSe llama ahora: {archivo.name}"
        return limpiar_nombre(self.pedir(peticion, texto))

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        """Pregunta el nombre de cada uno (por eso tarda un poco), pero no toca nada: esto
        es lo que enseña --simular. Sin IA desde el principio, ``IANoDisponible``."""
        if archivos:
            self.asegurar_ia()
        reservados: set[str] = set()
        plan = []
        for archivo in archivos:
            try:
                nombre = self.proponer(archivo)
            except IANoDisponible as error:  # se ha ido la red o el cupo a medias
                if not any(r.estado == "pendiente" for r in plan):
                    raise  # ni uno: que lo diga y ya
                plan.append(Resultado(archivo, None, "saltado", str(error)))
                continue
            except NavajaError as error:  # no se sabe leer, o la IA contestó algo raro
                plan.append(Resultado(archivo, None, "saltado", str(error)))
                continue
            deseado = archivo.with_name(nombre + archivo.suffix.lower())
            if deseado.name.lower() == archivo.name.lower():
                continue  # ya se llama así
            plan.append(Resultado(archivo, destino_libre(deseado, reservados)))
        return plan

    def aplicar(self, resultado: Resultado) -> None:
        cambiar_nombre(resultado)


class ResumirIA(AccionConIA):
    tipo = "resumir-ia"
    explicacion = (
        "La IA lee cada documento y escribe al lado su resumen en Markdown "
        "(«tema5.resumen.md»): la idea principal y los puntos clave. El original no se toca. "
        "Necesita IA (Gemini o tu servidor)."
    )
    campos = {"destino": False, "instrucciones": False}
    verbo = "Resumir"
    participio = ("resumido", "resumidos")
    para = "para resumir"
    columna = "Resumen en"
    como = "creado"
    FINAL = ".resumen.md"

    PETICION = (
        "Resume este documento en castellano y en Markdown: un título con # que diga de qué "
        "trata, un párrafo de 2 o 3 frases con la idea principal y, después, los puntos clave "
        "en una lista (como mucho 8). No inventes nada que no esté en el texto."
    )

    def base(self, carpeta: Path) -> Path:
        destino = self.datos.get("destino")
        return self.ruta(destino, carpeta) if destino else carpeta

    def excluir(self, carpeta: Path) -> Path | None:
        return self.base(carpeta) if self.datos.get("destino") else None

    def destino_comun(self, carpeta: Path) -> Path | None:
        return self.base(carpeta) if self.datos.get("destino") else None

    def pregunta(self, n: int) -> str:
        return f"¿Resumir {cuantos(n, 'archivo')} con IA?"

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        """Dónde iría cada resumen. Aquí aún no se pregunta a la IA (eso es al hacerlo),
        pero sí se mira que haya clave. El que ya tiene resumen se salta: así la segunda
        vez solo se resume lo nuevo."""
        if archivos:
            self.asegurar_ia()
        base = self.base(carpeta)
        reservados: set[str] = set()
        plan = []
        for archivo in archivos:
            if archivo.name.lower().endswith(self.FINAL):
                continue  # un resumen no se resume
            deseado = base / relativa(archivo, carpeta).parent / f"{archivo.stem}{self.FINAL}"
            if archivo.suffix.lower() not in cuenta.LEIBLES:
                plan.append(Resultado(archivo, None, "saltado", f"no sé leer los {archivo.suffix.lower() or 'archivos sin extensión'}"))
            elif deseado.exists():
                plan.append(Resultado(archivo, deseado, "saltado", "ya tiene resumen"))
            else:
                plan.append(Resultado(archivo, destino_libre(deseado, reservados)))
        return plan

    def resumen(self, archivo: Path) -> str:
        texto = self.texto(archivo)
        respuesta = self.pedir(f"{self.PETICION}{self.instrucciones}\nDocumento: {archivo.name}", texto)
        proveedor = self.proveedor
        cuando = datetime.now().strftime("%d/%m/%Y")
        return (
            f"{respuesta.strip()}\n\n---\n\n"
            f"_Resumen de «{archivo.name}» hecho con IA ({proveedor.nombre}, {proveedor.modelo}) "
            f"el {cuando}. Puede equivocarse: compruébalo con el original._\n"
        )

    def aplicar(self, resultado: Resultado) -> None:
        """Escribe el resumen. Lo que no sale bien (no se lee, la IA no está o contesta algo
        raro) es un fallo de ese archivo, como un error del disco: los demás siguen."""
        assert resultado.destino is not None
        try:
            contenido = self.resumen(resultado.origen)
        except NavajaError as error:
            raise OSError(0, str(error).rstrip(".")) from None
        if resultado.destino.exists():
            resultado.destino = ruta_libre(resultado.destino)
        resultado.creadas = crear_carpetas(resultado.destino.parent)
        with resultado.destino.open("x", encoding="utf-8", newline="\n") as archivo:  # «x»: nunca pisa
            archivo.write(contenido)
