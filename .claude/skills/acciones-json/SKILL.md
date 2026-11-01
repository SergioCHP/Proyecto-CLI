---
name: acciones-json
description: Reglas del archivo acciones.json de navaja (campos, tipos, filtro, plantillas y validación) y del código que lo lee. Úsala siempre que crees o cambies acciones o toques esquema.py, acciones.py, motor.py o comandos/mis_acciones.py.
---
# acciones.json de navaja

## Esquema
- Raíz: `{"version": 1, "acciones": [...]}`. Lo que empieza por `_` es una nota y no se lee.
- Cada acción: `nombre` (único, minúsculas-con-guiones), `descripcion`, `tipo`.
- Tipos y sus campos:
  - `mover`, `copiar`: `destino` (obligatorio).
  - `ordenar`: `por` = tipo | mes | año | día | letra; `destino` opcional.
  - `renombrar`: `plantilla` con huecos `{fecha:%Y-%m-%d}`, `{n:03}`, `{nombre}`, `{ext}`; `orden` = nombre | fecha.
  - `borrar`: manda a la papelera de navaja; necesita `filtro`.
  - `rutina`: `pasos` = lista de nombres de acciones (sin rutinas dentro). No lleva carpeta ni filtro.
- Las de archivos admiten `carpeta` (ruta con ~ y /) y `filtro`: `solo`, `contiene`, `patron`, `desde`, `hasta`, `mayor_que`, `recursivo`, `ocultos`.
- Una ruta relativa en `destino` se cuenta desde la carpeta de la acción.

## Reglas al programar
- Todo se valida en `esquema.py` ANTES de ejecutar; lo propio de cada tipo, en `comprobar_valores` de su clase. Errores con `AccionNoValida(accion, campo, motivo)` en castellano.
- Un tipo nuevo = una subclase de `AccionDeArchivos` en `acciones.py` (se registra sola). Nada de `if tipo == ...` en el motor.
- `planificar` no toca el disco (ni mkdir): es lo que enseña `--simular`. Nunca sobrescribir (`destino_libre`, `ruta_libre`).
- pathlib, `encoding="utf-8"`, nada de `shell=True`. Funciona en Windows.
- Si cambias el esquema: actualiza `DOC_CAMPOS`/`DOC_FILTRO` de `esquema.py`, el README y esta skill (las dos copias: `.opencode/` y `.claude/`).
- Probar siempre con `--config pruebas/acciones-prueba.json` (todo en `~/pruebas-navaja`) y `--simular`. Nunca ejecutar acciones sobre carpetas reales.
- Tests: `uv run --extra dev pytest`.
