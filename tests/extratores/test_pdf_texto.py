"""Extração de DANFE a partir do texto."""

from decimal import Decimal

from nfscan.detect.dialeto import Dialeto
from nfscan.extratores.pdf_texto import extrair_de_texto
from nfscan.modelo import ArquivoOrigem
from nfscan.modelo.coletor import CONFIANCA


def _nota(ler_fixture):
    conteudo, arquivo = ler_fixture("danfe_texto_simples.txt", "text/plain")
    return extrair_de_texto(
        conteudo.decode("utf-8"),
        arquivo,
        Dialeto.DANFE_PDF,
        CONFIANCA["pdf_ancora"],
        "ancoras_pdf",
    )


def test_chave_de_acesso_vem_da_ancora_universal(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert len(nota.documento.chave_acesso) == 44
    assert nota.extracao.campos["documento.chave_acesso"].confianca == CONFIANCA["pdf_chave"]


def test_campos_derivados_da_chave(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.documento.modelo == "55"
    assert nota.documento.tipo == "nfe"
    assert nota.documento.numero == "12345"
    assert nota.documento.serie == "1"
    assert nota.emitente.cnpj == "11222333000181"


def test_numero_da_chave_vence_o_lido_do_layout(ler_fixture) -> None:
    # A chave tem DV; o rótulo impresso não tem como ser verificado.
    nota = _nota(ler_fixture)
    assert nota.extracao.campos["documento.numero"].origem.startswith("chave:")
    assert nota.extracao.campos["emitente.cnpj"].origem.startswith("chave:")


def test_valores_em_formato_brasileiro(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.totais.valor_total == Decimal("5200.00")
    assert nota.totais.valor_produtos == Decimal("5050.00")
    assert nota.totais.frete == Decimal("150.00")


def test_data_de_emissao(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.documento.data_emissao.day == 14
    assert nota.documento.data_emissao.month == 9


def test_situacao_e_sempre_desconhecida_em_pdf(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.documento.situacao == "desconhecida"


def test_requer_revisao_porque_a_confianca_e_baixa(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.extracao.confianca_global < 0.85
    assert nota.extracao.requer_revisao is True


def test_avisa_que_itens_nao_foram_extraidos(ler_fixture) -> None:
    # Lista vazia por limitação, não porque a nota não tem item.
    nota = _nota(ler_fixture)
    assert nota.itens == []
    assert "ITENS_NAO_EXTRAIDOS" in {p.codigo for p in nota.extracao.problemas}


def test_informacoes_adicionais(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.informacoes_adicionais.startswith("Obra Residencial Alfa")


def test_texto_sem_chave_nao_inventa_campos() -> None:
    arquivo = ArquivoOrigem(nome="x.pdf", mime="application/pdf", bytes=1, sha256="a" * 64)
    nota = extrair_de_texto(
        "DANFE\nsem nada legivel",
        arquivo,
        Dialeto.DANFE_PDF,
        CONFIANCA["pdf_ancora"],
        "ancoras_pdf",
    )
    assert nota.documento.chave_acesso is None
    assert nota.documento.numero is None
    assert nota.emitente is None or nota.emitente.cnpj is None


def test_cnpj_ilegivel_e_descartado_com_aviso() -> None:
    arquivo = ArquivoOrigem(nome="x.pdf", mime="application/pdf", bytes=1, sha256="a" * 64)
    nota = extrair_de_texto(
        "DANFE\nCNPJ 11.222.333/0001-99\nVALOR TOTAL DA NOTA\n100,00",
        arquivo,
        Dialeto.DANFE_PDF,
        CONFIANCA["pdf_ancora"],
        "ancoras_pdf",
    )
    assert nota.emitente is None or nota.emitente.cnpj is None
    assert "CNPJ_ILEGIVEL" in {p.codigo for p in nota.extracao.problemas}


# --- Caminho completo: PDF de verdade, não só texto ---


def test_pdf_real_e_lido_fim_a_fim(ler_fixture) -> None:
    from decimal import Decimal

    from nfscan.extratores.pdf_texto import ExtratorPdfTexto

    conteudo, arquivo = ler_fixture("danfe_texto_simples.pdf", "application/pdf")
    nota = ExtratorPdfTexto().extrair(conteudo, arquivo)
    assert nota.documento.chave_acesso is not None
    assert nota.documento.numero == "12345"
    assert nota.emitente.cnpj == "11222333000181"
    # Os valores do bloco tabular exigem leitura por coluna: um motor que
    # pegasse "o primeiro número após o rótulo" devolveria 150,00 aqui.
    assert nota.totais.valor_total == Decimal("5200.00")
    assert nota.totais.valor_produtos == Decimal("5050.00")
    assert nota.totais.frete == Decimal("150.00")
    assert nota.totais.tributos.icms_valor == Decimal("909.00")
    assert nota.extracao.motor == "ancoras_pdf"


def test_pdf_real_percorre_o_pipeline(ler_fixture) -> None:
    from nfscan.pipeline import parse

    conteudo, _ = ler_fixture("danfe_texto_simples.pdf", "application/pdf")
    nota = parse(conteudo, "danfe.pdf")
    assert nota.extracao.dialeto == "danfe_pdf"
    assert nota.extracao.motor == "ancoras_pdf"
    assert nota.extracao.requer_revisao is True
    assert "ITENS_NAO_EXTRAIDOS" in {p.codigo for p in nota.extracao.problemas}
