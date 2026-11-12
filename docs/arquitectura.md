# Arquitectura de navaja

Cómo está hecho por dentro. AGENTS.md tiene solo las normas que el agente lee siempre;
esto se lee cuando hace falta (al añadir un comando, tocar el modo interactivo o la ayuda).
Las reglas de `acciones.json` están en la skill `acciones-json`.

## Estructura

```
src/navaja/
├── app.py              # Typer app raíz, version / --version y registro de comandos
├── interactivo.py      # `navaja` sin argumentos: menú, cd, preguntas guiadas
├── entrada.py          # leer en el modo interactivo: Tab, ↑ ↓ e historial (prompt_toolkit)
├── comun.py            # console Rich, tamaños, rutas, undo, editor, iteradores
├── filtros.py          # qué archivos: tipos, texto, fechas fáciles (ordena y renombra)
├── errores.py          # NavajaError (1), ConfigError (3), AccionNoValida(accion, campo, motivo)
├── esquema.py          # acciones.json: dónde está, leerlo y comprobarlo entero
├── acciones.py         # clases Accion (registro + fábrica desde_config) y una por tipo
├── motor.py            # Motor: elige carpeta y archivos, pide el plan a la acción
├── versiones.py        # las versiones viejas que sustituye copiar (carpeta + índice)
└── comandos/
    ├── listar.py       # listar (contenido de una carpeta en tabla)
    ├── ayuda.py        # «ayuda» (lo de aquí), «ayuda ocupa» y la orden manual
    ├── ocupa.py        # ocupa (analizar) y limpia (borrar basura)
    ├── ordena.py       # sub-app: tipo / fecha / tramo / nombre / letra / tipos / deshacer
    ├── renombra.py     # sub-app: cambiar / delante / detras / numerar / fecha / arreglar / plantilla / avanzado / deshacer
    ├── duplicados.py   # sub-app: buscar / borrar (a papelera) / restaurar / vaciar
    ├── copia.py        # sub-app: a / deshacer (una acción copiar hecha al momento)
    ├── notas.py        # sub-app SQLite: agregar / listar / buscar / abrir / borrar / etiquetas
    ├── mis_acciones.py # sub-app acciones: ver / ejecutar / deshacer / (versiones) / editar / validar
    ├── versiones.py    # acciones versiones: ver / recuperar / borrar
    └── ajustes.py      # sub-apps tema (ver / elegir) y config (ver / nombre)
tests/                  # un archivo por módulo
acciones.json           # las acciones de Sergio; pruebas/acciones-prueba.json, las mismas en ~/pruebas-navaja
```

Cada módulo de `comandos/` expone `registrar(app)` y se registra en el bucle de
`app.py`. Los comandos de nivel superior se añaden con `app.command(...)`; los
subcomandos con `app.add_typer(sub, name="...")`.

El modo interactivo no tiene una lista propia de comandos: lee los registrados
en la app (con `typer.main.get_command`), así que un comando nuevo aparece solo
en el menú y sus preguntas guiadas salen de sus argumentos (`help` y valor por
defecto). Por eso cada argumento debe tener un `help` claro. Las órdenes se
ejecutan con `raiz.main(args, standalone_mode=True)` y se captura `SystemExit`,
de modo que los errores salen igual que en la terminal y no cierran el bucle.
Solo se abre si stdin y stdout son una terminal (`puede_iniciar()`).

Al elegir un comando por número, el modo interactivo pregunta sus argumentos y,
además, las opciones con `rich_help_panel=AJUSTE` (de `comun.py`), con Intro
para dejar su valor por defecto. Marca así solo las que de verdad importan para
ese comando (en `renombra`: `--contiene`, `--orden` y, en `numerar`,
`--separador` y `--cifras`); las demás se escriben a mano. En `--help` salen en
su propio panel «Ajustes».

