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

## Decisiones técnicas

- **Typer + Rich** por rapidez de desarrollo y buena salida en terminal.
- **SQLite** para notas: sin dependencias extra y con consultas por etiqueta.
- **JSON en el directorio de datos** para el deshacer de `ordena` y `renombra`;
  solo se guarda la última operación.
- **Papelera propia para `duplicados`** en vez de borrar: es la única forma de
  poder deshacer un borrado sin añadir dependencias (como `send2trash`).
- **Sin dependencias más allá de Typer/Rich**: la lógica usa stdlib.
- **Temas de Rich con estilos semánticos**: los comandos dicen qué es cada
  texto (`[ok]`, `[aviso]`) y el tema decide el color; cambiar paleta no toca
  los comandos.
- **Modo interactivo sin lista propia de comandos:** el menú y las preguntas
  se generan a partir de los comandos de Typer, así que no hay que mantener dos
  sitios. Los comandos siguen funcionando igual desde la terminal (códigos de
  salida, scripts, tests).
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
