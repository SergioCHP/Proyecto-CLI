# Navaja

Caja de herramientas de terminal con utilidades cotidianas, con todos los comandos en castellano.

## Utilidades

| Comando | Qué hace |
| --- | --- |
| `navaja ocupa [ruta]` | Muestra qué archivos y carpetas ocupan más espacio. |
| `navaja limpia [ruta]` | Busca y borra cachés y temporales (`node_modules`, `__pycache__`, `dist`…). |
| `navaja ordena` | Organiza archivos por extensión o fecha, con deshacer. |
| `navaja renombra` | Renombrado masivo con expresiones regulares, con deshacer. |
| `navaja notas` | Notas y enlaces con etiquetas, guardados en SQLite. |

## Instalación

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

O con `pipx` para tenerlo disponible en todo el sistema:

```bash
pipx install .
```

## Ejemplos

```bash
# Ver qué ocupa espacio (2 niveles de profundidad, 20 entradas)
navaja ocupa ~/Descargas -n 20 -p 2

# Previsualizar la basura y luego borrarla
navaja limpia ~/Proyectos --seco
navaja limpia ~/Proyectos

# Organizar Descargas por tipo de archivo
navaja ordena previsualizar ~/Descargas
navaja ordena aplicar ~/Descargas
navaja ordena deshacer

# Renombrar IMG_1234.jpg -> foto_1234.jpg
navaja renombra previsualizar ~/Fotos 'IMG_(\d+)' 'foto_\1' --incluir '*.jpg'
navaja renombra aplicar ~/Fotos 'IMG_(\d+)' 'foto_\1' --incluir '*.jpg'
navaja renombra deshacer

# Notas y enlaces
navaja notas agregar "Repasar Python" --texto "Decoradores y generadores" -e estudio -e python
navaja notas agregar "Docs de Typer" --url https://typer.tiangolo.com -e docs
navaja notas listar -e python
navaja notas buscar generadores
navaja notas abrir 1
navaja notas etiquetas
```

## Seguridad

- `ordena` y `renombra` siempre tienen `previsualizar` (no toca nada) y `deshacer`.
- `limpia` muestra los candidatos y pide confirmación; usa `--seco` para solo mirar y `--si` para no preguntar.
- Las acciones para deshacer y la base de datos de notas se guardan en:
  - Linux: `~/.local/share/navaja/`
  - macOS: `~/Library/Application Support/navaja/`
  - Windows: `%LOCALAPPDATA%\navaja\`

## Desarrollo

```bash
.venv/bin/python -m pytest
```

La estructura está en `src/navaja/` y cada utilidad vive en `src/navaja/comandos/`.

## Documentación del proyecto

- [AGENTS.md](AGENTS.md): guía para agentes y desarrolladores (estructura,
  convenciones y cómo añadir comandos).
- [ESTADO.md](ESTADO.md): bitácora de lo implementado, decisiones y pendientes.
