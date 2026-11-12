# AGENTS.md

Normas para el agente (OpenCode o Claude Code). Se leen siempre: aquí solo lo
imprescindible. Cómo está hecho por dentro: [docs/arquitectura.md](docs/arquitectura.md).
Reglas de `acciones.json`: la skill `acciones-json`.

## Stack y órdenes

- Python 3.12+, Typer, Rich y prompt_toolkit (solo para leer en el modo interactivo), gestionado con `uv`. Paquete en `src/navaja/`.
- Ejecutar: `uv run navaja --help`
- Validar acciones: `uv run navaja acciones validar --config pruebas/acciones-prueba.json`
- Tests: `uv run --extra dev pytest` (y `uv run python -m compileall -q src tests`)

## Normas

- Mensajes, ayuda y comentarios en castellano. Código claro antes que astuto.
- `pathlib` y `encoding="utf-8"`; nada de `os.system` ni `shell=True`. Debe funcionar
  en Windows, Linux y macOS.
- Nunca actuar sobre carpetas reales: solo en `~/pruebas-navaja`, con
  `--config pruebas/acciones-prueba.json` y `--simular`. Las acciones sin `--simular`
  las ejecuta Sergio, no el agente.
- No tocar `.env` ni escribir claves en ningún archivo.
- Antes de cambiar un archivo, explicar en 2-3 líneas qué se va a hacer.
- Errores previsibles: `NavajaError` / `ConfigError` / `AccionNoValida` con mensaje en
  castellano; nunca una traza de Python.
- Colores solo con los estilos del tema (`ok`, `error`, `aviso`…) y todo texto del
  usuario dentro de markup Rich pasado por `escape()`.
- Cada comando, argumento y opción con `help` en castellano (sale en el menú y en el
  manual; `tests/test_ayuda.py` falla si falta).
- Al terminar un cambio: tests en verde, y `README.md` y `ESTADO.md` al día.
