"""El menú principal se adapta a la altura de la ventana: si no cabe entero, se reparte
en dos columnas (con sus frases) y el rótulo grande deja su sitio al sencillo."""

import io

import pytest
import typer
from rich.console import Console
from rich.theme import Theme

from navaja import app as app_, interactivo, logo
from navaja.comun import TEMAS


class Salida(io.StringIO):
    encoding = "utf-8"


def consola(ancho: int, alto: int, terminal: bool = True) -> tuple[Console, Salida]:
    salida = Salida()
    return (
        Console(
            file=salida,
            width=ancho,
            height=alto,
            force_terminal=terminal,
            # En Windows, con la salida capturada por pytest, Rich cree que es la consola
            # antigua y cambia los bordes redondeados (╭) por rectos (┌).
            legacy_windows=False,
            color_system=None,
            theme=Theme(TEMAS["clasico"]),
        ),
        salida,
    )


@pytest.fixture
def raiz():
    return typer.main.get_command(app_.app)


def pintar(monkeypatch, raiz, ancho, alto, reservado=0, terminal=True):
    c, salida = consola(ancho, alto, terminal)
    monkeypatch.setattr(interactivo, "console", c)
    interactivo.mostrar_menu(raiz, [], reservado)
    return salida.getvalue()


def test_con_altura_de_sobra_sale_el_menu_de_siempre(monkeypatch, raiz):
    texto = pintar(monkeypatch, raiz, 120, 80)
    assert "Muestra qué hay en una carpeta." in texto  # la frase de cada opción


def test_si_no_cabe_sale_en_dos_columnas_con_frases(monkeypatch, raiz):
    texto = pintar(monkeypatch, raiz, 160, 40, reservado=logo.ALTO_SENCILLO)
    assert "Muestra qué hay en una carpeta." in texto  # las frases siguen
    assert "listar" in texto and "manual" in texto  # y todas las opciones
    assert any(linea.count("╭") == 2 for linea in texto.splitlines())  # dos columnas
    assert logo.ALTO_SENCILLO + texto.count("\n") + interactivo.MARGEN <= 40


def test_ventana_muy_estrecha_no_hace_columnas(monkeypatch, raiz):
    texto = pintar(monkeypatch, raiz, 50, 20)
    assert not any(linea.count("╭") == 2 for linea in texto.splitlines())


def test_el_compacto_conserva_los_numeros_en_orden(monkeypatch, raiz):
    texto = pintar(monkeypatch, raiz, 160, 30, reservado=logo.ALTO_SENCILLO)
    nombres = [n for n, _ in interactivo.opciones_de(raiz)]
    for numero, nombre in enumerate(nombres, start=1):
        assert f"{numero}  " in texto and nombre in texto
    # un recuadro por sección, aunque estén en columnas
    assert texto.count("╭") >= 7


def test_sin_terminal_no_se_compacta(monkeypatch, raiz):
    texto = pintar(monkeypatch, raiz, 120, 10, terminal=False)
    assert "Muestra qué hay en una carpeta." in texto


def test_un_submenu_nunca_se_compacta(monkeypatch, raiz):
    c, salida = consola(120, 5)
    monkeypatch.setattr(interactivo, "console", c)
    grupo = raiz.commands["ordena"]
    interactivo.mostrar_menu(grupo, ["ordena"])
    assert "Imágenes, Documentos, Vídeos… a su carpeta." in salida.getvalue()


def test_repartir_mantiene_el_orden_y_equilibra():
    assert interactivo.repartir([14, 9, 8, 6, 3, 6, 6], 3) == [[0], [1, 2], [3, 4, 5, 6]]
    assert interactivo.repartir([5, 5], 4) == [[0], [1]]  # nunca más columnas que recuadros
    assert interactivo.repartir([5, 5, 5], 1) == [[0, 1, 2]]


def test_el_rotulo_grande_solo_si_cabe_con_el_menu(monkeypatch):
    for alto, esperado in ((36, False), (50, True)):
        c, _ = consola(120, alto)
        monkeypatch.setattr(interactivo, "console", c)
        monkeypatch.setattr(app_, "console", c)
        assert app_._rotulo_grande() is esperado


def test_rotulo_sencillo_si_se_pide():
    c, salida = consola(120, 30)
    c.print(logo.rotulo(c, "Hola", "navaja", grande=False))
    assert "█" not in salida.getvalue()
    assert salida.getvalue().count("\n") == logo.ALTO_SENCILLO


def test_los_tipos_se_leen_tambien_sin_param_type(raiz):
    """Typer nuevo no tiene ``param.type`` (usa ``type_descriptor``): ni la ruta ni las
    listas cerradas de opciones deben perderse ni romper el modo guiado."""
    from navaja.comandos import ayuda

    sistema = raiz.commands["sistema"]
    orden = next(p for p in sistema.params if p.name == "orden")
    assert [ayuda.valor_texto(c) for c in ayuda.elecciones_de(orden)] == ["cpu", "memoria"]
    cuenta = raiz.commands["cuenta"]
    assert ayuda.nombre_tipo(next(p for p in cuenta.params if p.name == "archivos")) == "path"
    assert ayuda.tipo_texto(next(p for p in cuenta.params if p.name == "minimo")) == "número"


def test_menu_limpia_y_vuelve_a_dibujar_con_el_tamano_de_ahora(monkeypatch, raiz):
    """Al achicar la ventana la terminal recoloca lo ya dibujado y se desordena: «menu»
    lo limpia y lo dibuja de nuevo con el ancho y el alto actuales."""
    c, salida = consola(160, 36)
    monkeypatch.setattr(interactivo, "console", c)
    ordenes = iter(["menu", "salir"])
    with pytest.raises(interactivo.Salir):
        interactivo.bucle(raiz, raiz, [], lambda prompt: next(ordenes))
    texto = salida.getvalue()
    assert "\x1b[2J" in texto  # se limpió la pantalla
    assert "listar" in texto and "manual" in texto  # y se dibujó el menú
