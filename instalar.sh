#!/bin/sh
# navaja: instalador para Linux y macOS. Se usa así:
#
#   curl -LsSf https://raw.githubusercontent.com/SergioCHP/Proyecto-CLI/main/instalar.sh | sh
#
# Instala uv (si no está) y navaja con sus librerías, todo dentro de tu usuario: sin sudo y
# sin git (se baja el .zip de la versión). uv trae su propio Python 3.12: no toca el tuyo.
# Para quitarlo: uv tool uninstall navaja
#
# Se puede cambiar con variables:  NAVAJA_VERSION=1.2.1  NAVAJA_EXTRAS=todo,fondo
# (NAVAJA_ORIGEN: otra dirección o archivo del que instalar; la usan las pruebas).

set -eu

VERSION="${NAVAJA_VERSION:-1.2.1}"
EXTRAS="${NAVAJA_EXTRAS:-todo}"
REPO="https://github.com/SergioCHP/Proyecto-CLI"
ORIGEN="${NAVAJA_ORIGEN:-$REPO/archive/refs/tags/v$VERSION.zip}"

paso() { printf '\033[36m-> %s\033[0m\n' "$1"; }
falla() { printf '\033[31mx %s\033[0m\n' "$1" >&2; exit 1; }

buscar_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return
    fi
    for ruta in "${XDG_BIN_HOME:-$HOME/.local/bin}/uv" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
        if [ -x "$ruta" ]; then
            echo "$ruta"
            return
        fi
    done
}

UV="$(buscar_uv)"
if [ -z "$UV" ]; then
    paso "Instalando uv (el que instala navaja y su Python)…"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        falla "Hace falta curl o wget para bajar uv: sudo apt install curl"
    fi
    UV="$(buscar_uv)"
    [ -n "$UV" ] || falla "No encuentro uv después de instalarlo. Abre otra terminal y vuelve a probar."
else
    paso "uv ya está: $UV"
fi

paso "Instalando navaja $VERSION (la primera vez baja Python y las librerías: tarda un poco)…"
"$UV" tool install --force "navaja[$EXTRAS] @ $ORIGEN" \
    || falla "No se pudo instalar navaja. Mira el mensaje de arriba (¿sin internet?)."

"$UV" tool update-shell >/dev/null 2>&1 || true  # que «navaja» se encuentre en las terminales nuevas
BIN="$("$UV" tool dir --bin)"
"$BIN/navaja" --version || falla "navaja se instaló pero no arranca: $BIN/navaja"

printf '\n\033[32mListo.\033[0m Abre otra terminal y escribe: navaja\n'
printf 'Para ver si le falta algo: navaja doctor · Para quitarlo: uv tool uninstall navaja\n'
