# Navaja

Caja de herramientas de terminal con utilidades cotidianas, con todos los comandos en castellano.

## Utilidades

| Comando | Qué hace |
| --- | --- |
| `navaja listar [ruta]` | Muestra qué hay en una carpeta: nombre, tipo, tamaño y fecha. |
| `navaja ocupa [ruta]` | Muestra qué archivos y carpetas ocupan más espacio. |
| `navaja limpia [ruta]` | Busca y borra cachés y temporales (`node_modules`, `__pycache__`…). `dist`, `build`, `target` y `coverage` solo dentro de un proyecto de programación. |
| `navaja ordena` | Ordena una carpeta: por tipo, por fecha (mes, año o día), los archivos de unas fechas a una carpeta, por un texto del nombre o por letra. Con deshacer. |
| `navaja renombra` | Renombrado masivo sin saber regex: cambiar texto, añadir delante o detrás, numerar, poner la fecha, arreglar nombres o una plantilla. Con deshacer. |
| `navaja duplicados` | Encuentra archivos repetidos por contenido y los manda a una papelera recuperable. |
| `navaja notas` | Notas y enlaces con etiquetas, guardados en SQLite. Lo que empieza por `https://` o `www.` es un enlace. |
| `navaja tema` | `ver` los temas y `elegir` uno (clasico, morado, terminal, pastel). |
| `navaja config` | Tu nombre para el saludo y dónde guarda navaja tus datos. La primera vez que abres navaja te pregunta cómo llamarte (Intro = tu usuario de Windows); con `config nombre` lo cambias para siempre. |
| `navaja manual [comando]` | El manual completo: cómo se usa, todos los comandos con sus opciones, atajos, seguridad y datos. Con un comando, solo su parte. |

`nav` es un alias corto: `nav ocupa` es lo mismo que `navaja ocupa`. (No es `nv` porque en
PowerShell `nv` ya es un atajo de `New-Variable` y se adelantaría a navaja.)

Toda la ayuda está en castellano: `navaja ocupa --help` (o `-h`) enseña lo mismo que
`navaja manual ocupa`, y los errores de uso dicen qué falta y cómo se escribe.

## Modo interactivo

Escribe `navaja` sin nada más y entras en navaja: sale un menú numerado y se
queda esperando órdenes hasta que escribas `salir`. Trabaja en la carpeta desde
la que entras, que se ve siempre en el prompt.

```text
PS C:\Users\sergi\Descargas> navaja
¡Hola! Es la primera vez que abres navaja.         ← solo la primera vez
¿Cómo quieres que te llame? (Intro = Sergi, tu usuario): Sergio
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
Descargas> renombra cambiar        ← si falta algo, lo pregunta
  volver: a la pregunta anterior · salir: cancelar
  ¿En qué carpeta? (Intro = esta: C:\Users\sergi\Descargas):
  Qué texto del nombre quieres cambiar (ej.: IMG_, o el nombre entero): IMG_
  Texto nuevo. Vacío para borrar el que buscas (Intro = vacío): foto_
→ navaja renombra cambiar IMG_ foto_
Descargas> cd ..
sergi> salir
PS C:\Users\sergi\Descargas>
```

| Dentro de navaja | Qué hace |
| --- | --- |
| un número | Elige esa opción. Si es un grupo (`ordena`, `notas`…) abre su submenú; si no, lo ejecuta en la carpeta actual y pregunta solo lo necesario. Lo que cambia archivos (`ordena`, `renombra`, `limpia`, `duplicados borrar`) pregunta primero «¿En qué carpeta?» (Intro = la actual; vale una ruta completa, `~\Documents` o arrastrar la carpeta desde el explorador). En `ordena` y `renombra` pregunta al final «¿Con qué archivos?» (todos, de un tipo, los que llevan un texto o los de unas fechas), salvo en `renombra cambiar` y `avanzado` y en `ordena nombre`, donde el texto ya dice qué archivos se tocan. Debajo te dice qué opciones tiene. |
| un comando | Igual que en la terminal, sin escribir `navaja` delante: `ocupa -n 5`, `ordena tipo --solo imagenes`. Si le falta algo obligatorio, lo pregunta. |
| `ayuda` · `?` | Explica lo que puedes hacer donde estás: en el menú principal, todas las opciones; dentro de una opción (`config`, `ordena`…), esa opción con las suyas, su uso y sus parámetros. |
| `menu` | Vuelve a enseñar el menú (en un submenú, el de ese grupo). |
| `volver` · `atrás` | En medio de las preguntas, repite la anterior; en la primera, vuelves al menú sin hacer nada. En las listas numeradas también vale `0`. `salir` en una pregunta cancela sin hacer nada. Al confirmar (`[s/n]`), `n` no hace nada y sigues en el menú. |
| `ayuda ocupa` · `ocupa ?` · `? 2` | Ayuda corta: qué hace un comando, cómo se escribe y sus opciones con su valor por defecto. |
| `manual` | El manual completo de navaja. `manual ocupa` enseña solo la parte de ese comando. |
| `cd RUTA` · `cd ..` · `cd` | Cambia de carpeta (`cd` solo enseña dónde estás). Al salir vuelves a la carpeta de antes. |
| `ls` · `dir` | Atajos de `listar`. |
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
# El manual completo, o solo la parte de un comando
navaja manual
navaja manual ordena tramo
navaja manual > manual.txt     # guardarlo en un archivo

