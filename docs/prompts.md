# Prompts clave del proyecto

Trabajo con Claude (Claude Code) en vez de OpenCode. Aquí van los mensajes que
marcaron el rumbo de navaja y lo que corregí o decidí yo de lo que hizo el agente.

## 2026-11-01 · Modo interactivo

**Herramienta:** Claude (Claude Code)

**Prompt (tal cual lo envié):**
> quiero un programa claro, estoy pensando que igual es mejor que se ejecuten las cosas cuando estas dentro, me explico, pones navaja y entra te sale un menu con todas las opciones y ejecutas lo que quieres, cuando terminas pones exit y vuenves a la terminal normal

**Qué hizo:** `navaja` sin nada abre un menú numerado que se queda esperando órdenes
hasta `salir`, y pregunta solo lo que hace falta.

**Qué corregí:** en `renombra cambiar` me preguntaba también «¿Con qué archivos?», y
sobraba, porque el texto que escribes ya dice qué archivos se cambian. Le pedí que lo
quitara (también en `renombra avanzado` y `ordena nombre`), y que `cambiar` no mirara
mayúsculas y aceptara el nombre entero con la extensión.

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · Repaso completo del proyecto

**Herramienta:** Claude (Claude Code)

**Prompt (tal cual lo envié):**
> revisa todo el proyecto para encontrar fallos, incloncuencias, que cada opcion funcione bien, que este claro para que es cada cosa mejorando que sea intuitivo en todas las opciones. en la pregunta  [s/n/volver] quizas quitaria volver porque al poner n ya vuelve.

**Qué hizo:** encontró y arregló fallos de verdad: `limpia` podía borrar carpetas mías
llamadas `build` o `coverage`, `renombra avanzado` se rompía con un traceback, había
números sin límite (`ocupa -n 0`) y plurales mal. También pasó al castellano `--help` y
los errores de uso.

**Qué corregí / decidí yo:** quitar `volver` de la confirmación: vuelve a ser `[s/n]`,
porque con `n` ya no se hace nada.

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · Mi nombre la primera vez

**Herramienta:** Claude (Claude Code)

**Prompt (tal cual lo envié):**
> cuando entres a la aplicacion la primera vez debe de preguntarte o llamarte por tu usuario, en config se cambia para que te lo llame  siempre

**Qué corregí:** navaja saludaba a todo el mundo como «Sergio» (estaba puesto a mano en
el código). Ahora la primera vez pregunta cómo llamarte; con Intro usa tu usuario de
Windows, y `config nombre` lo cambia para siempre.

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · Acciones: que sean mías, no las del maestro

**Herramienta:** Claude (Claude Code)

**Prompt (tal cual lo envié):**
> no entiendo bien las cosas, las ideas son casi todas mias, tiene que ser un proyecto mio, no tiene que se la app que diga el maestro, tiene que tener esas cosas pero mias, que es acciones.json?

**Qué hizo:** me explicó qué es `acciones.json` (el archivo dice *qué* hacer y el código
dice *cómo*) y cómo encaja en lo que ya tenía navaja, en vez de rehacerlo como `tareas`.

**Qué decidí yo:** seguir con el nombre «navaja», aprovechar los comandos que ya tenía
(`ordena`, `renombra`…) y seguir la estructura del maestro solo en lo obligatorio.

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · Esquema, validación, motor y comandos de acciones

**Herramienta:** Claude (Claude Code)

**Prompt (tal cual lo envié):**
> no se, con lo que tengo y algunas mas que introduciremos hazlo tu

**Qué hizo:** escribió `errores.py` (`NavajaError`, `ConfigError`, `AccionNoValida`),
`esquema.py` (comprueba todo el archivo antes de tocar nada), `acciones.py` (clase base
`Accion` con fábrica `desde_config` y una clase por tipo), `motor.py` y los comandos
`navaja acciones ver / ejecutar / validar / editar / deshacer`, con 5 acciones y 70 tests.

**Qué corregí / decidí yo:** pedí quitar la acción `copia-apuntes` (no la iba a usar) y que
todo lo de esta parte fuera en un solo commit.

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · Los tests fallaban en mi Windows

**Herramienta:** Claude (Claude Code)

**Prompt:** capturas del `pytest` con 3 fallos (`test_ayuda_en_el_menu_principal_explica_todas_las_opciones`).

**Qué hizo:** vio que en Windows Rich usa 79 columnas y no 80, y que un texto largo se
partía en dos líneas. Su primer arreglo (variable `COLUMNS`) no bastó; el definitivo fue
fijar el ancho de la consola en `tests/conftest.py`.

