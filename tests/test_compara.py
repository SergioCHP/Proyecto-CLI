import re

from typer.testing import CliRunner

from navaja.app import app

runner = CliRunner()


def escribir(ruta, texto, modo="w"):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(texto, bytes):
        ruta.write_bytes(texto)
    else:
        ruta.write_text(texto, encoding="utf-8", newline="")
    return ruta


def plano(texto):
    return " ".join(texto.split())


def test_dos_archivos_iguales(tmp_path):
    a = escribir(tmp_path / "a.txt", "hola\nadiós\n")
    b = escribir(tmp_path / "b.txt", "hola\nadiós\n")
    resultado = runner.invoke(app, ["compara", str(a), str(b)])
    assert resultado.exit_code == 0, resultado.output
    assert "Son iguales" in resultado.output


def test_dos_archivos_distintos_enseña_las_lineas(tmp_path):
    a = escribir(tmp_path / "v1" / "main.py", "uno\ndos\ntres\ncuatro\n")
    b = escribir(tmp_path / "v2" / "main.py", "uno\nDOS\ntres\ncuatro\ncinco\n")
    resultado = runner.invoke(app, ["compara", str(a), str(b)])
    assert resultado.exit_code == 0, resultado.output
    lineas = resultado.output.splitlines()
    assert "-dos" in lineas and "+DOS" in lineas and "+cinco" in lineas
    assert any(l.startswith("@@") for l in lineas)
    assert "-1 +2 líneas" in plano(resultado.output)


def test_contexto_cero_solo_enseña_lo_cambiado(tmp_path):
    a = escribir(tmp_path / "a.txt", "uno\ndos\ntres\n")
    b = escribir(tmp_path / "b.txt", "uno\nDOS\ntres\n")
    lineas = runner.invoke(app, ["compara", str(a), str(b), "-n", "0"]).output.splitlines()
    assert "uno" not in [l.strip() for l in lineas]


def test_solo_cambian_los_finales_de_linea(tmp_path):
    a = escribir(tmp_path / "a.txt", "uno\r\ndos\r\n")
    b = escribir(tmp_path / "b.txt", "uno\ndos\n")
    resultado = runner.invoke(app, ["compara", str(a), str(b)])
    assert "Solo cambian los finales de línea" in resultado.output


def test_sin_espacios(tmp_path):
    a = escribir(tmp_path / "a.txt", "def f():\n    return 1\n")
    b = escribir(tmp_path / "b.txt", "def  f():\n\treturn 1\n")
    assert "-def f():" in runner.invoke(app, ["compara", str(a), str(b)]).output
    resultado = runner.invoke(app, ["compara", str(a), str(b), "-w"])
    assert "Solo cambian los espacios" in resultado.output


def test_binarios_solo_dice_si_son_distintos(tmp_path):
    a = escribir(tmp_path / "a.bin", b"\x00\x01\x02")
    b = escribir(tmp_path / "b.bin", b"\x00\x01\x03")
    resultado = runner.invoke(app, ["compara", str(a), str(b)])
    assert resultado.exit_code == 0, resultado.output
    assert "Son distintos" in resultado.output and "binario" in resultado.output


def test_un_texto_con_corchetes_no_rompe_el_markup(tmp_path):
    a = escribir(tmp_path / "a.txt", "[bold]uno[/]\n")
    b = escribir(tmp_path / "b.txt", "[red]dos\n")
    resultado = runner.invoke(app, ["compara", str(a), str(b)])
    assert resultado.exit_code == 0, resultado.output
    assert "-[bold]uno[/]" in resultado.output and "+[red]dos" in resultado.output


def test_dos_carpetas(tmp_path):
    for nombre, texto in {"igual.txt": "x\n", "cambia.txt": "antes\n", "solo_a.txt": "a\n", "sub/igual.md": "#\n"}.items():
        escribir(tmp_path / "a" / nombre, texto)
    for nombre, texto in {"igual.txt": "x\n", "cambia.txt": "después\n", "nuevo.txt": "b\n", "sub/igual.md": "#\n"}.items():
        escribir(tmp_path / "b" / nombre, texto)
    escribir(tmp_path / "a" / ".git" / "HEAD", "ref\n")  # no se mira
    escribir(tmp_path / "b" / "node_modules" / "x.js", "x\n")
    resultado = runner.invoke(app, ["compara", str(tmp_path / "a"), str(tmp_path / "b")])
    assert resultado.exit_code == 0, resultado.output
    texto = plano(resultado.output)
    assert "- solo_a.txt (solo en la primera)" in texto
    assert "+ nuevo.txt (solo en la segunda)" in texto
    assert "~ cambia.txt (cambiado)" in texto
    assert "1 solo en la primera · 1 solo en la segunda · 1 cambiados · 2 iguales" in texto
    assert "HEAD" not in texto and "x.js" not in texto
    assert "-antes" not in resultado.output.splitlines()  # sin --detalle no salen las líneas
    assert "--detalle" in texto

    detalle = runner.invoke(app, ["compara", str(tmp_path / "a"), str(tmp_path / "b"), "--detalle"])
    lineas = detalle.output.splitlines()
    assert "-antes" in lineas and "+después" in lineas


def test_carpetas_iguales(tmp_path):
    escribir(tmp_path / "a" / "x.txt", "x\n")
    escribir(tmp_path / "b" / "x.txt", "x\n")
    resultado = runner.invoke(app, ["compara", str(tmp_path / "a"), str(tmp_path / "b")])
    assert "Son iguales" in resultado.output and "1 archivos" in resultado.output


def test_errores_sin_traza(tmp_path):
    archivo = escribir(tmp_path / "a.txt", "x\n")
    no_existe = runner.invoke(app, ["compara", str(archivo), str(tmp_path / "nada.txt")])
    assert no_existe.exit_code == 1 and "No existe" in no_existe.output
    mezcla = runner.invoke(app, ["compara", str(archivo), str(tmp_path)])
    assert mezcla.exit_code == 1 and "no un archivo con una carpeta" in mezcla.output
    assert not re.search("Traceback", no_existe.output + mezcla.output)


def test_un_texto_en_latin1_tambien_se_compara(tmp_path):
    a = escribir(tmp_path / "a.txt", "año\n".encode("cp1252"))
    b = escribir(tmp_path / "b.txt", "años\n".encode("cp1252"))
    resultado = runner.invoke(app, ["compara", str(a), str(b)])
    assert "-año" in resultado.output.splitlines() and "+años" in resultado.output.splitlines()
