---
name: acciones-json
description: Reglas del archivo acciones.json de navaja (campos, tipos, filtro, plantillas y validación) y del código que lo lee. Úsala siempre que crees o cambies acciones o toques esquema.py, acciones.py, motor.py o comandos/mis_acciones.py.
---
# acciones.json de navaja

## Esquema
- Raíz: `{"version": 1, "acciones": [...]}`. Lo que empieza por `_` es una nota y no se lee.
- Cada acción: `nombre` (único, minúsculas-con-guiones), `descripcion`, `tipo`.
- Tipos y sus campos:
  - `mover`, `copiar`: `destino` (obligatorio). `copiar` admite `si_cambia` = copia-aparte (por defecto) | el-mas-nuevo (el viejo se guarda en `versiones` de los datos, con índice: `navaja/versiones.py` y `acciones versiones ver|recuperar|borrar`; caducan solas a los `config versiones` días, 30 por defecto, en `versiones.caducar`). Con el-mas-nuevo, `guardar_viejas` (bool, true por defecto); false sustituye sin guardar (registro `sin_guardar`: deshacer no quita esa copia).
  - `ordenar`: `por` = tipo | mes | año | día | letra; `destino` opcional.
  - `renombrar`: `plantilla` con huecos `{fecha:%Y-%m-%d}`, `{n:03}`, `{nombre}`, `{ext}`; `orden` = nombre | fecha.
  - `borrar`: manda a la papelera de navaja; necesita `filtro`.
  - `rutina`: `pasos` = lista de nombres de acciones (sin rutinas dentro). No lleva carpeta ni filtro. Si un paso con IA no puede (`IANoDisponible`), se salta con aviso y siguen los demás (sale con 1).
  - Con IA (necesitan clave de Gemini): `renombrar-ia` (la IA propone el nombre por el contenido; pregunta en `planificar`, así que `--simular` ya enseña los nombres) y `resumir-ia` (escribe `nombre.resumen.md` al lado o en `destino`; pregunta en `aplicar`; registro `como: "creado"`, que `deshacer` manda a la papelera). Las dos admiten `instrucciones` (texto, ≤ 500) y leen lo que sabe `cuenta.texto_de` (`cuenta.LEIBLES`).
- Las de archivos admiten `carpeta` (ruta con ~ y /) y `filtro`: `solo`, `contiene`, `patron`, `desde`, `hasta`, `mayor_que`, `recursivo`, `ocultos`, `excluir` (nombres de carpeta en las que no entra con `recursivo`).
- Una ruta relativa en `destino` se cuenta desde la carpeta de la acción.
- `src/navaja/ejemplo-acciones.json` es una copia de `acciones.json` (lo que crea `acciones editar` al que instala desde GitHub): si cambias uno, copia el otro (un test lo comprueba).
- Al ejecutar, `CARPETA` y `--destino` cambian carpeta y destino solo esa vez (`AccionDeArchivos.con_destino`; no vale con rutinas ni con tipos sin destino).

## Cómo está repartido el código
- `esquema.py` comprueba el archivo entero antes de tocar nada (campos comunes, filtro, nombres repetidos, pasos de rutinas); el esquema se documenta en `DOC_CAMPOS` / `DOC_FILTRO`, que pinta el manual.
- Cada clase de `acciones.py` comprueba lo suyo en `comprobar_valores`.
- `Motor` (`motor.py`) elige la carpeta y los archivos; la acción hace el plan (`planificar`, sin tocar el disco) y lo ejecuta (`aplicar` por archivo).
- `comandos/mis_acciones.py` solo pinta y pregunta.
- La IA está solo en `proveedor_ia.py`: `ProveedorIA` (fábrica `desde_entorno`, `preguntar`, `llamar`), `Gemini` (urllib, clave en la cabecera) y `Servidor` (compatible con OpenAI: Ollama o el del centro, si hay `NAVAJA_IA_URL`). Los tipos con IA heredan de `AccionConIA` (`usa_ia = True`, `proveedor`, `texto`, `pedir`). Errores: `IANoDisponible` (código 4: sin clave, sin red, clave mala, sin cupo; no se insiste más) y `RespuestaIARara` (solo falla ese archivo).
- Tipo nuevo: subclase de `AccionDeArchivos` con `tipo`, `explicacion`, `campos` (campo → obligatorio), `planificar` y `aplicar`. Documenta sus campos en `DOC_CAMPOS` y en el README. Si el formato cambia de forma incompatible, sube `esquema.VERSION`.
- Errores: `NavajaError` (1), `ConfigError` (3) o `AccionNoValida` diciendo qué acción y qué campo; la orden los captura y sale con `error.codigo_salida`.

## Reglas al programar
- Todo se valida en `esquema.py` ANTES de ejecutar; lo propio de cada tipo, en `comprobar_valores` de su clase. Errores con `AccionNoValida(accion, campo, motivo)` en castellano.
- Un tipo nuevo = una subclase de `AccionDeArchivos` en `acciones.py` (se registra sola). Nada de `if tipo == ...` en el motor.
- `planificar` no toca el disco (ni mkdir): es lo que enseña `--simular`. Nunca sobrescribir (`destino_libre`, `ruta_libre`).
- pathlib, `encoding="utf-8"`, nada de `shell=True`. Funciona en Windows.
- Si cambias el esquema: actualiza `DOC_CAMPOS`/`DOC_FILTRO` de `esquema.py`, el README y esta skill (las dos copias: `.opencode/` y `.claude/`).
- `--config` vale en el grupo (`navaja acciones --config X ver`, guardado en `ctx.obj`) y en cada orden (`navaja acciones ver --config X`); si van los dos, gana el de la orden (`elegir_config`). Cada orden nueva del grupo recibe `ctx` y usa `elegir_config(ctx, config)`.
- Probar siempre con `--config pruebas/acciones-prueba.json` (todo en `~/pruebas-navaja`) y `--simular`. Nunca ejecutar acciones sobre carpetas reales.
- Tests: `uv run --extra dev pytest`. Nunca llaman a Gemini: `conftest.py` quita la clave y los `.env`, y `tests/test_ia.py` usa un proveedor `Falso` y simula los errores de red cambiando `urlopen`.
- La clave solo en `.env` (ignorado) o en la variable `GEMINI_API_KEY`; nunca en el código, en `acciones.json`, en un test ni en un mensaje. `.env.example` sin clave.
