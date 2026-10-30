# Estado del proyecto

Bitácora de lo implementado y de lo que queda pendiente.

## Resumen

- **Producto:** `navaja`, CLI de utilidades de terminal.
- **Versión:** 0.1.0.
- **Stack:** Python 3.10, Typer, Rich, SQLite (stdlib), setuptools.
- **Estado:** funcional y probado localmente.

## Hecho

### 2026-10-26 — Arranque

- Repositorio inicial con `README.md` y `.gitignore`.
- Commit inicial: `071c821 Initial commit: estructura del proyecto`.

### 2026-10-27 — Primera versión funcional

Estructura del paquete y tooling:

- `pyproject.toml` con entry point `navaja = navaja.app:main` y dependencias
  `typer` + `rich`.
- Paquete en `src/navaja/` y entorno `.venv/`.
- `comun.py` con utilidades compartidas: tamaños legibles, directorio de datos,
  confirmaciones, rutas libres, registro de deshacer, editor externo e
  iteración segura de archivos.

Comandos implementados:

- `navaja ocupa [ruta] [-n] [-p]`: tamaño total, archivos, espacio libre,
  tabla con porcentaje y barra, y árbol por profundidad.
- `navaja limpia [ruta] [--seco] [--si]`: detecta `node_modules`,
  `__pycache__`, `dist`, `build`, `target`, `*.pyc`, etc.; previsualiza y borra
  con confirmación.
- `navaja ordena previsualizar|aplicar|deshacer|categorias`: organiza por
  extensión o fecha (`--por`), destino alternativo (`--destino`), recursivo,
  ocultos; evita colisiones y guarda deshacer.
- `navaja renombra previsualizar|aplicar|deshacer`: regex sobre el nombre
  (o completo con `--completo`), filtro `--incluir`, recursivo, ocultos;
  detecta conflictos e inválidos y guarda deshacer.
- `navaja notas agregar|listar|buscar|abrir|borrar|etiquetas`: notas y enlaces
  con etiquetas en SQLite; abre enlaces en el navegador y notas en editor.

Documentación y calidad:

- `README.md` con instalación, ejemplos y notas de seguridad.
- `AGENTS.md` con estructura, convenciones y cómo añadir comandos.
- 17 tests en `tests/` (común, ocupa, ordena, renombra y notas).
- Verificado con `pytest`, `compileall` y pruebas manuales de todos los
  comandos, incluidos aplicar/deshacer.

### 2026-10-30 — Duplicados y nombres con corchetes

- **Arreglo:** los nombres con corchetes (`[borrador].pdf`, `[red]aviso.txt`)
  se perdían o cambiaban de color en todas las tablas, porque Rich los leía
  como formato. Ahora se escapan con `rich.markup.escape` en ocupa, limpia,
  ordena, renombra y notas. Test de regresión en `tests/test_salida.py`.
- **Nuevo:** `navaja duplicados buscar|borrar|restaurar|vaciar`.
  - Compara por contenido: tamaño → hash de los primeros 64 KB → SHA-256
    completo, así solo lee enteros los archivos que de verdad se parecen.
  - `--conservar antiguo|reciente|corto` decide qué copia se queda.
  - `--minimo 1MB` ignora archivos pequeños; los vacíos no cuentan salvo con `0`.
  - No cuenta dos veces los enlaces duros ni escanea la carpeta de datos de navaja.
  - `borrar` mueve las copias a una papelera propia (recuperable con
    `restaurar`); `vaciar` libera el espacio de verdad.
- `.gitignore` con `.env` y `.gitattributes` con `* text=auto`.
- Instalación y pruebas documentadas con `uv`.
- 31 tests pasando (también con Python 3.10).

## Decisiones técnicas

- **Typer + Rich** por rapidez de desarrollo y buena salida en terminal.
- **SQLite** para notas: sin dependencias extra y con consultas por etiqueta.
- **JSON en el directorio de datos** para el deshacer de `ordena` y `renombra`;
  solo se guarda la última operación.
- **Papelera propia para `duplicados`** en vez de borrar: es la única forma de
  poder deshacer un borrado sin añadir dependencias (como `send2trash`).
- **Sin dependencias más allá de Typer/Rich**: la lógica usa stdlib.
- **Comandos en castellano** y opciones cortas coherentes (`-n`, `-p`, `-e`,
  `-r`, `-s`).

## Pendientes / ideas

- [x] Buscar duplicados por contenido.

- [ ] `--json` en `ocupa` y `notas listar` para scripting.
- [ ] Exportar notas a Markdown o HTML.
- [ ] Comando `tarea` (tareas pendientes) reutilizando la base de notas.
- [ ] Historial de deshacer (varias operaciones, no solo la última).
- [ ] Autocompletado de shell.
- [ ] Linter/formateador (ruff) y CI (GitHub Actions).
- [ ] Empaquetado y publicación (pipx / PyPI).

## Cómo comprobar el estado

```bash
uv run --extra dev pytest
uv run python -m compileall -q src tests
uv run navaja --help
```
