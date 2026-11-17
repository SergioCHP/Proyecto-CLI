# Linux / bash: archivos, permisos, procesos y red

## Moverse y mirar

- `pwd` — en qué carpeta estás
- `ls -la` — todo lo que hay, también lo oculto, con permisos y tamaño
- `cd carpeta` · `cd ..` · `cd ~` · `cd -` — entrar, subir, ir a tu casa y volver a la anterior
- `tree -L 2` — el árbol de carpetas, dos niveles

## Archivos y carpetas

- `mkdir -p a/b/c` — crea carpetas, también las de en medio
- `touch archivo.txt` — crea un archivo vacío
- `cp origen destino` · `cp -r carpeta destino` — copiar un archivo o una carpeta entera
- `mv origen destino` — mover o cambiar de nombre
- `rm archivo` · `rm -r carpeta` — borrar (no hay papelera: no se recupera)
- `ln -s destino enlace` — enlace simbólico (un acceso directo)

## Ver y buscar

- `cat archivo` · `less archivo` — ver un archivo entero o página a página (`q` para salir)
- `head -n 20 archivo` · `tail -f registro.log` — el principio, o el final en directo
- `grep -rn "texto" carpeta` — busca un texto dentro de los archivos, con el número de línea
- `find . -name "*.py"` — busca archivos por nombre
- `wc -l archivo` — cuántas líneas tiene

## Permisos y dueños

- `chmod 755 script.sh` · `chmod +x script.sh` — cambiar permisos (`navaja chmod 755` te los explica)
- `chown usuario:grupo archivo` — cambiar el dueño
- `sudo orden` — hacer algo como administrador

## Usuarios

- `whoami` · `id` — quién eres y en qué grupos estás
- `sudo adduser nombre` — crear un usuario
- `sudo usermod -aG grupo nombre` — meter un usuario en un grupo
- `passwd` — cambiar tu contraseña

## Procesos

- `ps aux` — todos los procesos
- `top` o `htop` — los procesos en directo (`q` para salir)
- `kill PID` · `kill -9 PID` — pedir que se cierre, o cerrarlo a la fuerza
- `orden &` · `jobs` · `fg` — en segundo plano, ver cuáles y traerlo delante

## Red

- `ip a` — tus tarjetas de red y sus IP
- `ip r` — la puerta de enlace (la línea `default`)
- `ping -c 4 8.8.8.8` — ¿hay conexión?
- `ss -tulpn` — puertos abiertos y qué programa los usa
- `curl -I https://web.com` — ¿responde la web? (solo las cabeceras)
- `nslookup dominio.com` · `dig dominio.com` — preguntar al DNS

## Paquetes (Debian y Ubuntu)

- `sudo apt update` — actualiza la lista de programas
- `sudo apt upgrade` — actualiza los programas instalados
- `sudo apt install nombre` · `sudo apt remove nombre` — instalar y quitar
- `apt search texto` — buscar un programa

## Discos y espacio

- `df -h` — espacio libre de cada disco
- `du -sh carpeta` — cuánto ocupa una carpeta
- `lsblk` — los discos y sus particiones

## Tuberías y redirecciones

- `orden > archivo` · `orden >> archivo` — guardar la salida (pisando, o añadiendo al final)
- `orden1 | orden2` — la salida de una es la entrada de la otra: `ls | grep txt`
- `orden 2> errores.txt` — guardar solo los errores
- `orden1 && orden2` — la segunda solo si la primera sale bien

## Atajos de la terminal

- `Tab` — completa nombres · `Ctrl+C` — corta lo que está en marcha
- `Ctrl+R` — busca en lo que ya has escrito · `history` — todo lo escrito
- `Ctrl+L` o `clear` — limpia la pantalla
- `man orden` · `orden --help` — la ayuda de una orden
