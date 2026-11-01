# ADR-0001: Las acciones viven en acciones.json, no en el código

- Estado: aceptada
- Fecha: 2026-11-01
- Autor: Sergio Chorques Perales

## Contexto

navaja es mi caja de herramientas de terminal: ordena carpetas, renombra archivos,
busca duplicados… Hay tareas que repito siempre igual, como ordenar Descargas,
apartar las imágenes que hago con Gemini, quitar instaladores viejos o poner la
fecha a las fotos del móvil. Escribir cada vez la orden entera con sus opciones
(`navaja ordena tipo -c ~/Downloads --solo documentos`) es lento y es fácil olvidarse
de alguna opción.

Ahora mismo tengo 5 acciones: `ordenar-descargas`, `imagenes-ia`,
`instaladores-viejos`, `fotos-con-fecha` y la rutina `limpieza-semanal`, que hace
tres de ellas seguidas. La uso sobre todo yo. También la podrían usar mi familia o
mis compañeros, pero no creo que ganen mucho: las acciones que tengo son de mis
carpetas.

## Decisión

Las acciones se escriben en un archivo externo, `acciones.json`, con un esquema
documentado en el README y en `navaja manual acciones`. El código solo tiene el
motor que lee el archivo, lo comprueba y hace cada acción. Añadir o cambiar una
acción es editar el JSON y ejecutarla por su nombre: `navaja acciones ejecutar
ordenar-descargas`.

## Alternativas consideradas

1. **Escribir cada acción como una función en Python.**
   - A favor: no hace falta validar un archivo; si algo está mal, falla al programarlo.
   - En contra: cada acción nueva o cada cambio (por ejemplo, otra carpeta) obliga a
     tocar el código, probarlo y volver a hacer commit. Es más lento.
2. **Usar YAML o TOML en vez de JSON.**
   - A favor: YAML se lee mejor y admite comentarios.
   - En contra: JSON es el que más conozco y es fácil de usar. Python lo lee sin
     instalar nada (YAML necesita una librería más) y es el mismo formato que ya usa
     navaja para `config.json`.
3. **No guardar nada: usar solo las órdenes que ya tiene navaja con sus opciones.**
   - A favor: no hay nada nuevo que mantener.
   - En contra: hay que recordar y escribir todas las opciones cada vez, y no se
     pueden encadenar varias tareas como hace la rutina `limpieza-semanal`.

## Consecuencias

- **Positivas:** es más rápido y más fácil: una acción nueva son unas líneas en el
  JSON, sin tocar el código. Antes de hacer nada se comprueba el archivo entero, y
  todo se puede simular (`--simular`) y deshacer (`acciones deshacer`).
- **Negativas:** es fácil equivocarse escribiéndolo a mano (una coma de más, una
  barra `\` de una ruta de Windows, un campo mal escrito). Para eso, `acciones
  validar` dice qué acción y qué campo fallan, y `acciones editar` lo comprueba al
  cerrar el editor. A cambio, hay que mantener esa validación al día cada vez que
  el esquema crece.
- **Si el esquema cambia:** subo `"version"` a 2, navaja avisa si lee un archivo de
  otra versión, y lo apunto en un ADR nuevo.
