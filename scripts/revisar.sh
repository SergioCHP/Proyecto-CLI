#!/usr/bin/env sh
# Pide al agente «revisor» (solo lee) que revise los cambios de la rama.
# Funciona con OpenCode (opencode run) o con Claude Code (claude -p).
#
# Uso:   ./scripts/revisar.sh [RAMA_BASE]      (por defecto, main)
# Ej.:   ./scripts/revisar.sh                  revisa esta rama frente a main
#        ./scripts/revisar.sh release/1.2.2    revisa frente a otra rama
#        REVISOR=claude ./scripts/revisar.sh   fuerza Claude Code (o REVISOR=opencode)
#
# Sin REVISOR, usa opencode si está instalado y, si no, claude.
# El revisor no edita nada: .opencode/agents/revisor.md y .claude/agents/revisor.md.
set -eu

base="${1:-main}"
case "$base" in
    -*)
        echo "Uso: ./scripts/revisar.sh [RAMA_BASE]   (por defecto, main)" >&2
        exit 2
        ;;
esac

# Qué agente usar
agente="${REVISOR:-}"
if [ -z "$agente" ]; then
    if command -v opencode >/dev/null 2>&1; then
        agente=opencode
    elif command -v claude >/dev/null 2>&1; then
        agente=claude
    else
        echo "No encuentro ni opencode ni claude. Instala uno de los dos y vuelve a probar." >&2
        exit 1
    fi
fi
case "$agente" in
    opencode | claude) ;;
    *)
        echo "REVISOR debe ser «opencode» o «claude», no «$agente»." >&2
        exit 1
        ;;
esac
if ! command -v "$agente" >/dev/null 2>&1; then
    echo "No encuentro $agente. Instálalo o prueba con el otro (REVISOR=...)." >&2
    exit 1
fi

# Desde la raíz del repo, para que el agente lea su configuración (.opencode/ o .claude/)
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

nuevos="$(git ls-files --others --exclude-standard)"
if [ -n "$nuevos" ]; then
    echo "Ojo: estos archivos nuevos no tienen «git add» y el revisor no los verá:"
    echo "$nuevos" | sed 's/^/  /'
fi

echo "Revisando con $agente los cambios frente a «$base»…"
git diff --stat "$base"...HEAD
git diff --stat HEAD

instrucciones="Sigue tus instrucciones: errores seguros con archivo y línea, casos feos, problemas en Windows y una pregunta para el alumno."

if [ "$agente" = opencode ]; then
    # El revisor de OpenCode puede ejecutar git diff él mismo
    opencode run --agent revisor \
        "Revisa los cambios de esta rama frente a $base. Míralos con «git diff $base...HEAD» (lo confirmado) y «git diff HEAD» (lo que aún no está en un commit). $instrucciones"
else
    # El de Claude Code solo lee archivos: le pasamos el diff por la entrada.
    # Primero a una variable: en una tubería, set -e no vería un fallo de git diff.
    cambios="$(git diff "$base"...HEAD; git diff HEAD)"
    printf '%s\n' "$cambios" |
        claude -p --agent revisor \
            "Revisa estos cambios de la rama frente a $base (el diff va a continuación; lee los archivos enteros si te hace falta contexto). $instrucciones"
fi
