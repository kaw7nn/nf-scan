"""Identifica o dialeto fiscal e a confiança da identificação.

A inspeção é feita sobre os primeiros bytes decodificados de forma tolerante:
o objetivo é reconhecer namespace e nome de raiz, não validar o documento.
Validação é tarefa do extrator.
"""

from __future__ import annotations

from enum import StrEnum

from nfscan.sniff.container import Container, texto_de_pdf

_BOM_UTF8 = b"\xef\xbb\xbf"
_AMOSTRA = 4096

NS_NFE = "portalfiscal.inf.br/nfe"
NS_NFSE_NACIONAL = "sped.fazenda.gov.br/nfse"
_MARCAS_ABRASF = (
    "ConsultarNfseResposta",
    "CompNfse",
    "ListaNfse",
    "InfNfse",
    "GerarNfseResposta",
    "ConsultarNfseRpsResposta",
)
_MARCAS_CUPOM = ("CUPOM FISCAL", "NFC-E", "CONSUMIDOR")


class Dialeto(StrEnum):
    NFE_4_00 = "nfe_4.00"
    NFSE_NACIONAL_1_0 = "nfse_nacional_1.0"
    ABRASF_2_0X = "abrasf_2.0x"
    DANFE_PDF = "danfe_pdf"
    NFCE_CUPOM = "nfce_cupom"
    DESCONHECIDO = "desconhecido"


def _amostra_texto(conteudo: bytes) -> str:
    """Decodifica o começo do arquivo sem falhar por encoding."""
    return conteudo.removeprefix(_BOM_UTF8)[:_AMOSTRA].decode("utf-8", errors="replace")


def detectar_dialeto(
    conteudo: bytes, container: Container, texto_pdf: str | None = None
) -> tuple[Dialeto, float]:
    """Devolve ``(dialeto, confianca_da_deteccao)``.

    NF-e reconhecida pelo namespace oficial vale 1.0: o namespace não é
    ambíguo, e o pipeline toma o mínimo entre esta confiança e a da extração —
    um valor menor rebaixaria indevidamente a leitura de XML.
    """
    if container is Container.XML:
        amostra = _amostra_texto(conteudo)
        if NS_NFE in amostra:
            return Dialeto.NFE_4_00, 1.0
        if NS_NFSE_NACIONAL in amostra:
            return Dialeto.NFSE_NACIONAL_1_0, 1.0
        if any(marca in amostra for marca in _MARCAS_ABRASF):
            return Dialeto.ABRASF_2_0X, 0.90
        return Dialeto.DESCONHECIDO, 0.2

    if container is Container.PDF_TEXTO:
        # Reaproveita o texto que o sniff já extraiu, quando foi passado.
        texto = (texto_pdf if texto_pdf is not None else texto_de_pdf(conteudo)).upper()
        if any(marca in texto for marca in _MARCAS_CUPOM):
            return Dialeto.NFCE_CUPOM, 1.0
        return Dialeto.DANFE_PDF, 1.0

    if container in (Container.PDF_IMAGEM, Container.IMAGEM):
        # Sem camada de texto não há como distinguir antes do OCR. O extrator
        # de OCR refina o tipo depois de ler a chave.
        return Dialeto.DANFE_PDF, 0.3

    return Dialeto.DESCONHECIDO, 0.0
