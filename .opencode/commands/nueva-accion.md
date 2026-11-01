---
description: Añade una acción nueva a acciones.json y, si hace falta, el código que la soporta
agent: build
---
Quiero añadir la acción: $ARGUMENTS
1. Carga la skill acciones-json.
2. Propón primero la entrada JSON y espera mi visto bueno.
3. Si el tipo ya existe, solo edita acciones.json y añade la misma acción a pruebas/acciones-prueba.json con las rutas dentro de ~/pruebas-navaja. Si el tipo no existe, añade la clase en src/navaja/acciones.py siguiendo el patrón de las demás, con sus tests.
4. Termina ejecutando `uv run navaja acciones validar` y dime qué orden con --simular y --config pruebas/acciones-prueba.json debo probar yo.
Estado actual del repo:
!`git status --short`
