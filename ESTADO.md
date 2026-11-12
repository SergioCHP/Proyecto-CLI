# Estado del proyecto

Bitácora de lo implementado y de lo que queda pendiente.

## Resumen

- **Producto:** `navaja`, CLI de utilidades de terminal.
- **Versión:** 0.1.0.
- **Stack:** Python 3.12+, Typer, Rich, prompt_toolkit, SQLite (stdlib), setuptools.
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

### 2026-10-30 — Identidad visual

- **Estilos con nombre:** los colores fijos (`[green]`, `[red]`…) pasan a ser
  `ok`, `error`, `aviso`, `pista`, `acento`, `titulo`, `logro`, `marco` y
  `borde`, definidos en `TEMAS` (`comun.py`).
- **Temas:** `clasico`, `morado`, `terminal` y `pastel`.
  `navaja tema listar|fijar`.
- **Configuración:** `config.json` en el directorio de datos con `nombre` y
  `tema`; `navaja config ver|nombre`. Valores inválidos vuelven al defecto.
- **Bienvenida:** `navaja` sin argumentos saluda según la hora y lista los
  comandos (se generan solos a partir de los registrados).
- **Alias `nv`** en `pyproject.toml`.
- `NAVAJA_DATOS` sustituye el directorio de datos; `tests/conftest.py` lo usa
  para que ningún test toque el real.
- 39 tests pasando en Python 3.10 y 3.13.
- Ojo en Windows con Python 3.10: si la ruta del repo tiene tildes
  (`Programación`), la instalación editable no se encuentra porque 3.10 lee
  el `.pth` como cp1252. Se arregla con `PYTHONUTF8=1`; desde 3.13 no pasa.

### 2026-11-01 — Modo interactivo y listar

- **Modo interactivo:** `navaja` sin argumentos abre un menú numerado y espera
  órdenes hasta `salir` (`interactivo.py`).
  - Un número abre el submenú del grupo o ejecuta el comando en la carpeta
    actual. Solo pregunta los argumentos obligatorios (y entonces enseña la
    orden equivalente, `→ navaja renombra previsualizar . IMG_ foto_`); debajo
    del resultado dice qué opciones tiene (`Más opciones: --mayores …`).
  - También se pueden escribir los comandos como en la terminal, sin `navaja`
    delante. Un comando con argumentos obligatorios escrito solo los pregunta.
  - `ayuda ocupa`, `ocupa ?` o `? 2`: uso del comando y sus opciones con el
    valor por defecto, en castellano.
  - `menu` vuelve a enseñar el menú. `ayuda` (o `?`) explica lo que se puede
    hacer donde estás: en el menú principal, todas las opciones y qué hay
    dentro de cada una; dentro de una opción, esa opción con cada subopción,
    su uso (tal como se escribe ahí) y sus parámetros.
  - Un submenú (`config`, `ordena`…) sigue abierto después de ejecutar algo,
    hasta Intro, `0` o `volver`. Si desde él se escribe un comando del menú
    principal (`listar`), se ejecuta y se vuelve al menú principal.
  - Trabaja en la carpeta actual, que se ve en el prompt (`Descargas>`). `cd`
    cambia de carpeta solo dentro de navaja; al salir se vuelve a la de inicio.
  - Los errores no cierran el modo interactivo. Ctrl+C cancela la pregunta o
    la orden en curso; en el prompt principal, sale.
  - Las rutas de Windows (`C:\Users\...`) y las regex conservan las barras
    invertidas; `~` se expande.
  - Si no hay terminal (scripts, tests), sigue saliendo la bienvenida de antes.
- **Manual completo:** `navaja manual` (o `manual` dentro del modo interactivo)
  explica cómo se usa navaja, el modo interactivo con todos sus atajos, todos
  los comandos y subcomandos con sus argumentos y opciones (tipo y valor por
  defecto), la seguridad, dónde se guardan los datos y los códigos de salida.
  La parte de los comandos se genera de los propios comandos de Typer, así que
  no se desfasa; `tests/test_ayuda.py` comprueba que salen todos los comandos,
  opciones y atajos y que ninguna opción se queda sin explicación.
  `navaja manual ordena aplicar` da solo ese comando. Va el último del menú
  para no cambiar los números del resto. Es una orden aparte de `ayuda`, que dentro
  del modo interactivo explica solo lo que puedes hacer donde estás, y de
  `ayuda ocupa`, la ayuda corta de un comando.
- **Confirmaciones en castellano:** `[s/n]` en vez de `[y/n]` (acepta también
  «sí», «no» e «y»), en todos los comandos.
- **Alias `nav` en vez de `nv`:** en PowerShell `nv` ya es un atajo de
  `New-Variable` y tiene prioridad sobre los programas, así que `nv ocupa`
  creaba en silencio una variable `$ocupa` en vez de abrir navaja. Hay que
  reinstalar la herramienta para que cambie el comando.
- **Nuevo:** `navaja listar [ruta] [--ocultos]`: tabla con nombre, tipo,
  tamaño y fecha; carpetas primero; carpeta inexistente → código 1.
- **`ocupa`:** la barra de uso usa los colores del tema (antes eran fijos) y
  una línea fina en vez de bloques, que en Windows Terminal formaban una mancha.
- 79 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — renombra fácil

