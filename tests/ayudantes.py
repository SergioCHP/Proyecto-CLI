"""Archivos de prueba que usan varios tests: un PDF con texto hecho a mano."""


def pdf_con_texto(textos: list[str]) -> bytes:
    """Un PDF mínimo con una página por texto (Helvetica), sin librerías."""
    objetos = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    hijos = " ".join(f"{3 + i * 2} 0 R" for i in range(len(textos)))
    objetos.append(f"<< /Type /Pages /Kids [{hijos}] /Count {len(textos)} >>".encode())
    fuente = 3 + len(textos) * 2
    for i, texto in enumerate(textos):
        contenido = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode("latin-1")
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + i * 2} 0 R "
            f"/Resources << /Font << /F1 {fuente} 0 R >> >> >>".encode()
        )
        objetos.append(b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    datos = b"%PDF-1.4\n"
    posiciones = []
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(datos))
        datos += b"%d 0 obj\n" % numero + objeto + b"\nendobj\n"
    xref = len(datos)
    datos += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    datos += b"".join(b"%010d 00000 n \n" % p for p in posiciones)
    datos += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, xref)
    return datos
