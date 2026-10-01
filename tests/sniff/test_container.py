"""Detecção do container físico, por conteúdo e não por extensão."""

from nfscan.sniff.container import Container, detectar_container

XML = b'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"/>'


def test_detecta_xml() -> None:
    assert detectar_container(XML) is Container.XML


def test_detecta_zip() -> None:
    assert detectar_container(b"PK\x03\x04resto") is Container.ZIP


def test_detecta_imagem_png_e_jpeg() -> None:
    assert detectar_container(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20) is Container.IMAGEM
    assert detectar_container(b"\xff\xd8\xff\xe0" + b"\x00" * 20) is Container.IMAGEM


def test_detecta_bitmap_pelo_cabecalho_completo() -> None:
    # "BM" sozinho sao dois bytes; o BMP tem os campos reservados zerados.
    bmp = b"BM" + (100).to_bytes(4, "little") + b"\x00\x00\x00\x00" + b"\x00" * 10
    assert detectar_container(bmp) is Container.IMAGEM


def test_texto_comecando_com_bm_nao_e_imagem() -> None:
    assert detectar_container(b"BMW catalogo de pecas 2026") is Container.DESCONHECIDO


def test_conteudo_vazio_e_desconhecido() -> None:
    assert detectar_container(b"") is Container.DESCONHECIDO


def test_texto_qualquer_e_desconhecido() -> None:
    assert detectar_container(b"relatorio mensal de compras") is Container.DESCONHECIDO


# --- Foco de Revisão 3: XML com BOM e com declaração latin-1 ---


def test_detecta_xml_com_bom_utf8() -> None:
    assert detectar_container(b"\xef\xbb\xbf" + XML) is Container.XML


def test_detecta_xml_com_espacos_e_quebras_antes_da_declaracao() -> None:
    assert detectar_container(b"\r\n\t  " + XML) is Container.XML


def test_detecta_xml_declarado_em_latin1() -> None:
    bruto = '<?xml version="1.0" encoding="ISO-8859-1"?><nfeProc/>'.encode("latin-1")
    assert detectar_container(bruto) is Container.XML


def test_detecta_xml_sem_declaracao() -> None:
    assert detectar_container(b"<CompNfse><Nfse/></CompNfse>") is Container.XML
