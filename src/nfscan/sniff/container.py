"""Identifica o container físico do arquivo pelo conteúdo.

Extensão é palpite do cliente e vem errada com frequência. Só o conteúdo
decide. XML pode chegar com BOM UTF-8, com espaços antes da declaração ou
declarado em latin-1 — todos aparecem na prática com emissores antigos.
"""

from __future__ import annotations

import io
from enum import StrEnum

MINIMO_CARACTERES_POR_PAGINA = 60

_BOM_UTF8 = b"\xef\xbb\xbf"
_JANELA_PDF = 1024

# Assinaturas de pelo menos 4 bytes. O BMP tem só "BM", então é tratado à
# parte: dois bytes casariam com qualquer texto começando por "BM".
_ASSINATURAS_IMAGEM = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"II*\x00",
    b"MM\x00*",
)

_TAMANHO_CABECALHO_BMP = 14


class Container(StrEnum):
    XML = "xml"
    PDF_TEXTO = "pdf_texto"
    PDF_IMAGEM = "pdf_imagem"
    IMAGEM = "imagem"
    ZIP = "zip"
    DESCONHECIDO = "desconhecido"


def _e_bitmap(bruto: bytes) -> bool:
    """Confirma um BMP pelo cabeçalho inteiro, não só pelos dois bytes iniciais.

    Os campos reservados (bytes 6 a 10) são sempre zero em um BMP, o que
    distingue o arquivo de um texto que começa com "BM".
    """
    if not bruto.startswith(b"BM") or len(bruto) < _TAMANHO_CABECALHO_BMP:
        return False
    return bruto[6:10] == b"\x00\x00\x00\x00"


def texto_de_pdf(conteudo: bytes) -> str:
    """Extrai o texto do PDF, ou ``""`` quando o arquivo não abre.

    PDF protegido por senha, truncado ou corrompido devolve string vazia em vez
    de propagar exceção: o pipeline precisa seguir e relatar confiança baixa.
    """
    try:
        import pdfplumber
    except ImportError:  # extra "pdf" não instalado
        return ""
    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            return "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
    except Exception:
        # pdfplumber levanta tipos variados: senha, xref quebrado, EOF.
        return ""


def detectar_container(conteudo: bytes) -> Container:
    """Classifica o arquivo recebido."""
    if not conteudo:
        return Container.DESCONHECIDO

    bruto = conteudo.removeprefix(_BOM_UTF8)

    if bruto.startswith(b"PK\x03\x04"):
        return Container.ZIP
    if any(bruto.startswith(assinatura) for assinatura in _ASSINATURAS_IMAGEM) or _e_bitmap(bruto):
        return Container.IMAGEM
    if b"%PDF-" in bruto[:_JANELA_PDF]:
        texto = texto_de_pdf(conteudo)
        paginas = max(texto.count("\f") + 1, 1)
        if len(texto.strip()) >= MINIMO_CARACTERES_POR_PAGINA * paginas:
            return Container.PDF_TEXTO
        return Container.PDF_IMAGEM
    if bruto.lstrip()[:1] == b"<":
        return Container.XML
    return Container.DESCONHECIDO
