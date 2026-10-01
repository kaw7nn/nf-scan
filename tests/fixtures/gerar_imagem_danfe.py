"""Renderiza tests/fixtures/danfe_texto_simples.txt como PNG, para testar o OCR.

Usa fonte monoespaçada e uma linha por linha do texto, preservando as colunas.

Fixture sintética e limpa: serve para exercitar o caminho de OCR, não para
estimar precisão em foto de cupom real. Rode uma vez e versione o PNG gerado.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).parent
CORPO = 22
ALTURA_LINHA = 30
MARGEM = 40
CANDIDATAS_FONTE = (
    "/usr/share/fonts/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/noto/NotoSansMono-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/usr/share/fonts/gsfonts/NimbusMonoPS-Regular.otf",
)


def _fonte() -> ImageFont.FreeTypeFont:
    for caminho in CANDIDATAS_FONTE:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, CORPO)
    raise SystemExit(
        "nenhuma fonte monoespaçada encontrada; instale liberation-fonts ou noto-fonts"
    )


def main() -> None:
    linhas = (AQUI / "danfe_texto_simples.txt").read_text(encoding="utf-8").splitlines()
    fonte = _fonte()
    largura_caractere = fonte.getlength("M")
    colunas = max((len(linha) for linha in linhas), default=80)
    largura = int(MARGEM * 2 + colunas * largura_caractere)
    altura = MARGEM * 2 + len(linhas) * ALTURA_LINHA

    imagem = Image.new("L", (largura, altura), color=255)
    desenho = ImageDraw.Draw(imagem)
    for indice, linha in enumerate(linhas):
        desenho.text((MARGEM, MARGEM + indice * ALTURA_LINHA), linha, fill=0, font=fonte)

    destino = AQUI / "danfe_imagem_simples.png"
    imagem.save(destino, optimize=True)
    print("gerado:", destino, destino.stat().st_size, "bytes", f"({largura}x{altura})")


if __name__ == "__main__":
    main()
