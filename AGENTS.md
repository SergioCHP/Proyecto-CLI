# AGENTS.md

Guía para agentes y desarrolladores que trabajen en este repositorio.

## Qué es este proyecto

`navaja` es una CLI en Python (Typer + Rich) con utilidades de terminal y todos
los comandos en castellano. No hay servidor ni base de datos externa: todo es
local y el estado se guarda en el directorio de datos del usuario.

## Puesta en marcha

El entorno virtual ya existe en `.venv/`. En esta máquina el Python del sistema
no trae `pip`, así que el entorno se creó con `--without-pip` y se instaló
`pip` con `get-pip.py`. Para trabajo normal:

```bash
.venv/bin/pip install -e ".[dev]"   # dependencias + pytest
.venv/bin/python -m pytest          # tests
.venv/bin/navaja --help             # ejecutar la CLI instalada
```

Alternativa sin instalar el paquete:

```bash
PYTHONPATH=src .venv/bin/python -m navaja --help
```

No hay linter/formateador configurado. Antes de terminar un cambio, ejecuta al
menos:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q src tests
```

## Estructura

```
src/navaja/
├── app.py              # Typer app raíz, --version y registro de comandos
├── comun.py            # console Rich, tamaños, rutas, undo, editor, iteradores
└── comandos/
    ├── ocupa.py        # ocupa (analizar) y limpia (borrar basura)
    ├── ordena.py       # sub-app: previsualizar / aplicar / deshacer / categorias
    ├── renombra.py     # sub-app: previsualizar / aplicar / deshacer
    └── notas.py        # sub-app SQLite: agregar / listar / buscar / abrir / borrar / etiquetas
tests/                  # un archivo por módulo
```

Cada módulo de `comandos/` expone `registrar(app)` y se registra en el bucle de
`app.py`. Los comandos de nivel superior se añaden con `app.command(...)`; los
subcomandos con `app.add_typer(sub, name="...")`.

## Cómo añadir una utilidad nueva

1. Crea `src/navaja/comandos/<nombre>.py` con funciones puras para la lógica
   (planificar, calcular) y comandos Typer finos encima.
2. Añade `registrar(app)` al final del módulo.
3. Importa el módulo y añádelo al bucle de `app.py`.
4. Añade tests en `tests/test_<nombre>.py`.
5. Documenta el comando en `README.md` y actualiza `ESTADO.md`.

## Convenciones

- **Idioma:** comandos, opciones, ayuda y mensajes en castellano. Los
  identificadores de Python no llevan acentos (`previsualizar`, `deshacer`).
- **Comandos destructivos:** deben tener previsualización, confirmación
  (`--si` para saltarla) y deshacer cuando sea posible. Usa `--seco` para
  simular sin tocar nada.
- **Seguridad de rutas:** usa `ruta_libre()` para evitar sobrescribir archivos,
  `iterar_archivos()` para listar (no sigue enlaces simbólicos) y
  `guardar_acciones()` / `cargar_acciones()` / `limpiar_acciones()` para el
  deshacer.
- **Estado persistente:** siempre a través de `directorio_datos()`; nunca
  escribas en el directorio del proyecto.
- **Salida:** usa `console` para información y `error_console` para errores
  (stderr). No uses `print()`.
- **Python 3.10:** evita APIs de 3.11+ (por ejemplo `tomllib`). Usa
  `from __future__ import annotations`.
- **Tests:** sin mocks de Rich/Typer; prueba la lógica pura con `tmp_path`.
  No toques el directorio de datos real en tests.
- **Estilo:** docstrings concisas en castellano; sin comentarios obvios.

## Estado actual

Resumen y bitácora en [ESTADO.md](ESTADO.md). Última verificación conocida:
17 tests pasando y CLI probada de punta a punta (ocupa, limpia, ordena,
renombra y notas).
