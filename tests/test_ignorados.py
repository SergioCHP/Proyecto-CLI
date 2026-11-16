from navaja.ignorados import Ignorados, Patron, recorrer


def test_patrones_del_gitignore():
    ign = Ignorados(["*.log", "build/", "/notas.txt", "docs/borradores", "**/tmp", "!importante.log", "# comentario", ""])
    assert ign.ignora("debug.log", False)
    assert ign.ignora("src/debug.log", False)
    assert not ign.ignora("importante.log", False)  # «!» lo vuelve a incluir
    assert ign.ignora("build", True) and not ign.ignora("build", False)  # solo carpetas
    assert ign.ignora("notas.txt", False) and not ign.ignora("src/notas.txt", False)  # desde la raíz
    assert ign.ignora("docs/borradores", True) and not ign.ignora("otros/docs/borradores", True)
    assert ign.ignora("a/b/tmp", True)


def test_lineas_vacias_y_comentarios_no_son_patrones():
    assert Patron.de_linea("") is None and Patron.de_linea("# hola") is None and Patron.de_linea("/") is None


def test_recorrer_salta_lo_de_siempre_y_el_gitignore(tmp_path):
    for ruta in (".git/config", ".venv/lib/x.py", "src/__pycache__/a.pyc", "src/main.py", "debug.log", "dist/app.exe"):
        (tmp_path / ruta).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / ruta).write_text("x")
    (tmp_path / ".gitignore").write_text("*.log\ndist/\n")
    recorrido = recorrer(tmp_path, Ignorados.de_carpeta(tmp_path))
    assert sorted(p.relative_to(tmp_path).as_posix() for p in recorrido.archivos) == [".gitignore", "src/main.py"]
    assert recorrido.fuera[".venv/"] == 1 and recorrido.fuera["debug.log"] == 1
    todo = recorrer(tmp_path, Ignorados.de_carpeta(tmp_path, todo=True))
    assert len(todo.archivos) == 7 and todo.fuera == {}
