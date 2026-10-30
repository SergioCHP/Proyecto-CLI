# AGENTS.md

Guía para agentes y desarrolladores que trabajen en este repositorio.

## Qué es este proyecto

`navaja` es una CLI en Python (Typer + Rich) con utilidades de terminal y todos
los comandos en castellano. No hay servidor ni base de datos externa: todo es
local y el estado se guarda en el directorio de datos del usuario.

## Puesta en marcha

El proyecto se gestiona con `uv` (funciona igual en Linux, macOS y Windows).
`uv run` crea `.venv/` la primera vez e instala el paquete en modo editable:

```bash
uv run navaja --help              # ejecutar la CLI con el código actual
uv run --extra dev pytest         # tests
```

No hay linter/formateador configurado. Antes de terminar un cambio, ejecuta al
menos:

```bash
uv run --extra dev pytest
uv run python -m compileall -q src tests
```

Nunca ejecutes comandos destructivos (`aplicar`, `borrar`, `limpia`, `vaciar`)
sobre carpetas reales del usuario: prueba en una carpeta temporal.

## Estructura

```
src/navaja/
├── app.py              # Typer app raíz, --version y registro de comandos
├── comun.py            # console Rich, tamaños, rutas, undo, editor, iteradores
└── comandos/
    ├── ocupa.py        # ocupa (analizar) y limpia (borrar basura)
    ├── ordena.py       # sub-app: previsualizar / aplicar / deshacer / categorias
    ├── renombra.py     # sub-app: previsualizar / aplicar / deshacer
    ├── duplicados.py   # sub-app: buscar / borrar (a papelera) / restaurar / vaciar
    ├── notas.py        # sub-app SQLite: agregar / listar / buscar / abrir / borrar / etiquetas
    └── ajustes.py      # sub-apps tema (listar / fijar) y config (ver / nombre)
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
- **Colores:** nunca escribas colores fijos (`[green]`, `"cyan"`). Usa los
  estilos del tema: `ok`, `error`, `aviso`, `pista`, `acento`, `titulo`,
  `logro`, `marco` (bordes de paneles) y `borde` (tablas). `[bold]` sí vale.
  Un estilo nuevo se añade a todos los temas de `TEMAS` en `comun.py`.
- **Texto del usuario en Rich:** todo nombre de archivo, ruta, título o mensaje
  de excepción que vaya dentro de markup se pasa por `rich.markup.escape()`
  (si no, `[borrador].pdf` se pierde). Para un bloque de texto suelto, usa
  `rich.text.Text`.
- **Secretos:** nunca escribas claves en el código ni las subas; van en `.env`,
  que está en `.gitignore`.
- **Python 3.10:** evita APIs de 3.11+ (por ejemplo `tomllib`). Usa
  `from __future__ import annotations`.
- **Tests:** sin mocks de Rich/Typer; prueba la lógica pura con `tmp_path`.
  No toques el directorio de datos real en tests (`tests/conftest.py` ya
  apunta `NAVAJA_DATOS` a una carpeta temporal en cada test).
- **Estilo:** docstrings concisas en castellano; sin comentarios obvios.

## Estado actual

Resumen y bitácora en [ESTADO.md](ESTADO.md). Última verificación conocida
(2026-10-30): 39 tests pasando (Python 3.10 y 3.13) y CLI probada de punta a
punta (ocupa, limpia, ordena, renombra, duplicados, notas, tema y config).
