# Estado del proyecto

Bitácora de lo implementado y de lo que queda pendiente.

## Resumen

- **Producto:** `navaja`, CLI de utilidades de terminal.
- **Versión:** 1.2.1 (ver [CHANGELOG.md](CHANGELOG.md)).
- **Stack:** Python 3.12+, Typer, Rich, prompt_toolkit, SQLite (stdlib), setuptools, uv.
- **Estado:** funcional; tests y ruff en verde en Ubuntu, Windows y macOS (GitHub Actions).

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

### 2026-11-12 — `copia`: lo que vio el revisor

- **`~` fuera de navaja volvía a fallar** (lo rompió `windows_expand_args=False`): Click,
  además de `*`, expandía `~` y `%VARIABLES%`, y cmd y Windows PowerShell no lo hacen. Ahora
  `main()` los expande él en Windows (`argumentos_de_windows`) y sigue sin tocar `*`.
- Archivos que empiezan por «-» («-borrador.txt»): por menú, el destino y los archivos
  van al final de la orden, detrás de `--`.
- Dentro de una carpeta, escribir «Documentos» ya no te lleva a `~\Documents`: solo se
  traduce en la primera pregunta (`interpretar_carpeta(..., traducir=False)`).
- `copia a` con un destino que es un archivo, en una unidad que no está (con un consejo
  que vale para `copia`, no `--destino`) o igual que el origen: lo dice antes del plan.
- Lista de archivos: 0 vuelve; las comas solo separan números («1,4»), así que «"Factura
  1,5.pdf"» vale; «5-2» dice que va al revés; un nombre que no está se avisa ya, sin
  perder las respuestas.
- Al elegir la carpeta: una que no se puede leer lo dice; «..» en la raíz avisa; el
  nombre de una carpeta nueva se comprueba (sin `: * ? …`, ni CON, NUL…, ni acabar en
  punto); si una subcarpeta se llama como un número, dice cómo entrar (`.\2026`).
- `es_numero()`: solo cifras 0-9 («²» es dígito para Python y `int()` fallaba).
- 383 tests pasando (8 nuevos en `test_copia.py`, 1 en `test_salida.py`).

### 2026-11-12 — Rótulo de bienvenida

- Al abrir navaja, antes del saludo sale «NAVAJA» en letras grandes con sombra, al estilo
  de OpenCode (`src/navaja/logo.py`). Dos tonos que siguen al tema: los bloques con
  `titulo` y la sombra con `marco`. El saludo y la versión van debajo, sin recuadro.
- Si la terminal tiene menos de 51 columnas o no escribe UTF-8 (salida redirigida en
  PowerShell), sale el recuadro sencillo de antes en vez de un dibujo roto.
- 387 tests pasando.

### 2026-11-13 — Menú más visual

- El menú del modo interactivo va en recuadros redondeados, uno por sección, con el
  título a la izquierda y lo que la distingue abajo a la derecha. En un submenú, un solo
  recuadro con el nombre del comando.
- Los números van en negrita con un color propio (estilo nuevo `boton` en los cuatro
  temas; al principio llevaban fondo, pero el cian salía azul y no se leían) y todos los
  recuadros quedan alineados (mismo ancho, hasta 80 columnas).
- Cada opción cabe en una fila: el menú tiene su propia frase corta (`CORTO`, como mucho
  `LARGO_MENU` = 46 caracteres) para las que tienen una ayuda larga; `--help` y el manual
  siguen con la entera. En una ventana más estrecha la frase se acorta con «…», pero el
  número y el nombre no se recortan nunca. `test_ayuda` falla si una frase nueva no cabe.
- Iconos delante de cada comando y sección (`ICONOS` en `interactivo.py`): emojis de un solo
  carácter, sin U+FE0F, para que Rich y la terminal midan igual. Solo con UTF-8 y, en
  Windows, con Windows Terminal o VS Code (`WT_SESSION` / `TERM_PROGRAM`).
- Revisión del revisor:
  - En un submenú las opciones no llevan icono: «listar» de notas salía con el 📂 del
    «listar» de navaja y torcía la columna.
  - `comun.es_utf8()` reconoce `utf_8`, `UTF8`…, y la usan el rótulo y los iconos.
  - El rótulo grande solo sale en una terminal; con la salida a un archivo o a una tubería,
    el recuadro sencillo.
  - Los anchos se miden en columnas (`cell_len`) y los recuadros no bajan de 30 columnas.
  - `NAVAJA_SIN_ICONOS=1` quita los iconos.
  - Tests con ancho fijo y consola sin color.
- 394 tests pasando.

### 2026-11-13 — `ocupa` en un solo recuadro que cabe en la ventana

- Antes, «Uso de disco» ocupaba todo el ancho y la tabla iba en otro cuadro aparte; en
  una ventana estrecha las cabeceras se partían («Tamañ / o») y la barra ocupaba 4 líneas.
- Ahora un solo recuadro que mide lo que su contenido: carpeta, lo que ocupa y lo libre
  arriba, y la tabla dentro, sin borde propio. El porcentaje va detrás de la barra.
- `columnas_que_caben()`: se guarda sitio para la ruta más larga (de 12 a 30 columnas);
  la barra se acorta para que quepa, se quita si quedan menos de 6 y, si aun así falta,
  se quita «Archivos» (el total ya sale arriba). Tamaños y números no se parten nunca;
  solo una ruta que no cabe sigue en la línea de abajo, entera.
- Tests con anchos de 36 a 120.
- `listar` con el mismo formato: recuadro «Contenido» con la carpeta y lo que tiene
  (carpetas, archivos y lo que suman) arriba, y la tabla dentro. Si falta sitio se quita
  «Tipo» (la extensión ya está en el nombre), luego la hora y, si el nombre ya tiene solo
  16 columnas, la fecha. Nombre y tamaño siempre.
- Las piezas comunes en `comun.py`: `recuadro()`, `resumen()`, `tabla_ligera()` y las
  medidas `MARCO` y `HUECO` para calcular qué columnas caben.
- Revisión del revisor:
  - `listar` ya no saca una traza con una fecha de antes de 1970 en Windows (sale «—»).
  - La extensión va con `escape()` (`informe.[b]` perdía el «[b]»).
  - Una carpeta con solo ocultos dice «No hay nada visible: N ocultos» en vez de «vacía».
  - En `ocupa -p 2` las rutas van sin sangría: si una se parte, la línea de abajo se lee
    igual.
  - Con la salida a un archivo sin UTF-8, la barra sale con `#` y `-`.
- 409 tests pasando.

### 2026-11-16 — `subred` y la sección «Redes e informática»

- **Nuevo:** `navaja subred`, la primera orden de la fase 1 del documento de ideas. Todo
  con `ipaddress` (viene con Python): no añade dependencias.
  - `ver`: red, máscara, wildcard, broadcast, primer y último equipo, hosts útiles, tipo
    (privada, pública, loopback, APIPA, CGNAT, multicast…), clase y versión; en IPv4,
    la IP, la máscara, la red y el broadcast en binario, con los bits de red y los de host
    en colores distintos. La IP vale con `/26`, con la máscara aparte
    (`192.168.10.200 255.255.255.192`) o sola (máscara de su clase; en IPv6, /64).
    Avisa si la IP es la de la red o el broadcast; /31 y /32 se calculan bien.
  - `dividir RED N`: subredes iguales (FLSM). Si N no es potencia de 2, salen las de la
    siguiente y lo explica.
  - `vlsm RED 50 20 10`: reparte de mayor a menor, con nombre opcional (`ventas:50`),
    dice cuántas direcciones sobran en cada una y qué queda libre; si no cabe, cuánto falta.
  - `misma IP1 IP2`: si están en la misma red (la segunda sin máscara usa la de la primera)
    y el caso «a medias» de las máscaras distintas.
  - `practica [--nivel facil|medio|dificil] [-n 5]`: ejercicios con IP privadas al azar;
    pregunta máscara, red, broadcast y hosts, corrige y explica los fallos con el «número
    mágico» (256 − el octeto de la máscara). `salir` termina y da el resultado.
- **Menú:** sección nueva «Redes e informática» (🌐) para esta y las siguientes de red
  (`base`, `chmod`, `red`, `puertos`…). «Herramientas» pasa a llamarse «Archivos» (📁)
  y la constante `HERRAMIENTAS` es `ARCHIVOS`. `subred` es el 9 del menú; `acciones` pasa
  del 9 al 10, y `tema`, `config` y `manual`, uno más.
- `subred` es un grupo y no un comando suelto: Typer pone los sueltos antes que los
  grupos y saldría en mitad de «Archivos» (apuntado en `docs/arquitectura.md`).
- 72 tests nuevos en `tests/test_subred.py`.
- 480 tests pasando. `test_copia.py::test_por_menu_documentos_escrito_y_carpeta_nueva`
  falla en Linux porque escribe la ruta con barra de Windows (`documentos\ESTUDIO`); ya
  fallaba antes de este cambio y en Windows pasa.

### 2026-11-16 — Calculadoras rápidas y la sección «Programación»

- **Nuevas**, sin dependencias (todo viene con Python):
  - `base NUMERO [--de B] [--a B]`: binario, octal, decimal y hexadecimal. Lee `200`,
    `0b…`, `0o…`, `0x…`, `C8h` o con letras (hexadecimal). Pasos: divisiones sucesivas
    (de decimal), suma de potencias (a decimal) o el atajo de agrupar bits (binario ↔
    hexadecimal u octal). Con una IP, cada octeto en binario.
  - `chmod PERMISOS`: `755` ↔ `rwxr-xr-x`, también `4755` (setuid, setgid, sticky) y lo
    de `ls -l`. Tabla de quién puede qué en un archivo y en una carpeta, y avisos (777,
    los demás pueden más que el dueño…).
  - `hash archivo RUTA` / `hash texto TEXTO` con `--compara`: MD5, SHA-1 y SHA-256 en una
    sola lectura por trozos de 1 MB (barra si pasa de 50 MB). Reconoce el algoritmo por el
    largo de la huella; si no coincide, sale con 1. Es un grupo y no `hash RUTA --texto`
    porque el menú pregunta una ruta (con Tab) y un texto de forma distinta.
  - `codifica base64|url|html [-d]` y `codifica jwt`: solo escribe el resultado (para
    copiarlo o pasarlo a otra orden). Base64 acepta la variante de URL y sin `=`. El JWT
    enseña cabecera, datos y fechas (caduca, creado) y avisa de que la firma no se comprueba.
  - `genera uuid|lorem|numero`: UUID v4, lorem ipsum por palabras y párrafos, y números al
    azar (`--sin-repetir` para sorteos).
  - `clave nueva|frase|fuerza`: con `secrets`. `nueva` lleva siempre de cada tipo; `frase`
    usa 343 palabras sin tildes y un número (unos 49 bits con 5). `fuerza` lee sin eco
    (o la primera línea de una tubería), no la guarda ni la enseña, y calcula los bits de
    verdad: las de las más usadas valen 10 bits, y las repeticiones, series (123, abc,
    qwerty) y palabras de la lista casi no suman. Da el nivel, el tiempo para adivinarla a
    10.000 millones por segundo y consejos.
