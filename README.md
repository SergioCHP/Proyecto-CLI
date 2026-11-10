# Navaja

Caja de herramientas de terminal con utilidades cotidianas, con todos los comandos en castellano.

## Spec

1. **Problema que se repite:** copiar y ordenar archivos. La carpeta Descargas siempre
   tiene de todo, copio y pego los archivos de clase del USB al PC de casa y renombro
   muchas fotos una a una.
2. **Para quién:** para mí, y quizás para mi mujer, para que ordene los archivos de su PC.
3. **Uso:** `navaja ORDEN [CARPETA] [opciones]`. Sin orden (`navaja`), abre un menú
   interactivo. Alias corto: `nav`.
4. **Órdenes que ya tiene:** `listar`, `ocupa`, `limpia`, `ordena`, `renombra`,
   `duplicados`, `notas`, `acciones` (`ver`, `ejecutar`, `validar`, `editar`,
   `deshacer`, `versiones`), `tema`, `config` (también `config autocompletar`, Tab en PowerShell),
   `manual` y `version`. Dentro de navaja, Tab completa y ↑ ↓ recuperan lo de antes.
5. **Órdenes previstas:**
   - `navaja busca`: un buscador de texto dentro de archivos.
   - `navaja extrae` / `navaja comprime`: para unificar la compresión y descompresión
     de archivos.
   - Cambiar formatos de imagen o documentos.
6. **Acciones:** `ordenar-descargas`, `imagenes-ia`, `instaladores-viejos`,
   `fotos-con-fecha` y la rutina `limpieza-semanal`. La que más uso es
   `ordenar-descargas`, porque me gusta tenerlo todo en orden.
7. **Lo que nunca hará:**
   - Tocar nada sin enseñar antes qué va a hacer y preguntar `[s/n]` (salvo con `--si`).
   - Sobrescribir un archivo: si el nombre ya existe, añade « (1)».
   - Tocar archivos fuera de la carpeta que le digo.
   - Borrar para siempre sin avisar: `acciones` y `duplicados` mandan lo borrado a una
     papelera recuperable; `limpia` y `duplicados vaciar` sí borran de verdad, pero
     solo después de preguntar.
   - Con `--simular`, cambiar nada (ni siquiera crear carpetas).
8. **Plataformas:** Windows en mi PC y Linux en clase. Python 3.12 o superior.
9. **Códigos de salida:**
   - 0: todo bien (también si respondo «n» a una confirmación).
   - 1: fallo al ejecutar (una carpeta o una acción que no existe).
   - 2: uso incorrecto (falta un argumento o una opción no existe).
   - 3: `acciones.json` no existe o está mal escrito.
