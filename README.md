# Navaja

[![Tests](https://github.com/SergioCHP/Proyecto-CLI/actions/workflows/tests.yml/badge.svg)](https://github.com/SergioCHP/Proyecto-CLI/actions/workflows/tests.yml)

Caja de herramientas de terminal con utilidades cotidianas, con todos los comandos en castellano.

## Spec

1. **Problema que se repite:** copiar y ordenar archivos. La carpeta Descargas siempre
   tiene de todo, copio y pego los archivos de clase del USB al PC de casa y renombro
   muchas fotos una a una.
2. **Para quién:** para mí, y quizás para mi mujer, para que ordene los archivos de su PC.
3. **Uso:** `navaja ORDEN [CARPETA] [opciones]`. Sin orden (`navaja`), abre un menú
   interactivo. Alias corto: `nav`.
4. **Órdenes que ya tiene:** `listar`, `ocupa`, `limpia`, `arbol`, `busca`, `comprime`,
   `extrae`, `ordena`, `renombra`, `duplicados`, `copia`, `notas`, `convierte`, `cuenta`,
   `fondo`, `baja`, `qr`, `pdf`, `imagen`, `base`, `chmod`, `subred` (`ver`, `dividir`, `vlsm`,
   `misma`, `practica`), `estudia` (`repasa`, `importa`, `estadisticas`), `foco` (`empieza`,
   `historial`), `entregas` (`agregar`, `listar`, `hecha`, `borrar`), `chuleta`, `nuevo`, `hoy`,
   `compara`, `falsos`, `sql`, `hash`, `genera`, `clave`, `doctor`, `comprobar-ia`,
   `acciones` (`ver`, `ejecutar`, `deshacer`, `versiones`,
   `editar`, `validar`), `tema`, `config` (también `config autocompletar`, Tab en PowerShell),
   `manual` y `version`. Dentro de navaja, Tab completa y ↑ ↓ recuperan lo de antes.
5. **Órdenes previstas:** se eligen una a una de la lista de ideas, según hagan falta.
6. **Acciones:** `ordenar-descargas`, `imagenes-ia`, `instaladores-viejos`,
   `fotos-con-fecha`, `usb-a-pc`, `pc-a-usb` y la rutina `limpieza-semanal`; con IA,
   `nombres-claros` (renombra documentos por lo que dicen), `resumir-apuntes` y la rutina
   `descargas-con-ia`. La que más uso es `ordenar-descargas`, porque me gusta tenerlo todo
   en orden.
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
   - 0: todo bien (en las órdenes sueltas, también si respondo «n» a una confirmación).
   - 1: fallo al ejecutar (una carpeta o una acción que no existe). En `acciones ejecutar`,
     también si respondo «n» o si un paso de una rutina no se pudo hacer: así un script sabe
     que la acción no se hizo entera.
   - 2: uso incorrecto (falta un argumento o una opción no existe).
   - 3: `acciones.json` no existe o está mal escrito.
   - 4: la IA no se puede usar ahora (sin clave, sin internet, clave mala o sin cupo).
10. **Instalación:** con una orden desde GitHub,
    `uv tool install "navaja[todo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.1.0"`
    (más detalles en [Instalación](#instalación)). Cuando falta una librería opcional,
    navaja dice la orden que toca según cómo la instalaste: desde GitHub o desde la carpeta
    del proyecto (`--editable`).

## Utilidades

| Comando | Qué hace |
| --- | --- |
| `navaja listar [ruta]` | Muestra qué hay en una carpeta: nombre, tipo, tamaño y fecha. |
| `navaja ocupa [ruta]` | Muestra qué archivos y carpetas ocupan más espacio. |
| `navaja limpia [ruta]` | Busca y borra cachés y temporales (`node_modules`, `__pycache__`…). `dist`, `build`, `target` y `coverage` solo dentro de un proyecto de programación. |
| `navaja arbol [carpeta]` | Dibuja el árbol de carpetas de un proyecto, sin `.git`, `.venv`, `__pycache__` ni lo del `.gitignore` (`--todo` lo enseña todo). `--profundidad`, `--solo-carpetas` y `--guardar arbol.md` para pegarlo en el README. |
| `navaja busca TEXTO [carpeta]` | Busca un texto dentro de los archivos de una carpeta y sus subcarpetas, también en Word, LibreOffice y PDF, sin mirar mayúsculas ni tildes, y resalta la línea. `--regex`, `--exacto`, `--solo pdf,md`. Se salta `.git`, `.venv` y lo del `.gitignore`. Al final avisa de los que no ha podido leer (un PDF con contraseña o dañado). |
| `navaja convierte ARCHIVOS a FORMATO` | Una sola orden para cambiar de formato: imágenes entre sí (HEIC del iPhone a JPG…) y a un PDF, PDF a Word o a imágenes, Word/Excel/PowerPoint a PDF, Markdown a Word, CSV ↔ JSON ↔ Excel, vídeo a MP3, GIF o MP4 (`--comprime` para WhatsApp). Vale `*.heic a jpg`. |
| `navaja cuenta ARCHIVOS` | Palabras, caracteres, párrafos, páginas y minutos de lectura (y en voz alta) de un `.docx`, `.odt`, `.md`, `.txt`, `.html` o `.pdf` (este con `pypdf`). `--minimo 1500` dice si llegas. |
| `navaja pdf` | `une`, `separa`, `saca` y `quita` páginas (`1-3,7`), `gira`, `comprime`, `protege` y `desprotege` (contraseña AES-256) e `info`. Siempre un PDF nuevo al lado. |
| `navaja imagen` | `reduce`, `comprime`, `recorta` (`1:1`, `16:9`…), `grises`, `limpia` (quita la ubicación GPS y los datos ocultos), `icono` (favicon.ico) e `info`. Las fotos salen derechas y sin datos ocultos. |
| `navaja fondo FOTOS` | Quita el fondo de las fotos con IA y sin internet (rembg): PNG transparente, `--color blanco` para fotos de carné o `--mascara`. |
| `navaja baja ENLACES` | Descarga vídeos o el audio (`--audio`, MP3) de YouTube, Instagram, TikTok, X… con yt-dlp. Enseña título, duración y tamaño antes de bajar. `--calidad 720`, `--subtitulos es`, un `.txt` con enlaces. |
| `navaja qr TEXTO` | Un QR en la terminal para pasar un enlace o un texto al móvil; `--wifi` para que el móvil se conecte a tu wifi; `--guardar` en PNG. |
| `navaja comprime [carpeta]` | Crea un `.zip` (o `.tar.gz`) al lado de la carpeta, sin `.git`, `.venv`, `node_modules`, `__pycache__` ni lo del `.gitignore`: lo que se entrega de una práctica. `--sin *.log`, `--todo`, `--destino`, `--simular` y `[s/n]`. Nunca pisa uno que ya exista. |
| `navaja extrae ARCHIVO` | Descomprime un `.zip`, `.tar` o `.tar.gz` enseñando antes lo que lleva y preguntando `[s/n]`. Va a una carpeta nueva al lado (sin repetir la que trae dentro), se salta lo que se saldría de la carpeta y nunca pisa nada. |
| `navaja ordena` | Ordena una carpeta: por tipo, por fecha (mes, año o día), los archivos de unas fechas a una carpeta, por un texto del nombre o por letra. Con deshacer. |
| `navaja renombra` | Renombrado masivo sin saber regex: cambiar texto, añadir delante o detrás, numerar, poner la fecha, arreglar nombres o una plantilla. Con deshacer. |
| `navaja duplicados` | Encuentra archivos repetidos por contenido y los manda a una papelera recuperable. |
| `navaja copia a DESTINO [ARCHIVOS]` | Copia los archivos de una carpeta (o solo los que digas: `horario.pdf`, `*.pdf`) a otra al momento, sin escribir una acción; los originales se quedan. Con filtros, simulación y `copia deshacer`. |
| `navaja notas` | Notas y enlaces con etiquetas, guardados en SQLite. Lo que empieza por `https://` o `www.` es un enlace. |
| `navaja base NUMERO` | Pasa un número entre binario, octal, decimal y hexadecimal (`200`, `0b11001000`, `0o310`, `0xC8` o `C8h`; con `--de 2`, unos y ceros sin prefijo), con los pasos: las divisiones sucesivas, la suma de potencias o el atajo de agrupar bits (`--a 16`). Con una IP, cada octeto en binario. |
| `navaja chmod PERMISOS` | Calculadora de permisos de Linux: `755` ↔ `rwxr-xr-x` (también `4755` y lo que sale en `ls -l`), con quién puede qué en un archivo y en una carpeta, y avisos si es peligroso (`777`). Solo calcula. |
| `navaja red` | Tu tarjeta de red de un vistazo: IP con su `/prefijo`, máscara, puerta de enlace (tu router), MAC y velocidad de cada tarjeta encendida; la que sale a internet va primero con ★ y al final te da la orden `subred ver` con tu IP. Avisa si la IP es APIPA (169.254.x.x: el router no le ha dado ninguna). `--todas` enseña también las apagadas y la de loopback; `--ipv6`, las IPv6. Solo mira. |
| `navaja puertos [PUERTO]` | Qué puertos TCP esperan conexiones en tu PC (`--udp`, también UDP), con el programa, su PID, desde dónde se puede entrar (toda la red o solo este PC) y para qué se suele usar (3306 MySQL, 5173 Vite…). `puertos 8000` dice quién usa el 8000 (o que está libre) y `puertos 8000 --cerrar` cierra ese programa después de enseñarlo y preguntar `[s/n]` (`--si`, `--simular`). Nunca cierra programas del sistema. En Windows, algunos solo se ven como administrador. |
| `navaja sistema` | Cómo va el PC, en vivo hasta Ctrl+C: equipo y sistema, tiempo encendido, CPU, memoria, intercambio, cada disco y la batería con barras de colores (verde, amarillo desde el 70 %, rojo desde el 90 %), y los programas que más gastan (los procesos que se llaman igual, sumados, como en el Administrador de tareas). `--orden memoria`, `-n 10`, `--cada 5` segundos y `--una-vez`. Solo mira. |
| `navaja subred` | Calculadora de subredes para clase. `ver 192.168.10.200/26` (o `ver 192.168.10.200 255.255.255.192`, o solo la IP con la máscara de su clase): red, broadcast, primer y último equipo, hosts útiles, máscara, wildcard, clase, si es privada, pública, loopback o APIPA, y la IP en binario con los bits de red y de host en colores distintos. `dividir RED N` (partes iguales, FLSM), `vlsm RED 50 20 10` (por equipos, de mayor a menor; con nombre: `ventas:50`), `misma IP1 IP2` (¿se hablan sin router?) y `practica` (ejercicios al azar que corrige y explica paso a paso). Solo calcula: no toca la red ni los archivos. |
| `navaja hash` | Huellas MD5, SHA-1 y SHA-256 de un archivo (`hash archivo ubuntu.iso`) o de un texto (`hash texto hola`). Con `--compara` dice si coincide con la que da la web (sale con 1 si no). Lee por trozos: vale para ISO de varios GB. |
| `navaja genera` | `uuid`, `lorem` (texto de relleno) y `numero MIN MAX` (al azar; con `--sin-repetir`, un sorteo). |
| `navaja estudia` | Tarjetas de memoria con repetición espaciada (algoritmo SM-2, como Anki), sacadas de tus apuntes en `.md`: una línea `P: pregunta` y otra `R: respuesta` (que puede seguir en las líneas de debajo). `estudia importa CARPETA -a asignatura` las guarda (si una pregunta ya estaba con otra respuesta, la cambia sin perder lo aprendido; con `--simular` solo cuenta). `estudia` (o `estudia repasa`) te pregunta las que tocan hoy: Intro para ver la respuesta y `1` otra vez, `2` difícil, `3` bien, `4` fácil, `s` salir; una fallada vuelve en la misma sesión. `estudia estadisticas`: tarjetas, pendientes, aprendidas y racha de días. Se guardan en `estudia.db`. |
| `navaja foco` | Pomodoro con cuenta atrás grande en la terminal, aviso con sonido (el de Windows, o el pitido en Linux) e historial. Solo `foco` es un bloque de 25 minutos; `foco empieza -t 50 -d 10 -b 3 -a redes` cambia minutos de trabajo, de descanso, bloques y asignatura; con `--simular` enseña el plan sin esperar. Con Ctrl+C se para y lo que llevabas se apunta si pasó un minuto. `foco historial` suma el tiempo por asignatura. Se guarda en `foco.db`. |
| `navaja entregas` | Deberes y exámenes con fecha: `agregar "Práctica CLI" 20/11 -a programación` (la fecha puede ser `2026-12-15`, `15/12/2026`, `15/12`, `hoy`, `mañana` o `+3`; con `--examen` es un examen), `listar` (con cuenta atrás: rojo si queda menos de 2 días, amarillo si menos de una semana, y `--todas` enseña las hechas), `hecha N` y `borrar N`. Al abrir navaja en modo interactivo, el saludo avisa de lo que vence pronto. Se guarda en `entregas.db`. |
| `navaja chuleta [TEMA]` | Chuletas cortas y en castellano de `git`, `linux` y `powershell` (con una tabla «De Linux a PowerShell»), sin internet. Sin tema, la lista. Con `--editar`, abre tu copia en el editor (la crea copiando la de navaja, o con una plantilla si el tema es nuevo); las tuyas se guardan en `chuletas/` de la carpeta de datos y tapan a la de navaja con el mismo nombre. |
| `navaja nuevo NOMBRE` | Crea un proyecto listo para trabajar: carpeta, `README.md`, el `.gitignore` del lenguaje y una plantilla (`-l python`: `src/main.py` y `tests/`; `-l java`: `src/Main.java`; `-l web`: `index.html`, `css/`, `js/` e `img/`), y luego `git init` (rama `main`) y el primer commit. Enseña antes lo que va a crear y pregunta `[s/n]`; `--simular` solo mira, `--sin-git` no crea repositorio y `-c CARPETA` dice dónde. Si la carpeta ya existe, crea «nombre (1)». Sin git instalado, crea los archivos y dice cómo instalarlo; si git no sabe tu nombre, explica el `git config` que falta. |
| `navaja hoy [CARPETA]` | Tus commits de hoy en todos los repositorios git de la carpeta (mira 3 niveles hacia dentro, sin entrar en `.venv` ni `node_modules`), en todas las ramas, con hora y mensaje. Solo los tuyos (el `user.email` de cada repo); con `--todos`, los de todo el mundo. `--desde ayer`, `--desde -3` (hace 3 días), `--desde 10/11`. Con `--md`, en Markdown y sin colores para pegarlo en el diario de prácticas. |
| `navaja compara A B` | Diferencias entre dos archivos (las líneas quitadas en rojo y las añadidas en verde, como `git diff`; `-n` líneas de contexto, `-w` sin contar espacios; avisa si solo cambian los finales de línea; de un binario dice si son iguales) o dos carpetas (qué está solo en una, solo en la otra y qué ha cambiado, sin mirar `.git` ni `node_modules`; con `--detalle`, también las líneas). No cambia nada. |
| `navaja falsos` | Datos de prueba realistas en español (Faker, extra `falsos`): `id`, `nombre`, `apellidos`, `email` (sacado del nombre y sin repetir), `dni` (con la letra bien calculada), `telefono`, `ciudad`… y más con `--campos` (`--lista` los enseña todos). `-n` filas; `-f tabla` (para ver), `csv` (con `;` para Excel), `json` o `sql` (`CREATE TABLE` + `INSERT`, tabla con `-t`); `--guardar archivo` (el formato sale de la extensión; nunca pisa); `--semilla` para que salgan siempre los mismos. |
| `navaja sql BASE [CONSULTA]` | Abre una base SQLite. Sin consulta, sus tablas y vistas con columnas, clave, obligatorias y cuántas filas tienen. Un `SELECT` sale en una tabla (`-n` filas; `--csv` lo guarda entero), siempre con la base en solo lectura. Un `INSERT`, `UPDATE`, `DELETE`, `CREATE`… enseña antes las sentencias y pregunta `[s/n]`; guarda una copia de la base (las 5 últimas, en `sql-copias` de tus datos) y lo hace todo o nada. `--simular` lo prueba y lo deshace (dice cuántas filas cambiaría). `--archivo datos.sql` ejecuta un script (como el de `falsos`) y `--crear` crea la base si no existe. |
| `navaja clave` | `nueva` (contraseña segura al azar), `frase` (palabras al azar, fácil de recordar) y `fuerza` (cómo de fuerte es la tuya: la escribes sin que se vea y no se guarda). |
| `navaja acciones` | Tus tareas de siempre guardadas con un nombre en `acciones.json` (ordenar Descargas, copiar apuntes, quitar instaladores viejos…) para hacerlas con una orden. Con simulación, confirmación y deshacer; lo que sustituye una copia se guarda en `acciones versiones`. |
| `navaja doctor` | Revisa que todo esté listo: Python, librerías (y las opcionales), programas de fuera (git, LibreOffice, Pandoc, FFmpeg, 7-Zip, Word, winget), la carpeta de datos, `acciones.json`, si hay clave para la IA y la terminal. Dice cómo arreglar lo que falta. |
| `navaja comprobar-ia` | Dice si la IA (Gemini) está lista: de dónde sale la clave (sin enseñarla), qué modelo se usa y, con una pregunta mínima, si contesta. Si no, por qué y qué hacer (código 4). `--sin-llamar` solo mira la configuración. Ver [IA](#ia). |
| `navaja tema` | `ver` los temas y `elegir` uno (clasico, morado, terminal, pastel). |
| `navaja config` | Tu nombre para el saludo y dónde guarda navaja tus datos. La primera vez que abres navaja te pregunta cómo llamarte (Intro = tu usuario de Windows); con `config nombre` lo cambias para siempre; con `config versiones 30`, cuántos días se guardan las versiones viejas de «el-mas-nuevo» (0: siempre); con `config autocompletar $PROFILE`, Tab en PowerShell. |
| `navaja manual [comando]` | El manual completo: cómo se usa, todos los comandos con sus opciones, atajos, seguridad y datos. Con un comando, solo su parte. |

`navaja version` (o `navaja --version`) dice la versión.

`nav` es un alias corto: `nav ocupa` es lo mismo que `navaja ocupa`. (No es `nv` porque en
PowerShell `nv` ya es un atajo de `New-Variable` y se adelantaría a navaja.)

Toda la ayuda está en castellano: `navaja ocupa --help` (o `-h`) enseña lo mismo que
`navaja manual ocupa`, y los errores de uso dicen qué falta y cómo se escribe.

## Modo interactivo

Escribe `navaja` sin nada más y entras en navaja: te recibe el rótulo («NAVAJA»
en letras grandes, con los colores de tu tema) y el saludo, sale un
menú numerado y se queda esperando órdenes hasta que escribas `salir`. Si la ventana es
muy estrecha (menos de 51 columnas) o la salida no es UTF-8, el saludo sale en un
recuadro sencillo.

El menú va en recuadros, uno por grupo (Archivos, Documentos e imágenes, Redes e informática, Estudio, Programación, Lo que repites y navaja), con los
números resaltados, un icono delante de cada comando (📂 listar, 📋 copia…) y una frase
corta que cabe en una fila (la explicación entera está en `ayuda` y en el manual).
Los iconos salen en Windows Terminal, en la terminal de VS Code y en las de Linux y macOS;
en la consola antigua de Windows o con una salida que no es UTF-8 se quitan solos. Trabaja en la carpeta desde
la que entras, que se ve siempre en el prompt.

El menú (y `navaja --help`) va en siete grupos. Los de **Archivos** (1-12) se usan al
momento: les dices qué hacer y lo hacen. **Documentos e imágenes** (13-19) convierten,
trabajan con PDF y fotos, bajan vídeos y hacen QR, sin tocar nunca el original. **Redes e
informática** (20-22) son calculadoras para clase: `base`, `chmod` y `subred`.
**Estudio** (23-26) es para clase y para todo lo que quieras tener a mano: `chuleta` (chuletas
sin internet, de cualquier tema), `estudia` (tarjetas para memorizar), `foco` (pomodoro) y
`entregas` (deberes y exámenes con cuenta atrás). **Programación** (27-34) es la caja de
herramientas para tus proyectos: `nuevo`, `hoy`, `compara`, `falsos`, `sql`, `hash`, `genera` y `clave`. **Lo que repites** (35) son tus acciones: recetas
guardadas en `acciones.json` que se hacen con una palabra (`acciones ejecutar
usb-a-pc`). Y **navaja**: colores, tu nombre y el manual.

```text
PS C:\Users\sergi\Descargas> navaja
¡Hola! Es la primera vez que abres navaja.         ← solo la primera vez
¿Cómo quieres que te llame? (Intro = Sergi, tu usuario): Sergio
╭────────── navaja ───────────╮
│ Buenos días, Sergio         │
╰─────────────────────────────╯
Archivos — Se usan al momento: les dices qué hacer y lo hacen.
 1  listar      Muestra qué hay en una carpeta.
 2  ocupa       Muestra qué ocupa espacio en disco.
 …
Documentos e imágenes — Convertir, PDF, fotos, vídeos y QR. El original nunca se toca.
13  convierte   Imágenes, PDF ↔ Word, a PDF, CSV, vídeo…
 …
Redes e informática — Calculadoras para clase, con los pasos explicados.
20  base        Binario, octal, decimal y hexadecimal.
 …
Programación — Para tus proyectos: huellas, datos de prueba y contraseñas.
23  hash        Comprueba que una descarga está bien.
 …
Lo que repites — Recetas guardadas en acciones.json: se hacen con una palabra.
26  acciones    Tus recetas guardadas: verlas y hacerlas.
navaja — Colores, tu nombre y el manual.
27  doctor      Revisa que todo esté listo y cómo arreglarlo.
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
| un número | Elige esa opción. Si es un grupo (`ordena`, `notas`…) abre su submenú; si no, lo ejecuta en la carpeta actual y pregunta solo lo necesario. Lo que cambia archivos (`ordena`, `renombra`, `copia`, `limpia`, `duplicados borrar`) pregunta primero «¿En qué carpeta?» (Intro = la actual; vale una ruta completa, `~\Documents` o arrastrar la carpeta desde el explorador). `copia a` pregunta primero «¿Qué quieres copiar?»: toda una carpeta (y luego «¿Con qué archivos?») o unos archivos que eliges de una lista numerada (`1 3`, `2-5` o un nombre como `*.pdf`); después, a qué carpeta: una lista con Documentos, Descargas, Escritorio, Imágenes, Música, Vídeos, los USB y discos conectados y la carpeta actual, o una ruta escrita (`Documentos\ESTUDIO`, `E:\DAM`; Tab completa carpetas). Al elegir, entras en ella: Intro copia ahí, un número baja a una subcarpeta, `..` sube y `+` crea una nueva. Si escribes una que no existe, lo dice con su ruta entera y pregunta antes de crearla. Al final, qué hacer si allí ya hay uno distinto. En `ordena` y `renombra` pregunta al final «¿Con qué archivos?» (todos, de un tipo, los que llevan un texto o los de unas fechas), salvo en `renombra cambiar` y `avanzado` y en `ordena nombre`, donde el texto ya dice qué archivos se tocan. Debajo te dice qué opciones tiene. |
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

Mientras hace una acción sale una barra con el archivo por el que va, cuántos lleva
(«23 de 140»), el porcentaje y el tiempo. Avanza por tamaño, así que en una copia al
USB un vídeo grande cuenta más que un .txt. Al terminar se borra y queda el resumen.
En Git Bash no sale (Python no lo ve como una terminal): la acción se hace igual, solo
que sin barra. En PowerShell y Windows Terminal sí.

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
| `nombres-claros` | renombrar-ia | La IA lee los PDF y Word de la última semana en Descargas y les pone un nombre que dice lo que son: `documento (3).pdf` → `factura-movistar-octubre-2026.pdf`. |
| `resumir-apuntes` | resumir-ia | La IA resume los apuntes nuevos de `ESTUDIO/DAM` (con sus subcarpetas) y deja `tema.resumen.md` al lado de cada uno, «para estudiar». Los que ya tienen resumen se saltan. |
| `descargas-con-ia` | rutina | `instaladores-viejos` → `nombres-claros` → `ordenar-descargas`. Sin internet o sin clave, el paso con IA se salta y los otros dos se hacen igual. |

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
| `tipo` | obligatorio | `mover`, `copiar`, `ordenar`, `renombrar`, `borrar`, `rutina`, o con IA: `renombrar-ia` o `resumir-ia`. |
| `carpeta` | opcional | Dónde trabaja (`~/Downloads`). Sin ella, en la carpeta actual. Al ejecutar puedes darle otra. |
| `filtro` | opcional | Qué archivos se tocan (tabla de abajo). Sin filtro, todos. |
| `destino` | mover, copiar (en ordenar y resumir-ia, opcional) | A qué carpeta van (en `resumir-ia`, dónde se guardan los resúmenes; sin él, al lado de cada documento). Si no existe, se crea. Una ruta relativa se cuenta desde la carpeta de la acción. Si está en una unidad que no existe (un USB sin conectar), la acción no empieza. |
| `si_cambia` | copiar, opcional | Si en el destino ya hay uno distinto con el mismo nombre: `copia-aparte` (por defecto: guarda `nombre (1)` al lado, una sola vez) o `el-mas-nuevo` (se queda el más reciente; el viejo se guarda y `acciones versiones` lo enseña, lo recupera o lo borra). Con un USB (FAT32 o exFAT) de por medio, tras el cambio de hora Windows enseña sus fechas movidas una hora: si los dos se diferencian en menos de una hora, no se adivina cuál es más nuevo y sale «míralo tú» (cada vez, hasta que lo arregles tú). Copia primero a un temporal: si se corta a medias, no queda un archivo roto. `deshacer` no quita una copia que hayas editado después. |
| `guardar_viejas` | copiar, opcional | Con `el-mas-nuevo`: `true` (por defecto) guarda la versión vieja, que se borra sola pasados 30 días (`navaja config versiones` lo cambia; 0 = siempre); `false` la sustituye sin guardarla: no ocupa nada, pero no hay vuelta atrás (ni `deshacer` ni `acciones versiones` la traen). En `navaja copia a`: `--sin-guardar-viejas`. |
| `por` | ordenar | `tipo`, `mes`, `año`, `día` o `letra`. |
| `plantilla` | renombrar | El nombre nuevo con huecos: `{fecha:%Y-%m-%d}`, `{n:03}`, `{nombre}` y `{ext}`. |
| `orden` | renombrar | En qué orden se cuenta `{n}`: `nombre` (por defecto) o `fecha`. |
| `instrucciones` | renombrar-ia, resumir-ia, opcional | Lo que le pides a la IA además, hasta 500 letras: `"pon la asignatura delante"`, `"resúmelo para estudiar"`. |
| `pasos` | rutina | Las acciones que hace, en orden. No puede tener otra rutina dentro. Puede mezclar acciones con IA y sin ella. |
| `_lo-que-sea` | opcional | Lo que empieza por `_` es una nota para ti: navaja no lo lee. |

| Tipo | Qué le pasa a cada archivo |
| --- | --- |
| `mover` | Va a `destino`. Con `recursivo`, conserva las subcarpetas. |
| `copiar` | Se copia a `destino` y el original se queda. Si la copia ya está igual (mismo tamaño y fecha), no se repite; una hora justa de diferencia cuenta como igual (el cambio de hora en un USB FAT32). |
| `ordenar` | Va a una subcarpeta según `por`, como `navaja ordena`. |
| `renombrar` | Cambia de nombre según `plantilla`, como `navaja renombra plantilla`. |
| `borrar` | Va a la papelera de navaja (se recupera con `acciones deshacer`). Necesita un filtro: sin él mandaría la carpeta entera. |
| `rutina` | No toca archivos: hace sus `pasos` uno detrás de otro y pregunta en cada uno. Si un paso necesita IA y no se puede, lo dice, se lo salta y sigue (sale con 1). |
| `renombrar-ia` | La IA lee el principio del documento (`.pdf`, `.docx`, `.odt`, `.txt`, `.md`, `.html`…) y propone un nombre: minúsculas, sin tildes y con guiones; la extensión no cambia. Se pregunta al hacer el plan, así que `--simular` ya enseña los nombres (sin tocar nada). Lo que no sabe leer o no tiene texto (un PDF escaneado) se salta. Con deshacer. |
| `resumir-ia` | La IA lee el documento y escribe `nombre.resumen.md` (título, idea principal y puntos clave, y al final una nota de que lo ha hecho la IA). El original no se toca y nunca pisa nada. El que ya tiene resumen se salta. `acciones deshacer` manda los resúmenes a la papelera de navaja. |

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

Para las acciones con IA hacen falta documentos con texto de verdad:

```powershell
New-Item -ItemType Directory -Force "$p\Apuntes" | Out-Null
"Factura de Movistar. Periodo: octubre de 2026. Total a pagar: 30,25 euros." | Set-Content "$p\Descargas\documento (3).txt"
"# Subredes`nVLSM reparte una red en subredes de distinto tamaño según los equipos de cada una." | Set-Content "$p\Apuntes\Tema5.md"

navaja acciones ejecutar nombres-claros --simular --config pruebas/acciones-prueba.json
navaja acciones ejecutar resumir-apuntes --config pruebas/acciones-prueba.json
navaja acciones deshacer
```

Siempre primero con `--simular`, y en tus carpetas de verdad solo cuando la simulación
diga exactamente lo que esperas.

Si `acciones.json` está mal escrito, `acciones validar` dice la línea y la columna, enseña
la línea con una `^` debajo de lo que falla y explica qué pasa en castellano (una coma de
más antes de cerrar, comillas simples, una barra invertida suelta…). También avisa si una
clave sale dos veces en el mismo sitio (solo cuenta la última).

```text
✘ acciones.json no es JSON válido: línea 4, columna 3: sobra una coma antes de cerrar (JSON no deja una coma tras el último).
    4 │ ]
        ^
```

Para ver los errores de `acciones validar` (siempre con código de salida 3 y sin traza),
en `pruebas/` hay cuatro archivos rotos a propósito: `roto-coma.json`, `roto-tipo.json`,
`roto-repetido.json` y `roto-regex.json`:

```powershell
navaja acciones validar --config pruebas/roto-tipo.json
$LASTEXITCODE   # 3
```

## IA

Dos tipos de acción usan IA: `renombrar-ia` y `resumir-ia`. Por defecto usan Gemini
(Google); también pueden usar Ollama o el servidor de modelos del centro (más abajo). Las
dos le mandan al modelo el texto del documento (en `renombrar-ia`, solo el principio) y nada más: ni la
ruta ni otros archivos. No uses las acciones con IA con documentos privados que no
quieras mandar a Google.

**La clave.** Se saca gratis en [Google AI Studio](https://aistudio.google.com/apikey) y
va en un archivo `.env`, nunca en el código ni en `acciones.json`:

```powershell
Copy-Item .env.example .env     # y escribe tu clave detrás de GEMINI_API_KEY=
navaja comprobar-ia             # ✔ La IA está lista
```

navaja busca la clave por este orden: la variable de entorno `GEMINI_API_KEY`, el `.env`
de la carpeta en la que estás y el `.env` de tus datos (`%LOCALAPPDATA%\navaja\.env`
en Windows; así vale en cualquier carpeta). `.env` está en el `.gitignore` desde el
principio, así que la clave no se sube nunca; [.env.example](.env.example) explica qué
poner. Otras variables: `NAVAJA_MODELO` (por defecto `gemini-flash-lite-latest`, el Flash-Lite
más nuevo: contesta en un segundo; el Flash normal piensa antes y puede tardar más de 60 s) y `NAVAJA_SIN_IA=1` (apaga la IA aunque haya clave).

**Sin IA, todo lo demás sigue.** Sin clave, sin internet, con la clave mal copiada, con
la red del instituto bloqueando Gemini o sin cupo gratis, navaja lo explica en una línea
y sale con el código 4, sin trazas. Las órdenes y acciones sin IA funcionan igual; en una
rutina, el paso con IA se salta y se hacen los demás. Si la red se va a medias, lo hecho
se queda (y se puede deshacer) y no se le vuelve a preguntar.

```text
✘ No hay conexión con Gemini: ¿tienes internet? Las acciones sin IA funcionan igual; vuelve a probar cuando tengas red (navaja comprobar-ia).
```

`acciones validar` avisa si tienes acciones con IA y no hay clave, y `navaja doctor` dice
si la hay (sin llamar a Gemini). Por qué IA y por qué así: [ADR-0002](docs/adr/0002-capa-ia.md).

**Con Ollama o el servidor del centro, en vez de Gemini.** navaja también habla con
cualquier servidor compatible con la API de OpenAI (`…/v1/chat/completions`): Ollama en tu
PC, LM Studio o el servidor de modelos del centro. No hay que tocar código: basta con su
dirección en el `.env` (si está, se usa en vez de Gemini y `GEMINI_API_KEY` no hace falta):

```ini
NAVAJA_IA_URL=http://localhost:11434/v1   # Ollama; el del centro te lo da el profesor
NAVAJA_MODELO=llama3.2                    # por defecto, llama3.2
NAVAJA_IA_CLAVE=                          # solo si el servidor pide clave
```

`navaja comprobar-ia` dice a qué servidor pregunta, con qué modelo y si contesta. Si no
llega («¿está encendido o estás en la red del centro?»), si el modelo no existe («ollama
list» dice cuáles tienes) o si tarda demasiado (un modelo grande en un PC normal), lo
explica igual que con Gemini, y lo demás de navaja sigue funcionando. Con un modelo
pequeño en local, los nombres y los resúmenes salen algo peores que con Gemini.

## Instalación

Hace falta [uv](https://docs.astral.sh/uv/) (Linux, macOS y Windows). En Windows se instala con
`winget install astral-sh.uv`; en Linux y macOS, con `curl -LsSf https://astral.sh/uv/install.sh | sh`.
uv se encarga de todo lo demás, también de Python 3.12.

**Con una orden, desde GitHub** (no hace falta clonar nada):

```bash
uv tool install "navaja[todo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.1.0"
navaja --help
```

Queda el comando `navaja` (y su atajo `nav`) en cualquier carpeta. Si dice «orden no
encontrada», ejecuta `uv tool update-shell` y abre otra terminal. Sin `@v1.1.0` al final se
instala lo último de `main`; para actualizar, `uv tool upgrade navaja`; para quitarlo,
`uv tool uninstall navaja`. Con pipx también vale: `pipx install "navaja[todo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.1.0"`.

Instalada así, navaja guarda tus cosas en su carpeta de datos (`navaja config ver` te dice
cuál es; en Windows, `%LOCALAPPDATA%\navaja`; en Linux, `~/.local/share/navaja`). Ahí van tu `acciones.json` (créalo con
`navaja acciones editar`, que lo crea con las 10 acciones de este repo: cambia las carpetas
que no tengas por las tuyas) y, si usas
la IA, tu `.env` con la clave (ver [IA](#ia)).

Las órdenes de documentos e imágenes usan librerías opcionales, para no instalar lo que no
uses. `[todo]` las trae todas menos la de quitar fondos, que pesa unos 300 MB más:

```bash
uv tool install "navaja[todo,fondo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.1.0"
```

Siempre todos juntos en el mismo comando: `uv tool install` deja solo los extras que le
dices, así que instalar después solo `[fondo]` quitaría los de `todo`.

**En Ubuntu**, desde cero (uv trae su propio Python; no hace falta instalarlo):

```bash
sudo apt update && sudo apt install -y curl git   # git: navaja se instala desde GitHub
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env        # o abre otra terminal
uv tool install "navaja[todo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.1.0"
navaja doctor
```

Un `acciones.json` hecho en Windows con `~/Downloads` vale tal cual: en un Ubuntu en
español navaja usa `~/Descargas` (lo mismo con Documentos, Imágenes, Escritorio, Música y
Vídeos). Va en `~/.local/share/navaja/`, junto al `.env` si usas la IA.

**Para programar en ella**, desde una copia del repositorio:

```bash
git clone https://github.com/SergioCHP/Proyecto-CLI.git
cd Proyecto-CLI
uv tool install --editable ".[todo]"   # navaja usa el código de esta carpeta: lo que cambies, se nota ya
uv run --extra dev pytest              # los tests
```

Si cambias algo de `pyproject.toml`, vuelve a ejecutar el mismo `uv tool install`.

| Extra | Librerías | Para |
| --- | --- | --- |
| `pdf` | pypdf (con cryptography) | `pdf`, y leer PDF en `cuenta` y `busca` |
| `imagen` | Pillow, pillow-heif | `imagen` y `convierte` con imágenes (también HEIC) |
| `qr` | qrcode, Pillow | `qr` |
| `documentos` | pdf2docx (PyMuPDF), openpyxl, docx2pdf (Windows) | `convierte`: PDF a Word o a imágenes, Excel, Word a PDF |
| `baja` | yt-dlp | `baja` |
| `fondo` | rembg (con onnxruntime) | `fondo` (la primera vez descarga el modelo, unos 170 MB) |

Algunas conversiones usan programas de fuera: **FFmpeg** (vídeo y audio; también lo usa `baja`
para juntar vídeo y audio y sacar el MP3), **LibreOffice** (Word, Excel y PowerPoint a PDF; en
Windows también vale Word) y **Pandoc** (Markdown a Word). En Windows se instalan con `winget
install Gyan.FFmpeg`, `winget install TheDocumentFoundation.LibreOffice` y `winget install
JohnMacFarlane.Pandoc`. `navaja doctor` dice qué tienes y qué falta.

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

# Copiar una vez, sin crear una acción (para repetirlo siempre, mejor una acción)
navaja copia a E:/DAM -c ~/Documents/DAM -r --simular   # qué copiaría, sin tocar nada
navaja copia a E:/DAM -c ~/Documents/DAM -r             # enseña el plan y pregunta [s/n]
navaja copia a ~/Copia --solo pdf --desde "hace 7 días"  # solo los PDF de esta semana
navaja copia a E:/DAM -r --si-cambia el-mas-nuevo       # si ya está allí, gana el más reciente
navaja copia a E:/DAM horario.pdf "tema 3.docx"         # solo esos archivos
navaja copia a E:/DAM "*.pdf" -c ~/Downloads             # los PDF de Descargas (el * se busca en -c)
navaja copia deshacer                                   # quita lo que copiaste la última vez

# Notas y enlaces
navaja notas agregar "Repasar Python" "Decoradores y generadores" -e estudio,python
navaja notas agregar "Docs de Typer" https://typer.tiangolo.com -e docs   # es un enlace
navaja notas listar -e python
navaja notas buscar generadores     # sin mirar mayúsculas ni tildes
navaja notas abrir 1                # el 1 es la columna ID de «notas listar»
navaja notas etiquetas

# Proyectos y entregas
navaja arbol                                     # el árbol de la carpeta, sin .git ni .venv
navaja arbol -p 2 --guardar arbol.md             # dos niveles, en Markdown para el README
navaja comprime                                  # Proyecto-CLI.zip al lado, sin lo que sobra
navaja comprime --sin "*.log" -f tar.gz --simular
navaja extrae practica.zip                       # enseña lo que lleva y pregunta
navaja busca "función recursiva" ~/Documents/DAM  # ¿en qué apuntes salía esto?
navaja doctor                                    # ¿está todo listo?
navaja nuevo practica-redes                      # README, .gitignore, git init y primer commit
navaja nuevo mi-web -l web -c ~/Documents/DAM     # plantilla web, en otra carpeta
navaja hoy ~/Documents/DAM                       # tus commits de hoy en todos los repos
navaja hoy --desde -3 --md                       # los de 3 días, en Markdown para el diario
navaja compara v1/main.py v2/main.py             # líneas quitadas en rojo, añadidas en verde
navaja compara entrega-vieja entrega-nueva --detalle

# Documentos e imágenes
navaja convierte trabajo.pdf a docx              # PDF a Word
navaja convierte memoria.docx a pdf              # Word a PDF (LibreOffice o Word)
navaja convierte "*.heic" a jpg                  # las fotos del iPhone
navaja convierte "pizarra/*.jpg" a pdf           # todas las fotos en un PDF (pizarra.pdf)
navaja convierte clase.mp4 a mp3                 # solo el audio
navaja convierte video.mov a mp4 --comprime      # para mandarlo por WhatsApp
navaja cuenta memoria.docx --minimo 1500         # ¿llego a las palabras que piden?
navaja pdf une tema1.pdf tema2.pdf -n apuntes    # apuntes.pdf
navaja pdf saca libro.pdf 12-30                  # solo esas páginas
navaja pdf protege notas.pdf                     # con contraseña (no se ve al escribirla)
navaja imagen reduce "*.jpg" --lado 1600         # para mandarlas
navaja imagen limpia foto.jpg                    # sin la ubicación GPS
navaja fondo foto.jpg --color blanco             # foto de carné
navaja baja https://youtu.be/… --audio           # el audio en MP3
navaja qr https://github.com/SergioCHP           # al móvil con la cámara
navaja qr MiCasa --wifi                          # que el móvil se conecte a la wifi

# Calculadoras de clase
navaja base 200                                  # binario, octal y hex, con las divisiones
navaja base 0xC8                                 # de hexadecimal a decimal, con las potencias
navaja base 11001000 --de 2 --a 16               # el atajo: cada 4 bits, una cifra hex
navaja base 192.168.1.10                         # una IP, octeto a octeto en binario
navaja chmod 755                                 # rwxr-xr-x y quién puede qué
navaja chmod -- -rw-r--r--                       # lo que sale en ls -l (con -- delante)

# Tu PC: red, puertos y cómo va
navaja red                                       # IP, máscara, router y MAC
navaja puertos                                   # qué está abierto y qué programa lo usa
navaja puertos 8000                              # ¿quién usa el 8000?
navaja puertos 8000 --cerrar                     # cierra ese programa (pregunta [s/n])
navaja sistema                                   # CPU, memoria, discos… en vivo (Ctrl+C)
navaja sistema --orden memoria --una-vez         # lo que más memoria gasta, una vez

# Subredes (para clase)
navaja subred ver 192.168.10.200/26              # red, broadcast, hosts… y en binario
navaja subred ver 192.168.10.200 255.255.255.192 # la máscara también vale aparte
navaja subred ver 10.0.0.5                       # sin máscara: la de su clase (A → /8)
navaja subred dividir 192.168.1.0/24 4           # 4 subredes iguales (/26)
navaja subred vlsm 192.168.1.0/24 50 20 10 2     # por equipos, de mayor a menor
navaja subred vlsm 10.0.0.0/24 ventas:100 aula:30
navaja subred misma 192.168.1.10/24 192.168.2.5  # ¿están en la misma red?
navaja subred practica --nivel facil             # ejercicios corregidos y explicados

# Estudio
navaja estudia importa ~/Documents/apuntes -a redes   # saca las tarjetas (líneas P: y R:)
navaja estudia                                   # repasa las que te tocan hoy
navaja estudia estadisticas                      # cuántas, aprendidas y racha
navaja foco                                      # pomodoro: 25 minutos, con cuenta atrás
navaja foco empieza -t 50 -d 10 -b 2 -a bd       # dos bloques de 50 con 10 de descanso
navaja foco historial                            # cuánto has estudiado y de qué
navaja entregas agregar "Práctica CLI" 20/11 -a programación
navaja entregas agregar "Examen de redes" +10 --examen
navaja entregas listar                           # la cuenta atrás, con colores
navaja entregas hecha 1

# Programación
navaja falsos -n 5                               # 5 personas de prueba en una tabla
navaja falsos -n 100 -c nombre,email,dni -g alumnos.csv
navaja falsos -n 50 -t alumnos -g alumnos.sql    # CREATE TABLE + INSERT
navaja sql clase.db -a alumnos.sql --crear       # mete esos datos en una base nueva
navaja sql clase.db                              # sus tablas y columnas
navaja sql clase.db "SELECT ciudad, COUNT(*) FROM alumnos GROUP BY ciudad"
navaja sql clase.db "DELETE FROM alumnos WHERE id > 40" --simular
navaja hash archivo ubuntu.iso --compara 3f2a…   # ¿la descarga está bien?
navaja genera uuid -n 3
navaja genera lorem --palabras 80 --parrafos 2
navaja genera numero 1 30 -n 5 --sin-repetir     # un sorteo
navaja clave nueva --largo 20
navaja clave frase                               # nube-cobre-faro-pinza-tigre-47
navaja clave fuerza                              # la escribes sin que se vea
navaja chuleta                                   # los temas: git, linux, powershell y las tuyas
navaja chuleta git                               # la chuleta de git entera
navaja chuleta sql --editar                      # hacer una tuya (o cambiar una de navaja)

# Personalizar
navaja tema ver                 # muestra cada tema con sus colores
navaja tema elegir morado
navaja config nombre Sergio
navaja config versiones 60      # las versiones viejas, 60 días (0: siempre)
navaja config ver
```

## Seguridad

- `ordena`, `renombra` y `copia` enseñan siempre el plan y preguntan `[s/n]` antes de tocar nada; con `--simular` solo miran. Los tres tienen `deshacer`. `copia` nunca pisa un archivo distinto: guarda `nombre (1)` al lado o, con `--si-cambia el-mas-nuevo`, aparta el viejo a `acciones versiones`.
- Comodines (`copia`, `convierte`, `imagen`, `pdf`, `fondo`): navaja los expande él mismo, así que valen igual en PowerShell y en bash. Solo `*` y `?`: los corchetes son parte del nombre (`*[borrador].pdf` encuentra «apuntes [borrador].pdf»). `*` no coge ocultos ni archivos de sistema (`desktop.ini`, `Thumbs.db`); para eso, escríbelos por su nombre o empieza el patrón por punto (`.*`).
- `acciones` comprueba `acciones.json` entero antes de tocar un solo archivo, enseña el plan y pregunta `[s/n]`; `--simular` solo mira y `acciones deshacer` lo revierte (una rutina, entera). Lo que borra va a la papelera de navaja.
- La clave de la IA solo está en `.env` (ignorado por git) o en una variable de entorno; navaja nunca la enseña entera (`comprobar-ia` solo dice las 4 últimas letras) ni la escribe en ningún sitio, y va en una cabecera, no en la URL. A Gemini solo se le manda el texto de los documentos de las acciones con IA.
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

Y el linter, que busca fallos sin ejecutar nada (nombres sin definir, imports o variables
que no se usan); su configuración está en `pyproject.toml`:

```bash
uvx ruff check src tests
```

En cada `push` y en cada PR, [GitHub Actions](.github/workflows/tests.yml) pasa ruff y los
mismos tests en Ubuntu, Windows y macOS (la insignia de arriba dice si están en verde). Los
tests trabajan siempre en carpetas temporales y nunca llaman a Gemini.

La estructura está en `src/navaja/` y cada utilidad vive en `src/navaja/comandos/`.

## Documentación del proyecto

- [AGENTS.md](AGENTS.md): normas cortas que el agente lee siempre.
- [docs/arquitectura.md](docs/arquitectura.md): cómo está hecho por dentro (estructura,
  modo interactivo, ayuda, convenciones y cómo añadir comandos).
- [docs/adr/](docs/adr/): las decisiones importantes y por qué: [0001](docs/adr/0001-configuracion-externa.md)
  (acciones en un JSON y no en el código) y [0002](docs/adr/0002-capa-ia.md) (la capa de IA).
- [CHANGELOG.md](CHANGELOG.md): qué trae cada versión.
- [ESTADO.md](ESTADO.md): bitácora de lo implementado, decisiones y pendientes.
- Agente de programación: las normas están en [AGENTS.md](AGENTS.md). Para OpenCode,
  `opencode.json` y `.opencode/`; para Claude Code, `CLAUDE.md` y `.claude/`. En los dos:
  la skill `acciones-json`, el comando `/nueva-accion` y el subagente `revisor` (solo lee).