- **Menú:** sección «Programación» (💻) con `hash`, `codifica`, `genera` y `clave`; `base` y
  `chmod` van en «Redes e informática», antes que `subred`. Numeración: Archivos 1-8, Redes
  9-11, Programación 12-15, `acciones` 16, `tema` 17, `config` 18 y `manual` 19.
- `ayuda.subcomandos()` ordena por el orden de `SECCIONES`: así una orden suelta (`base`,
  `chmod`) ya no se sale de su sección aunque Typer ponga los sueltos antes que los grupos.
- 88 tests nuevos (`test_base`, `test_chmod`, `test_huella`, `test_codifica`, `test_genera`,
  `test_clave`): 568 pasando (y el de `copia` con la ruta de Windows, que en Linux falla).

### 2026-11-16 — Fin de la fase 1: arbol, cuenta, json, comprime, extrae y doctor

- **`ignorados.py`** (nuevo): lo que se saltan `arbol` y `comprime`. Siempre .git, .venv,
  venv, node_modules, __pycache__, .pytest_cache, .mypy_cache, .ruff_cache, *.egg-info,
  *.pyc y los del sistema; y el `.gitignore` de la carpeta (nombres, `carpeta/`, rutas
  desde la raíz, `**/` y `!`). No lee los `.gitignore` de las subcarpetas.
- **`arbol [CARPETA]`**: ramas ├── └── │, carpetas primero; `--profundidad`,
  `--solo-carpetas`, `--todo` y `--guardar` (Markdown nuevo, sin pisar). Se corta a las
  1000 líneas.
- **`cuenta ARCHIVOS… [--minimo N]`**: palabras, caracteres (con y sin espacios),
  párrafos, páginas (a 300 palabras), lectura (230/min) y en voz alta (130/min). `.docx` y
  `.odt` sin librerías (son un zip con XML); `.md` sin símbolos ni código; `.html` sin
  etiquetas; `.pdf` con pypdf. Varios archivos: tabla y total.
- **`json comprueba|arbol|formatea|compacta`**: los errores con línea, columna, la línea y
  un ^ debajo, en castellano (los de `esquema.ERRORES_JSON` y además «sobra una coma» y
  «comillas simples»). Avisa de claves repetidas. Lee el BOM del Bloc de notas. YAML con
  pyyaml. `--guardar` crea `nombre-formateado.json` (o `-compacto`) al lado.
- **`comprime [CARPETA]`**: .zip o .tar.gz al lado (o `--destino`, carpeta o nombre),
  todo dentro de una carpeta con su nombre, sin lo de `ignorados.py` ni lo de `--sin`.
  Enseña qué mete y qué deja fuera, `--simular` y `[s/n]`. Escribe a un temporal oculto y
  solo al final le pone el nombre (con «(1)» si ya existe); si falla o se cancela, lo borra.
- **`extrae ARCHIVO`**: .zip, .tar, .tar.gz/.bz2/.xz. Enseña los primeros 15 y pregunta.
  Rutas seguras (fuera ../, absolutas y C:\), sin enlaces ni dispositivos de un .tar,
  comprueba el espacio libre, conserva las fechas y nunca pisa. Sin `--destino`, carpeta
  nueva al lado; si el zip ya trae su carpeta, no se repite. Si se cancela o falla, quita
  la carpeta que había creado. Zip con contraseña, RAR y 7z: aún no (lo dice).
- **`doctor`**: Python, librerías obligatorias y opcionales, git, LibreOffice, Pandoc,
  FFmpeg, 7-Zip (y Word y winget en Windows), carpeta de datos (que se pueda escribir),
  acciones.json y la terminal. ✔ / ! (opcional) / ✘ (sale con 1), con el comando para
  arreglarlo (winget en Windows, apt en Linux).
- **Dependencias opcionales** en `pyproject.toml`: `pdf` (pypdf), `yaml` (pyyaml) y `todo`;
  `dev` las lleva para los tests. `uv.lock` actualizado.
- **Menú**: Archivos 1-12 (`listar`, `ocupa`, `limpia`, `arbol`, `cuenta`, `comprime`,
  `extrae`, y luego `ordena`…`notas`), Redes 13-15, Programación 16-20 (con `json`),
  `acciones` 21 y navaja 22-25 (`doctor`, `tema`, `config`, `manual`).
- 55 tests nuevos: 623 pasando (y el de `copia` con la ruta de Windows, que en Windows sí
  pasa).
- Arreglo tras probarlo en Windows: `doctor` buscaba winget con `shutil.which` directamente
  y no con `buscar_programa`, así que `test_programa_que_falta` fallaba en un PC con winget.
  Ahora el test se pasa como si fuera Windows y como si fuera Linux.

### 2026-11-16 — Fuera `json` y `codifica`; sus mejoras, a `acciones validar`

- **Quitadas** `json` y `codifica` (con sus tests y el extra `yaml`/pyyaml): no me quitan
  trabajo. El único JSON que toco a mano es `acciones.json`, y para eso ya está
  `acciones validar`. `hash`, `genera` y `clave` se quedan de momento. Están en git por si
  hacen falta.
- **`acciones validar`** se queda con lo bueno de `json comprueba`:
  - `esquema.mejor_motivo()`: «sobra una coma antes de cerrar» cuando hay una coma justo
    antes de `}` o `]`, y «comillas dobles, no simples» cuando el error está en una `'`.
  - `esquema.senalar()`: la línea del error y una `^` debajo de la columna exacta (antes
    solo la línea).
  - `esquema.claves_repetidas()`: avisa (sin fallar) si una clave sale dos veces en el
    mismo sitio, porque JSON se queda con la última sin decir nada.
- Menú: Programación 16-18 (`hash`, `genera`, `clave`), `acciones` 19 y navaja 20-23.
- 3 tests nuevos en `test_acciones.py`.

### 2026-11-16 — Fase 2: busca, convierte, pdf, imagen, qr, baja y fondo

- **Sección nueva «Documentos e imágenes»** (📚) entre Archivos y Redes: `convierte`,
  `cuenta` (que viene de Archivos), `fondo`, `baja`, `qr`, `pdf` e `imagen`. Numeración:
  Archivos 1-12 (`busca` es el 5), Documentos 13-19, Redes 20-22, Programación 23-25,
  `acciones` 26 y navaja 27-30.
- **`lotes.py`** (nuevo), lo común de las órdenes que crean archivos a partir de otros:
  comodines (`*.heic`, que en Windows no expande la terminal), el nombre nuevo al lado sin
  pisar ni repetirse (`al_lado`), el plan «de → a», `--simular`, `[s/n]`, el trabajo en
  paralelo con barra (si uno falla, se quita lo que dejó a medias y siguen los demás), y
  `FaltaAlgo` con el comando exacto para instalar la librería o el programa que falta.
  También `pedir_secreto` (contraseña sin eco; por tubería, la primera línea).
- **`busca TEXTO [CARPETA]`**: en subcarpetas, sin lo de `ignorados.py`; sin mayúsculas ni
  tildes manteniendo las posiciones para resaltar (`sin_tildes_igual_largo`); `--regex`,
  `--exacto`, `--solo`, `--todo`. Lee .docx, .odt y .pdf (por página); se salta binarios y
  textos de más de 20 MB; recorta líneas largas alrededor de lo encontrado. Sale con 1 si no
  encuentra nada. Era la orden de la spec que faltaba.
- **`convierte ARCHIVOS a FORMATO`**: imágenes entre sí y a PDF (varias en uno con el nombre
  de la carpeta; `--separados`), PDF a docx (pdf2docx, sin sus mensajes en inglés) y a
  png/jpg (PyMuPDF, `--dpi`), ofimática a PDF (LibreOffice con un perfil propio para que
  funcione aunque esté abierto; en Windows sin LibreOffice, Word con docx2pdf), md/html con
  Pandoc, csv ↔ json (detecta `;` o `,`) y csv ↔ xlsx, vídeo y audio con FFmpeg (`--comprime`:
  720p para WhatsApp; un vídeo al mismo formato se recomprime). Lo que no sabe, lo dice con
  la lista de lo que sí.
- **`pdf`**: `info`, `une` (`-n`), `separa` (por tramos o una por página), `saca`, `quita`,
  `gira` (90/180/270, `--paginas`), `comprime` (se adapta a los nombres nuevos de pypdf 7),
  `protege` (AES-256, la pide dos veces) y `desprotege`. Páginas como `1-3,7`, `10-`, `ultima`.
- **`imagen`**: `info` (dice si lleva GPS), `reduce`, `comprime`, `limpia`, `recorta`,
  `grises` e `icono`. Todas salen derechas (`exif_transpose`) y sin EXIF; HEIC → JPG; lo
  transparente a JPG, con fondo blanco.
- **`qr`**: medios bloques blanco sobre negro (la única excepción a «colores del tema», para
  que lo lea la cámara), borde de 3 módulos, `--wifi` (texto WIFI: con los caracteres
  especiales protegidos) y `--guardar` PNG.
- **`baja`**: yt-dlp como librería. Mira antes (título, duración, tamaño, web) y un enlace
  malo no para los demás. Sin FFmpeg baja la versión ya junta; con él, vídeo+audio y MP3.
  `--calidad`, `--subtitulos`, `--cookies chrome`, un .txt con enlaces; destino
  Descargas/Videos; `nooverwrites`. Mensajes en castellano para privado, sesión y web no
  soportada, y cómo actualizar yt-dlp.
- **`fondo`**: rembg con `isnet-general-use` (171 MB) y no el de por defecto, que ahora pesa
  1 GB; la sesión se carga una vez para todas las fotos. `--color` y `--mascara`. Probado
  con el modelo de verdad.
- **Menú**: en una pregunta de lista (fotos, archivos a convertir, PDF a unir) ya no se
  rechaza lo que parece una ruta, porque es justo lo que va ahí.