10. **Instalación:** `uv tool install --editable .` desde la carpeta del repo (más
    detalles en [Instalación](#instalación)).

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
| `navaja acciones` | Tus tareas de siempre guardadas con un nombre en `acciones.json` (ordenar Descargas, copiar apuntes, quitar instaladores viejos…) para hacerlas con una orden. Con simulación, confirmación y deshacer; lo que sustituye una copia se guarda en `acciones versiones`. |
| `navaja tema` | `ver` los temas y `elegir` uno (clasico, morado, terminal, pastel). |
| `navaja config` | Tu nombre para el saludo y dónde guarda navaja tus datos. La primera vez que abres navaja te pregunta cómo llamarte (Intro = tu usuario de Windows); con `config nombre` lo cambias para siempre; con `config autocompletar $PROFILE`, Tab en PowerShell. |
| `navaja manual [comando]` | El manual completo: cómo se usa, todos los comandos con sus opciones, atajos, seguridad y datos. Con un comando, solo su parte. |

`navaja version` (o `navaja --version`) dice la versión.

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
| Tab | Completa lo que escribes: comandos, subcomandos, opciones (escribe `-` y Tab), rutas (después de `cd`, de `listar` o de `--carpeta`) y los nombres de tus acciones (después de `acciones ejecutar`, también cuando te lo pregunta). Si hay varias, sale una lista. |
| ↑ ↓ | Recuperan lo que escribiste antes, también de otras veces (se guarda en `historial.txt`, en tus datos). |
| `cls` | Limpia la pantalla. |
| `salir` · `exit` · `0` · Ctrl+C | Vuelve a la terminal normal. Un submenú sigue abierto hasta que pulsas Intro o `0`; desde él también puedes escribir un comando del menú principal. |

Un error enseña el mensaje y sigues dentro. Las confirmaciones son `[s/n]`. Si `navaja` no se ejecuta en una
terminal (por ejemplo, en un script), no abre el menú: solo enseña el saludo y
la lista de comandos. Fuera del modo interactivo todo funciona como siempre:
`navaja ocupa ~/Descargas` desde la terminal normal.

## Acciones: `acciones.json`

Una acción es una tarea que repites, escrita una sola vez en un archivo de texto con un
nombre: `ordenar-descargas`, `imagenes-ia`… Luego la haces con una orden. El archivo
dice **qué** hacer; el código de navaja sabe **cómo**. Para añadir una acción nueva se
edita el JSON, no el programa.

```bash
navaja acciones ver                                  # mis acciones, con su número
navaja acciones ejecutar ordenar-descargas --simular # qué haría, sin tocar nada
navaja acciones ejecutar ordenar-descargas           # enseña el plan y pregunta [s/n]
navaja acciones ejecutar 2                           # también por su número
navaja acciones ejecutar imagenes-ia ~/pruebas-navaja/Descargas   # en otra carpeta
navaja acciones ejecutar pc-a-usb --destino E:/DAM                 # a otro destino (el USB con otra letra)
navaja acciones versiones ver                                      # las versiones viejas que sustituyó una copia
navaja acciones versiones recuperar 2                              # devolver una a su sitio (sin pisar nada)
navaja acciones versiones borrar --hasta "hace 30 días"            # quitar las que ya no hacen falta
navaja acciones deshacer                             # deja todo como estaba
navaja acciones validar                              # comprueba el archivo sin hacer nada
navaja acciones editar                               # lo abre en el Bloc de notas y lo comprueba al cerrar
```

navaja usa el `acciones.json` de la carpeta en la que estás y, si no hay, el de tus datos
(`%LOCALAPPDATA%\navaja\acciones.json` en Windows). Con `--config RUTA` usa otro, escrito
antes o después de la orden (si van los dos, gana el de después):

```bash
navaja acciones --config pruebas/acciones-prueba.json validar
navaja acciones validar --config pruebas/acciones-prueba.json
```

Antes de hacer nada comprueba el archivo **entero**. Si algo está mal, dice qué acción y
qué campo fallan y sale con el código 3, sin trazas de Python:

```text
✘ Acción «imagenes-ia», campo «tipo»: «mober» no existe; usa uno de: mover, copiar, ordenar, renombrar, borrar, rutina. ¿Querías decir «mover»?
✘ acciones.json no es JSON válido: línea 9, columna 21: hay una barra invertida \ suelta: en JSON se escribe doble (C:\\Users) o, mejor, usa / (C:/Users o ~/Downloads).
```

### Mis acciones

Están en [acciones.json](acciones.json):

| Nombre | Tipo | Qué hace |
| --- | --- | --- |
| `ordenar-descargas` | ordenar | Mete cada archivo de Descargas en su carpeta (Imagenes, Documentos…). |
| `imagenes-ia` | mover | Saca de Descargas las imágenes de Gemini a `~/Pictures/Imagenes IA`. |
| `instaladores-viejos` | borrar | Manda a la papelera de navaja los instaladores de hace más de un mes. |
| `fotos-con-fecha` | renombrar | `IMG_1234.jpg` → `2026-10-26_IMG_1234.jpg`; solo las que empiezan por `IMG_` o `PXL_`, así que no se renombran dos veces. |
| `limpieza-semanal` | rutina | `instaladores-viejos` → `imagenes-ia` → `ordenar-descargas`, en ese orden. |
| `usb-a-pc` | copiar | Trae al PC (`~/Documents/ESTUDIO/DAM`) lo nuevo del USB de clase (`D:/DAM`), con sus subcarpetas. Si un archivo es distinto en los dos sitios, gana el más reciente. |
| `pc-a-usb` | copiar | Lo mismo al revés. Las dos se saltan `node_modules`, `__pycache__`, `build`, `dist` y `target`, y los ocultos. Con el USB sin conectar, se paran antes de empezar. |

### Esquema

```json
{
  "version": 1,
  "acciones": [
    {
      "nombre": "instaladores-viejos",
      "descripcion": "Manda a la papelera los instaladores de hace más de un mes",
      "tipo": "borrar",
      "carpeta": "~/Downloads",
      "filtro": { "solo": "ejecutables", "hasta": "hace 30 días" }
    }
  ]
}
```

| Campo | Cuándo | Qué es |
| --- | --- | --- |
| `version` | obligatorio | Siempre `1`. Si un día cambia el formato, sube a `2` y navaja sabe qué está leyendo. |
| `acciones` | obligatorio | La lista de acciones. Vacía es un error. |
| `nombre` | obligatorio | Con el que la ejecutas: minúsculas, números y guiones, sin espacios. Único. |
| `descripcion` | obligatorio | Qué hace, en una frase. Sale en `acciones ver`. |
| `tipo` | obligatorio | `mover`, `copiar`, `ordenar`, `renombrar`, `borrar` o `rutina`. |
| `carpeta` | opcional | Dónde trabaja (`~/Downloads`). Sin ella, en la carpeta actual. Al ejecutar puedes darle otra. |
| `filtro` | opcional | Qué archivos se tocan (tabla de abajo). Sin filtro, todos. |
| `destino` | mover, copiar (en ordenar, opcional) | A qué carpeta van. Si no existe, se crea. Una ruta relativa se cuenta desde la carpeta de la acción. Si está en una unidad que no existe (un USB sin conectar), la acción no empieza. |
| `si_cambia` | copiar, opcional | Si en el destino ya hay uno distinto con el mismo nombre: `copia-aparte` (por defecto: guarda `nombre (1)` al lado, una sola vez) o `el-mas-nuevo` (se queda el más reciente; el viejo se guarda y `acciones versiones` lo enseña, lo recupera o lo borra). Copia primero a un temporal: si se corta a medias, no queda un archivo roto. `deshacer` no quita una copia que hayas editado después. |
| `por` | ordenar | `tipo`, `mes`, `año`, `día` o `letra`. |
| `plantilla` | renombrar | El nombre nuevo con huecos: `{fecha:%Y-%m-%d}`, `{n:03}`, `{nombre}` y `{ext}`. |
| `orden` | renombrar | En qué orden se cuenta `{n}`: `nombre` (por defecto) o `fecha`. |
| `pasos` | rutina | Las acciones que hace, en orden. No puede tener otra rutina dentro. |
| `_lo-que-sea` | opcional | Lo que empieza por `_` es una nota para ti: navaja no lo lee. |

| Tipo | Qué le pasa a cada archivo |
| --- | --- |
| `mover` | Va a `destino`. Con `recursivo`, conserva las subcarpetas. |
| `copiar` | Se copia a `destino` y el original se queda. Si la copia ya está igual (mismo tamaño y fecha), no se repite; una hora justa de diferencia cuenta como igual (el cambio de hora en un USB FAT32). |
| `ordenar` | Va a una subcarpeta según `por`, como `navaja ordena`. |
| `renombrar` | Cambia de nombre según `plantilla`, como `navaja renombra plantilla`. |
| `borrar` | Va a la papelera de navaja (se recupera con `acciones deshacer`). Necesita un filtro: sin él mandaría la carpeta entera. |
| `rutina` | No toca archivos: hace sus `pasos` uno detrás de otro y pregunta en cada uno. |

| Filtro | Ejemplo | Qué elige |
| --- | --- | --- |
| `solo` | `"imagenes"`, `"jpg,png"`, `["pdf", "docx"]` | Un tipo (imagenes, documentos, videos, audio, comprimidos, codigo, ejecutables) o extensiones. `FOTO.JPG` cuenta como jpg. |
| `contiene` | `"gemini"` | Los que llevan ese texto en el nombre, sin mirar mayúsculas. |
| `patron` | `"^(IMG\|PXL)_"` | Expresión regular sobre el nombre, sin mirar mayúsculas. En JSON la barra invertida va doble (`"\\d"`). |
| `desde` · `hasta` | `"hace 30 días"`, `"septiembre 2026"` | Fecha de modificación. `"hasta": "hace 30 días"` = los de hace más de un mes. |
| `mayor_que` | `"100MB"` | Los que ocupan al menos eso. |
| `recursivo` | `true` | Mirar también en las subcarpetas. |
| `ocultos` | `true` | Incluir ocultos y de sistema (`desktop.ini`…). |
| `excluir` | `"node_modules, build"`, `["dist"]` | Con `recursivo`, carpetas en las que no entra, se llamen así donde estén (sin mirar mayúsculas). Nombres, no rutas ni comodines. Sin `recursivo`, `validar` avisa de que no hace nada. |

Si pones varios filtros, el archivo tiene que cumplirlos todos. En Windows las rutas se
escriben con `/` (`C:/Users/sergi/Downloads` o `~/Downloads`): con `\` sueltas el JSON no
vale, y `\n` o `\t` dentro de una ruta se leerían como salto de línea o tabulador.

### Probar sin riesgo

[pruebas/acciones-prueba.json](pruebas/acciones-prueba.json) tiene las mismas acciones,
pero todo (origen y destino) dentro de `~/pruebas-navaja`. Para crear esa carpeta con
archivos de mentira en PowerShell:

```powershell
$p = "$HOME\pruebas-navaja"
New-Item -ItemType Directory -Force "$p\Descargas", "$p\Fotos" | Out-Null
"factura.pdf", "apuntes de redes.docx", "FOTO1.JPG", "cumpleaños 2.png", "Gemini_Generated_Image_1.png", "[borrador].pdf", "setup.exe", "viejo.msi" |
  ForEach-Object { New-Item -ItemType File -Force "$p\Descargas\$_" | Out-Null }
(Get-Item "$p\Descargas\viejo.msi").LastWriteTime = (Get-Date).AddDays(-40)
New-Item -ItemType File -Force "$p\Fotos\IMG_0001.jpg", "$p\Fotos\playa.jpg" | Out-Null

navaja acciones ejecutar limpieza-semanal --simular --config pruebas/acciones-prueba.json
navaja acciones ejecutar limpieza-semanal --config pruebas/acciones-prueba.json
navaja acciones deshacer
```

Siempre primero con `--simular`, y en tus carpetas de verdad solo cuando la simulación
diga exactamente lo que esperas.

Para ver los errores de `acciones validar` (siempre con código de salida 3 y sin traza),
en `pruebas/` hay cuatro archivos rotos a propósito: `roto-coma.json`, `roto-tipo.json`,
`roto-repetido.json` y `roto-regex.json`:

```powershell
navaja acciones validar --config pruebas/roto-tipo.json
$LASTEXITCODE   # 3
```

## Instalación

Con [uv](https://docs.astral.sh/uv/) (Linux, macOS y Windows), desde la carpeta del repo:

```bash
uv tool install --editable .   # deja el comando navaja disponible en cualquier carpeta
navaja --help
```

Si dice «orden no encontrada», ejecuta `uv tool update-shell` y abre otra terminal.

Para tener Tab también en PowerShell (`navaja ord` y Tab → `navaja ordena`, y lo mismo con
`nav`; también los nombres de tus acciones: `navaja acciones ejecutar us` y Tab →
`usb-a-pc`, con el `--config` que hayas escrito), una sola vez:

```powershell
navaja config autocompletar $PROFILE   # lo añade a tu perfil de PowerShell
```

Abre una terminal nueva. Si dice que la ejecución de scripts está deshabilitada:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Sin `$PROFILE`, solo enseña lo que
habría que añadir. En Linux: `navaja config autocompletar ~/.bashrc`. Dentro del modo
interactivo Tab funciona siempre, sin hacer nada.

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
- `acciones` comprueba `acciones.json` entero antes de tocar un solo archivo, enseña el plan y pregunta `[s/n]`; `--simular` solo mira y `acciones deshacer` lo revierte (una rutina, entera). Lo que borra va a la papelera de navaja.
- Nunca se sobrescribe un archivo, y se saltan los ocultos y los de sistema de Windows (`desktop.ini`, `Thumbs.db`), salvo con `--ocultos`.
- Fechas fáciles en `--desde`, `--hasta` y `ordena tramo`: `1/9/2026`, `septiembre 2026`, `2026`, `hoy`, `hace 30 días`. Un mes o un año valen enteros.
- `limpia` dice qué es cada cosa que borraría y pide confirmación; `--simular` solo mira y `--si` no pregunta. Solo borra lo que se vuelve a crear solo: `build`, `dist`, `target` y `coverage` únicamente dentro de un proyecto de programación (fuera pueden ser tuyas), y nunca `desktop.ini`. Lo que borra no va a la papelera.
- `duplicados borrar` no borra: mueve las copias a la papelera de navaja. Compara el
  contenido completo (SHA-256), no solo el nombre o el tamaño, y nunca toca el archivo
  que se conserva. El espacio solo se libera con `duplicados vaciar`.
- Las acciones para deshacer, la papelera, la base de datos de notas, `config.json` y el
  historial del modo interactivo
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

- [AGENTS.md](AGENTS.md): normas cortas que el agente lee siempre.
- [docs/arquitectura.md](docs/arquitectura.md): cómo está hecho por dentro (estructura,
  modo interactivo, ayuda, convenciones y cómo añadir comandos).
- [ESTADO.md](ESTADO.md): bitácora de lo implementado, decisiones y pendientes.
- Agente de programación: las normas están en [AGENTS.md](AGENTS.md). Para OpenCode,
  `opencode.json` y `.opencode/`; para Claude Code, `CLAUDE.md` y `.claude/`. En los dos:
  la skill `acciones-json`, el comando `/nueva-accion` y el subagente `revisor` (solo lee).