Los filtros (`--solo`, `--contiene`, `--desde`, `--hasta`) llevan
`rich_help_panel=FILTRO` (de `filtros.py`): el modo interactivo no los pregunta
uno a uno, sino con una sola pregunta, «¿Con qué archivos?» (todos / de un tipo /
con un texto / de unas fechas). Las fechas se leen con `filtros.periodo()`; un
argumento que se llame `desde` o `hasta` se valida igual al preguntarlo.

Si la orden tiene `--carpeta` (ordena y renombra), o pide confirmación (`--si`)
y recibe la carpeta como primer argumento (limpia, duplicados borrar), la primera
pregunta es «¿En qué carpeta?» (`pasos_carpeta`), con Intro para la actual. Las
que solo miran (listar, ocupa, duplicados buscar) no la preguntan. Un texto
obligatorio que parece una ruta (`C:\...`, `~/...`) se rechaza con un aviso:
es el error típico de escribir la carpeta donde va el texto del nombre.

En las órdenes de `EL_TEXTO_YA_ELIGE` (`renombra cambiar`, `renombra avanzado`,
`ordena nombre`) no se pregunta «¿Con qué archivos?»: el texto que se escribe ya
dice qué archivos se tocan.

Las órdenes de `PREGUNTAS_PROPIAS` (hoy, `copia a` → `pasos_copia`) hacen sus
propias preguntas en vez de las de siempre, porque unas dependen de otras: primero
«¿Qué quieres copiar?» (toda una carpeta o unos archivos de una lista, con
`elegir_archivos`) y según eso se pregunta la lista o «¿Con qué archivos?». Una
pregunta que no toca devuelve `None` en vez de una lista: `guiado` la salta, y al
volver hacia atrás también, para no quedarse atascado en ella.

Lo que se escribe se lee con el lector de `entrada.py` (prompt_toolkit): el prompt del
menú con `lector.orden(prompt, camino)`, que completa con Tab según el submenú y guarda
`historial.txt`; las preguntas con `lector(prompt)`, que completan rutas. Un argumento
con `autocompletion` (como `NOMBRE` de `acciones ejecutar`, con `nombres_para_tab`) se
completa con lo suyo en los tres sitios: PowerShell/bash (Typer), el prompt del menú
(`palabras_del_argumento()` llama a `shell_complete` del parámetro) y la pregunta guiada
(`lector.con_palabras()`). `sugerencias()`
decide qué se puede escribir y se prueba sin terminal (`tests/test_entrada.py`). Si no se
puede crear el lector, se usa `console.input`. El Tab de PowerShell/bash lo da Typer
(`completion_init()` en `app.py`) y se instala con `config autocompletar`.

Cada pregunta del modo guiado es un paso (`Paso` en `interactivo.py`):
`guiado()` los hace en orden y, si en uno se escribe «volver» (o `0` en una
lista numerada), el paso lanza `Atras` y se repite el anterior; en el primero,
se vuelve al menú. La confirmación de la orden es siempre `[s/n]`: con «n» no se
hace nada y se sigue en el menú. Una pregunta nueva debe leer con
`leer_texto()` o `elegir_numero()`, que ya saben volver (y cancelar con «salir»).
`ANTES_DE_PREGUNTAR` enseña algo antes de las preguntas (la lista de notas antes
de pedir su número).

`--help` y los errores de uso no son los de Typer (en inglés): `ayuda.py` cambia
`typer.rich_utils.rich_format_help`, `rich_format_error` y `rich_abort_error` por
los suyos (`instalar_en_castellano()`, llamada en `app.py`). La ayuda de un comando
es la misma que su parte del manual. Para que un error salga bien traducido, usa
`min=` en las opciones numéricas y `typer.BadParameter` con el mensaje en castellano.
Los consejos que nombran una orden («Para deshacerlo: …») usan
`comun.como_se_escribe()`: con «navaja» delante en la terminal y sin él dentro.

