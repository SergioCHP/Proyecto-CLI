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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from .comandos import ordena, renombra
from .comun import carpeta_papelera, cuantos, destino_libre, ruta_libre
from .errores import AccionNoValida, NavajaError
from .filtros import sin_tildes
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
        return plan

    def para_deshacer(self, resultado: Resultado) -> dict[str, str]:
        return {"origen": str(resultado.origen), "destino": str(resultado.destino), "como": self.como}


def mover(resultado: Resultado) -> None:
    """Mueve sin sobrescribir nunca: si el destino ha aparecido después del plan, «(1)»."""
    assert resultado.destino is not None
    if resultado.destino.exists():
        resultado.destino = ruta_libre(resultado.destino)
    resultado.destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(resultado.origen), str(resultado.destino))


TOLERANCIA = 2
"""Segundos de diferencia que no cuentan: FAT32 (muchos USB) guarda la hora de 2 en 2 s."""


def misma_copia(original: Path, copia: Path) -> bool:
    """Mismo tamaño y misma fecha (la copia conserva la fecha): ya está copiado.

    Una hora justa de diferencia también cuenta como la misma fecha: FAT32 guarda la hora
    local, y tras el cambio de hora Windows ve todas las fechas del USB movidas una hora.
    """
    try:
        a, b = original.stat(), copia.stat()
    except OSError:
        return False
    diferencia = abs(a.st_mtime - b.st_mtime)
    return a.st_size == b.st_size and (
        diferencia <= TOLERANCIA or abs(diferencia - 3600) <= TOLERANCIA
    )


def copia_igual_al_lado(original: Path, deseado: Path) -> Path | None:
    """Una «nombre (n).ext» junto a ``deseado`` que ya es copia de ``original``: así la
    segunda vez no se hace otra «(n)» con lo mismo."""
    indice = 1
    while True:
        candidato = deseado.with_name(f"{deseado.stem} ({indice}){deseado.suffix}")
        if not candidato.exists():
            return None
        if misma_copia(original, candidato):
            return candidato
        indice += 1


def apartar(archivo: Path, papelera: Path) -> Path:
    """Lleva ``archivo`` a ``papelera`` (una carpeta de navaja) sin pisar nada y dice dónde
    ha quedado."""
    papelera.mkdir(parents=True, exist_ok=True)
    destino = ruta_libre(papelera / archivo.name)
    shutil.move(str(archivo), str(destino))
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
    campos = {"destino": True, "si_cambia": False}
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

    @staticmethod
    def cual_gana(archivo: Path, deseado: Path) -> Resultado:
        """«el-mas-nuevo» y allí hay otro distinto: si el de aquí es más reciente, lo
        sustituye; si no, no se toca."""
        try:
            aqui, alli = archivo.stat().st_mtime, deseado.stat().st_mtime
        except OSError:
            return Resultado(archivo, deseado, "saltado", "no puedo leer su fecha")
        if aqui > alli + TOLERANCIA:
            return Resultado(archivo, deseado, sustituir=True)
        if alli > aqui + TOLERANCIA:
            return Resultado(archivo, deseado, "saltado", "allí hay una versión más nueva")
        return Resultado(archivo, deseado, "saltado", "distinto pero con la misma fecha: míralo tú")

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        base = self.base(carpeta)
        el_mas_nuevo = self.datos.get("si_cambia") == "el-mas-nuevo"
        reservados: set[str] = set()
        plan = []
        for archivo in archivos:
            deseado = base / relativa(archivo, carpeta)
            if deseado == archivo:
                continue
            if misma_copia(archivo, deseado):  # la segunda vez no se copia otra vez
                plan.append(Resultado(archivo, deseado, "saltado", "ya está copiado"))
                continue
            if el_mas_nuevo and deseado.is_file():
                plan.append(self.cual_gana(archivo, deseado))
                continue
            igual = copia_igual_al_lado(archivo, deseado)
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
            # así «acciones versiones» las lista y se recuperan
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
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(f".{destino.name}.navaja-copiando")
        try:
            shutil.copy2(resultado.origen, temporal)  # copy2 conserva la fecha
            if resultado.sustituir and destino.exists():
                assert self._versiones is not None
                resultado.apartado = apartar(destino, self._versiones)
            os.replace(temporal, destino)
        except BaseException as error:  # también Ctrl+C: que no quede el temporal
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
            shutil.move(str(apartado), str(resultado.destino))
        except OSError as exc:
            raise OSError(
                exc.errno,
                f"no se pudo copiar ni devolver la versión vieja: está en {apartado}",
            ) from None
        resultado.apartado = None

    def para_deshacer(self, resultado: Resultado) -> dict[str, str]:
        registro = super().para_deshacer(resultado)
        if resultado.apartado is not None:
            registro["apartado"] = str(resultado.apartado)
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
        self._papelera.mkdir(parents=True, exist_ok=True)
        resultado.destino = ruta_libre(self._papelera / resultado.origen.name)
        shutil.move(str(resultado.origen), str(resultado.destino))


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
