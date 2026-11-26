# Changelog

Lo que cambia en cada versión de navaja. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[Versionado Semántico](https://semver.org/lang/es/). El detalle de cada día está en
[ESTADO.md](ESTADO.md) y en el historial de git.

## [Sin publicar]

### Añadido

- `scripts/revisar.sh`: pide al subagente `revisor` de OpenCode, con `opencode run`, que
  revise los cambios de la rama frente a `main` (o la rama que se le pase).
- `opencode.json`: el MCP `context7`, apagado por defecto (se enciende con `/mcps`).

### Cambiado

- El `revisor` pasa de `mode: subagent` a `mode: all`, para que `opencode run --agent
  revisor` lo use; sus permisos (solo lectura) no cambian.

## [1.2.2] - 2026-11-26

### Documentación

- README: los números de los grupos del menú y el ejemplo del menú eran de antes de `red`,
  `puertos`, `sistema` y el grupo Estudio; la spec no nombraba `red`, `puertos` ni
  `sistema`; `comprobar-ia` no es solo Gemini; y dónde va el `.env` si instalaste navaja.
- `.env.example`: con clave de Gemini y servidor a la vez manda el servidor, sin pasar solo a
  Gemini si no contesta; cómo volver a Gemini sin un 404 por `NAVAJA_MODELO`; y qué hacer si
  el servidor del centro tiene un certificado HTTPS propio.

## [1.2.1] - 2026-11-22

### Añadido

- Instalador de una línea, sin tener nada instalado (ni Python ni git):
  `irm …/instalar.ps1 | iex` en Windows y `curl -LsSf …/instalar.sh | sh` en Linux y macOS.
  Instala uv si falta y navaja desde el `.zip` de la versión. GitHub Actions lo prueba de
  verdad en los tres sistemas (trabajo «instalador»).
- `doctor` y los avisos de librerías opcionales dicen la orden con ese `.zip` si navaja se
  instaló con el instalador (y, si no se sabe cómo, también: no necesita git).

## [1.2.0] - 2026-11-22

### Añadido

- `navaja renombra ia`: la IA lee cada documento y le pone un nombre que dice lo que es, en
  la carpeta actual o la de `-c` (la acción `nombres-claros` se queda para Descargas). Por
  defecto PDF, Word y ODT; `--instrucciones` para pedirle algo más. Se deshace con
  `renombra deshacer`.
  Si no encuentra nada pero hay documentos en las subcarpetas, dice cuántos y que añadas `-r`.

### Cambiado

- `acciones editar`, si aún no tienes `acciones.json`, lo crea con las 10 acciones del
  proyecto (antes, una sola de ejemplo). Así quien instala navaja desde GitHub las ve todas.
  Van dentro del paquete (`navaja/ejemplo-acciones.json`, copia de `acciones.json`).

### Arreglado

- Ubuntu en español: `acciones validar` avisaba de que `~/Downloads` no existe y `acciones
  ver` lo enseñaba así, aunque al ejecutar se usaba `~/Descargas`. Ahora los dos dicen
  `~/Descargas`.
- `doctor` y el aviso de «sin clave» decían «copia .env.example», que solo está en el repo;
  ahora dicen dónde va el `.env` (la carpeta de datos de navaja).

### Documentación

- README: en Ubuntu hace falta `git` para instalar desde GitHub (`sudo apt install git`).

## [1.1.0] - 2026-11-22

### Añadido

- IA con Ollama, LM Studio o el servidor de modelos del centro: cualquier servidor
  compatible con la API de OpenAI, con `NAVAJA_IA_URL` (y `NAVAJA_IA_CLAVE` si la pide) en
  el `.env`. Gemini sigue siendo el de por defecto.
- Linux en español: una acción con `~/Downloads` (o Documents, Pictures, Desktop, Music,
  Videos) usa `~/Descargas`, `~/Documentos`… si la primera no existe (lo lee de
  `~/.config/user-dirs.dirs`). Así el mismo `acciones.json` vale en Windows y en Ubuntu.

### Cambiado

- Modo guiado de `falsos`: pregunta filas, columnas (enseñando las que hay y avisando de
  las que no existen) y formato, y solo si hace falta el archivo, la tabla del SQL o el
  separador del CSV. Antes eran 8 preguntas siempre, algunas en «idioma de terminal».
- Las preguntas de `qr` y `acciones versiones borrar` ya no hablan de `--wifi` ni `--hasta`.
- `sistema`: barras finas como las de `ocupa`, con media celda de precisión.
- `doctor` y los avisos de librerías opcionales dicen la orden para instalarlas según cómo
  se instaló navaja (desde GitHub o desde la carpeta con `--editable`).
- GitHub Actions pasa también ruff (el linter) en cada push y PR; la configuración está en
  `pyproject.toml` (solo fallos de verdad y código sin usar, no el estilo).

### Arreglado

- El cerrojo del índice de versiones se quedaba puesto en Windows si otro navaja lo estaba
  leyendo al quitarlo; ahora se reintenta (fallaba a veces en GitHub Actions).
- Modo guiado: un número opcional vacío ya no se escribe como `""` (`puertos` con Intro
  fallaba).
- Modo guiado: `nuevo` preguntaba la carpeta dos veces («¿En qué carpeta?» y «Dónde
  crearlo»); ahora, una. En «¿En qué carpeta?» vale también `cd ..` o `cd Documentos`.
- Modo guiado: en una pregunta de archivo (por ejemplo, en `compara`), `ls` o `dir` enseñan
  lo que hay en la carpeta y vuelven a preguntar, en vez de tomarse como un archivo «ls».
- README: los códigos de salida dicen que en `acciones ejecutar` responder «n» sale con 1
  (en las órdenes sueltas, con 0), como hace el programa.
- Limpieza: imports que no se usaban y un f-string vacío (lo marcaba ruff). En el menú,
  `comprobar-ia` ya no dice solo «Gemini» (también puede ser un servidor).

## [1.0.0] - 2026-11-22

Primera versión completa: la que se entrega. Se instala con una orden:

```bash
uv tool install "navaja[todo] @ git+https://github.com/SergioCHP/Proyecto-CLI@v1.0.0"
```

### Acciones (`acciones.json`)

- Las acciones viven en `acciones.json`, no en el código: tipos `mover`, `copiar`, `ordenar`,
  `renombrar`, `borrar`, `rutina` y, con IA, `renombrar-ia` y `resumir-ia`. Añadir una
  acción es escribirla en el JSON ([ADR-0001](docs/adr/0001-configuracion-externa.md)).
- Órdenes `acciones ver`, `ejecutar`, `deshacer`, `validar`, `editar` y `versiones`. Todas
  enseñan el plan y preguntan `[s/n]` antes de tocar nada; `--simular` solo mira; `deshacer`
  devuelve lo último que se hizo y nada se borra de verdad (va a la papelera de navaja).
- El JSON se valida antes de ejecutar: cada error dice qué acción y qué campo falla, y
  sugiere la palabra correcta («¿Querías decir mover?»).
- Acciones propias: `ordenar-descargas`, `imagenes-ia`, `instaladores-viejos`,
  `fotos-con-fecha`, `usb-a-pc`, `pc-a-usb`, `nombres-claros`, `resumir-apuntes` y las
  rutinas `limpieza-semanal` y `descargas-con-ia`.
- Copias entre el USB y el PC con «el más nuevo gana»: la versión vieja se guarda aparte
  (`acciones versiones`) y caduca sola.

### IA (Gemini)

- `renombrar-ia`: la IA lee el principio de cada documento y le pone un nombre que dice lo
  que es. `resumir-ia`: escribe `nombre.resumen.md` al lado de cada documento.
- `navaja comprobar-ia`: dice si la IA está lista y, si no, por qué.
- La clave va en `.env` (ignorado por git; `.env.example` explica qué poner). Sin clave, sin
  red o sin cupo, navaja lo explica en una línea (código 4) y lo demás funciona igual; en
  una rutina, el paso con IA se salta y se hacen los demás
  ([ADR-0002](docs/adr/0002-capa-ia.md)).

### Órdenes

- **Archivos:** `listar`, `ocupa`, `limpia`, `arbol`, `busca`, `comprime`, `extrae`,
  `ordena`, `renombra`, `duplicados`, `copia` y `notas`.
- **Documentos e imágenes:** `convierte`, `cuenta`, `fondo`, `baja`, `qr`, `pdf` e `imagen`.
- **Redes e informática:** `base`, `chmod`, `red`, `puertos`, `sistema` y `subred`.
- **Estudio:** `chuleta`, `estudia`, `foco` y `entregas`.
- **Programación:** `nuevo`, `hoy`, `compara`, `falsos`, `sql`, `hash`, `genera` y `clave`.
- **navaja:** `doctor`, `comprobar-ia`, `tema`, `config`, `manual` y `version`.

### Modo interactivo

- `navaja` sin nada abre un menú por grupos con iconos; cada opción se puede elegir por
  número o escribiendo la orden, y las que necesitan datos los preguntan paso a paso.
- Tab completa órdenes, opciones, rutas y nombres de acciones (también en PowerShell y bash
  con `config autocompletar`); flechas con historial; `ayuda` según dónde estés.
- En ventanas bajas, el menú pasa a dos columnas.

### Calidad

- Errores propios (`ConfigError`, `AccionNoValida`, `IANoDisponible`…) con mensajes en
  castellano y códigos de salida: 0 bien, 1 algo falló, 2 orden mal escrita, 3
  `acciones.json` mal, 4 sin IA. Ningún error previsible acaba en traza.
- Más de 1000 tests con pytest, siempre en carpetas temporales y sin llamar a Gemini.
- GitHub Actions pasa los tests en Ubuntu, Windows y macOS en cada push y PR.

### Documentación

- README con la spec, todas las órdenes, el esquema de `acciones.json`, la IA y la
  instalación. Arquitectura en `docs/arquitectura.md` y decisiones en `docs/adr/`.

[Sin publicar]: https://github.com/SergioCHP/Proyecto-CLI/compare/v1.2.2...HEAD
[1.2.2]: https://github.com/SergioCHP/Proyecto-CLI/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/SergioCHP/Proyecto-CLI/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/SergioCHP/Proyecto-CLI/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/SergioCHP/Proyecto-CLI/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/SergioCHP/Proyecto-CLI/releases/tag/v1.0.0