- `renombra` deja de exigir expresiones regulares: una opción por tarea, y en
  el menú interactivo cada una pregunta solo lo que necesita.
  - `cambiar BUSCAR [POR]`: texto tal cual (vacío borra). `delante TEXTO`,
    `detras TEXTO`. `numerar NOMBRE` (`--desde`, `--cifras`, `--separador`,
    `--orden nombre|fecha`; cuenta por carpeta). `fecha` (`--formato`; no la
    repite). `arreglar` (minúsculas, sin tildes ni eñes, guiones). `plantilla
    "{fecha:%Y-%m-%d}_{n:03}{ext}"` con los mismos huecos que acciones.json.
    `avanzado PATRON REEMPLAZO` es lo de antes (regex, `--completo`). `deshacer`.
  - Un solo paso: enseña «antes → después» (solo lo que cambia y los problemas)
    y pregunta [s/n]; `--simular` solo mira. Sustituye a previsualizar/aplicar.
  - Comunes: `--carpeta/-c`, `--solo jpg,png`, `--contiene TEXTO` (solo los
    archivos cuyo nombre lo lleva, sin mirar mayúsculas), `-r`, `--ocultos`,
    `--simular`, `--si`.
  - Seguridad: no toca un archivo si dos acabarían igual, si el nombre ya
    existe o si no vale en Windows (`: * ? " < > |`). Cambiar solo mayúsculas
    (FOTO.JPG → foto.jpg) sí se permite.
  - Motor común en `renombrar()`; cada opción es una función
    `(archivo, n) -> nombre nuevo`.
- Modo interactivo: también pregunta los argumentos opcionales de texto (como
  el «por» de cambiar, con «Intro = vacío»); la carpeta sigue sin preguntarse.
  «Más opciones» dice la ayuda tal como se escribe donde estás.
- Al elegir por número también se preguntan los «ajustes» que importan (opciones
  con `rich_help_panel=AJUSTE`): en renombra, `--contiene` y `--orden`, y en
  numerar además `--separador` y `--cifras`. Intro deja el valor por defecto,
  un espacio vale como espacio y las opciones con valores fijos se validan
  («Escribe nombre o fecha»). Así se puede hacer todo desde el menú, por
  ejemplo `Gemini_Generated_Image_….png → gemini 1.png` con 4 → gemini → espacio
  → 1 → Intro → gemini.
- 96 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — ordena fácil y por fechas

- `ordena` rehecho como `renombra`: una opción por tarea y un solo paso
  (tabla «archivo → carpeta» y [s/n]; `--simular` solo mira).
  - `tipo`: Imagenes/, Documentos/, Videos/… `fecha --por mes|año|día`:
    «2026/10 octubre», «2026» o «2026-10-26». `tramo DESDE [HASTA]`: los
    archivos de unas fechas a una carpeta («del 2026-09-01 al 2026-09-30», o
    `--nombre`). `tipos` (antes categorias). `deshacer`, que ahora además quita
    las carpetas que quedan vacías. Sustituye a previsualizar/aplicar.
  - Comunes: `--carpeta/-c`, `--destino/-d`, `-r`, `--ocultos`, `--simular`, `--si`.
- Filtros comunes en `filtros.py` para ordena y renombra: `--solo` (tipos por
  nombre: imagenes, documentos, fotos…, o extensiones), `--contiene`, `--desde`,
  `--hasta`.
- Fechas como las escribe cualquiera: `1/9/2026`, `1/9`, `01-09-26`,
  `2026-09-15`, `septiembre 2026`, `9/2026`, `2026`, `hoy`, `ayer`,
  `hace 30 días` (o semanas, meses, años). Un mes o un año valen enteros. Si no
  se entiende, lo dice con ejemplos.
- Modo interactivo: en ordena y renombra, una sola pregunta «¿Con qué
  archivos?» (todos / de un tipo, con la lista de tipos / con un texto / de unas
  fechas, validadas en el momento) en vez de un filtro tras otro. «día» y «dia»
  valen igual.
- renombra numerar: `--desde` (primer número) pasa a `--empieza`, porque
  `--desde` es ahora el filtro de fecha.
- Archivos ocultos y de sistema: además de los que empiezan por punto, se saltan
  `desktop.ini`, `Thumbs.db` y los que Windows marca ocultos o de sistema
  (listar, ordena, renombra, duplicados). `--ocultos` los incluye.
- 128 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — ordena por nombre y por letra

- `ordena nombre TEXTO`: los que llevan ese texto en el nombre (sin mirar
  mayúsculas) van juntos a una carpeta que se llama como el texto, o como diga
  `--nombre`. Los demás no se tocan. Avisa si el nombre no vale como carpeta en
  Windows.
- `ordena letra`: una carpeta por inicial (A/, B/…, Ñ/), 0-9/ para los que
  empiezan por número y Otros/ si no hay letras ni números. Las tildes y los
  signos del principio no cuentan (`Álbum` → A, `_borrador` → B).
- Van detrás de `tramo` para no cambiar los números de tipo, fecha y tramo en
  el submenú. Notas en el manual y en la ayuda.
- 146 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — Volver a la pregunta anterior

- En el modo interactivo, en cualquier pregunta de cualquier opción, `volver`
  (o `atrás`) repite la anterior; en la primera, vuelves al menú sin hacer nada.
  Al empezar las preguntas se recuerda: «volver: a la pregunta anterior · Ctrl+C:
  cancelar».
- En «¿Con qué archivos?» y «¿Qué tipo?» sale `0 volver`; dentro (el texto, las
  fechas), `volver` lleva a la lista y, en «hasta», a «desde».
- Al confirmar una orden hecha desde el menú, `[s/n/volver]`: `volver` vuelve a
  la última pregunta (por ejemplo, para elegir otros archivos) sin cambiar nada.
  Fuera del modo interactivo sigue siendo `[s/n]`.
- `"volver"` entre comillas es el texto volver (por si hace falta buscarlo).
- Las preguntas guiadas pasan a ser pasos (`Paso`) en `interactivo.py`.
- 156 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — Elegir la carpeta en ordena y renombra

- Desde el menú, ordena y renombra preguntan primero «¿En qué carpeta?»
  (Intro = la actual, que se enseña con su ruta). Vale una ruta completa,
  relativa (`..\Documents`), `~\Documents` o arrastrar la carpeta desde el
  explorador. Si no existe o es un archivo, lo dice y la vuelve a pedir.
- Si en el texto del nombre se escribe una ruta (`C:\Users\...`), avisa de que
  la carpeta se elige en la primera pregunta y vuelve a preguntar.
- El plan de ordena y renombra dice en qué carpeta trabaja («En C:\...»), y
  en ordena con `--destino`, dónde se crean las carpetas.
