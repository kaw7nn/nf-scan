"""DANFE no layout oficial: rótulos numa linha, valores alinhados abaixo.

A fixture reproduz a geometria de um DANFE real — inclusive a linha em branco
entre o rótulo e o valor — com dados sintéticos e chave de DV válido.

O que este layout tem e os anteriores não: sob os rótulos ficam também **texto**
(razão social, natureza da operação), **data**, **CNPJ** e **inteiro simples**
(inscrição estadual), não só dinheiro. A âncora de coluna só sabia achar valor
monetário, então oito campos sumiam em silêncio.
"""

from datetime import date
from decimal import Decimal

from nfscan.detect.dialeto import Dialeto
from nfscan.extratores.pdf_texto import extrair_de_texto
from nfscan.modelo.coletor import CONFIANCA
from nfscan.validar import validar

ARQUIVO = "danfe_layout_oficial.txt"


def _nota(ler_fixture):
    conteudo, arquivo = ler_fixture(ARQUIVO, "text/plain")
    return extrair_de_texto(
        conteudo.decode("utf-8"),
        arquivo,
        Dialeto.DANFE_PDF,
        CONFIANCA["pdf_ancora"],
        "ancoras_pdf",
    )


def test_chave_e_os_campos_que_ela_entrega(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert len(nota.documento.chave_acesso) == 44
    assert nota.documento.modelo == "55"
    assert nota.documento.numero == "325177"
    assert nota.documento.serie == "1"
    assert nota.emitente.cnpj == "11222333000181"


# --- coluna de TEXTO ---


def test_natureza_da_operacao_vem_da_coluna(ler_fixture) -> None:
    # Rótulo e valor em linhas diferentes, com a chave de acesso na coluna ao
    # lado: capturar "a linha seguinte" inteira traria a chave junto.
    assert _nota(ler_fixture).documento.natureza_operacao == "VENDA DE MERCADORIA"


def test_razao_social_do_destinatario_vem_da_coluna(ler_fixture) -> None:
    assert _nota(ler_fixture).destinatario.razao_social == "CONSTRUTORA EXEMPLO LTDA"


def test_razao_social_do_emitente_vem_do_canhoto(ler_fixture) -> None:
    # O nome do emitente não tem rótulo no corpo do DANFE; o canhoto tem.
    assert _nota(ler_fixture).emitente.razao_social == "FORNECEDOR DE MATERIAIS LTDA"


# --- coluna de DATA, CNPJ e INTEIRO ---


def test_data_de_emissao_vem_da_coluna(ler_fixture) -> None:
    assert _nota(ler_fixture).documento.data_emissao.date() == date(2026, 9, 29)


def test_cnpj_do_destinatario_vem_da_coluna(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.destinatario.cnpj == "11444777000161"
    assert nota.emitente.cnpj != nota.destinatario.cnpj


def test_inscricao_estadual_vem_da_coluna(ler_fixture) -> None:
    assert _nota(ler_fixture).emitente.inscricao_estadual == "122105303"


# --- dinheiro com os rótulos que o layout oficial usa ---


def test_valores_do_bloco_de_imposto(ler_fixture) -> None:
    # Os rótulos aqui são "BC ICMS" e "VALOR DOS PRODUTOS", não
    # "BASE DE CALCULO DO ICMS" e "VALOR TOTAL DOS PRODUTOS".
    totais = _nota(ler_fixture).totais
    assert totais.tributos.icms_base == Decimal("69.30")
    assert totais.tributos.icms_valor == Decimal("15.94")
    assert totais.icms_st == Decimal("7.24")
    assert totais.valor_produtos == Decimal("801.43")


def test_valores_do_bloco_de_totais(ler_fixture) -> None:
    totais = _nota(ler_fixture).totais
    assert totais.frete == Decimal("0.00")
    assert totais.seguro == Decimal("0.00")
    assert totais.desconto == Decimal("7.24")
    assert totais.outras_despesas == Decimal("36.87")
    assert totais.valor_total == Decimal("838.30")


def test_o_total_fecha_e_nao_acusa_divergencia_falsa(ler_fixture) -> None:
    # 801,43 + 7,24 (ICMS ST) + 36,87 (despesas) - 7,24 (desconto) = 838,30.
    # Sem o ICMS ST e as despesas acessórias, a conferência acusaria divergência
    # numa nota perfeitamente legível.
    nota = _nota(ler_fixture)
    assert "TOTAL_DIVERGENTE" not in {p.codigo for p in validar(nota)}


def test_informacoes_complementares_trazem_o_conteudo(ler_fixture) -> None:
    # Não o cabeçalho "INFORMAÇÕES COMPLEMENTARES".
    adicionais = _nota(ler_fixture).informacoes_adicionais
    assert adicionais.startswith("401234 240")