# Ver qué hay en una carpeta (carpetas primero)
navaja listar ~/Descargas

# Ver qué ocupa espacio (2 niveles de profundidad, 20 entradas)
navaja ocupa ~/Descargas -n 20 -p 2

# Previsualizar la basura y luego borrarla
navaja limpia ~/Proyectos --simular
navaja limpia ~/Proyectos

# Ordenar: enseña «archivo → carpeta» y pregunta [s/n] (--simular solo mira)
navaja ordena tipo -c ~/Downloads                    # Imagenes/, Documentos/, Videos/…
navaja ordena fecha                                  # 2026/10 octubre/…
navaja ordena fecha --por año --solo imagenes        # solo las imágenes, en 2026/, 2025/…
navaja ordena tramo 1/9/2026 31/10/2026              # a «del 2026-09-01 al 2026-10-31»
navaja ordena tramo "septiembre 2026" --nombre Curso # de septiembre a hoy, en «Curso»
navaja ordena tipo --desde "hace 30 días"            # solo lo de los últimos 30 días
navaja ordena nombre factura                         # los que llevan «factura», a factura/
navaja ordena nombre gemini --nombre "Imagenes IA"   # los de Gemini, a «Imagenes IA»
navaja ordena letra                                  # A/, B/, C/… y 0-9/ para los números
navaja ordena deshacer

# Renombrar: enseña «antes → después» y pregunta [s/n] (--simular solo mira)
navaja renombra cambiar IMG_ foto_                   # IMG_1234.jpg → foto_1234.jpg
navaja renombra cambiar " (1)" ""                    # informe (1).pdf → informe.pdf
navaja renombra cambiar informe.pdf final            # un solo archivo: informe.pdf → final.pdf
navaja renombra delante 2026_ --solo pdf             # informe.pdf → 2026_informe.pdf
navaja renombra detras _v2                           # informe.pdf → informe_v2.pdf
navaja renombra numerar playa --solo jpg,png --orden fecha   # playa_001.jpg, playa_002.png…
navaja renombra numerar gemini --separador " " --cifras 1 --contiene gemini
                                                     # Gemini_Generated_Image_….png → gemini 1.png…
navaja renombra fecha -c ~/Fotos                     # IMG_1.jpg → 2026-10-26_IMG_1.jpg
navaja renombra arreglar                             # Foto Año (1).JPG → foto-ano-1.jpg
navaja renombra plantilla "{fecha:%Y-%m-%d}_{n:03}{ext}" --simular
navaja renombra avanzado 'IMG_(\d+)' 'foto_\1'       # con expresiones regulares
navaja renombra deshacer

# Duplicados: mirar, quitar las copias y, si te arrepientes, recuperarlas
navaja duplicados buscar ~/Descargas -r
navaja duplicados buscar ~/Fotos -r --minimo 1MB --conservar corto
navaja duplicados borrar ~/Descargas -r
navaja duplicados restaurar
navaja duplicados vaciar        # libera el espacio de verdad (no se puede deshacer)

# Notas y enlaces
navaja notas agregar "Repasar Python" "Decoradores y generadores" -e estudio,python
navaja notas agregar "Docs de Typer" https://typer.tiangolo.com -e docs   # es un enlace
navaja notas listar -e python
navaja notas buscar generadores     # sin mirar mayúsculas ni tildes
navaja notas abrir 1                # el 1 es la columna ID de «notas listar»
navaja notas etiquetas

# Personalizar
navaja tema ver                 # muestra cada tema con sus colores
navaja tema elegir morado
navaja config nombre Sergio
navaja config ver
```

## Seguridad

- `ordena` y `renombra` enseñan siempre el plan y preguntan `[s/n]` antes de tocar nada; con `--simular` solo miran. Los dos tienen `deshacer`.
- Nunca se sobrescribe un archivo, y se saltan los ocultos y los de sistema de Windows (`desktop.ini`, `Thumbs.db`), salvo con `--ocultos`.
- Fechas fáciles en `--desde`, `--hasta` y `ordena tramo`: `1/9/2026`, `septiembre 2026`, `2026`, `hoy`, `hace 30 días`. Un mes o un año valen enteros.
- `limpia` dice qué es cada cosa que borraría y pide confirmación; `--simular` solo mira y `--si` no pregunta. Solo borra lo que se vuelve a crear solo: `build`, `dist`, `target` y `coverage` únicamente dentro de un proyecto de programación (fuera pueden ser tuyas), y nunca `desktop.ini`. Lo que borra no va a la papelera.
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
