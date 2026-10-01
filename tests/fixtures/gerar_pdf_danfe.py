"""Gera tests/fixtures/danfe_texto_simples.pdf a partir do .txt de mesmo nome.

Escreve o PDF à mão, sem dependência externa, com Courier e posicionamento
absoluto por linha. Isso preserva o alinhamento de coluna, que é justamente o
que o motor de âncoras precisa ler — um gerador que reflui o texto (groff,
libreoffice) destruiria a informação que o teste existe para exercitar.

Fixture sintética: prova que o caminho de PDF com camada de texto funciona.
Não mede precisão em DANFE real. Rode uma vez e versione o PDF gerado.
"""

import re
from pathlib import Path

AQUI = Path(__file__).parent
FONTE = "Courier"
CORPO = 9
LARGURA_CARACTERE = CORPO * 0.6
ALTURA_LINHA = 11
MARGEM_X = 20
TOPO = 820
PAGINA = (0, 0, 595, 842)  # A4 em pontos


def _escapar(texto: str) -> str:
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _celulas(linha: str) -> list[tuple[int, str]]:
    """Quebra a linha em células por corridas de dois ou mais espaços.

    Um DANFE real tem uma célula por text run, cada uma na sua posição. Emitir
    a linha inteira como um run único perderia a coluna, que é exatamente a
    informação que o motor de âncoras precisa.
    """
    celulas: list[tuple[int, str]] = []
    for pedaco in re.finditer(r"\S(?:.*?\S)?(?=\s{2,}|$)", linha):
        celulas.append((pedaco.start(), pedaco.group()))
    return celulas


def _fluxo(linhas: list[str]) -> bytes:
    partes = [f"BT /F1 {CORPO} Tf"]
    for indice, linha in enumerate(linhas):
        if not linha.strip():
            continue
        y = TOPO - indice * ALTURA_LINHA
        for coluna, celula in _celulas(linha):
            x = MARGEM_X + coluna * LARGURA_CARACTERE
            partes.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm ({_escapar(celula)}) Tj")
    partes.append("ET")
    return "\n".join(partes).encode("latin-1", errors="replace")


def _montar(fluxo: bytes) -> bytes:
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [{PAGINA[0]} {PAGINA[1]} "
            f"{PAGINA[2]} {PAGINA[3]}] /Resources << /Font << /F1 4 0 R >> >> "
            f"/Contents 5 0 R >>"
        ).encode("latin-1"),
        f"<< /Type /Font /Subtype /Type1 /BaseFont /{FONTE} >>".encode("latin-1"),
        b"<< /Length " + str(len(fluxo)).encode() + b" >>\nstream\n" + fluxo + b"\nendstream",
    ]

    saida = bytearray(b"%PDF-1.4\n")
    deslocamentos: list[int] = []
    for numero, corpo in enumerate(objetos, start=1):
        deslocamentos.append(len(saida))
        saida += f"{numero} 0 obj\n".encode() + corpo + b"\nendobj\n"

    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode()
    saida += b"0000000000 65535 f \n"
    for deslocamento in deslocamentos:
        saida += f"{deslocamento:010d} 00000 n \n".encode()
    saida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
        f"startxref\n{inicio_xref}\n%%EOF\n"
    ).encode()
    return bytes(saida)


def main() -> None:
    linhas = (AQUI / "danfe_texto_simples.txt").read_text(encoding="utf-8").splitlines()
    destino = AQUI / "danfe_texto_simples.pdf"
    destino.write_bytes(_montar(_fluxo(linhas)))
    print("gerado:", destino, destino.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