- 160 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — renombra cambiar sin preguntas de más

- `renombra cambiar` y `avanzado` y `ordena nombre` ya no preguntan «¿Con qué
  archivos?» en el menú: el texto que se escribe ya dice qué archivos se tocan
  (los demás se quedan igual). Los filtros siguen valiendo escritos.
- `renombra cambiar` no mira mayúsculas («gemini» encuentra «Gemini_…») y acepta
  el nombre entero con su extensión: `cambiar informe.pdf final` (o `final.pdf`)
  deja `final.pdf`. La pregunta dice ahora «Qué texto del nombre quieres cambiar
  (ej.: IMG_, o el nombre entero)».
- 165 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — Repaso completo: fallos, coherencia y claridad

Fallos arreglados:

- `renombra avanzado` con un reemplazo que usa un grupo que no existe (`\\3` con
  dos paréntesis) reventaba con un traceback. Ahora lo explica y sale con código 2.
  Los errores de expresión regular más comunes salen en castellano.
- `limpia` borraba carpetas tuyas que se llamaran `build`, `dist`, `target` o
  `coverage` (por ejemplo, «Seguro/coverage» con una póliza) y `desktop.ini`.
  Ahora esas cuatro solo cuentan dentro de un proyecto de programación (si al
  lado hay package.json, pyproject.toml, Cargo.toml…) y `desktop.ini` nunca.
  El patrón `*.~` era un error: ahora `*~` (copias de seguridad de editores).
- `ocupa -n 0`, `-n -2`, `--cifras 0`… se aceptaban o daban mensajes raros:
  ahora las opciones numéricas tienen mínimo y el error lo dice en castellano.
- `renombra fecha` con un formato de fecha que no vale ya no da un error en inglés.
- Plurales: «Movidas 1 copias», «Se devolverían 1 archivos», «en 1 entradas»…
- Python 3.10: una f-string con comillas anidadas solo valía en 3.12+.

En castellano y coherente:

- `--help` (y ahora también `-h`) y los errores de uso («Missing argument»,
  «No such option», «Invalid value»…) salían en inglés. Ahora son los de navaja:
  la ayuda de un comando es su parte del manual, y un error dice qué pasa, cómo
  se escribe la orden y dónde está la ayuda. «Cancelado.» en vez de «Aborted!».
- La confirmación vuelve a ser `[s/n]` (sin «volver»): con «n» no se hace nada.
- `limpia --seco` pasa a `--simular`, como en ordena y renombra.
- `duplicados --conservar` ya no tiene `-c`: en ordena y renombra `-c` es la carpeta.
- `tema listar` / `tema fijar` pasan a `tema ver` / `tema elegir`; `config` dice
  ahora dónde están todos tus datos.
- Los consejos con una orden («Para deshacerlo: …») llevan «navaja» delante en la
  terminal y no dentro del modo interactivo (antes iba al revés en unos y otros).
- `--ocultos` dice lo mismo en todos los comandos.
- La bienvenida (sin terminal) sigue el mismo orden que el menú.

Más claro:

- `limpia` dice qué es cada cosa («caché de Python», «paquetes de Node»…) y que no
  va a la papelera; `listar`, `limpia`, `duplicados` y los planes dicen en qué
  carpeta trabajan; `listar` ya no corta la ruta a la mitad y ordena sin mirar tildes.
- `renombra`: si el texto no está, «Ningún nombre lleva «xyz».» sin tabla; si un
  nombre no vale, dice por qué («no puede llevar /») y enseña el nombre que saldría.
- `ordena tramo` de un solo día crea «2026-11-01» y no «del 2026-11-01 al
  2026-11-01»; si «desde» va después de «hasta», dice las dos fechas.
- `duplicados buscar` termina con la orden exacta para borrar esas copias.
- `notas agregar TÍTULO [CONTENIDO]`: si el contenido empieza por https:// o www.
  es un enlace (ya no hace falta `--url`); las etiquetas se preguntan en el menú.
  `notas buscar` no mira tildes. `notas listar` enseña la dirección de los enlaces.
  Si una nota no existe, dice dónde ver los números.
- Modo interactivo: `limpia` y `duplicados borrar` también preguntan la carpeta;
  `duplicados` pregunta si mirar las subcarpetas y cuál conservar; `notas abrir` y
  `notas borrar` enseñan la lista antes de pedir el número; «salir» en una pregunta
  cancela sin hacer nada.
- Se quitan las referencias a un `acciones.json` que ya no existe.
- 187 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — Tu nombre la primera vez

- El nombre por defecto ya no es «Sergio» para todo el mundo. Sin nombre guardado,
  navaja te llama por tu usuario del sistema (en Windows, «sergi» → «Sergi»).
- La primera vez que abres el menú pregunta «¿Cómo quieres que te llame?» (Intro =
  tu usuario) y lo guarda en config.json: ya no vuelve a preguntar. Si se cancela,
  usa el usuario sin guardarlo y lo pregunta la próxima vez.
- `config nombre` lo cambia para siempre; `config ver` dice si el nombre es el
  tuyo guardado o tu usuario del sistema.
- 192 tests pasando en Python 3.10 y 3.13.

### 2026-11-01 — Acciones en acciones.json

- **Nuevo:** `navaja acciones ver|ejecutar|validar|editar|deshacer`. Una acción es una
  tarea con nombre escrita en `acciones.json`; el archivo dice qué hacer y el motor lo
  hace. Añadir una acción no toca el código.
- **Tipos:** `mover`, `copiar`, `ordenar` (reutiliza `ordena`), `renombrar` (reutiliza
  `renombra plantilla`), `borrar` (a la papelera de navaja, necesita filtro) y `rutina`
  (varias acciones seguidas, sin rutinas dentro).
- **Filtro:** `solo`, `contiene`, `patron`, `desde`/`hasta` (fechas fáciles),
  `mayor_que`, `recursivo` y `ocultos`.
- **Dónde:** el `acciones.json` de la carpeta actual o, si no hay, el de los datos;
  `--config RUTA` para otro. `acciones editar` lo crea si no existe y lo comprueba al cerrar.