**Qué corregí / decidí yo:** probé yo el arreglo en mi Windows y fui yo quien dijo que
el primero seguía fallando.

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · Mi herramienta es Claude Code, no OpenCode

**Herramienta:** Claude (Claude Code)

**Prompt (tal cual lo envié):**
> en el paso 2, pone open code, pero yo estoy gastando cloude code y a ti, que hacemos

**Qué hizo:** hizo la skill `acciones-json`, el comando `/nueva-accion` y el subagente
`revisor` también para Claude Code (`.claude/`), además de los de `.opencode/`, y un
`CLAUDE.md` que importa `AGENTS.md`. El revisor no puede editar y solo ve `git diff`,
`git log` y `git status`.

**Qué corregí:** me dijo que creara el subagente con `/agents`, y esa opción ya no existe
en mi versión (captura). Para comprobarlo, le pido «¿qué subagentes tiene este proyecto?».

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · El ADR con mis razones

**Herramienta:** Claude (Claude Code)

**Prompt (mis respuestas, tal cual):**
> 1, Creo que es mas rapido y facil / 2, familia y compañeros, no creo que ganen mucho / 3, es el que mas conozco y es facil de usar / 4. es fácil equivocarse escribiéndolo a mano

**Qué hizo:** con esas 4 razones escribió `docs/adr/0001-configuracion-externa.md`
(contexto, decisión, tres alternativas y consecuencias).

**Qué decidí yo:** las razones son mías: por qué el JSON es más rápido y fácil, quién la
usará, por qué JSON y no YAML, y qué sale mal si lo escribes a mano.

**Qué aprendí:** _(escríbelo tú)_

## 2026-11-01 · Revisión de motor.py con el subagente revisor

**Herramienta:** subagente `revisor` (Claude Code)

**Prompt (tal cual lo envié):**
> usa el subagente revisor para revisar src/navaja/motor.py

**Qué señaló el revisor:**
- **Rutas relativas (`motor.py:58`):** sin carpeta, se trabaja con `Path(".")` y los archivos
  salen como rutas relativas. Al compararlas con el destino, que es absoluto, nunca
  coinciden: un `mover` a la carpeta donde ya estás renombra a «x (1).ext», y `deshacer` no
  encuentra los archivos si cambias de carpeta.
- **Destino por encima de la carpeta (`motor.py:86`):** con `"destino": ".."` se descartaban
  todos los archivos y decía «ningún archivo cumple el filtro».
- **`isdigit` con `²` (`motor.py:34`):** `acciones ejecutar ²` terminaba en traza.
- **Otros:** `stat()` sin proteger en `filtros.py:256`, `except ValueError` demasiado amplio
  (`motor.py:112`), y detalles menores (nombre `empiezan`, importar `a_bytes` desde
  `duplicados.py`, el `assert` desaparece con `python -O`) y sospechas sobre Windows
  (caracteres no válidos en rutas, `\\?\`).

**Qué arreglé (cada uno con su test):**
- `carpeta.resolve()` en `Motor.carpeta`: ahora las rutas son absolutas y comparables.
- El destino solo se excluye si está dentro de la carpeta de trabajo.
- `isdecimal()` en vez de `isdigit()`.

**Qué dejé y por qué:**
- `stat()` de `filtros.py:256`: solo falla si un archivo desaparece mientras se elige. Es muy
  raro y no pierde nada. Apuntado en ESTADO.md.
- `except ValueError` demasiado amplio: solo lo provocan plantillas de nombre malas, que ya
  se comprueban al validar; cambiarlo arriesga más de lo que arregla. Apuntado en ESTADO.md.
- Los menores (`empiezan`, `a_bytes`, `assert` con `-O`): no son errores.
- Las sospechas de Windows: las probaré en mi Windows antes de tocar nada.

**Su pregunta, y mi respuesta:** no hizo ninguna pregunta: terminó con «No he cambiado nada.
Si quieres, empiezo por la línea 58 con sus tests, que es lo que más se nota». Le contesté:

> arregla la línea 58 con resolve(), el destino por encima de la carpeta (línea 86) y el isdigit (línea 34), cada uno con su test. Explícame antes qué vas a cambiar

Una pregunta que yo debo saber responder: ¿por qué fallaba la línea 58? Porque sin carpeta se
trabajaba con `Path(".")` y los archivos salían como rutas relativas (`a.txt`), mientras que el
destino es absoluto. Python las compara tal cual, nunca coinciden, y por eso trataba como
distintos archivos que ya estaban en su sitio. `resolve()` convierte la carpeta en absoluta
y ya se pueden comparar; además el deshacer guarda rutas que no dependen de dónde estés.

**Qué aprendí:** _(escríbelo tú)_
