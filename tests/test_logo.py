"""El rótulo de bienvenida y su versión sencilla."""

import io

from rich.console import Console
from rich.theme import Theme

from navaja import logo
from navaja.comun import TEMAS


class Salida(io.StringIO):
    """Un archivo en memoria que dice tener la codificación que queramos."""

    def __init__(self, encoding: str) -> None:
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return self._encoding


def consola(ancho: int, encoding: str = "utf-8") -> tuple[Console, Salida]:
    salida = Salida(encoding)
    # como una terminal, pero sin códigos de color: el texto se compara tal cual
    consola_ = Console(
        file=salida,
        width=ancho,
        theme=Theme(TEMAS["clasico"]),
        force_terminal=True,
        color_system=None,
    )
    return consola_, salida


def test_con_sitio_sale_el_rotulo_grande():
    c, salida = consola(80)
    c.print(logo.rotulo(c, "Buenas tardes, [Sergio]", "navaja 0.1.0 · tema clasico"))
    texto = salida.getvalue()
    assert logo.LETRAS[0] in texto
    assert logo.LETRAS[-1] in texto
    assert "Buenas tardes, [Sergio]" in texto  # los corchetes no se toman como formato


def test_estrecha_o_sin_utf8_sale_el_recuadro_sencillo():
    for c, salida in (consola(30), consola(80, "cp1252")):
        c.print(logo.rotulo(c, "Buenos días, Ana", "navaja 0.1.0 · tema clasico"))
        texto = salida.getvalue()
        assert "Buenos días, Ana" in texto
        assert "█" not in texto


def test_cabe_justo_en_su_ancho():
    ancho = logo.ancho_necesario("Hola", "navaja")
    assert logo.cabe(consola(ancho)[0], "Hola", "navaja")
    assert not logo.cabe(consola(ancho - 1)[0], "Hola", "navaja")


def test_las_letras_van_en_dos_tonos():
    texto = logo.letras()
    estilos = {texto.plain[s.start] : s.style for s in texto.spans}
    assert estilos["█"] == "titulo"
    assert estilos["╗"] == "marco"


def test_con_la_salida_a_un_archivo_sale_el_recuadro():
    salida = Salida("utf-8")
    c = Console(file=salida, width=120, force_terminal=False, theme=Theme(TEMAS["clasico"]))
    c.print(logo.rotulo(c, "Hola", "navaja"))
    assert "█" not in salida.getvalue() and "Hola" in salida.getvalue()


def test_utf8_se_reconoce_con_cualquier_nombre():
    for nombre in ("utf-8", "UTF8", "utf_8"):
        assert logo.cabe(consola(80, nombre)[0], "Hola", "navaja")
