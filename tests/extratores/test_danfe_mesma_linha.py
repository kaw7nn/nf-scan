"""DANFE com rótulo e valor na mesma linha, prefixados por R$.

Layout gerado por ReportLab, comum em emissores que montam o DANFE em
relatório em vez do formato tabular do leiaute oficial. Difere da outra fixture
em três pontos que quebravam a extração: o valor fica à direita do rótulo e não
abaixo, vem precedido de ``R$``, e o número do documento usa o rótulo ``NÚMERO``
com pontuação de milhar.

A chave e os CNPJs deste documento são fabricados e não passam nos respectivos
dígitos verificadores. Recusá-los é o comportamento correto, e os testes
afirmam isso em vez de contorná-lo.
"""

from decimal import Decimal

from nfscan.pipeline import parse

ARQUIVO = "danfe_rotulo_na_mesma_linha.pdf"


def _nota(ler_fixture):
    conteudo, _ = ler_fixture(ARQUIVO, "application/pdf")
    return parse(conteudo, ARQUIVO, "application/pdf")


def test_e_reconhecido_como_danfe_em_pdf(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.extracao.dialeto == "danfe_pdf"
    assert nota.extracao.motor == "ancoras_pdf"


def test_valores_com_prefixo_de_moeda_na_mesma_linha(ler_fixture) -> None:
    # "VALOR TOTAL DA NOTA (NF-e):            R$ 12.000,00"
    nota = _nota(ler_fixture)
    assert nota.totais.valor_total == Decimal("12000.00")
    assert nota.totais.valor_produtos == Decimal("12000.00")


def test_numero_com_rotulo_por_extenso_e_pontuacao(ler_fixture) -> None:
    # "NÚMERO: 000.012.345" -> 12345
    nota = _nota(ler_fixture)
    assert nota.documento.numero == "12345"


def test_serie_e_data(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.documento.serie == "1"
    assert nota.documento.data_emissao.date().isoformat() == "2026-10-01"


def test_chave_fabricada_e_recusada_mas_relatada(ler_fixture) -> None:
    """Silêncio aqui deixaria o integrador adivinhando por que faltou a chave."""
    nota = _nota(ler_fixture)
    assert nota.documento.chave_acesso is None
    assert "CHAVE_DV_INVALIDO" in {p.codigo for p in nota.extracao.problemas}


def test_cnpj_fabricado_e_descartado_com_aviso(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.emitente is None or nota.emitente.cnpj is None
    assert "CNPJ_ILEGIVEL" in {p.codigo for p in nota.extracao.problemas}


def test_pede_revisao(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.extracao.requer_revisao is True
