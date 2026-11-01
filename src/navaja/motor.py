"""El motor: de las acciones de acciones.json a los archivos que tocan.

Recibe las acciones ya comprobadas (``esquema.cargar``), las convierte en objetos con
la fábrica ``Accion.desde_config`` y, para ejecutar una, elige la carpeta, selecciona
los archivos que cumplen su filtro y le pide a la acción el plan. No sabe nada de
tipos: eso es cosa de cada clase.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from .acciones import Accion, AccionDeArchivos, Resultado, Rutina
from .comandos.duplicados import a_bytes
from .comun import como_se_escribe, directorio_datos
from .errores import NavajaError
from .filtros import Filtro
from .filtros import seleccionar as seleccionar_filtro


class Motor:
    def __init__(self, acciones: list[dict[str, Any]]) -> None:
        self.acciones: dict[str, Accion] = {
            datos["nombre"]: Accion.desde_config(datos) for datos in acciones
        }

    def buscar(self, pedido: str) -> Accion:
        """Por nombre (sin mirar mayúsculas) o por su número en «acciones ver»."""
        pedido = pedido.strip()
        lista = list(self.acciones.values())
        if pedido.isdecimal() and 1 <= int(pedido) <= len(lista):
            return lista[int(pedido) - 1]
        for nombre, accion in self.acciones.items():
            if nombre.lower() == pedido.lower():
                return accion
        empiezan = [n for n in self.acciones if pedido and pedido.lower() in n]
        cerca = empiezan if len(empiezan) == 1 else difflib.get_close_matches(
            pedido.lower(), list(self.acciones), n=1
        )
        pista = f" ¿Querías decir «{cerca[0]}»?" if cerca else ""
        raise NavajaError(
            f"No hay ninguna acción «{pedido}».{pista} Míralas con: {como_se_escribe('acciones ver')}"
        )

    def pasos(self, accion: Accion) -> list[AccionDeArchivos]:
        """Lo que hay que hacer: la acción, o en una rutina, cada una de sus acciones."""
        if isinstance(accion, Rutina):
            return [self.acciones[nombre] for nombre in accion.pasos]  # type: ignore[misc]
        assert isinstance(accion, AccionDeArchivos)
        return [accion]

    @staticmethod
    def carpeta(accion: AccionDeArchivos, elegida: Path | None = None) -> Path:
        """La que se pasa al ejecutar; si no, la de la acción; si no, la actual."""
        carpeta = (elegida or accion.carpeta or Path(".")).expanduser()
        if not carpeta.is_dir():
            que = "no es una carpeta" if carpeta.exists() else "no existe"
            raise NavajaError(f"La carpeta {carpeta} {que} (acción «{accion.nombre}»).")
        return carpeta.resolve()  # absoluta: el plan y el deshacer no dependen de la carpeta actual

    @staticmethod
    def seleccionar(carpeta: Path, filtro: dict[str, Any], excluir: Path | None = None) -> list[Path]:
        """Archivos de la carpeta que cumplen todo el filtro, por orden alfabético.

        Nunca elige lo que hay en la carpeta de datos de navaja (la papelera) ni, si se
        indica, en ``excluir`` (el destino, para no volver a coger lo ya movido).
        """
        solo = filtro.get("solo", "")
        archivos = seleccionar_filtro(
            carpeta,
            Filtro(
                solo=",".join(solo) if isinstance(solo, list) else solo,
                contiene=filtro.get("contiene", ""),
                desde=filtro.get("desde", ""),
                hasta=filtro.get("hasta", ""),
                recursivo=filtro.get("recursivo", False),
                ocultos=filtro.get("ocultos", False),
            ),
        )
        patron = re.compile(filtro["patron"], re.IGNORECASE) if "patron" in filtro else None
        minimo = a_bytes(filtro["mayor_que"]) if "mayor_que" in filtro else 0
        prohibidas = [directorio_datos().resolve()]
        if excluir is not None:
            ex, base = excluir.resolve(), carpeta.resolve()
            if ex != base and ex.is_relative_to(base):  # uno por encima excluiría todo
                prohibidas.append(ex)

        elegidos = []
        for archivo in archivos:
            if patron and not patron.search(archivo.name):
                continue
            try:
                if minimo and archivo.stat().st_size < minimo:
                    continue
                resuelto = archivo.resolve()
            except OSError:
                continue
            if any(resuelto.is_relative_to(p) for p in prohibidas):
                continue
            elegidos.append(archivo)
        return elegidos

    def planificar(
        self, accion: AccionDeArchivos, carpeta: Path | None = None
    ) -> tuple[Path, list[Resultado]]:
        """La carpeta en la que trabaja y qué le pasaría a cada archivo. No toca nada."""
        base = self.carpeta(accion, carpeta)
        archivos = self.seleccionar(base, accion.filtro, accion.excluir(base))
        try:
            return base, accion.planificar(archivos, base)
        except ValueError as exc:  # una plantilla que no sirve para algún archivo…
            raise NavajaError(f"Acción «{accion.nombre}»: {exc}") from None
