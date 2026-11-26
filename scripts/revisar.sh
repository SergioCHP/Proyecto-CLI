#!/usr/bin/env sh
# Pide al subagente «revisor» de OpenCode (solo lee) que revise los cambios de la rama.
#
# Uso:   ./scripts/revisar.sh [RAMA_BASE]      (por defecto, main)
# Ej.:   ./scripts/revisar.sh                  revisa esta rama frente a main
#        ./scripts/revisar.sh release/1.2.2    revisa frente a otra rama
#
# El revisor no puede editar ni ejecutar nada salvo git diff/log/status
# (.opencode/agents/revisor.md): solo señala y explica.
set -eu

base="${1:-main}"

if ! command -v opencode >/dev/null 2>&1; then
    echo "No encuentro opencode. Instálalo (https://opencode.ai) y vuelve a probar." >&2
    exit 1
fi

# Desde la raíz del repo, para que opencode lea opencode.json y .opencode/
raiz="$(git rev-parse --show-toplevel)" || {
    echo "Esto no es un repositorio git." >&2
    exit 1
}
cd "$raiz"

if ! git rev-parse --verify --quiet "$base" >/dev/null; then
    echo "No existe la rama «$base»." >&2
    exit 1
fi

if git diff --quiet "$base"...HEAD && git diff --quiet HEAD; then
    echo "No hay cambios frente a «$base»: nada que revisar."
    exit 0
fi

echo "Revisando los cambios frente a «$base»…"
git diff --stat "$base"...HEAD
git diff --stat HEAD

opencode run --agent revisor \
    "Revisa los cambios de esta rama frente a $base. Míralos con «git diff $base...HEAD» (lo confirmado) y «git diff HEAD» (lo que aún no está en un commit). Sigue tus instrucciones: errores seguros con archivo y línea, casos feos, problemas en Windows y una pregunta para el alumno."