- **Validación antes de ejecutar** (`esquema.py`): todo el archivo, con mensajes «Acción
  «x», campo «y»: motivo» en castellano y sugerencias («¿Querías decir «mover»?»). JSON
  roto con línea, columna y qué pasa (coma de más, `\` suelta de una ruta de Windows,
  BOM del Bloc de notas, archivo que no es UTF-8). Campos desconocidos o de otro tipo
  son error (un `fitro` mal escrito no puede convertirse en «todos los archivos»).
- **Excepciones propias** (`errores.py`): `NavajaError` (código 1), `ConfigError`
  (código 3) y `AccionNoValida(accion, campo, motivo)`. La CLI las captura una vez.
- **Clases** (`acciones.py`): `Accion` con registro de tipos (`__init_subclass__`) y
  fábrica `desde_config`; `AccionDeArchivos` con `planificar` (no toca el disco) y
  `ejecutar`; una subclase por tipo. `Motor` (`motor.py`) elige carpeta y archivos.
- **Seguridad:** plan y `[s/n]` siempre; `--simular` no crea ni carpetas; nunca
  sobrescribe («(1)»); copiar no repite lo ya copiado; `acciones deshacer` revierte la
  última (una rutina, entera) y quita las carpetas que quedan vacías.
- `acciones.json` del repo con 5 acciones (ordenar-descargas, imagenes-ia,
  instaladores-viejos, fotos-con-fecha y la rutina limpieza-semanal) y
  `pruebas/acciones-prueba.json` con las mismas dentro de `~/pruebas-navaja`.
- Manual: sección «acciones.json» con el esquema (`manual acciones` también la enseña)
  y código de salida 3.
- 262 tests pasando en Python 3.10 y 3.13.

### 2026-11-05 — Al día con las instrucciones nuevas (sesiones 1 y 2)

- **AGENTS.md corto:** solo stack, órdenes y normas (lo que el agente lee siempre). El
  detalle técnico pasa a `docs/arquitectura.md` y el reparto del código de acciones, a
  la skill `acciones-json` (las dos copias).
- **opencode.json:** el agente `explore` tampoco puede editar, como `plan`.
- **`navaja version`:** orden oculta (no cambia los números del menú) que hace lo mismo
  que `--version`.
- **Python 3.12+:** `requires-python = ">=3.12"`, `.python-version` con 3.12 y
  `uv.lock` regenerado. Hay que reinstalar: `uv tool install --editable . --force`.
- 270 tests pasando en Python 3.12.

### 2026-11-05 — `--config` antes de la orden

- `navaja acciones --config RUTA ver|ejecutar|validar|editar`, como lo escribe el
  profesor (opción del grupo, guardada en `ctx.obj`). La forma de antes,
  `navaja acciones validar --config RUTA`, sigue valiendo; si van las dos, gana la de
  la orden, que es la más concreta.
- 273 tests pasando en Python 3.12.

### 2026-11-05 — Tab y ↑ ↓

- **Modo interactivo** (`entrada.py`, con prompt_toolkit): Tab completa comandos,
  subcomandos, opciones y rutas según dónde estás (en un submenú, también los del menú
  principal); con varias posibilidades enseña una lista. ↑ ↓ recuperan lo escrito, también
  de otras veces (`historial.txt` en el directorio de datos). Las preguntas guiadas tienen
  su propio historial y Tab completa rutas. Si prompt_toolkit no puede usar la terminal
  (por ejemplo, Git Bash), se lee como antes.
- **En PowerShell y bash:** `navaja config autocompletar $PROFILE` añade al perfil el
  script de Typer para `navaja` y `nav` (una sola vez; no toca un perfil en UTF-16 ni
  cambia la política de ejecución). Sin perfil, solo lo enseña. `app.py` llama a
  `completion_init()` para que Typer conteste a PowerShell aunque `add_completion=False`.
- Primera dependencia nueva desde Typer y Rich: `prompt_toolkit`.
- Hay que reinstalar: `uv tool install --editable . --force`.
- **Arreglo de velocidad:** dentro de navaja cada orden tardaba 1 segundo de más: tras
  cada Intro, prompt_toolkit preguntaba a la terminal dónde está el cursor y, si no
  contestaba, esperaba 1 s. Ahora no lo pregunta (`PROMPT_TOOLKIT_NO_CPR`): de ~1 s a
  0,03 s. `NAVAJA_SIN_TAB=1` lee como antes, sin prompt_toolkit (para comparar).
- **`ocupa`** recorre la carpeta una sola vez aunque se pida `-p 2` o más (antes medía
  varias veces lo mismo) y enseña «Midiendo…» mientras trabaja: en la carpeta personal
  tarda porque tiene muchísimos archivos (AppData, OneDrive…), no porque se cuelgue.

### 2026-11-10 — USB de clase ↔ PC

- **Acciones `usb-a-pc` y `pc-a-usb`** (tipo `copiar`, `si_cambia: el-mas-nuevo`):
  `D:/DAM` ↔ `~/Documents/ESTUDIO/DAM`, con subcarpetas. Lo que ya está igual en el otro lado
  se salta; si un archivo es distinto, gana el más reciente. También en
  `pruebas/acciones-prueba.json` (`~/pruebas-navaja/USB/DAM` y `~/pruebas-navaja/PC/DAM`).
- **`copiar` con `si_cambia`** (tras la revisión del revisor):
  - Antes, un archivo distinto en el destino creaba una «(n)» nueva **en cada ejecución**
    (y en la ida y vuelta se multiplicaban). Ahora, con `copia-aparte` (por defecto) se
    salta si ya hay una «(n)» igual al lado.
  - `el-mas-nuevo`: si el de origen es más reciente, sustituye al del destino y el viejo va a
    la papelera de navaja; si el del destino es más reciente (o tienen la misma fecha), no
    se toca. El plan marca «(sustituye a la versión vieja)» y `acciones deshacer` la devuelve.
  - Una hora justa de diferencia cuenta como la misma fecha: tras el cambio de hora, Windows
    ve movidas una hora todas las fechas de un USB en FAT32 (como `robocopy /DST`).
- **Destino en una unidad que no existe** (USB sin conectar): `mover` y `copiar` se paran
  antes de empezar, y `validar` lo avisa. Si en `D:` hay otro disco, no hay forma de saberlo.
- **Nuevo en el filtro: `excluir`**: con `recursivo`, carpetas en las que no entra, se
  llamen así donde estén (`"node_modules, __pycache__"` o una lista; sin mirar
  mayúsculas). Se corta en `iterar_archivos`, así que ni recorre `node_modules`. Al validar
  son error una ruta, una unidad (`C:`), un comodín o un `excluir` vacío; sin `recursivo`,
  aviso. En una lista también se parte por comas.
- **Plan más legible:** si `mover` o `copiar` llevan a una carpeta de fuera, el recuadro lo
  dice una vez («A ~\…\PC\DAM») y la columna «Copia en» / «Va a» solo lleva la ruta desde
  allí (`Programacion\tema3.txt`), en vez de repetirla entera en cada fila.
- Probado en simulación con `pruebas/acciones-prueba.json`: archivo nuevo en cada lado,
  editado en casa, editado en clase, igual, igual con una hora de diferencia, distinto con
  la misma fecha, y `node_modules` / `__pycache__` / `Build` / `.vscode` fuera.
- El test que contaba las acciones de `acciones-prueba.json` ahora las cuenta del archivo.
- **Segunda revisión del revisor (que no se pierda nada):**
  - `copiar` copia a un temporal oculto (`.nombre.navaja-copiando`) y solo al final le pone
    el nombre: si el USB se llena o se desconecta, no queda un archivo a medias con fecha de
    ahora que «el-mas-nuevo» tomaría por bueno.
  - Si falla y ni siquiera se puede devolver la versión vieja, el error dice en qué carpeta
    de la papelera está.
  - `acciones deshacer` solo quita una copia si sigue idéntica al original (si la editaste
    después, la deja y avisa), y la manda a la papelera en vez de borrarla. Si la versión
    vieja ya no está en la papelera, lo dice antes de preguntar y deja la copia.
  - Si `deshacer` falla con algún archivo, guarda esos registros para volver a intentarlo
    (antes se borraba el registro igualmente).
- **Manual** (`navaja manual acciones`): `si_cambia` y `excluir` salen de `DOC_CAMPOS` /
  `DOC_FILTRO`; las notas de `acciones ejecutar` y `acciones deshacer` explican el más nuevo,
  la unidad que no existe y el deshacer que no pisa ediciones.
- **Dentro de navaja** (modo interactivo) funciona igual: test que copia, simula la vuelta
  y deshace desde el bucle (`tests/test_interactivo.py`).
- `docs/arquitectura.md`: convención «sustituir sin perder nada».
- 311 tests pasando.

### 2026-11-10 — Tab con los nombres de las acciones

- `acciones ejecutar` y Tab completa los nombres de tus acciones, con su descripción
  recortada (si se partiera en dos líneas, PowerShell sacaría una sugerencia suelta). Usa el
  `--config` ya escrito (en la orden o en el grupo); con un acciones.json roto no sugiere nada.
- Igual en los tres sitios: PowerShell/bash (`autocompletion=nombres_para_tab`), el prompt
  de navaja (`entrada.palabras_del_argumento`, que pregunta al propio parámetro: vale para
  cualquier argumento con autocompletado) y la pregunta guiada «Nombre de la acción», que
  además enseña «Puedes elegir: …».
- Detrás del nombre, Tab vuelve a completar rutas (la CARPETA).
- Manual, README y arquitectura al día. 316 tests pasando.

### 2026-11-10 — Git Bash sin trazas de codificación

- En Git Bash (o con la salida redirigida) Python escribía en cp1252 y `✔`, `→` o `…`
  rompían navaja con una traza (`UnicodeEncodeError`); las tildes salían como `acci�n`.
- `comun.preparar_salida()`, llamada en `main()` para stdout y stderr: si ya es UTF-8 no
  toca nada; en Git Bash (`MSYSTEM`) pasa a UTF-8 (símbolos y tildes bien); en lo demás
  (`navaja … > a.txt` en PowerShell) conserva la codificación y lo que no cabe sale «?».
- 319 tests pasando.

### 2026-11-10 — `--destino` al ejecutar

- `navaja acciones ejecutar NOMBRE [CARPETA] --destino RUTA` (`-d`, como en `ordena`): lleva
  los archivos a otro sitio solo esa vez, sin tocar acciones.json. Si el USB sale con otra
  letra: `pc-a-usb --destino E:/DAM` (y `usb-a-pc E:/DAM`, que cambia la carpeta).
- Vale con mover, copiar y ordenar (`AccionDeArchivos.con_destino`, sin `if tipo ==`). Con
  renombrar o borrar, o con una rutina (llevaría todos los pasos al mismo sitio), error
  claro y código 1. Una ruta relativa se cuenta desde donde estás.
- El aviso de «USB sin conectar» sugiere `--destino`; Tab completa rutas tras `--destino`.
- Manual, README, notas de los JSON y skill al día. 324 tests pasando.

### 2026-11-10 — Sin traza al cortar la salida con una tubería

- `navaja acciones validar | head -1` (o `| Select-Object -First 1`) soltaba a veces una
  traza: en Windows, escribir en una tubería que ya se cerró da `OSError: [Errno 22]` en
  vez de `BrokenPipeError`, y Rich solo maneja el segundo. Reproducido 5 de 5 veces cerrando
  la tubería a propósito.
- `main()` lo captura (`tuberia_cerrada()`): `BrokenPipeError`, o el 22 solo si la salida
  de verdad no se puede vaciar (el mismo número sale con una ruta mala, y ese error no se
  traga). Manda lo que queda a la nada (`silenciar_salida()`, si no Python avisa al
  cerrar) y sale con 1. Tras el arreglo, 0 de 10.
- 327 tests pasando.

### 2026-11-10 — Versiones viejas: que no se pierdan y que se puedan borrar

- Antes, lo que sustituía «copiar» con «el-mas-nuevo» iba a la papelera común: solo
  `acciones deshacer` lo devolvía, y solo hasta la siguiente acción; y `duplicados vaciar`
  lo borraba sin decir que era de `acciones`.
- Ahora va a `versiones/` en los datos, con un índice (`navaja/versiones.py`: de dónde
  salió, cuándo y qué acción lo sustituyó). El índice se limpia solo (lo que ya no está no
  se lista) y, si se rompe, los archivos siguen ahí.
- Grupo nuevo `acciones versiones` (`comandos/versiones.py`):
  - `ver`: lista numerada con archivo, dónde estaba, cuándo, qué acción y tamaño.
  - `recuperar 1 3`: las devuelve a su sitio; si allí hay un archivo, la deja al lado
    como «nombre (1)», sin pisar nada.
  - `borrar [números] [--hasta "hace 30 días"]`: borra para siempre (todas, unas o las
    antiguas), enseñando cuáles y cuánto ocupan y preguntando.
  - Tab completa los números con el nombre del archivo; también por menú dentro de navaja.
- `duplicados vaciar` ya no las toca. `acciones deshacer` sigue devolviendo la vieja; si
  la borraste, lo dice y deja la copia.
- `bonita()` pasa de `mis_acciones.py` a `comun.py` (ahora la usan dos módulos).
- Manual, README, notas de los JSON, skill y arquitectura al día. 338 tests pasando.

### 2026-11-10 — Modo guiado: no pregunta si no hay nada que elegir

- Por menú, `acciones ejecutar` enseña antes la lista (`acciones ver`) para elegir por
  número. Sin acciones.json (navaja abierto fuera del proyecto), la lista fallaba con «No
  encuentro acciones.json» y aun así preguntaba «Nombre de la acción». Ahora, si la lista
  previa falla, vuelve al submenú (igual en `notas abrir` / `notas borrar`).
- acciones.json se queda en la carpeta del proyecto: navaja se usa desde ahí.
- Submenú de `acciones` en otro orden: primero lo de cada día (ver, ejecutar, deshacer,
  versiones) y abajo lo de mantener el archivo (editar, validar). Sale así en el menú,
  en `--help` y en el manual, porque se generan del orden de `registrar()`.
- 339 tests pasando.

### 2026-11-12 — Menú en tres grupos: herramientas, lo que repites y navaja

- En el menú principal salían 11 opciones seguidas y no se veía por qué unas están del 1 al
  7 y otra es «acciones». Ahora van en tres grupos, cada uno con una frase:
  **Herramientas** (1-7, se usan al momento), **Lo que repites** (acciones: recetas de
  acciones.json) y **navaja** (tema, config, manual). Igual en `navaja --help` y en la
  bienvenida sin terminal. Los números no cambian.
- Cada comando dice su grupo con `rich_help_panel` al registrarse; los nombres y las
  frases están en `comun.py` (`SECCIONES`). `ayuda.por_secciones()` los reparte sin
  reordenar (corta cuando cambia el grupo), así que el número de cada opción sigue
  siendo su posición en `subcomandos()`.
- Los submenús no tienen grupos: salen como antes.
- 342 tests pasando (3 nuevos en `test_ayuda.py`).

### 2026-11-12 — Barra de progreso al hacer una acción

- Copiar varios GB al USB (`usb-a-pc`, `pc-a-usb`) tardaba minutos sin decir nada. Ahora
  `acciones ejecutar` enseña una barra: el archivo en curso, «N de M», porcentaje y
  tiempo transcurrido. Sale en todas las acciones de archivos; en las rápidas (mover en
  el mismo disco) apenas se ve.
- Avanza por tamaño, no por número de archivos. Se borra al terminar y fuera de una
  terminal (salida redirigida, tests) no sale.
- No enseña el tiempo que queda: Rich lo calcula con la velocidad de los primeros
  archivos y, si son pequeños, sale disparatado (119 horas).
- `AccionDeArchivos.ejecutar(plan, avance)`: `avance` se llama con el origen antes de
  cada archivo. Las acciones no saben nada de la pantalla; la barra está en
  `comun.barra_de_archivos`.
- Un archivo grande no mueve la barra hasta acabar (`shutil.copy2` no avisa por el
  camino); el nombre en pantalla y el reloj enseñan que sigue trabajando.
- 345 tests pasando (3 nuevos en `test_acciones.py`).

### 2026-11-12 — Ctrl+C en mitad de una acción

Con la barra se ve avanzar una copia larga y es más fácil cortarla. Ctrl+C dejaba tres
cosas mal:

- El temporal oculto `.nombre.navaja-copiando` en el destino. `Copiar.aplicar` ahora
  limpia también con Ctrl+C (no solo con `OSError`) y devuelve la versión vieja si ya
  la había apartado. Si no puede devolverla, no lanza su `OSError`: taparía el corte y
  la copia seguiría con el siguiente archivo.
- Las versiones viejas ya apartadas no se apuntaban: `acciones versiones` no las
  listaba. Ahora `Copiar.ejecutar` las apunta en un `finally`.
- Lo copiado en ese paso no se guardaba para `acciones deshacer`. Ahora se guarda antes
  de cortar y avisa: «Cortado a medias: 1 archivo copiado antes de cortar. Para deshacer
  lo hecho: navaja acciones deshacer».
- Sale con código 130, como cualquier programa cortado con Ctrl+C.
- 349 tests pasando (4 nuevos en `test_acciones.py`).

### 2026-11-12 — Barra de progreso: lo que vio el revisor

- Colores del tema: el porcentaje y el reloj salían en magenta y amarillo (los de Rich).
  Ahora el porcentaje lleva `pista` en su formato, el fondo de la barra `borde`, y el
  reloj se pinta con `pista` mientras dura la barra (`console.use_theme`).
- Nombres largos: se partían en varias líneas y la barra cambiaba de altura. Ahora el
  nombre es la única columna que encoge (`ratio=1`, `expand=True`) y se corta con «…».
  Con solo `no_wrap`, Rich apretaba las demás columnas y la cuenta salía como «2…».
- Spinner de rayitas en la consola clásica de Windows (el de puntos es braille).
- En Git Bash no sale la barra (Python no ve una terminal); apuntado en el README.
- 350 tests pasando (1 nuevo: barra a 60 columnas con el tema pastel).

### 2026-11-12 — `navaja copia`: copiar una vez sin crear una acción

- `navaja copia a DESTINO` copia los archivos de la carpeta actual (o `-c CARPETA`) a
  otra, con los filtros de siempre (`--solo`, `--contiene`, `--desde`, `--hasta`, `-r`,
  `--ocultos`), `--simular`, `--si` y `--si-cambia copia-aparte|el-mas-nuevo`.
  `navaja copia deshacer` quita lo copiado la última vez.
- Por dentro es una acción `copiar` hecha al momento (`Accion.desde_config` + `Motor`):
  la misma copia segura, las versiones viejas en `acciones versiones`, la barra y Ctrl+C.
  Su deshacer tiene su propio registro («copia»), separado del de `acciones`.
- De `acciones ejecutar` salen dos funciones para compartir: `hacer()` (barra, Ctrl+C,
  fallos y guardar para deshacer) y `deshacer_registro()`.
- Va en «Herramientas» (7) y el menú pasa a 12 opciones. En el modo guiado pregunta
  carpeta, destino, si cambia y «¿Con qué archivos?».
- Solo copia (no `mueve`): mover suelto ya lo hacen `ordena` y `renombra` en casi todo.
- 359 tests pasando (9 nuevos en `test_copia.py`).

### 2026-11-12 — `copia` de archivos concretos

- `navaja copia a DESTINO horario.pdf "tema 3.docx" *.pdf`: solo esos archivos. Sin ruta
  se buscan en `-c` (por defecto, la actual); cada uno va al destino con su nombre, sin
  subcarpetas. Mismo plan, barra y `copia deshacer`.
- Los comodines los expande `copia` en la carpeta de `-c`: igual en PowerShell (que no
  los expande), en bash y dentro de navaja.
- Se para, con un mensaje y sin traza: un archivo que no está, un comodín sin
  coincidencias, una carpeta (dice que use `-c`), dos con el mismo nombre (se pisarían)
  y archivos mezclados con filtros (`--solo`, `-r`…).
- `main()` llama a la app con `windows_expand_args=False`. Click, en Windows, expandía
  `*` en la carpeta actual antes de que el comando lo viera: chocaba con `-c` y podía
  estropear un patrón con `*` de `renombra`. En bash el shell expande igual que antes.
- Por menú no cambia nada: las listas opcionales no se preguntan, sigue siendo la carpeta.
- 364 tests pasando (4 nuevos en `test_copia.py`, 1 en `test_salida.py`).

### 2026-11-12 — `copia` guiada: carpeta o archivos de una lista

- Por menú, `copia a` pregunta primero «¿Qué quieres copiar?»: 1 toda una carpeta (o
  parte, con «¿Con qué archivos?») o 2 unos archivos de una lista. Con 2 enseña los de
  la carpeta numerados, con su tamaño, y se eligen con `1 3`, `2-5`, `1,4` o por
  nombre o patrón (`*.pdf`). Un número que no está se vuelve a preguntar; una carpeta
  sin archivos devuelve a «¿En qué carpeta?».
- «¿A qué carpeta?» y «Si allí ya hay uno distinto…» (1 al lado como «nombre (1)» / 2 el
  más reciente) con texto propio, corto, en vez de la ayuda de `--help`.
- `guiado` admite preguntas propias por orden (`PREGUNTAS_PROPIAS`) y preguntas que no
  tocan (devuelven `None`): se saltan, también al escribir «volver».
- 369 tests pasando (6 del modo guiado en `test_copia.py`).

### 2026-11-12 — Copiar a una carpeta que no existe

- Sergio copió por menú a `sergi/Descargas` desde `Documents`: al ser relativa, navaja
  creó `Documents\sergi\Descargas` y copió allí, sin avisar. (Y en Windows la carpeta de
  descargas se llama `Downloads`: «Descargas» es solo lo que enseña el Explorador.)
- Ahora el plan dice siempre «A <ruta entera>», también si queda dentro de la carpeta de
  origen, y añade «(no existe: se creará)». Vale para `copia` y para las acciones.
- En el modo guiado, si el destino no existe lo dice con su ruta entera y pregunta:
  crearla ahí, escribir otra o, si el nombre es Descargas, Documentos, Escritorio,
  Imágenes, Música o Vídeos, usar la de verdad (`~\Downloads`…).
- 372 tests pasando (3 nuevos en `test_copia.py`).

### 2026-11-12 — Elegir la carpeta de destino, guiado

- Sergio: «¿A qué carpeta?» con un ejemplo de USB no ayudaba; quería elegirla fácil,
  con Tab. Ahora es una lista: Documentos, Descargas, Escritorio, Imágenes, Música y
  Vídeos (las que existen, con su ruta de verdad: `~\Documents`…), los USB y discos
  conectados (`os.listdrives()` + `GetDriveTypeW` en Windows; `/media/<usuario>` y
  `/Volumes` en Linux y macOS) y «Esta carpeta». También se puede escribir una ruta; si
  empieza por un nombre en castellano (`documentos\ESTUDIO`) se traduce al de verdad.
- Al elegir un sitio se entra en él (`navegar`): Intro copia ahí, un número entra en una
  subcarpeta, `..` sube, `+` pide el nombre de una nueva y 0 vuelve a la lista.
- Tab en estas preguntas (`Lector.con_carpetas` en `entrada.py`): completa los nombres
  en castellano y las carpetas del sitio en el que estás (o de la ruta que escribes).
- 374 tests pasando (2 nuevos en `test_copia.py`: bajar por la lista y subir, y
  «documentos\ESTUDIO» escrito con carpeta nueva).

## Decisiones técnicas

- **Typer + Rich** por rapidez de desarrollo y buena salida en terminal.
- **SQLite** para notas: sin dependencias extra y con consultas por etiqueta.
- **JSON en el directorio de datos** para el deshacer de `ordena` y `renombra`;
  solo se guarda la última operación.
- **Papelera propia para `duplicados`** en vez de borrar: es la única forma de
  poder deshacer un borrado sin añadir dependencias (como `send2trash`).
- **Sin dependencias más allá de Typer/Rich**: la lógica usa stdlib. Excepción:
  `prompt_toolkit` para Tab y el historial del modo interactivo, porque `readline` no
  existe en Windows y la consola de Windows no completa.
- **Temas de Rich con estilos semánticos**: los comandos dicen qué es cada
  texto (`[ok]`, `[aviso]`) y el tema decide el color; cambiar paleta no toca
  los comandos.
- **Modo interactivo sin lista propia de comandos:** el menú y las preguntas
  se generan a partir de los comandos de Typer, así que no hay que mantener dos
  sitios. Los comandos siguen funcionando igual desde la terminal (códigos de
  salida, scripts, tests).
- **Comandos en castellano** y opciones cortas coherentes (`-n`, `-p`, `-e`,
  `-r`, `-s`).
- **Acciones en un archivo externo (acciones.json)** y no en código: añadir o
  cambiar una acción no exige programar ni reinstalar. Razones y alternativas en
  `docs/adr/0001-configuracion-externa.md`.

## Pendientes / ideas

- [ ] **Que se entienda la diferencia entre herramientas y acciones** (A y B hechas el 2026-11-12) (Sergio, 2026-11-10:
  «no sé por qué unas opciones están del 1 al 7 y otras en acciones»). Del 1 al 7 son
  herramientas que se usan al momento diciéndoles qué hacer; las acciones son recetas
  guardadas en acciones.json para repetir con una palabra; 9-11, ajustes y ayuda. El
  menú no lo enseña: son 11 opciones seguidas al mismo nivel. Ideas, de menos a más
  trabajo:
  - [x] **A. Agrupar el menú** en «Herramientas» (1-7), «Lo que repites» (acciones) y
    «navaja» (tema, config, manual), con `rich_help_panel` para que `--help` salga igual.
    Empezar por esta.
  - [x] **B. `navaja copia` suelto**: hoy copiar y mover solo existen como acciones, así que
    para copiar una vez hay que crear una acción.
  - **C. «Guardar como acción»** desde una orden (`navaja ordena tipo ~/Downloads --guardar
    ordenar-descargas`), para pasar de herramienta a receta sin escribir el JSON a mano.
- [x] Buscar duplicados por contenido.

- [ ] `--json` en `ocupa` y `notas listar` para scripting.
- [ ] Exportar notas a Markdown o HTML.
- [ ] Comando `tarea` (tareas pendientes) reutilizando la base de notas.
- [ ] Historial de deshacer (varias operaciones, no solo la última).
- [x] ADR-0001 (por qué acciones.json) y `docs/prompts.md`.
- [ ] Mejoras que dejó el revisor (de `src/navaja/motor.py`) y no he arreglado todavía:
  - `filtros.py:256`: el `stat()` del filtro de fechas no está protegido. Si un archivo
    desaparece mientras se elige (una descarga a medias), sale una traza. Es muy raro y
    no hace daño: no se toca nada ni se pierde nada.
  - `motor.py:112`: `except ValueError` es demasiado amplio y el mensaje no dice qué
    campo falla. Hoy solo lo provocan plantillas de nombre malas, que ya se comprueban
    antes al validar; tocarlo ahora arriesga más de lo que arregla.
- [ ] En una rutina simulada, cada paso se calcula con la carpeta como está ahora (no
  con lo que habrían cambiado los pasos de antes).
- [x] Autocompletado de shell.
- [x] Acción `copiar` para pasar los archivos de clase del USB al PC de casa (y al revés).
- [x] `--destino` al ejecutar.
- [x] Traza al cortar la salida con una tubería (`| head -1`).
- [ ] De la segunda revisión de `copiar`, sin arreglar:
  - «el-mas-nuevo» se fía del reloj de cada PC; y con el desfase de una hora de FAT32, si
    los dos lados se editaron con menos de una hora de diferencia, puede ganar el viejo (va
    a la papelera, no se pierde).
  - La hora justa de tolerancia vale en cualquier disco: dos archivos distintos del mismo
    tamaño con 3600 s de diferencia se darían por iguales (muy raro).
  - `comprobar_destino` no sirve en Linux/macOS (la raíz «/» siempre existe: un USB sin
    montar se copiaría al disco interno) ni distingue otro USB que coja la misma letra.
  - En `pc-a-usb` la versión vieja del USB va a la papelera de C: (lento; un archivo de
    solo lectura falla).
- [x] Ctrl+C en mitad de una copia: temporal, versiones y deshacer.
- [ ] `excluir` compara el nombre tal cual: en macOS un nombre con tildes en NFD no coincide
  con el del JSON (en NFC).
- [x] Traza `UnicodeEncodeError` con `✔` o `→` en Git Bash o con la salida redirigida.
- [ ] `navaja busca` (texto dentro de archivos), `navaja extrae` / `navaja comprime` y cambiar
  formatos de imagen o documentos (órdenes previstas en la spec).
- [ ] Mejoras de la revisión del `--config` del grupo: que «Uso:» de `navaja acciones`
  enseñe `[--config RUTA]`, y permitir también `acciones --config * validar` en los
  permisos del agente.
- [ ] Que el agente no pueda ejecutar acciones en ningún caso (ahora pide permiso).
- [ ] Linter/formateador (ruff) y CI (GitHub Actions).
- [ ] Empaquetado y publicación (pipx / PyPI).

## Cómo comprobar el estado

```bash
uv run --extra dev pytest
uv run python -m compileall -q src tests
uv run navaja --help
```
