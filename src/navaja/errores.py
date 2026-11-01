"""Errores previsibles de navaja: cada uno sabe con qué código de salida termina.

La orden que los captura solo tiene que atrapar ``NavajaError`` una vez y salir con
``error.codigo_salida``: nunca se enseña una traza de Python por algo que se
puede explicar.
"""

from __future__ import annotations


class NavajaError(Exception):
    """Base de todos los errores previsibles: una carpeta que no existe, una acción
    que no existe…"""

    codigo_salida = 1


class ConfigError(NavajaError):
    """acciones.json no existe, no es JSON o no cumple el esquema."""

    codigo_salida = 3


class AccionNoValida(ConfigError):
    """Una acción concreta tiene un campo mal: dice cuál y por qué."""

    def __init__(self, accion: str, campo: str, motivo: str) -> None:
        super().__init__(f"Acción «{accion}», campo «{campo}»: {motivo}")
        self.accion = accion
        self.campo = campo
        self.motivo = motivo