El manual (`navaja manual`) también se genera de los comandos registrados. Todo
comando, argumento y opción necesita un `help` en castellano
(`tests/test_ayuda.py` falla si falta). Lo que no se deduce del código (qué
considera basura `limpia`, cómo compara `duplicados`…) va en `EXTRA` de
`comandos/ayuda.py`; si añades un atajo al modo interactivo, añádelo también a
`MODO_INTERACTIVO` en ese archivo.

## Cómo añadir una utilidad nueva

1. Crea `src/navaja/comandos/<nombre>.py` con funciones puras para la lógica
   (planificar, calcular) y comandos Typer finos encima.
2. Añade `registrar(app)` al final del módulo.
3. Importa el módulo y añádelo al bucle de `app.py`.
4. Añade tests en `tests/test_<nombre>.py`. Pon `help` a cada argumento y
   opción: así salen en el menú, en las preguntas guiadas, en `ayuda` y en `navaja manual`.
5. Documenta el comando en `README.md` y actualiza `ESTADO.md`.

## Convenciones

- **Idioma:** comandos, opciones, ayuda y mensajes en castellano. Los
  identificadores de Python no llevan acentos (`previsualizar`, `deshacer`).
- **Comandos destructivos:** deben tener previsualización, confirmación
  (`--si` para saltarla) y deshacer cuando sea posible. Usa `--simular` para
  enseñar lo que haría sin tocar nada (el mismo nombre en todos los comandos).
  Los plurales, con `cuantos()` («1 archivo», «3 archivos»).
- **Seguridad de rutas:** usa `ruta_libre()` para evitar sobrescribir archivos,
  `iterar_archivos()` para listar (no sigue enlaces simbólicos) y
  `guardar_acciones()` / `cargar_acciones()` / `limpiar_acciones()` para el
  deshacer.
- **Sustituir sin perder nada** (como `Copiar` con `si_cambia: el-mas-nuevo` en
  `acciones.py`): copiar primero a un temporal oculto junto al destino y ponerle el
  nombre con `os.replace` solo cuando está entero; lo que se sustituye se guarda
  en `versiones` de los datos con un índice (`navaja/versiones.py`, que maneja
  `acciones versiones`), no en la papelera común (`apartar()`) y, si algo falla, se devuelve o el error dice dónde
  ha quedado. Al deshacer, no quitar nada que haya cambiado desde la acción
  (`misma_copia()`), mandar lo que se quita a la papelera en vez de borrarlo y, si algo
  falla, guardar el registro para reintentarlo.
- **Estado persistente:** siempre a través de `directorio_datos()`; nunca
  escribas en el directorio del proyecto.
- **Salida:** usa `console` para información y `error_console` para errores
  (stderr). No uses `print()`.
- **Colores:** nunca escribas colores fijos (`[green]`, `"cyan"`). Usa los
  estilos del tema: `ok`, `error`, `aviso`, `pista`, `acento`, `titulo`,
  `logro`, `marco` (bordes de paneles) y `borde` (tablas). `[bold]` sí vale.
  Un estilo nuevo se añade a todos los temas de `TEMAS` en `comun.py`.
- **Texto del usuario en Rich:** todo nombre de archivo, ruta, título o mensaje
  de excepción que vaya dentro de markup se pasa por `rich.markup.escape()`
  (si no, `[borrador].pdf` se pierde). Para un bloque de texto suelto, usa
  `rich.text.Text`.
- **Secretos:** nunca escribas claves en el código ni las subas; van en `.env`,
  que está en `.gitignore`.
- **Python 3.12 o superior** (`.python-version` fija 3.12). Usa
  `from __future__ import annotations`.
- **Tests:** sin mocks de Rich/Typer; prueba la lógica pura con `tmp_path`.
  No toques el directorio de datos real en tests (`tests/conftest.py` ya
  apunta `NAVAJA_DATOS` a una carpeta temporal en cada test).
- **Estilo:** docstrings concisas en castellano; sin comentarios obvios.