- **Extras** en `pyproject.toml`: `pdf` (pypdf[crypto]), `imagen`, `qr`, `documentos`, `baja`,
  `fondo` y `todo` (todas menos `fondo`). `dev` lleva las ligeras; rembg no (en los tests se
  sustituye por uno falso). `doctor` las revisa todas.
- 66 tests nuevos (`test_lotes`, `test_busca`, `test_convierte`, `test_pdf`, `test_imagen`,
  `test_qr`, `test_baja` con un yt-dlp falso, `test_fondo` con un rembg falso) y
  `tests/ayudantes.py` con un PDF con texto hecho a mano: 672 pasando.
- Probado en Windows: 672 pasando y 2 saltados (los que necesitan FFmpeg). Arreglo: los
  mensajes de «falta X» y `doctor` decían `".[qr]"`, `".[pdf]"`… pero `uv tool install`
  deja solo los extras que se le dicen, así que instalar uno quitaba los demás. Ahora
  siempre `".[todo]"` (o `".[todo,fondo]"`), con `lotes.como_instalar()`.

### 2026-11-16 — Arreglos de la revisión de la fase 2

- **`busca`** ya no se cae con un PDF con contraseña o dañado en la carpeta (pypdf lanza sus
  propios errores, que no se capturaban): cualquier archivo que no se puede leer se salta.
- **`pdf une -n sub/x`** daba una traza (`with_name` no admite carpetas): ahora un mensaje.
  Usa `problema_del_nombre`, que pasa de `interactivo.py` a `comun.py`: rechaza también
  `ab:c` (en NTFS sería un flujo escondido), `x?y`, `CON`/`NUL`… y lo vacío, igual en todos
  los sistemas. Y `-n juntos.pdf` da `juntos.pdf`, no `juntos.pdf.pdf`.
