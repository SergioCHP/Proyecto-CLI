# Navaja

Caja de herramientas de terminal con utilidades cotidianas, con todos los comandos en castellano.

## Utilidades

| Comando | Qué hace |
| --- | --- |
| `navaja listar [ruta]` | Muestra qué hay en una carpeta: nombre, tipo, tamaño y fecha. |
| `navaja ocupa [ruta]` | Muestra qué archivos y carpetas ocupan más espacio. |
| `navaja limpia [ruta]` | Busca y borra cachés y temporales (`node_modules`, `__pycache__`, `dist`…). |
| `navaja ordena` | Organiza archivos por extensión o fecha, con deshacer. |
| `navaja renombra` | Renombrado masivo con expresiones regulares, con deshacer. |
| `navaja duplicados` | Encuentra archivos repetidos por contenido y los manda a una papelera recuperable. |
| `navaja notas` | Notas y enlaces con etiquetas, guardados en SQLite. |
| `navaja tema` | Elige los colores (clasico, morado, terminal, pastel). |
| `navaja config` | Tu nombre para el saludo y el tema actual. |

`nv` es un alias corto: `nv ocupa` es lo mismo que `navaja ocupa`.

## Modo interactivo

Escribe `navaja` sin nada más y entras en navaja: sale un menú numerado y se
queda esperando órdenes hasta que escribas `salir`. Trabaja en la carpeta desde
la que entras, que se ve siempre en el prompt.

```text
PS C:\Users\sergi\Descargas> navaja
╭────────── navaja ───────────╮
│ Buenos días, Sergio         │
╰─────────────────────────────╯
1  listar      Muestra qué hay en una carpeta.
2  ocupa       Muestra qué ocupa espacio en disco.
…
0  salir

Descargas> 2                       ← un número: lo ejecuta aquí mismo
…
Más opciones: --mayores --profundidad · ayuda ocupa explica cada una
Descargas> ocupa -n 5              ← o escribe el comando con sus opciones
Descargas> renombra previsualizar  ← si falta algo obligatorio, lo pregunta
  Expresión regular a buscar: IMG_
  Texto de reemplazo. Usa \1, \2… para los grupos: foto_
→ navaja renombra previsualizar . IMG_ foto_
Descargas> cd ..
sergi> salir
PS C:\Users\sergi\Descargas>
```

| Dentro de navaja | Qué hace |
| --- | --- |
| un número | Elige esa opción. Si es un grupo (`ordena`, `notas`…) abre su submenú; si no, lo ejecuta en la carpeta actual y solo pregunta lo obligatorio. Debajo te dice qué opciones tiene. |
| un comando | Igual que en la terminal, sin escribir `navaja` delante: `ocupa -n 5`, `ordena aplicar ~/Descargas`. Si le falta algo obligatorio, lo pregunta. |
| `ayuda ocupa` · `ocupa ?` · `? 2` | Qué hace un comando, cómo se escribe y sus opciones con su valor por defecto. |
| `cd RUTA` · `cd ..` · `cd` | Cambia de carpeta (`cd` solo enseña dónde estás). Al salir vuelves a la carpeta de antes. |
| `ls` · `dir` | Atajos de `listar`. |
| `menu` · `?` | Vuelve a enseñar las opciones. |
| `cls` | Limpia la pantalla. |
| `salir` · `exit` · `0` · Ctrl+C | Vuelve a la terminal normal. Un submenú sigue abierto hasta que pulsas Intro o `0`; desde él también puedes escribir un comando del menú principal. |

Un error enseña el mensaje y sigues dentro. Las confirmaciones son `[s/n]`. Si `navaja` no se ejecuta en una
terminal (por ejemplo, en un script), no abre el menú: solo enseña el saludo y
la lista de comandos. Fuera del modo interactivo todo funciona como siempre:
`navaja ocupa ~/Descargas` desde la terminal normal.

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
# Ver qué hay en una carpeta (carpetas primero)
navaja listar ~/Descargas

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

# Personalizar
navaja tema listar              # muestra cada tema con sus colores
navaja tema fijar morado
navaja config nombre Sergio
navaja config ver
```

## Seguridad

- `ordena` y `renombra` siempre tienen `previsualizar` (no toca nada) y `deshacer`.
- `limpia` muestra los candidatos y pide confirmación; usa `--seco` para solo mirar y `--si` para no preguntar.
- `duplicados borrar` no borra: mueve las copias a la papelera de navaja. Compara el
  contenido completo (SHA-256), no solo el nombre o el tamaño, y nunca toca el archivo
  que se conserva. El espacio solo se libera con `duplicados vaciar`.
- Las acciones para deshacer, la papelera, la base de datos de notas y `config.json`
  se guardan en (o en la carpeta que indique la variable `NAVAJA_DATOS`):
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
