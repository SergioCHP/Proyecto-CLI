# Navaja

Caja de herramientas de terminal con utilidades cotidianas, con todos los comandos en castellano.

## Utilidades

| Comando | Qué hace |
| --- | --- |
| `navaja ocupa [ruta]` | Muestra qué archivos y carpetas ocupan más espacio. |
| `navaja limpia [ruta]` | Busca y borra cachés y temporales (`node_modules`, `__pycache__`, `dist`…). |
| `navaja ordena` | Organiza archivos por extensión o fecha, con deshacer. |
| `navaja renombra` | Renombrado masivo con expresiones regulares, con deshacer. |
| `navaja duplicados` | Encuentra archivos repetidos por contenido y los manda a una papelera recuperable. |
| `navaja notas` | Notas y enlaces con etiquetas, guardados en SQLite. |

## Instalación

Con [uv](https://docs.astral.sh/uv/) (Linux, macOS y Windows), desde la carpeta del repo:

```bash
uv tool install --editable .   # deja el comando navaja disponible en cualquier carpeta
navaja --help
```

Si dice «orden no encontrada», ejecuta `uv tool update-shell` y abre otra terminal.

Sin instalar nada, para probar mientras desarrollas:

```bash
uv run navaja --help
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

# Duplicados: mirar, quitar las copias y, si te arrepientes, recuperarlas
navaja duplicados buscar ~/Descargas -r
navaja duplicados buscar ~/Fotos -r --minimo 1MB --conservar corto
navaja duplicados borrar ~/Descargas -r
navaja duplicados restaurar
navaja duplicados vaciar        # libera el espacio de verdad (no se puede deshacer)

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
- `duplicados borrar` no borra: mueve las copias a la papelera de navaja. Compara el
  contenido completo (SHA-256), no solo el nombre o el tamaño, y nunca toca el archivo
  que se conserva. El espacio solo se libera con `duplicados vaciar`.
- Las acciones para deshacer, la papelera y la base de datos de notas se guardan en:
  - Linux: `~/.local/share/navaja/`
  - macOS: `~/Library/Application Support/navaja/`
  - Windows: `%LOCALAPPDATA%\navaja\`

## Desarrollo

```bash
uv run --extra dev pytest
```

La estructura está en `src/navaja/` y cada utilidad vive en `src/navaja/comandos/`.

## Documentación del proyecto

- [AGENTS.md](AGENTS.md): guía para agentes y desarrolladores (estructura,
  convenciones y cómo añadir comandos).
- [ESTADO.md](ESTADO.md): bitácora de lo implementado, decisiones y pendientes.
