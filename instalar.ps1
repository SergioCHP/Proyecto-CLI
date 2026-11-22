# navaja: instalador para Windows. Se usa así, en PowerShell:
#
#   irm https://raw.githubusercontent.com/SergioCHP/Proyecto-CLI/main/instalar.ps1 | iex
#
# Instala uv (si no está) y navaja con sus librerías, todo dentro de tu usuario: sin
# permisos de administrador y sin git (se baja el .zip de la versión). uv trae su propio
# Python 3.12: no toca el tuyo. Para quitarlo: uv tool uninstall navaja
#
# Se puede cambiar con variables:  $env:NAVAJA_VERSION = "1.2.1"; $env:NAVAJA_EXTRAS = "todo,fondo"
# ($env:NAVAJA_ORIGEN: otra dirección o archivo del que instalar; la usan las pruebas).
#
# Va todo dentro de & { }: con «irm | iex», un «exit» cerraría tu ventana de PowerShell.

& {
    $ErrorActionPreference = "Continue"  # con «Stop», PowerShell 5.1 toma lo que uv escribe en stderr por un error
    $Version = if ($env:NAVAJA_VERSION) { $env:NAVAJA_VERSION } else { "1.2.1" }
    $Extras = if ($env:NAVAJA_EXTRAS) { $env:NAVAJA_EXTRAS } else { "todo" }
    $Repo = "https://github.com/SergioCHP/Proyecto-CLI"
    $Origen = if ($env:NAVAJA_ORIGEN) { $env:NAVAJA_ORIGEN } else { "$Repo/archive/refs/tags/v$Version.zip" }

    function Paso($Texto) { Write-Host "-> $Texto" -ForegroundColor Cyan }
    function Falla($Texto) { Write-Host "x $Texto" -ForegroundColor Red }

    function Buscar-Uv {
        $Orden = Get-Command uv -ErrorAction SilentlyContinue
        if ($Orden) { return $Orden.Source }
        foreach ($Ruta in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:USERPROFILE\.cargo\bin\uv.exe")) {
            if (Test-Path $Ruta) { return $Ruta }
        }
        return $null
    }

    $Uv = Buscar-Uv
    if (-not $Uv) {
        Paso "Instalando uv (el que instala navaja y su Python)..."
        powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        $Uv = Buscar-Uv
        if (-not $Uv) {
            Falla "No encuentro uv después de instalarlo. Abre otra terminal y vuelve a probar."
            return
        }
    } else {
        Paso "uv ya está: $Uv"
    }

    Paso "Instalando navaja $Version (la primera vez baja Python y las librerías: tarda un poco)..."
    & $Uv tool install --force "navaja[$Extras] @ $Origen"
    if ($LASTEXITCODE -ne 0) {
        Falla "No se pudo instalar navaja. Mira el mensaje de arriba (¿sin internet?)."
        return
    }

    & $Uv tool update-shell 2>&1 | Out-Null  # que «navaja» se encuentre en las terminales nuevas
    $Bin = (& $Uv tool dir --bin).Trim()
    if (-not ($env:Path -split ";" | Where-Object { $_ -eq $Bin })) {
        $env:Path = "$Bin;$env:Path"  # y también en esta, sin abrir otra
    }
    & "$Bin\navaja.exe" --version
    if ($LASTEXITCODE -ne 0) {
        Falla "navaja se instaló pero no arranca: $Bin\navaja.exe"
        return
    }

    Write-Host ""
    Write-Host "Listo. " -ForegroundColor Green -NoNewline
    Write-Host "Escribe: navaja"
    Write-Host "Para ver si le falta algo: navaja doctor - Para quitarlo: uv tool uninstall navaja"
}
