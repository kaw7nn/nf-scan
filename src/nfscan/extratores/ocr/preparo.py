"""Pré-processamento de imagem antes do OCR.

Tesseract erra mais em imagem colorida, torta ou com contraste baixo —
exatamente a foto de cupom tirada no celular. O preparo não resolve o problema,
só reduz o erro.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from nfscan.sniff.container import Container

DPI_RENDER = 300
# Teto de páginas: um PDF-imagem de muitas páginas a 300 dpi enche o /tmp e a
# memória, e nota fiscal não tem dezenas de páginas.
MAXIMO_PAGINAS = 10
_TIMEOUT_RENDER = 120


def preparar(imagem: Any) -> Any:
    """Escala de cinza e autocontraste.

    Não binariza: o Tesseract tem a própria binarização adaptativa (Otsu), e um
    limiar global fixo apaga impressão térmica fraca, que é justamente o caso
    difícil do cupom fiscal.
    """
    from PIL import ImageOps

    return ImageOps.autocontrast(ImageOps.grayscale(imagem))


def imagens_de(conteudo: bytes, container: Container) -> list[Any]:
    """Devolve as páginas como imagens PIL já preparadas.

    PDF-imagem é renderizado com ``pdftoppm`` do poppler, que já é dependência
    declarada e evita acrescentar uma biblioteca de renderização.
    """
    from PIL import Image

    if container is Container.IMAGEM:
        try:
            return [preparar(Image.open(io.BytesIO(conteudo)))]
        except Exception:
            return []

    if container is not Container.PDF_IMAGEM:
        return []

    if shutil.which("pdftoppm") is None:
        return []
    with tempfile.TemporaryDirectory() as pasta:
        origem = Path(pasta) / "entrada.pdf"
        origem.write_bytes(conteudo)
        try:
            subprocess.run(  # noqa: S603
                [
                    "pdftoppm",
                    "-r",
                    str(DPI_RENDER),
                    "-f",
                    "1",
                    "-l",
                    str(MAXIMO_PAGINAS),
                    "-png",
                    str(origem),
                    f"{pasta}/pag",
                ],
                capture_output=True,
                timeout=_TIMEOUT_RENDER,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        imagens = []
        for caminho in sorted(Path(pasta).glob("pag*.png"))[:MAXIMO_PAGINAS]:
            try:
                imagens.append(preparar(Image.open(caminho)))
            except Exception:
                continue
        return imagens
