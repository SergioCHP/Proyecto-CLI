# ADR-0002: La capa de IA: Gemini, con la clave en .env y navaja sigue sin ella

- Estado: aceptada
- Fecha: 2026-11-17
- Autor: Sergio Chorques Perales

## Contexto

Todo lo que hace navaja con mis archivos se decide por cosas que se ven desde fuera:
la extensión, la fecha, el nombre. Hay dos tareas en las que eso no basta, porque
dependen de lo que **dice** el documento:

- En Descargas acaban `documento (3).pdf`, `Tema5.pdf` o `descarga.docx`, y para saber
  qué son hay que abrirlos uno a uno.
- Los apuntes de DAM son PDF largos; antes de estudiar me viene bien un resumen con la
  idea principal y los puntos clave.

Para eso hace falta un modelo de lenguaje. La rúbrica pide además que la clave no esté
nunca en el repositorio y que la CLI funcione sin red.

## Decisión

1. **Dos tipos de acción nuevos en `acciones.json`**, como los demás: `renombrar-ia` y
   `resumir-ia`. Siguen el mismo camino que el resto (plan, `--simular`, `[s/n]`,
   `deshacer`) y se pueden meter en una rutina (`descargas-con-ia`). Así sigue valiendo
   el ADR-0001: una acción con IA nueva es editar el JSON (con `instrucciones` para
   decirle a la IA qué quiero), no el código.
2. **Proveedor: Gemini (Google)**, con la clave gratuita de Google AI Studio y el modelo
   `gemini-flash-lite-latest` (cambiable con `NAVAJA_MODELO`): con `gemini-flash-latest`, que
   piensa antes de contestar, la prueba pasaba de 60 segundos; el Lite contesta en uno. Se le llama por su API REST con
   `urllib` de la librería estándar: ninguna dependencia nueva.
3. **Todo lo de la IA está en un módulo**, `proveedor_ia.py`: la clase `ProveedorIA` (con
   la fábrica `desde_entorno`) y su subclase `Gemini`. Las acciones solo llaman a
   `preguntar`; no saben a quién preguntan.
4. **La clave, en `.env`** (variable `GEMINI_API_KEY`), que está en el `.gitignore` desde
   el primer commit; `.env.example` dice qué poner. También vale como variable de entorno.
   Va en una cabecera HTTP, no en la URL, y navaja nunca la enseña entera.
5. **Sin IA no se rompe nada.** Sin clave, sin red, con la clave mala o sin cupo se lanza
   `IANoDisponible` (código 4): se explica en una línea, sin traza, y las órdenes y
   acciones sin IA funcionan igual. En una rutina, el paso con IA se salta y se hacen los
   demás. `navaja comprobar-ia` dice qué pasa y cómo arreglarlo.

## Alternativas consideradas

1. **Ollama (un modelo en mi PC), como en clase.**
   - A favor: sin clave, sin cupo, funciona sin internet y los documentos no salen del PC.
   - En contra: no lo tengo instalado en casa y los modelos pesan varios GB; con mi PC
     iría lento. Como el proveedor está separado, añadirlo sería otra subclase de
     `ProveedorIA` sin tocar las acciones.
2. **El SDK oficial de Google (`google-genai`).**
   - A favor: menos código para la llamada.
   - En contra: una dependencia más (y sus dependencias) solo para un POST con JSON. Con
     `urllib` controlo cada error (sin red, clave mala, cupo, proxy del instituto) y lo
     explico en castellano.
3. **Una orden suelta (`navaja resume archivo.pdf`) en vez de acciones.**
   - A favor: más directo para un archivo.
   - En contra: no se configura en `acciones.json`, no se encadena en rutinas y no tendría
     simulación ni deshacer sin repetir todo lo que ya hace el motor de acciones.
4. **Clasificar con IA (mover cada archivo a la carpeta de su asignatura).**
   - En contra (por ahora): mover archivos según lo que diga la IA es más arriesgado que
     renombrarlos o escribir un archivo nuevo al lado. Primero las dos más seguras.

## Consecuencias

- **Positivas:** los nombres y los resúmenes salen del contenido. Todo se prueba con
  `--simular` y se deshace. Sin clave o sin red, navaja funciona como antes. Los tests no
  llaman nunca a Gemini: usan un proveedor falso y simulan los errores de red.
- **Negativas:** el texto de los documentos se manda a Google (el README lo avisa: no
  usarlo con documentos privados). El cupo gratis tiene límite de peticiones; si se acaba
  a medias, lo hecho se queda y lo demás sale como «sin IA». La IA puede equivocarse:
  por eso todo pasa por el plan y `[s/n]`, y cada resumen lleva una nota que lo dice.
  `renombrar-ia` pregunta al hacer el plan, así que `--simular` también gasta cupo.
- **Si cambia el proveedor:** una subclase nueva de `ProveedorIA` y que `desde_entorno`
  la elija; las acciones y `acciones.json` no cambian.
