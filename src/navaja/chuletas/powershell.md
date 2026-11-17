# PowerShell / Windows: archivos, procesos, red y winget

## Moverse y mirar

- `Get-Location` (`pwd`) — en qué carpeta estás
- `Get-ChildItem` (`ls`, `dir`) — lo que hay; con `-Force`, también lo oculto
- `Set-Location carpeta` (`cd`) · `cd ..` · `cd ~` — entrar, subir e ir a tu carpeta de usuario
- `Get-ChildItem -Recurse -Filter *.pdf` — buscar archivos por nombre en las subcarpetas
- `explorer .` — abre la carpeta actual en el Explorador

## Archivos y carpetas

- `New-Item -ItemType Directory carpeta` (`mkdir`) — crear una carpeta
- `New-Item archivo.txt` — crear un archivo vacío
- `Copy-Item origen destino` (`cp`) · con `-Recurse` — copiar un archivo o una carpeta entera
- `Move-Item origen destino` (`mv`) — mover
- `Rename-Item viejo.txt nuevo.txt` — cambiar de nombre
- `Remove-Item archivo` (`rm`) · con `-Recurse` — borrar (no va a la Papelera)

## Ver y buscar

- `Get-Content archivo` (`cat`) — ver un archivo
- `Get-Content registro.log -Tail 20 -Wait` — el final de un archivo, en directo
- `Select-String "texto" *.txt` — busca un texto dentro de los archivos (el `grep` de Windows)
- `(Get-Content archivo).Count` — cuántas líneas tiene

## Procesos

- `Get-Process` (`ps`) — los programas en marcha
- `Get-Process chrome` — solo los que se llaman así
- `Stop-Process -Name notepad` · `Stop-Process -Id 1234` — cerrar un programa
- `taskmgr` — abre el Administrador de tareas

## Red

- `ipconfig` · `ipconfig /all` — tu IP, máscara y puerta de enlace (con `/all`, también la MAC y el DNS)
- `ipconfig /flushdns` — vacía la caché del DNS
- `ping 8.8.8.8` · `Test-Connection 8.8.8.8` — ¿hay conexión?
- `Test-NetConnection web.com -Port 443` — ¿está abierto ese puerto en ese equipo?
- `Get-NetTCPConnection -LocalPort 8000` — ¿quién usa el puerto 8000? (mira `OwningProcess`)
- `netstat -ano` — todas las conexiones con el número de proceso (PID)
- `Resolve-DnsName dominio.com` · `nslookup dominio.com` — preguntar al DNS
- `tracert 8.8.8.8` — por qué routers pasa

## Programas (winget)

- `winget search nombre` — buscar un programa
- `winget install --id Git.Git` — instalarlo
- `winget upgrade` · `winget upgrade --all` — ver las actualizaciones, o hacerlas todas
- `winget uninstall nombre` — quitarlo

## Sistema

- `systeminfo` — Windows, memoria, procesador y desde cuándo está encendido
- `Get-PSDrive -PSProvider FileSystem` — los discos y su espacio libre
- `hostname` · `whoami` — nombre del PC y tu usuario

## Variables y perfil

- `$env:PATH` — las carpetas donde Windows busca programas
- `$env:EDITOR = "code --wait"` — una variable solo para esta ventana
- `$PROFILE` — tu archivo de perfil (lo que se carga al abrir PowerShell); `notepad $PROFILE` para editarlo
- `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` — permite ejecutar tus scripts `.ps1`

## Tuberías y redirecciones

- `orden > archivo.txt` · `orden >> archivo.txt` — guardar la salida (pisando, o añadiendo al final)
- `Get-Process | Sort-Object CPU -Descending | Select-Object -First 5` — los 5 que más gastan
- `Get-ChildItem | Where-Object Length -gt 100MB` — solo los archivos de más de 100 MB
- `orden | Out-File salida.txt -Encoding utf8` — guardar en UTF-8 (para las tildes)

## De Linux a PowerShell

| Linux | PowerShell |
| --- | --- |
| `ls -la` | `Get-ChildItem -Force` |
| `grep texto archivo` | `Select-String texto archivo` |
| `cat` / `tail -f` | `Get-Content` / `Get-Content -Wait` |
| `ps aux` / `kill` | `Get-Process` / `Stop-Process` |
| `ip a` | `ipconfig` |
| `ss -tulpn` | `Get-NetTCPConnection` |
| `which python` | `Get-Command python` |
| `clear` | `cls` |
| `man orden` | `Get-Help orden` |
