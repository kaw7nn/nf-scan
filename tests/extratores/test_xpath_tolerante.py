"""Leitura de XML por nome local de tag, ignorando namespace."""

from nfscan.extratores.xpath_tolerante import carregar, primeiro_texto, todos_elementos

COM_NS = b"""<?xml version="1.0"?>
<ns2:CompNfse xmlns:ns2="http://www.abrasf.org.br/nfse.xsd">
  <ns2:Nfse><ns2:InfNfse>
    <ns2:Numero>1234</ns2:Numero>
    <ns2:ValoresNfse><ns2:ValorLiquidoNfse>1500,00</ns2:ValorLiquidoNfse></ns2:ValoresNfse>
  </ns2:InfNfse></ns2:Nfse>
</ns2:CompNfse>"""

SEM_NS = b"<CompNfse><Nfse><InfNfse><Numero>99</Numero></InfNfse></Nfse></CompNfse>"


def test_le_com_namespace() -> None:
    assert primeiro_texto(carregar(COM_NS), "Numero") == "1234"


def test_le_sem_namespace() -> None:
    assert primeiro_texto(carregar(SEM_NS), "Numero") == "99"


def test_le_em_profundidade_arbitraria() -> None:
    assert primeiro_texto(carregar(COM_NS), "ValorLiquidoNfse") == "1500,00"


def test_aceita_lista_de_nomes_alternativos() -> None:
    assert primeiro_texto(carregar(COM_NS), "NumeroNfse", "Numero") == "1234"


def test_a_ordem_dos_nomes_define_a_precedencia() -> None:
    bruto = b"<N><NumeroNfse>1</NumeroNfse><Numero>2</Numero></N>"
    assert primeiro_texto(carregar(bruto), "NumeroNfse", "Numero") == "1"
    assert primeiro_texto(carregar(bruto), "Numero", "NumeroNfse") == "2"


def test_tag_ausente_vira_none() -> None:
    assert primeiro_texto(carregar(SEM_NS), "Inexistente") is None


def test_todos_elementos() -> None:
    bruto = b"<Lista><Item><V>1</V></Item><Item><V>2</V></Item></Lista>"
    assert len(todos_elementos(carregar(bruto), "Item")) == 2


def test_carregar_tolera_bom() -> None:
    assert primeiro_texto(carregar(b"\xef\xbb\xbf" + SEM_NS), "Numero") == "99"


def test_carregar_tolera_encoding_latin1_declarado() -> None:
    bruto = '<?xml version="1.0" encoding="ISO-8859-1"?><N><X>Jos\xe9</X></N>'.encode("latin-1")
    assert primeiro_texto(carregar(bruto), "X") == "José"
