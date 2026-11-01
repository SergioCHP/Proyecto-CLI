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

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from .comandos import ordena, renombra
from .comun import carpeta_papelera, cuantos, destino_libre, ruta_libre
from .errores import AccionNoValida
from .filtros import sin_tildes


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

    def ejecutar(self, plan: list[Resultado]) -> list[Resultado]:
        """Hace lo pendiente del plan; cada archivo acaba «hecho» o «fallo»."""
        for resultado in plan:
            if resultado.estado != "pendiente":
                continue
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


def misma_copia(original: Path, copia: Path) -> bool:
    """Mismo tamaño y misma fecha (la copia conserva la fecha): ya está copiado."""
    try:
        a, b = original.stat(), copia.stat()
    except OSError:
        return False
    return a.st_size == b.st_size and abs(a.st_mtime - b.st_mtime) <= 2


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
    explicacion = "Copia los archivos a otra carpeta; el original se queda donde está."
    verbo = "Copiar"
    participio = ("copiado", "copiados")
    para = "para copiar"
    columna = "Copia en"
    como = "copiado"

    def planificar(self, archivos: list[Path], carpeta: Path) -> list[Resultado]:
        base = self.base(carpeta)
        reservados: set[str] = set()
        plan = []
        for archivo in archivos:
            deseado = base / relativa(archivo, carpeta)
            if deseado == archivo:
                continue
            if misma_copia(archivo, deseado):  # la segunda vez no se copia otra vez
                plan.append(Resultado(archivo, deseado, "saltado", "ya está copiado"))
                continue
            plan.append(Resultado(archivo, destino_libre(deseado, reservados)))
        return plan

    def aplicar(self, resultado: Resultado) -> None:
        assert resultado.destino is not None
        if resultado.destino.exists():
            resultado.destino = ruta_libre(resultado.destino)
        resultado.destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resultado.origen, resultado.destino)  # copy2 conserva la fecha


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

    def ejecutar(self, plan: list[Resultado]) -> list[Resultado]:
        # una carpeta por vez, como hace «duplicados borrar»
        self._papelera = carpeta_papelera() / datetime.now().strftime("%Y%m%d-%H%M%S")
        return super().ejecutar(plan)

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