- **`qr --guardar`** en una carpeta que no existe, o con `.`, `~` o `C:\` (carpetas, no un
  nombre), daba una traza: ahora un mensaje, y antes de dibujar el QR.
- **`convierte` csv → xlsx** ya no estropea datos; se quedan como texto: «08001» (códigos
  postales, teléfonos), más de 15 cifras (Excel las redondea), «1.500» o «2,250» (¿mil
  quinientos o uno y medio? no se adivina), «inf», «nan», «1_000», «+5» y cifras no ASCII.
  Una fila con más columnas que la cabecera ya no falla con un error en inglés.
- Pasado el revisor: lo que encontró en la primera versión de estos arreglos está corregido
  arriba. Tests de regresión en busca, pdf, qr y convierte: 698 pasando y 1 saltado.

### 2026-11-16 — `busca` avisa de lo que no ha podido leer

- Antes, un PDF con contraseña o dañado se saltaba sin decir nada: con todos así, salía
  «no aparece» sin haber mirado ninguno. Ahora `buscar` devuelve también los no leídos
  (`NoLeido`, con el motivo: «con contraseña», «dañado», «no se puede abrir»), no cuentan
  como mirados, y al final sale «No se han podido leer N archivos (puede estar ahí)» con
  los cinco primeros. Los binarios se siguen saltando sin avisar (no son texto).
- Un PDF protegido solo contra copia o impresión (contraseña de propietario, sin la de
  abrir: lo normal en apuntes descargados) se abre con la contraseña vacía y se lee. Lo
  mismo en `cuenta`, que antes rechazaba cualquier PDF cifrado.
- Tras el revisor: también avisa de un archivo de texto bloqueado (abierto en Office, de
  OneDrive sin bajar: «no se puede abrir»), de los PDF si falta pypdf y de los cifrados
  que necesitan cryptography; «de 1 mirado» en singular. `cuenta` ya no da traza con un
  PDF que rompe pypdf de otra forma (KeyError, cifrado raro, falta cryptography).

### 2026-11-16 — Ctrl+C en `convierte`, `imagen`, `pdf` y `fondo`

- Antes, Ctrl+C no paraba: el `ThreadPoolExecutor` hacía toda la cola, salía «Aborted!»
  en inglés y el archivo a medias se quedaba. Ahora (`lotes.cortar`) no se empieza nada
  más, se espera a lo que ya estaba en marcha (un hilo no se puede matar; FFmpeg y
  LibreOffice reciben el Ctrl+C y paran), se borra lo que falló o quedó a medias, se queda
  lo que acabó bien, dice «Cortado: N archivos nuevos de M» y sale con 130.
- Tras el revisor:
  - `wait` con esperas de 0,2 s en vez de `as_completed`: en Windows (hasta Python 3.14)
    una espera sin límite no deja pasar el Ctrl+C hasta que acaba alguna tarea.
  - Mientras se recoge, otro Ctrl+C se ignora (`sin_ctrl_c`): ni traza ni archivos a medias.
  - Se dicen también los fallos de antes del corte, y si algo a medias no se ha podido
    borrar (abierto por el antivirus, OneDrive…) se dice cuál, en vez de «no queda nada».
  - La salida de FFmpeg y Pandoc se lee en UTF-8: con «Árbol.mp4» el motivo del fallo era
    un `UnicodeDecodeError` (LibreOffice, en cambio, escribe en cp1252: ver más abajo).
  - El test ya no depende del reloj (eventos en vez de esperas).
- `Tarea.mas_destinos`: un PDF a imágenes que falla a mitad ya no deja páginas sueltas.
- PyMuPDF (PDF a imágenes) entra en los extras `documentos`, `todo` y `dev`; antes llegaba
  de rebote con pdf2docx.
- Tests nuevos: 704 pasando y 1 saltado.

### 2026-11-16 — `convierte` a PDF con LibreOffice, probado en Windows

- Primera prueba real (un .docx en `~/pruebas-navaja`): LibreOffice hacía el PDF, pero
  al borrar la carpeta temporal con su perfil, `update.log` seguía abierto un instante
  (`WinError 32`); la tarea contaba como fallida y se borraba el PDF bueno.
- Ahora el perfil es fijo, en la carpeta de datos (`libreoffice/`): no se borra, y las
  siguientes conversiones van más rápido. La carpeta temporal de salida se borra con
  `ignore_cleanup_errors`: si algo sigue abierto, se queda en %TEMP% en vez de fallar.
- Un hilo si cualquier archivo es de ofimática o vídeo (antes miraba solo el primero): dos
  LibreOffice no pueden compartir el perfil.
- Segunda prueba real: «LibreOffice no ha podido convertirlo» sin más. Una llamada sí y
  otra no, LibreOffice salía en 0,4 s con código 0 sin convertir nada (igual con perfil
  fijo o nuevo, `soffice.exe` o `soffice.com`, con o sin `--norestore`). Y después, con
  `WinError 32` al arrancar `soffice.exe`.
- **Causa:** el actualizador automático de LibreOffice (el nuevo, con `update.mar`). Desde
  el perfil de navaja descargaba una versión nueva y, en cada arranque «vacío», intentaba
  instalarla en `C:\Program Files\LibreOffice` con permisos elevados (fallaba: `failed: 4`
  en `updates/0/update.status`), bloqueando `soffice.exe` mientras. El primer error ya lo
  apuntaba: `perfil\updates\0\update.log`.
- **Arreglo:** `preparar_perfil` pone `/org.openoffice.Office.Update/Update/Enabled` a
  `false` en el `registrymodifications.xcu` del perfil de navaja (respetando lo demás) y
  borra `updates/`. Probado: 8 de 8 a la primera, unos 4 s cada una. El perfil de LibreOffice
  del usuario no se toca. Se dejan el reintento y el plan B como red, por si acaso.
- La salida de LibreOffice va en la codificación del sistema (cp1252 en Windows), no en
  UTF-8 como FFmpeg: se lee así. Si stderr viene vacío, un mensaje que dice qué hacer.
- Word a PDF con Word (`docx2pdf`) desde un hilo de `hacer_todo`, probado a mano: funciona
  (la duda era si COM fallaba sin `CoInitialize`; no). Su barra en inglés (tqdm, por
  stderr) ya no sale.
- Tras el revisor: si con el perfil fijo sale «bien» sin PDF tres veces (otro navaja en otra
  terminal lo está usando, o está estropeado), plan B con un perfil nuevo en la carpeta
  temporal. Un segundo entre intentos. Mensajes en castellano si LibreOffice se cuelga
  (timeout de 5 min) o si Windows no deja arrancarlo; si no dice nada, el mensaje dice qué
  carpeta del perfil borrar. Ruta del perfil absoluta (`NAVAJA_DATOS` relativo).
- Si aun así Windows no deja arrancar LibreOffice (`WinError 32`), mensaje que dice
  cerrarlo, en vez de un `PermissionError`.
- Última pasada del revisor: si el perfil fijo no se puede preparar (otro navaja lo tiene
  abierto), se va directo al plan B; el `.xcu` solo se escribe si cambia, de golpe (a un
  temporal y `os.replace`) y con «\n» como LibreOffice; `con_word` comprueba que el PDF
  existe (docx2pdf se traga a veces el error de Word); el test de la barra de docx2pdf no
  comprobaba nada (buscaba «it/s» en un texto con «s/it»).
- Tests: 717 pasando y 1 saltado.
- Plan B probado con LibreOffice de verdad (2026-11-17, un .docx hecho en la carpeta
  temporal): 3 de 3 con un perfil nuevo que ya trae el `.xcu` (9 s el primero, 3,5 s los
  demás; sin carpeta `updates`).

### 2026-11-17 — Deshacer sin quitar carpetas tuyas; comodines de `copia`; filtro de fechas

- **Deshacer** (acciones, `copia` y `ordena`) quitaba las carpetas que quedaban vacías
  (la del archivo y la de encima) aunque ya existieran antes: podía borrar una carpeta
  vacía tuya. Ahora `comun.crear_carpetas` crea la de destino (de una en una, con rutas
  absolutas) y devuelve solo las que no existían; se guardan en el registro («creadas»,
  también en `Borrar` para su carpeta de la papelera). Al deshacer se juntan las de
  **todos** los registros (la crea el primer archivo, pero la usan los demás) y se quitan
  si han quedado vacías. Si un archivo falla (o Ctrl+C) tras crear su carpeta, se quita en
  el momento, y el siguiente la vuelve a crear y la apunta. Si al deshacer algo queda
  pendiente, las carpetas que siguen ahí pasan al registro pendiente. Un registro de antes,
  sin «creadas», se deshace como entonces (`carpetas_supuestas`, nunca una de origen).
  (Primera versión, corregida por el revisor: apuntaba la carpeta solo en el primer
  archivo, y si ese fallaba o no se deshacía, la carpeta se quedaba para siempre.)
- **Comodines de `copia`**: ya no cogen ocultos ni de sistema (desktop.ini, Thumbs.db),
  como la lista del menú (por su nombre, sí). Solo `*` y `?` son comodines: los corchetes
  van tal cual, así que «tema[1].pdf» que no existe da «no lo encuentro» (antes cogía
  tema1.pdf) y `*[borrador].pdf` encuentra «apuntes [borrador].pdf». `**.pdf` ya no da
  traza en Python 3.12, y un comodín en la carpeta (`te*/a.pdf`) dice que solo valen en el
  nombre.
- **Filtro de fechas** (`filtros.seleccionar`): un archivo que desaparece mientras se elige
  (una descarga a medias) se salta en vez de dar traza.
- **`ordena deshacer`** borraba el registro aunque algún archivo no se pudiera devolver (ya
  no se podía reintentar) y salía con 0. Ahora guarda lo pendiente, como las acciones, y
  sale con 1 (`comun.pasar_a_pendientes`, compartida).
- **Tests y datos reales:** `monkeypatch.undo()` deshace también el `NAVAJA_DATOS` del
  `conftest`. Dos tests nuevos lo usaban y su segundo «deshacer» corrió sobre la carpeta de
  datos real (no había registros de `ordena` ni `copia`: no se movió nada; comprobado que
  notas, config y demás siguen con sus fechas). Ahora cada test devuelve solo lo que cambió;
  quitados también los dos `undo()` de `test_acciones.py` (eran seguros porque ponían
  `NAVAJA_DATOS` otra vez, pero frágiles). **No usar `monkeypatch.undo()` en los tests.**
- Tests: los de los fallos fallan con el código de antes; los demás vigilan lo que ya iba
  bien (el primer archivo que falla, un registro antiguo, reintentar el deshacer). 727
  pasando y 1 saltado.
- `lotes.expandir` (convierte, imagen, pdf…) igual: ver la entrada «Comodines iguales en
  todas las órdenes».

### 2026-11-17 — «el-mas-nuevo» y el cambio de hora de los USB FAT32

- FAT y FAT32 guardan la hora local, y Windows la pasa a UTC con el horario de verano de
  **ahora**: tras el cambio de hora, todo lo del USB se ve movido una hora. Antes solo se
  disimulaba en `misma_copia` («una hora justa vale como igual», y en cualquier disco), y
  `cual_gana` no lo tenía en cuenta: con dos ediciones a menos de una hora, podía ganar la
  vieja (la nueva iba a «versiones»).
- **No se puede corregir.** Primera versión: corregir la fecha con el desfase de cuando
  se guardó. El revisor vio el fallo: lo que *navaja copia* al USB se guarda con el desfase
  del momento de copiar, no con el de la fecha del archivo; con la hora local de FAT no se
  sabe cuál de los dos fue, y la «corrección» hacía que la segunda ejecución no
  reconociera su propia copia (una «(1)» o una sustitución en cada ejecución). Descartada.
- **Lo que hay:** `comun.hora_dudosa(carpetas)` dice si algún lado puede tener la hora
  movida: FAT, FAT32, exFAT o desconocido (fuera de Windows) → sí; NTFS o ReFS → no
  (`sistema_de_archivos`, con `GetVolumeInformationW`, sin caché: en el modo interactivo
  se puede cambiar de USB con la misma letra). Se mira **una vez por carpeta** al planificar,
  no por archivo (rápido, y sin bloqueos con unidades de red). Con duda:
  - `misma_copia`: una hora justa de diferencia cuenta como la misma fecha (como antes).
  - `cual_gana`: con menos de una hora de diferencia no decide: «míralo tú». Así nunca
    gana el viejo por el cambio de hora.
  Sin duda (NTFS ↔ NTFS): las fechas son exactas; una hora justa ya no es «la misma copia».
- Comprobado en este PC: C: es NTFS. Tests con un USB FAT32 simulado: copiar, mover la hora
  una hora (como Windows tras el cambio de hora) y ejecutar otra vez da «ya está copiado»
  (con copia-aparte y con el-mas-nuevo); «míralo tú» con menos de una hora; entre NTFS una
  hora justa no es la misma copia (también de punta a punta, ejecutando). README al día.
  734 pasando y 1 saltado.

### 2026-11-17 — `ordena`: Ctrl+C a medias y deshacer desde otra carpeta

- Con Ctrl+C a mitad de ordenar no se guardaba nada: lo ya movido no se podía deshacer.
  Ahora se guarda, avisa («Cortado a medias: N archivos movidos antes de cortar») y sale
  con 130, como las acciones.
- Con `-c .` (lo de por defecto) el registro guardaba rutas relativas y `ordena deshacer`
  desde otra carpeta no encontraba los archivos. Ahora `ordenar` empieza con rutas
  absolutas (`os.path.abspath`); el plan se sigue enseñando igual. Los registros que ya
  estuvieran guardados con rutas relativas se deshacen como antes (desde su carpeta).
- Tras el revisor, los huecos del Ctrl+C:
  - Justo después de moverlo todo y antes de guardar: el guardado va dentro de lo que
    protege el Ctrl+C (antes se perdía el registro entero).
  - Justo entre mover un archivo y apuntarlo: si ya está en su destino, se apunta.
  - Mientras se recoge, otro Ctrl+C se ignora (`lotes.sin_ctrl_c`); el aviso dice también
    los fallos de antes del corte.
  - **`comun.guardar_acciones`** escribía vaciando el archivo primero: cortado a medias, el
    registro quedaba roto (se leía como vacío) y el anterior ya se había perdido. Ahora a un
    temporal y `os.replace`. Vale para todos los registros (acciones, copia, ordena…).
- Ctrl+C a mitad de mover entre dos unidades: arreglado con `comun.mover_seguro` (ver
  «Los fallos poco probables»).
- Los seis tests nuevos fallan con el código de antes. 740 pasando y 1 saltado.

### 2026-11-17 — Comodines iguales en todas las órdenes

- `comun.buscar_con_comodin`, compartida por `copia` y `lotes.expandir` (convierte,
  imagen, pdf, fondo): solo `*` y `?` son comodines; los corchetes van tal cual, también
  en la carpeta («[2026] fotos/*.jpg»); `**` es `*`; sin ocultos ni de sistema salvo que el
  patrón empiece por punto (`.*`).
- Arreglo práctico: `navaja convierte carpeta/* a png` en una carpeta de Windows cogía
  `desktop.ini` y paraba todo con «No sé pasar .ini a .png».
- `lotes` sigue admitiendo comodines en la carpeta (`fotos/*/a.jpg`); `copia`, no (avisa).
- Tras el revisor: los corchetes de un recurso de red (`\\servidor\apuntes[1]`) no se
  escapan (glob ya toma la unidad tal cual; antes no encontraba nada), y el «?» del prefijo
  `\\?\C:\…` ya no cuenta como comodín (`comun.patron_glob` y `comun.tiene_comodin`, con
  `os.path.splitdrive`). Quitado el «`**` → `*`»: `glob.glob` ya lo hace (lo que daba traza
  era `Path.glob`). Orden estable aunque solo cambien las mayúsculas.
- Sin tocar: `**` no entra en subcarpetas (como `*`); en Linux y macOS `*.jpg` no coge
  `FOTO.JPG`; `desktop.*` no coge `desktop.ini` (por su nombre, sí); los enlaces a archivos
  se siguen (los rotos se saltan sin avisar); en carpetas enormes o de red, un `stat` de más
  por archivo.
- README: una nota sobre los comodines. Los tests nuevos de corchetes y de `desktop.ini`
  fallan con el código de antes; más: recurso de red, prefijo `\\?\`, patrón relativo, y en
  Windows mayúsculas y atributo oculto. 745 pasando y 1 saltado.
- Aprendido: al pasar código por la terminal (heredoc), las barras dobles se quedan en una
  (`\\servidor` → `\servidor`, `"\n"` → salto de línea): lo que lleve barras, con un editor.

### 2026-11-17 — Versiones viejas: caducan, se pueden no guardar, y las de solo lectura

- Sergio: «si siempre guarda la copia anterior ocupará mucho». Las versiones viejas que
  aparta «el-mas-nuevo» se quedaban para siempre hasta `acciones versiones borrar`.
- **Caducan solas:** `config versiones DIAS` (por defecto 30; 0 = siempre), guardado en
  `config.json` como `dias_versiones`. `versiones.caducar` borra las más antiguas al terminar
  `acciones ejecutar` y `copia a` (no con `--simular`), y lo dice («Borradas N versiones
  viejas de hace más de 30 días (tamaño)»). `config ver` lo enseña.
- **No guardarlas:** campo nuevo de `copiar`, `guardar_viejas` (true por defecto; solo con
  `el-mas-nuevo`, si no `validar` da error). Con false, la vieja se sustituye de golpe
  (`os.replace`); el plan lo dice («sin guardarla»); el registro lleva `sin_guardar` y
  deshacer **no quita** esa copia (dejaría el sitio vacío) y lo explica. En `copia a`:
  `--sin-guardar-viejas` (solo con `--si-cambia el-mas-nuevo`).
- **Solo lectura:** apartar una vieja de solo lectura del USB a C: (mover entre unidades =
  copiar y borrar) fallaba en Windows. `comun.quitar_solo_lectura` antes de apartarla, de
  sustituirla sin guardar y de borrar el temporal; la versión guardada queda sin él.
- Dónde se guardan: siguen en C: (decidido con Sergio: se recuperan sin el USB).
- Tras el revisor:
  - No caduca una versión que necesita un deshacer pendiente (de `copia` o de acciones:
    `versiones.para_deshacer`), aunque sea antigua.
  - Sin trazas: `config versiones` hasta 3650 días; en `config.json`, `dias_versiones`
    escrito a mano como número (7) vale, y «²» o un disparate vuelven a 30; si el índice no
    se puede escribir al caducar, se sigue.
  - Si la sustitución sin guardar falla, la vieja vuelve a ser de solo lectura como estaba.
  - Si apartar a C: falla a medias (copiada pero sin poder borrar la de origen), se quita la
    copia suelta de «versiones» (sin índice, nunca caducaría).
  - `acciones ejecutar` solo caduca si se ha hecho algo (no al cancelar), como `copia a`.
- Caducar borra las versiones de todas las acciones por igual (por fecha). El índice roto:
  ver la entrada siguiente.
- Manual, README, `DOC_CAMPOS` y la skill (las dos copias) al día. Los tests nuevos fallan
  con el código de antes (el de solo lectura, solo en Windows). 762 pasando y 1 saltado.

### 2026-11-17 — Índice de versiones a prueba de roturas

- Antes, con `versiones/indice.json` roto (o borrado) no se listaba ni caducaba nada, y el
  siguiente `apuntar` escribía uno nuevo solo con las nuevas: las de antes quedaban en la
  carpeta para siempre, sin índice.
- `versiones.guardar` escribe a un temporal y `os.replace` (cortado a medias, queda el de
  antes). Si el que hay está roto, lo guarda aparte como `indice.roto.json` antes de
  escribir el nuevo.
- `versiones.cargar` = lo del índice + lo que hay en la carpeta sin estar en él
  (`sin_indice`), con la fecha de su subcarpeta (`20261117-103000`) o la del archivo. Esas
  se ven («Estaba en: no se sabe»), caducan y se borran; `recuperar` no puede devolverlas a
  su sitio y dice dónde están para que las copies tú (sale con 1).
- `apuntar` y `olvidar` escriben solo lo que se sabe (las «sin índice» no se guardan: se
  encuentran solas en la carpeta). Si el índice no se puede escribir al copiar, la copia no
  se para: se encuentran igual en la carpeta (sin sitio).
- Tras el revisor:
  - Una entrada mala ya no tira todo el índice (y con él el «de dónde salió» de todas): se
    ignora esa sola. También las que apuntan fuera de la carpeta de versiones (caducar
    borraría un archivo tuyo); fechas con zona horaria y `accion` que no es texto, sin traza.
  - Un índice que no se puede leer (bloqueado por el antivirus) no es uno roto: se listan
    igual, pero no se escribe encima (`apuntar`/`olvidar` lanzan `OSError`).
  - Un `indice.roto.json` anterior no se pisa («(1)»); un índice con BOM (Bloc de notas) vale.
  - `versiones borrar` quita el solo lectura antes de borrar, nombra bien las de sitio
    desconocido y, si no puede poner al día el índice, avisa en vez de dar traza (también
    `recuperar`).
  - `sin_indice`: sin traza si un archivo desaparece mientras se mira; en una carpeta sin
    fecha en el nombre, la fecha de la carpeta (no la del archivo, que conserva la original).
- Sin arreglar: `versiones borrar` deja borrar una que necesita un deshacer pendiente
  (pregunta antes; el deshacer luego deja la copia); archivos sueltos en la raíz de
  `versiones` no se listan.
- Los tests nuevos fallan con el código de antes. 769 pasando y 1 saltado.

### 2026-11-17 — Los fallos poco probables

- **Mover a otra unidad, sin nada a medias** (`comun.mover_seguro`, en `ordena`, las acciones
  mover y borrar, y al apartar versiones): en el mismo disco renombra; a otro (un USB),
  `shutil.move` copiaba y luego borraba, y un Ctrl+C a mitad dejaba el archivo a medias en
  el destino o en los dos sitios, sin apuntar. Ahora: copia a un temporal oculto, le pone el
  nombre de golpe y solo entonces borra el original; si se corta copiando, fuera el temporal;
  si se corta (o no se puede) al borrar el original, fuera la copia. Nunca en dos sitios.
- **La lista de unidades no se frena con una de red desconectada** (`interactivo.responden`):
  las de red se miran todas a la vez, cada una en su hilo, con medio segundo en total; la
  que no contesta no sale. Comprobado en este PC: sale «USB (D:)» al momento.
- **Dos navaja a la vez con el índice de versiones** (`versiones._cerrojo`, `indice.lock`
  creado con `O_EXCL`): solo uno lee-cambia-escribe; el otro espera hasta 5 s, y un cerrojo
  de hace más de un minuto (de uno que se cortó) se quita. Comprobado sin cerrojo: con dos
  hilos se perdían versiones (17, 2 o 16 de 30); con cerrojo, las 30.
- **Plan B de LibreOffice** probado de verdad (ver la entrada de LibreOffice).
- Tras el revisor (lo más serio: **se podía perder el archivo**):
  - En `mover_seguro`, un Ctrl+C justo al volver de borrar el original hacía que la limpieza
    quitara también la copia: el archivo desaparecía de los dos sitios. Ahora la limpieza
    **mira qué hay en el disco** en vez de suponer en qué paso iba: quita el temporal, y la
    copia solo si el original sigue ahí; si ya no está, el archivo está movido y no se toca.
  - Nunca pisa: si el destino ya existe, `FileExistsError` (`ordena` ya no pisa un archivo que
    aparezca entre el plan y el mover). En el mismo disco, `os.rename` (`shutil.move` copiaba
    si no podía renombrar, p. ej. abierto en Word, y lo dejaba en dos sitios).
  - Deshacer (`ordena` y acciones) también con `mover_seguro`: un archivo de solo lectura
    movido a otra unidad ya se puede deshacer.
  - Cerrojo: espera también con `PermissionError` (Windows, a medio borrar); dentro va una
    marca y la hora del que lo pone, y cada uno quita solo el suyo (un navaja lento ya no
    borra el del siguiente); se quita con Ctrl+C a cualquier altura; uno vacío (cortado al
    ponerlo) caduca por la fecha del archivo.
  - La lista de unidades mira también los discos (un disco USB dormido también la frenaba).
- Segunda vuelta del revisor:
  - `apartar` tenía su propia limpieza (de antes de `mover_seguro`) que, si el destino
    aparecía justo entonces (otro navaja), **borraba ese archivo ajeno**. Quitada:
    `mover_seguro` ya limpia, y mirando el disco.
  - Lo que quedaba con `shutil.move` (devolver la versión vieja tras un fallo, y el deshacer
    de copias) usa también `mover_seguro`: nunca pisa ni deja a medias.
  - `ordena` decía «[Errno 17] … 'C:\\…'»: ahora el motivo en castellano (`exc.strerror`).
  - Los tests que simulan fallos parchean `os.rename` o `mover_seguro` (con la misma firma).
- Sin arreglar (raro): el temporal `.nombre.navaja-moviendo` alarga el nombre (con rutas al
  límite de Windows, mover a otra unidad puede fallar donde uno directo no); una unidad de
  red lenta pero conectada (más de medio segundo) no sale en la lista; en Linux/macOS, un
  archivo que aparezca justo entre comprobar y renombrar se pisaría. El cerrojo tiene dos
  carreras mínimas (quitar uno abandonado justo cuando otro pone el suyo) que solo arregla un
  bloqueo del sistema (`msvcrt.locking`/`fcntl`); con los datos en red y un PC con el reloj
  adelantado, su cerrojo tarda en darse por abandonado.
- 784 pasando y 1 saltado.

### 2026-11-17 — `chuleta`: git, Linux y PowerShell sin internet

- **`navaja chuleta [TEMA]`** (Programación, la 23 del menú; `hash` pasa a 24, `genera` 25,
  `clave` 26, `acciones` 27 y navaja 28-31). Sin tema, la lista con el título de cada una y
  si es de navaja o tuya; con tema, la chuleta entera en Markdown con los colores del tema
  (los estilos `markdown.*` de Rich salen de `titulo`, `acento`, `pista`…).
- **Tres chuletas** en `src/navaja/chuletas/*.md` (en el paquete con `package-data`): `git`
  (empezar, día a día, ramas, GitHub, deshacer, stash, .gitignore), `linux` (archivos,
  permisos, usuarios, procesos, red, apt, discos, tuberías, atajos) y `powershell` (lo mismo
  en Windows, winget, `$PROFILE` y una tabla «De Linux a PowerShell»). SQL descartada.
- **Las tuyas:** `chuleta NOMBRE --editar` crea `chuletas/NOMBRE.md` en la carpeta de datos
  (copiando la de navaja o con una plantilla) y la abre en el editor; si ya existe, no la
  pisa. Una tuya con el mismo nombre tapa a la de navaja. Una que no se puede leer o no es
  UTF-8 se salta sin romper la lista.
- El tema solo admite letras, números, `-` y `_` (ni barras ni `..`, ni `con`/`nul`); uno que
  no existe sugiere el parecido («¿Querías decir git?»). Tab completa los temas.
- Decidido (Sergio): solo se ve el tema entero, sin búsqueda dentro.
- 10 tests en `test_chuleta.py`. 798 pasando y 1 saltado.

### 2026-11-17 — Estudio: `estudia`, `foco` y `entregas`

- **Sección nueva «Estudio»** en el menú y en `--help` (`ESTUDIO` en `comun.py`, con icono 🎓
  en `interactivo.py`), entre «Redes e informática» y «Programación». Los números del menú
  cambian: Estudio 23-25, Programación 26-29, acciones 30 y navaja 31-34.
- **`navaja estudia`** (`comandos/estudia.py`): tarjetas con repetición espaciada, SM-2 hecho a
  mano (`siguiente()`: 1 día, 6 días y luego intervalo × facilidad; la facilidad nunca baja de
  1,3 y fallar no la toca). `importa` lee líneas `P:` / `R:` de los `.md` (con viñeta, la
  pregunta o la respuesta en varias líneas) de un archivo o carpeta; si la pregunta ya estaba
  con otra respuesta, la cambia sin perder lo aprendido; `--simular` solo cuenta. `repasa`
  (también `navaja estudia` a secas) pregunta las de hoy: `1` otra vez, `2` difícil, `3` bien,
  `4` fácil (calidades SM-2 1, 3, 4 y 5), `s` salir; una fallada vuelve en la misma sesión.
  `estadisticas`: tarjetas, pendientes, sin estudiar, aprendidas (intervalo de 21 días o más),
  repasadas hoy y racha. SQLite en `estudia.db` (`tarjetas` y `repasos`).
- **`navaja foco`** (`comandos/foco.py`): pomodoro con cuenta atrás grande (`rich.live`, cifras
  de 5 líneas; con `#` si la salida no es UTF-8) y sonido (`winsound` en Windows, `\a` en
  Linux). `foco` a secas = un bloque de 25 min; `foco empieza` con `-t`, `-d`, `-b`, `-a` y
  `--simular`; el descanso no se hace tras el último bloque. Con Ctrl+C se para y se apunta lo
  que llevabas si pasó un minuto. `foco historial` suma por asignatura. SQLite en `foco.db`.
- **`navaja entregas`** (`comandos/entregas.py`): `agregar`, `listar`, `hecha` y `borrar`, con
  `--simular` en las que cambian algo. Fechas: `2026-12-15`, `15/12/2026`, `15/12` (la próxima),
  `hoy`, `mañana` o `+3`. Rojo si queda menos de 2 días, amarillo si menos de 7. El saludo del
  modo interactivo avisa de lo que vence pronto (`aviso_de_pendientes()`, nunca falla).
  SQLite en `entregas.db`.
- Decidido por mí (Sergio no lo pidió): `foco` y `estudia` sin subcomando hacen lo más común, y
  además tienen subcomandos para que el menú numerado los ofrezca; un bloque de `foco` parado
  antes del minuto no se apunta.
- 69 tests nuevos (`test_entregas.py`, `test_foco.py`, `test_estudia.py`); `test_ayuda.py`
  cuenta la sección nueva. Probado fuera de tu PC (Linux, Typer 0.29): en esa máquina hay 11
  tests antiguos de `test_ayuda.py` y `test_interactivo.py` que fallan por la versión de
  Typer/Click, también sin estos cambios; ejecuta toda la suite en tu equipo.

### 2026-11-17 — `nuevo`, `hoy` y `compara` (Programación)

- **Menú:** las tres van en Programación (los comandos sueltos salen antes que los grupos).
  `chuleta` pasa a Estudio (Sergio: «chuleta vale para todo, no solo programación»): Estudio
  23-26 (`chuleta`, `estudia`, `foco`, `entregas`), Programación 27-32, acciones 33 y navaja
  34-37.
- **`navaja nuevo NOMBRE`** (`comandos/nuevo.py`): plantillas `python` (por defecto), `java` y
  `web` con su `.gitignore` (más uno común de sistema y editores), `README.md` con cómo se
  ejecuta, y `git init -b main` (o `git init` con un git anterior a 2.28) + primer commit.
  Plan y `[s/n]` (`--si`), `--simular`, `--sin-git`, `-c CARPETA` (el menú la pregunta). Nunca
  pisa: «nombre (1)». Nombre comprobado con `problema_del_nombre`. Sin git o sin `user.name`,
  explica qué hacer en vez de fallar.
- **`navaja hoy [CARPETA]`** (`comandos/hoy.py`): busca repositorios hasta 3 niveles (sin entrar
  en uno ya encontrado, ni en `.venv`, `node_modules`, `dist`…) y saca `git log --all
  --no-merges --since` de cada uno filtrado por su `user.email` (`--fixed-strings`, para que un
  `+` del email no sea regex). `--todos`, `--desde` (`hoy`, `ayer`, `-3`, `10/11` = la última,
  `2026-11-10`) y `--md`. Un repo sin commits no rompe nada.
- **`navaja compara A B`** (`comandos/compara.py`): `difflib.unified_diff` con colores del tema
  (cada línea como `Text`, así un `[bold]` del archivo no es markup), `-n` contexto, `-w` sin
  espacios. Lee UTF-8 o, si no, Windows-1252; binario o más de 5 MB: solo iguales/distintos;
  como mucho 400 líneas por archivo. Carpetas con `filecmp` (contenido, no fecha), sin `.git`,
  `.venv`, `node_modules`…; `--detalle` añade las líneas. Solo mira, nunca cambia nada.
- 38 tests nuevos (`test_nuevo.py`, `test_hoy.py`, `test_compara.py`) con git de verdad y una
  configuración propia (`tests/ayudantes_git.py`: `GIT_CONFIG_GLOBAL`, no toca la tuya); se
  saltan si no hay git. Probado en Linux: sin fallos nuevos (siguen los 11 de la versión de
  Typer/Click de esa máquina).

### 2026-11-17 — `falsos` y `sql` (Programación)

- **Menú:** Programación 27-34 (`nuevo`, `hoy`, `compara`, `falsos`, `sql`, `hash`, `genera`,
  `clave`), acciones 35 y navaja 36-39.
- **`navaja falsos`** (`comandos/falsos.py`): Faker `es_ES` como extra opcional `falsos` (también
  en `todo` y `dev`; `doctor` lo revisa; sin él, dice cómo instalarlo). 17 campos (`--lista`);
  el DNI con la letra calculada a mano (número mod 23) y sin repetir, el email sacado del nombre
  sin tildes y sin repetir. Formatos `tabla` (50 filas como mucho), `csv` (`;`, con BOM al
  guardar para Excel), `json` y `sql` (`CREATE TABLE IF NOT EXISTS` + un `INSERT` por fila, con
  `'` escapado). `--guardar` elige el formato por la extensión y nunca pisa; `--semilla`,
  `--simular`. Hasta 10.000 filas.
- **`navaja sql BASE [CONSULTA]`** (`comandos/sql.py`): sin consulta, tablas y vistas con sus
  columnas. Las sentencias se parten con `sqlite3.complete_statement` (un `;` entre comillas no
  corta). Si alguna empieza por `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`…, es un
  cambio: enseña el SQL con colores, pregunta `[s/n]`, copia la base con la API de backup de
  SQLite (quedan 5 en `sql-copias`) y lo hace en una transacción (todo o nada). `--simular`
  hace lo mismo y `ROLLBACK`. Todo lo demás se abre en solo lectura (`mode=ro`): un `WITH …
  DELETE` o un error de escritura no pueden cambiar nada. Nunca crea una base por mirar (solo
  con `--crear`). `--csv` guarda el resultado entero; `--archivo` lee un `.sql`.
- Pendiente: formatear SQL desordenado (necesitaría `sqlparse`).
- 37 tests nuevos (`test_falsos.py`, `test_sql.py`, uno de `falsos` + `sql` juntos). Sin
  fallos nuevos en Linux. Al añadir el extra, `uv` actualiza `uv.lock` la primera vez.

### 2026-11-17 — Fase 4: `red`, `puertos` y `sistema` (Redes e informática)

- **Fase 4 decidida** (Sergio): `red`, `puertos`, `sistema`, `respaldo`, `apps` y `encuentra`.
  Fuera `sincroniza`: `usb-a-pc`, `pc-a-usb` y `copia a` ya copian en los dos sentidos solo lo
  nuevo o cambiado. Fuera también `dns`, `cron`, `escanea` y `web` (por ahora).
- **Menú:** las tres van en Redes e informática, entre `chmod` y `subred`: Redes 20-25, Estudio
  26-29, Programación 30-37, acciones 38 y navaja 39-42. La sección dice ahora «Calculadoras de
  clase y tu PC: red, puertos y sistema».
- **psutil** como extra opcional `sistema` (también en `todo` y `dev`; `doctor` lo revisa; sin él,
  las tres dicen cómo instalarlo).
- **`navaja red`** (`comandos/red.py`): IP con `/prefijo`, máscara, puerta de enlace, MAC y
  velocidad de cada tarjeta. La que sale a internet (un socket UDP «conectado» a 8.8.8.8, que no
  envía nada) va primero con ★; luego cable y Wi-Fi, y al final las virtuales (VirtualBox,
  vEthernet de WSL, Docker…). La puerta de enlace sale de `/proc/net/route` en Linux, de
  `route print -4 0.0.0.0` en Windows (solo se leen números: vale en cualquier idioma) y de
  `route -n get default` en macOS. Avisa de APIPA. `--todas`, `--ipv6`. Termina con la orden
  `subred ver` de tu IP.
- **`navaja puertos [PUERTO]`** (`comandos/puertos.py`): TCP en LISTEN (`--udp`, también UDP),
  juntando IPv4 e IPv6 del mismo programa; programa, PID, «desde» (toda la red / solo este PC) y
  para qué se suele usar el puerto (unos 50 conocidos). Con un puerto libre lo dice (código 0).
  `--cerrar` enseña el programa, pregunta `[s/n]` (`--si`, `--simular`), hace `terminate` y, si
  a los 3 segundos sigue, `kill`. Nunca cierra navaja misma, el PID 4 ni programas del sistema
  (`svchost.exe`, `lsass.exe`, `systemd`…); sin permiso, dice que abras la terminal como
  administrador.
- **`navaja sistema`** (`comandos/sistema.py`): `rich.live` hasta Ctrl+C (`--cada`, 2 s); con
  `--una-vez`, o si la salida no es una terminal, una sola vez. CPU (núcleos, físicos y GHz),
  memoria (usada = total − disponible, como el Administrador de tareas), intercambio, discos
  (sin CD, snap, tmpfs…), batería (barra al revés: poca carga en rojo) y tiempo encendido. Los
  procesos se suman por nombre y su CPU se divide entre los núcleos (100 % = el PC entero); el
  objeto de cada proceso se guarda entre vueltas para que psutil compare con la medida anterior.
  `--orden cpu|memoria` (el menú lo pregunta) y `-n`.
- 55 tests nuevos (`test_red.py`, `test_puertos.py`, `test_sistema.py`): la lógica con datos
  falsos de psutil (tarjetas, rutas de Linux, Windows y macOS, conexiones) y, si psutil está,
  las órdenes de verdad: `puertos` encuentra y cierra un `http.server` lanzado por el test. Sin
  fallos nuevos en Linux (siguen los 2 de rutas de Windows, `test_copia` y `test_lotes`).
- Pendiente de probar en Windows: la puerta de enlace con `route print`, los nombres de las
  tarjetas («Wi-Fi», «Ethernet 2», «vEthernet (WSL)»), `puertos` sin ser administrador y la
  batería del portátil.

### 2026-11-17 — Menú compacto

- Si el menú no cabe en la altura de la ventana, se reparte en dos columnas (con sus frases) y
  el rótulo grande deja su sitio al sencillo. Los submenús y la salida sin terminal no cambian.
  11 tests en `test_menu_compacto.py`.
- Arreglos de los tests en Windows: con la salida capturada por pytest, Rich cree que es la
  consola antigua (`legacy_windows`) y cambia `╭` por `┌`; los tests lo fijan a `False`.
  `test_iconos_solo_con_utf8_y_terminal_moderna` mira `legacy_windows` y no `WT_SESSION`.
- `ayuda.tipo_texto`: una opción con `min=`/`max=` (tipo «int range») sale como «número».

### 2026-11-17 — Capa de IA: `renombrar-ia`, `resumir-ia` y `comprobar-ia`

- **Decisión** (Sergio): Gemini, con la clave en `.env`; Ollama no (no lo tiene en casa). Las
  dos acciones con IA son las que propone el profesor: renombrar por contenido y resumir.
  Por qué y alternativas: [ADR-0002](docs/adr/0002-capa-ia.md).
- **`proveedor_ia.py`**: `ProveedorIA` (fábrica `desde_entorno`, `preguntar`, `comprobar`) y
  `Gemini` (API REST con `urllib`, sin dependencias nuevas; clave en la cabecera
  `x-goog-api-key`, nunca en la URL). La clave sale de `GEMINI_API_KEY`, del `.env` de la
  carpeta actual o del de los datos (por ese orden). `NAVAJA_MODELO` (por defecto
  `gemini-flash-lite-latest`: probado en casa, contesta en 0,9 s; `gemini-flash-latest` pasaba
  de 60 s) y `NAVAJA_SIN_IA`. `.env.example` documentado.
- **Errores** (`errores.py`): `IANoDisponible` (código 4: sin clave, sin red, clave mala, cupo
  gastado, modelo que no existe, Gemini caído o un proxy que lo bloquea; cada uno con su
  mensaje) y `RespuestaIARara` (bloqueada, vacía o un nombre imposible: solo falla ese archivo).
- **Acciones** (`acciones.py`): `AccionConIA` (lee el texto con `cuenta.texto_de`, como mucho
  12 000 letras; si la IA deja de estar a medias, no se le vuelve a preguntar) y dos tipos:
  `renombrar-ia` (pregunta en el plan: `--simular` enseña los nombres; `limpiar_nombre` deja
  minúsculas, sin tildes y con guiones, hasta 60 letras) y `resumir-ia` (escribe
  `nombre.resumen.md` al lado o en `destino`, con una nota de que lo ha hecho la IA; se salta
  el que ya tiene resumen; `deshacer` lo manda a la papelera: registro `como: "creado"`). Las
  dos admiten `instrucciones`. `Renombrar.aplicar` pasa a la función `cambiar_nombre`, que
  usan las dos.
- **Sin IA, lo demás sigue:** una acción con IA sin clave lo dice en una línea y sale con 4;
  en una rutina, ese paso se salta con aviso y se hacen los demás (sale con 1). `acciones
  validar` avisa si hay acciones con IA y no hay clave; `doctor` dice si hay clave (sin
  llamar). En el plan, un archivo saltado sin destino ya no sale como «papelera de navaja».
- **`navaja comprobar-ia`** (`comandos/ia.py`, en la sección navaja tras `doctor`): proveedor,
  modelo, de dónde sale la clave (solo las 4 últimas letras) y una pregunta mínima;
  `--sin-llamar` no gasta cupo.
- **acciones.json**: `nombres-claros` (renombrar-ia en Descargas, última semana),
  `resumir-apuntes` (resumir-ia en `ESTUDIO/DAM`, recursivo, última semana) y la rutina
  `descargas-con-ia`. Las mismas en `pruebas/acciones-prueba.json`.
- 42 tests nuevos (`test_ia.py`) que nunca llaman a Gemini: un proveedor `Falso` para las
  acciones y `urlopen` cambiado para los errores de red. `conftest.py` quita la clave y los
  `.env` reales en todos los tests.
- Pendiente de probar en casa con la clave de verdad: `comprobar-ia`, `nombres-claros
  --simular` y `resumir-apuntes` con un PDF de apuntes.

### 2026-11-17 — GitHub Actions: tests en Ubuntu, Windows y macOS

- `.github/workflows/tests.yml`: en cada push y PR, con `uv sync --frozen --extra dev` (las
  versiones de `uv.lock`), `compileall`, `pytest` y `navaja --help`, en los tres sistemas
  (`fail-fast: false`: si falla uno, se ven los otros). Insignia en el README.
- Los dos tests que solo tienen sentido en Windows (`test_copia` con `documentos\ESTUDIO` y
  `test_lotes` con `C:` y `\\servidor`) se saltan fuera de Windows en vez de fallar.

### 2026-11-22 — Versión 1.0.0

- `pyproject.toml` y `__version__` a 1.0.0. `CHANGELOG.md` con todo lo que trae.
- README: instalación con una orden desde GitHub
  (`uv tool install "navaja[todo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.0.0"`,
  probada en limpio: instala, `navaja --version`, las chuletas incluidas y el aviso de
  `acciones.json` sin traza), dónde van `acciones.json` y `.env` cuando está instalada, y
  aparte cómo instalarla para programar (`--editable`).
- Etiqueta `v1.0.0` y Release en GitHub con las notas del CHANGELOG.

### 2026-11-22 — La orden para instalar lo que falta, según cómo se instaló navaja

- Antes, `doctor` y los avisos de librerías opcionales decían siempre
  `uv tool install --editable ".[todo]"`, que solo vale desde la carpeta del proyecto.
- `lotes.origen_instalacion()` lee el `direct_url.json` que deja uv: si navaja está instalada
  con `--editable`, sale esa orden («Desde la carpeta de navaja»); si vino de GitHub, la
  misma dirección y versión con `--force` («Instálalo con: uv tool install --force
  "navaja[todo,fondo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.0.0"»). Lo usan
  `doctor`, `libreria()` (todas las órdenes con librerías opcionales), `cuenta` y `baja`.
- 3 tests nuevos en `test_lotes.py` (editable, GitHub con y sin versión, y `doctor`).

### 2026-11-22 — IA con Ollama o el servidor del centro (compatible con OpenAI)

- **Decisión** (Sergio): dejarlo preparado para quien quiera usar el servidor de modelos del
  centro (en casa no tiene su dirección ni su clave) u Ollama.
- `proveedor_ia.Servidor`: habla la API de OpenAI (`POST {NAVAJA_IA_URL}/chat/completions`,
  clave opcional en `Authorization: Bearer`, `NAVAJA_IA_CLAVE`). Con `NAVAJA_IA_URL` en el
  `.env` se usa en vez de Gemini; modelo por defecto `llama3.2`. Espera hasta 120 s (los
  modelos locales van más lentos), quita lo que va entre `<think>` y `</think>`, y cada
  error dice qué hacer (no llega, la clave, el modelo que no existe, saturado, tarda mucho).
- La llamada HTTP pasa a `ProveedorIA.llamar`, que usan los dos; cada uno traduce sus errores
  (`error_http`, `error_de_red`).
- `comprobar-ia` y `doctor` enseñan el servidor; `.env.example`, README, ayuda y ADR-0002
  (actualización) lo explican.
- 12 tests nuevos en `test_ia.py` (lo que se manda, sin clave sin cabecera, `<think>`, cada
  error, URL mal escrita y `comprobar-ia`), sin servidor de verdad.

### 2026-11-22 — Revisión: códigos de salida en el README y limpieza

- Revisión completa (tests, ruff con F/E9/PLE, `--help` de todas las órdenes y los códigos
  de salida comparados con el README): sin fallos graves.
- README: «0 también si respondo n» solo vale en las órdenes sueltas; en `acciones ejecutar`
  decir «n» (o un paso de rutina sin hacer) sale con 1, a propósito.
- Fuera los imports sin usar (`shutil` en `ordena`, `escape` en `convierte`, dos en tests) y
  un f-string sin nada dentro en `doctor`. El menú ya no dice «(Gemini)» en `comprobar-ia`.
- Pendiente para el final: la v1.1.0 (versión, CHANGELOG, README con `@v1.1.0`, etiqueta y
  Release), por si cambia algo más antes de entregar.

### 2026-11-22 — ruff en GitHub Actions

- `pyproject.toml`: `[tool.ruff]` con `select = ["F", "E9", "PLE"]` (nombres sin definir,
  imports y variables sin usar, errores de sintaxis); el estilo no se revisa. En `tests/`
  se ignora F811, porque pytest pasa los fixtures importados como parámetro.
- `.github/workflows/tests.yml`: un trabajo «ruff (linter)» en Ubuntu con
  `uvx ruff@0.17.6 check src tests`, aparte de los tests. Versión fija para que no falle
  de repente por una regla nueva. README: cómo pasarlo en local.

### 2026-11-22 — Modo guiado: la carpeta una sola vez y «cd …»

- `pasos_ajustes` ya no pregunta `--carpeta`: lo pregunta antes `pasos_carpeta` («¿En qué
  carpeta?»). En `nuevo` salía dos veces.
- `preguntar_carpeta` entiende `cd ..` / `cd "Mis cosas"` (se escribe por costumbre de la
  terminal) igual que `..`.
- En una pregunta de archivo obligatoria, `ls` o `dir` enseñan lo que hay en la carpeta
  (`ver_carpeta`: en columnas, carpetas con «/», como mucho 60) y vuelven a preguntar.
- 3 tests en `test_interactivo.py`.

### 2026-11-22 — Repaso de los documentos

- `docs/arquitectura.md`: faltaban `logo.py`, `chuletas/` y las órdenes de estudio y
  programación (`chuleta`, `estudia`, `foco`, `entregas`, `nuevo`, `hoy`, `compara`,
  `falsos`, `sql`); `config` tiene también `versiones` y `autocompletar`.
- `AGENTS.md`: ruff y `IANoDisponible`; los tests nunca llaman a la IA de verdad.
- README: la sección «IA (Gemini)» pasa a «IA» (también Ollama o el servidor del centro).
- Resumen de este archivo: probado en los tres sistemas con GitHub Actions.

### 2026-11-22 — Modo guiado de `falsos` paso a paso

- `interactivo.pasos_falsos` (en `PREGUNTAS_PROPIAS`): cuántas filas (1-10 000), qué
  columnas (enseña las que hay, las comprueba con `falsos.leer_campos`), formato en un menú
  (tabla, csv, json, sql) y, según el formato, el archivo (Intro = `datos.csv`…), el nombre
  de la tabla SQL (validado) o el separador del CSV (`;` o `,`). La semilla y `--simular`
  no se preguntan: quien los quiera los escribe en la orden.
- Repaso de las preguntas del guiado que nombraban opciones (`--algo`): `qr` y
  `acciones versiones borrar` cambiadas a castellano normal; `copia a` tiene sus preguntas.
- 3 tests en `test_interactivo.py`.

### 2026-11-22 — El cerrojo del índice de versiones en Windows

- En GitHub Actions (Windows) fallaba a veces `test_dos_navaja_a_la_vez_no_se_pisan_el_indice`:
  11 de 30 versiones en el índice. Al terminar, cada navaja borra su cerrojo, pero en
  Windows no se puede borrar mientras otro lo está leyendo (para ver si está abandonado); el
  error se ignoraba y el cerrojo se quedaba puesto, y los demás se rendían a los 5 s.
- `_quitar_el_mio` reintenta unos 2 s. Test nuevo que simula tres fallos al borrar.

### 2026-11-22 — Carpetas personales de Linux en español

- `carpeta_personal` (en `comun.py`): `~/Downloads` que no existe → la de
  `XDG_DOWNLOAD_DIR` en `~/.config/user-dirs.dirs` (`~/Descargas`). Igual con Documents,
  Pictures, Desktop, Music y Videos. La usan `Motor.carpeta` y las rutas absolutas de
  destino de las acciones. Si el archivo no está (Windows, macOS), la ruta tal cual.
- Tests en `test_comun.py` con una carpeta personal falsa en `tmp_path`.

### 2026-11-22 — Versión 1.1.0

- `pyproject.toml`, `__version__` y `uv.lock` a 1.1.0. En el CHANGELOG, lo de «Sin publicar»
  pasa a `[1.1.0]`. README: instalación con `@v1.1.0` y cómo instalar en Ubuntu desde cero.
- Etiqueta `v1.1.0` y Release en GitHub con las notas del CHANGELOG.

### 2026-11-22 — Prueba en Ubuntu (PC de casa, en español)

- Instalada la 1.1.0 desde GitHub con uv: `doctor` bien (Python 3.12 lo trae uv). Hizo
  falta `git` (ya en el README).
- `acciones validar` avisaba de que `~/Downloads` no existe y `ver` lo enseñaba así: ahora
  `esquema.avisos` y `donde` usan `carpeta_personal`. Test con un Ubuntu falso.
- `doctor` y `sin_clave` dicen la ruta del `.env` en vez de «copia .env.example».
- Instalado desde GitHub, `acciones editar` creaba un `acciones.json` con una sola acción:
  ahora copia las 10 del proyecto, que van en el paquete (`ejemplo-acciones.json`,
  `package-data`). Un test comprueba que es igual que el `acciones.json` del repo.

### 2026-11-22 — `renombra ia`: nombres claros en cualquier carpeta

- Orden nueva `renombra ia` (en `comandos/renombra.py`): una acción `renombrar-ia` hecha en
  el momento, como `copia a` con `copiar`: el mismo plan, `Motor.planificar`, `mostrar_plan`
  y `hacer`, con el registro «renombra» (`renombra deshacer`). Por defecto
  `--solo pdf,docx,odt`; `-i/--instrucciones` pasa por la misma validación que en
  `acciones.json`. Los imports de acciones/motor/mis_acciones van dentro de la función:
  `esquema` importa `renombra` y se importarían en círculo.
- Tests en `test_ia.py` con el proveedor `Falso`: otra carpeta y deshacer, la carpeta
  actual con `--simular`, el filtro por defecto, las instrucciones, sin clave (código 4) y
  una carpeta que no existe.
- Probado en `DAM/Inglés`: «0 archivos» porque los apuntes están por unidades. Ahora, sin
  `-r` y sin nada arriba, dice cuántos documentos hay en las subcarpetas (`avisar_de_subcarpetas`).

### 2026-11-22 — Versión 1.2.0

- `pyproject.toml`, `__version__` y `uv.lock` a 1.2.0. En el CHANGELOG, lo de «Sin publicar»
  pasa a `[1.2.0]`: `renombra ia`, las 10 acciones al crear `acciones.json` y los arreglos
  de la prueba en Ubuntu. README con `@v1.2.0`.
- Etiqueta `v1.2.0` y Release en GitHub con las notas del CHANGELOG.

### 2026-11-22 — Instalador de una línea

- `instalar.ps1` (Windows, PowerShell 5.1) e `instalar.sh` (Linux y macOS): buscan uv (o lo
  instalan con el instalador oficial de astral.sh), y `uv tool install --force
  "navaja[todo] @ …/archive/refs/tags/vX.Y.Z.zip"`: el .zip de la versión, para no
  necesitar git. Luego `uv tool update-shell` y `navaja --version`. Variables:
  `NAVAJA_VERSION`, `NAVAJA_EXTRAS` y `NAVAJA_ORIGEN` (las pruebas).
- El .ps1 va dentro de `& { }` y sin `exit`: con `irm | iex`, un exit cierra la ventana.
  `$ErrorActionPreference = "Continue"`: con «Stop», PowerShell 5.1 toma el stderr de uv
  (su barra de progreso) por un error.
- `lotes.como_instalar` entiende `archive_info` en `direct_url.json` (instalado desde un
  .zip) y, si no se sabe el origen, propone el .zip de la versión (`zip_de_version`).
- Tests (`test_instalar.py`): la versión de los dos scripts es la de navaja (al sacar una
  versión hay que cambiarla también ahí), bajan el .zip y no usan git, el .ps1 no tiene
  `exit`, `sh -n`, y el camino de `instalar.sh` con un `uv` de mentira (instala con
  `--force`, otra versión y extras, y si uv falla sale con 1).
- GitHub Actions: trabajo «instalador» en Ubuntu, Windows (PowerShell 5.1) y macOS que
  instala de verdad desde el .zip de ese commit. Probado aquí con un .zip local.

### 2026-11-22 — Versión 1.2.1

- La etiqueta `v1.2.0` era de antes del instalador: quien instalaba con él tenía un `doctor`
  sin la orden del `.zip`. La 1.2.1 lo lleva.
- `pyproject.toml`, `__version__`, `uv.lock`, `instalar.ps1` e `instalar.sh` a 1.2.1. En el
  CHANGELOG, lo de «Sin publicar» pasa a `[1.2.1]`. README con `@v1.2.1`.
- Etiqueta `v1.2.1` y Release en GitHub con las notas del CHANGELOG.

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
  - «el-mas-nuevo» se fía del reloj de cada PC (si uno va adelantado, gana el suyo; la
    versión que pierde va a «versiones», no se pierde).
  - Fuera de Windows no se sabe el sistema de archivos: siempre hay duda (± 1 h vale como
    igual; con menos de una hora, «míralo tú»).
  - `hora_dudosa` no se ha probado con un USB FAT32 de verdad (solo simulado). Un recurso de
    red (UNC) dice «NTFS» aunque detrás sea otra cosa.
  - `comprobar_destino` no sirve en Linux/macOS (la raíz «/» siempre existe: un USB sin
    montar se copiaría al disco interno) ni distingue otro USB que coja la misma letra.
  - En `pc-a-usb` la versión vieja del USB se aparta a C: (con archivos grandes, lento:
    hay que copiarla). Decidido así (Sergio, 2026-11-17): en el PC se recuperan aunque el
    USB no esté; para que no ocupen, caducan y hay `guardar_viejas: false`.
- [x] Ctrl+C en mitad de una copia: temporal, versiones y deshacer.
- [ ] De la revisión de `copia`, sin arreglar:
  - Con OneDrive, Documentos y Escritorio están en otra ruta (Known Folders de Windows):
    la lista no los encontraría.
  - Nombres repetidos sin normalizar Unicode (NFC/NFD en macOS).
- [ ] `excluir` compara el nombre tal cual: en macOS un nombre con tildes en NFD no coincide
  con el del JSON (en NFC).
- [x] Traza `UnicodeEncodeError` con `✔` o `→` en Git Bash o con la salida redirigida.
- [ ] De la revisión de la fase 2, sin arreglar:
  - Ctrl+C con trabajo en Python (Pillow, PyMuPDF, pdf2docx): la tarea en marcha no se
    puede parar, hay que esperar a que acabe (con un PDF de 200 páginas, un rato). Con
    LibreOffice en Windows puede quedar un `soffice.bin` vivo y su carpeta en %TEMP%.
    Mientras se recoge, Ctrl+C se ignora: si una tarea se cuelga (FFmpeg va sin `timeout`)
    solo queda cerrar la terminal. Hay un instante, justo tras el primer Ctrl+C, en que un
    segundo aún daría traza.
  - `busca`: un fallo de navaja al leer un archivo saldría como «dañado», sin traza (es el
    precio de que un archivo raro no pare la búsqueda); imágenes y binarios cuentan como
    mirados; si se para en 500 líneas, la lista de no leídos queda a medias sin decirlo.
  - `baja` con una lista: cuenta como «1 vídeo» y resuelve todos antes de enseñar nada.
  - `busca` sin tildes: «año» encuentra «ano»; con `--regex` sí mira las tildes.
  - `busca`: el tope de 20 MB no se aplica a PDF ni a docx (uno de 500 MB se lee entero).
  - `qr --guardar foto.jpg` lo cambia a `foto.png` sin avisar; los mensajes con
    `error.strerror` salen en inglés en Windows («Permission denied»).
- [ ] Fase 3 (documento de ideas): `chuleta`, `estudia`, `foco` y `entregas` hechas; también `nuevo`, `hoy` y `compara`. El resto, solo si hace falta (Sergio,
  2026-11-17: «no las quiero todas»). `falsos` y `sql` también. Quedan `regex` y `tiempo`; de estudio,
  `apuntes` y `horario` (aparcadas: «pasamos ya de estudio»). `portada` descartada.
- [ ] `baja`: no se puede probar de verdad aquí (sin internet a YouTube); probarlo en casa.
- [ ] `convierte`: EPUB, SRT, RAR y SVG (ideas de Filee); `pdf`: varias páginas por hoja.
- [ ] `extrae`: zip con contraseña, RAR y 7z (con 7-Zip). `arbol` y `comprime`: los
  `.gitignore` de las subcarpetas.
- [ ] `clave fuerza`: la lista de contraseñas comunes es corta (unas 40) y la de palabras
  solo tiene 343; es una estimación, no lo que haría un atacante de verdad.
- [ ] `subred`: escribir `navaja subred 192.168.1.5/24` sin `ver` (hoy hace falta `ver`).
- [ ] Mejoras de la revisión del `--config` del grupo: que «Uso:» de `navaja acciones`
  enseñe `[--config RUTA]`, y permitir también `acciones --config * validar` en los
  permisos del agente.
- [ ] Que el agente no pueda ejecutar acciones en ningún caso (ahora pide permiso).
- [ ] Con `COLUMNS=40`, `test_help_de_un_comando_en_castellano` falla (el `--help` se parte
  en líneas estrechas). Ya pasaba antes del menú nuevo.
- [ ] Un nombre con un emoji de dos partes (❤️, con U+FE0F) mide 1 columna para Rich y 2 en
  Windows Terminal: en `listar` y `ocupa` esa fila descoloca el borde derecho. Es un límite
  de Rich; se podría dejar una columna de margen.
- [ ] La barra de `ocupa` con `#` y `-` (salida sin UTF-8) no se ha probado a mano: desde Git
  Bash navaja siempre escribe en UTF-8.
- [x] Linter (ruff) en GitHub Actions. Formateador: no, para no cambiar el estilo de todo.
- [x] IA: Ollama o el servidor del centro como otro proveedor (`Servidor`, con `NAVAJA_IA_URL`).
- [ ] Empaquetado y publicación (pipx / PyPI).

## Cómo comprobar el estado

```bash
uv run --extra dev pytest
uv run python -m compileall -q src tests
uv run navaja --help
```
