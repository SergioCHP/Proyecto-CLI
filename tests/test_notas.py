from navaja.comandos.notas import _normalizar_etiquetas


def test_normalizar_etiquetas():
    assert _normalizar_etiquetas(["Python", "#Docs, python", "  "]) == [
        "python",
        "docs",
    ]


def test_normalizar_etiquetas_vacias():
    assert _normalizar_etiquetas([]) == []
    assert _normalizar_etiquetas(["", ",", "#"]) == []
