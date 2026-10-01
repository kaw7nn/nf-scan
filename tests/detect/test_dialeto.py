"""Detecção do dialeto fiscal."""

from nfscan.detect.dialeto import Dialeto, detectar_dialeto
from nfscan.sniff.container import Container

NFE = (
    b'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" '
    b'versao="4.00"><NFe/></nfeProc>'
)
ABRASF = (
    b'<?xml version="1.0"?><ConsultarNfseResposta><ListaNfse><CompNfse><Nfse>'
    b"<InfNfse><Numero>1</Numero></InfNfse></Nfse></CompNfse></ListaNfse>"
    b"</ConsultarNfseResposta>"
)
NFSE_NAC = (
    b'<?xml version="1.0"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse" '
    b'versao="1.00"><infNFSe Id="NFS1"/></NFSe>'
)


def test_detecta_nfe_por_namespace_com_confianca_plena() -> None:
    # O namespace oficial não é ambíguo, e o pipeline toma o mínimo entre a
    # confiança da detecção e a da extração: 0.99 aqui rebaixaria o XML.
    dialeto, confianca = detectar_dialeto(NFE, Container.XML)
    assert dialeto is Dialeto.NFE_4_00
    assert confianca == 1.0


def test_detecta_nfse_nacional() -> None:
    dialeto, _ = detectar_dialeto(NFSE_NAC, Container.XML)
    assert dialeto is Dialeto.NFSE_NACIONAL_1_0


def test_detecta_abrasf() -> None:
    dialeto, confianca = detectar_dialeto(ABRASF, Container.XML)
    assert dialeto is Dialeto.ABRASF_2_0X
    assert confianca < 0.95


def test_xml_desconhecido() -> None:
    dialeto, confianca = detectar_dialeto(b"<Relatorio/>", Container.XML)
    assert dialeto is Dialeto.DESCONHECIDO
    assert confianca <= 0.3


def test_detecta_nfe_com_bom() -> None:
    dialeto, _ = detectar_dialeto(b"\xef\xbb\xbf" + NFE, Container.XML)
    assert dialeto is Dialeto.NFE_4_00


def test_imagem_e_sempre_danfe_pdf_por_ocr() -> None:
    dialeto, confianca = detectar_dialeto(b"\x89PNG\r\n\x1a\n", Container.IMAGEM)
    assert dialeto is Dialeto.DANFE_PDF
    assert confianca <= 0.4
