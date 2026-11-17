# git: guardar, ramas, GitHub y deshacer

## Empezar

- `git init` — convierte la carpeta actual en un repositorio
- `git clone URL` — baja un repositorio de GitHub a una carpeta nueva
- `git config --global user.name "Tu Nombre"` — tu nombre en los commits (una vez por PC)
- `git config --global user.email "tu@correo.com"` — tu correo en los commits

## El día a día

- `git status` — qué ha cambiado y qué está preparado para el commit
- `git add archivo.py` — prepara un archivo para el siguiente commit
- `git add .` — prepara todo lo que ha cambiado en la carpeta
- `git commit -m "Mensaje"` — guarda lo preparado con un mensaje
- `git push` — sube tus commits a GitHub
- `git pull` — baja lo nuevo de GitHub y lo junta con lo tuyo

## Ver qué ha pasado

- `git log --oneline` — los commits, uno por línea
- `git log --oneline --graph --all` — los commits con el dibujo de las ramas
- `git diff` — lo que has cambiado y aún no has preparado
- `git diff --staged` — lo que has preparado y va a ir en el commit
- `git show HASH` — qué cambió en un commit concreto
- `git blame archivo.py` — quién cambió cada línea y en qué commit

## Ramas

- `git branch` — las ramas que hay (la actual, con `*`)
- `git switch -c nueva-rama` — crea una rama y se pasa a ella
- `git switch main` — vuelve a la rama main
- `git merge otra-rama` — junta otra rama con la actual
- `git branch -d rama` — borra una rama que ya está juntada

## GitHub (el remoto)

- `git remote -v` — a qué repositorio de GitHub está conectado
- `git remote add origin URL` — conecta un repositorio local con uno de GitHub
- `git push -u origin main` — la primera subida de una rama (luego basta `git push`)
- `git fetch` — mira lo nuevo de GitHub sin juntarlo todavía

## Deshacer

- `git restore archivo.py` — descarta los cambios de un archivo (¡se pierden!)
- `git restore --staged archivo.py` — lo quita de lo preparado, sin perder los cambios
- `git commit --amend -m "Otro mensaje"` — cambia el mensaje del último commit (si no lo has subido)
- `git reset --soft HEAD~1` — deshace el último commit y deja los cambios preparados
- `git revert HASH` — crea un commit que deshace otro (lo seguro si ya lo has subido)

## Guardar para luego

- `git stash` — aparta lo que estás haciendo y deja la carpeta limpia
- `git stash pop` — recupera lo apartado
- `git stash list` — lo que tienes apartado

## .gitignore

- Un nombre por línea: `.venv/`, `__pycache__/`, `*.pyc`, `.env`
- `git rm --cached archivo` — deja de seguir un archivo que ya se subió (no lo borra de tu PC)
