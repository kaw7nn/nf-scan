"""Extração de NF-e 4.00 a partir do XML."""

from decimal import Decimal

from nfscan.extratores.xml_nfe import ExtratorNfe


def _extrair(ler_fixture):
    conteudo, arquivo = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    return ExtratorNfe().extrair(conteudo, arquivo)


def test_documento(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert nota.documento.tipo == "nfe"
    assert nota.documento.modelo == "55"
    assert nota.documento.numero == "1234"
    assert nota.documento.serie == "1"
    assert nota.documento.natureza_operacao == "Venda de mercadoria"
    assert nota.documento.finalidade == "normal"
    assert nota.documento.chave_acesso.startswith("3526")
    assert len(nota.documento.chave_acesso) == 44
    assert nota.documento.data_emissao.year == 2026


def test_situacao_fica_desconhecida_sem_protocolo(ler_fixture) -> None:
    # Sem consulta à SEFAZ não há como afirmar que a nota está autorizada.
    nota = _extrair(ler_fixture)
    assert nota.documento.situacao == "desconhecida"


def test_emitente(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert nota.emitente.cnpj == "11222333000181"
    assert nota.emitente.cpf is None
    assert nota.emitente.razao_social == "Fornecedor de Materiais Ltda"
    assert nota.emitente.nome_fantasia == "Fornecedora"
    assert nota.emitente.inscricao_estadual == "123456789"
    assert nota.emitente.regime_tributario == "real"
    assert nota.emitente.endereco.uf == "SP"
    assert nota.emitente.endereco.codigo_municipio_ibge == "3550308"
    assert nota.emitente.endereco.cep == "01001000"


def test_destinatario(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert nota.destinatario.cnpj == "11444777000161"
    assert nota.destinatario.razao_social == "Construtora Exemplo Ltda"


def test_itens(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert len(nota.itens) == 2
    primeiro = nota.itens[0]
    assert primeiro.ordem == 1
    assert primeiro.codigo == "MAT-001"
    assert primeiro.descricao == "Cimento CP-II 50kg"
    assert primeiro.ncm == "25232910"
    assert primeiro.cfop == "5102"
    assert primeiro.unidade == "SC"
    assert primeiro.quantidade == Decimal("100.0000")
    assert primeiro.valor_unitario == Decimal("38.5000")
    assert primeiro.valor_total == Decimal("3850.00")
    assert primeiro.impostos.icms.cst == "00"
    assert primeiro.impostos.icms.aliquota == Decimal("18.00")
    assert primeiro.impostos.icms.valor == Decimal("693.00")


def test_totais(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert nota.totais.valor_produtos == Decimal("5050.00")
    assert nota.totais.frete == Decimal("150.00")
    assert nota.totais.desconto == Decimal("0.00")
    assert nota.totais.valor_total == Decimal("5200.00")
    assert nota.totais.tributos.icms_valor == Decimal("909.00")


def test_pagamento_e_transporte(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert nota.pagamento.formas[0].tipo == "boleto"
    assert nota.pagamento.formas[0].valor == Decimal("5200.00")
    assert nota.transporte.modalidade_frete == "emitente"


def test_informacoes_adicionais(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert nota.informacoes_adicionais == "Obra Residencial Alfa - bloco 2"


def test_metadados_de_extracao(ler_fixture) -> None:
    nota = _extrair(ler_fixture)
    assert nota.extracao.dialeto == "nfe_4.00"
    assert nota.extracao.motor == "nfelib"
    assert nota.extracao.confianca_global == 1.0
    assert nota.extracao.campos["emitente.cnpj"].confianca == 1.0
    assert nota.extracao.campos["emitente.cnpj"].origem.startswith("xml:")


def test_preco_unitario_com_tres_decimais_nao_e_lido_como_milhar(ler_fixture) -> None:
    # vUnCom aceita 3 decimais. Se o extrator não disser a para_decimal que o
    # ponto é decimal, "38.500" viraria 38500 — erro de mil vezes.
    conteudo, arquivo = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    adulterado = conteudo.replace(b"<vUnCom>38.5000</vUnCom>", b"<vUnCom>38.500</vUnCom>")
    nota = ExtratorNfe().extrair(adulterado, arquivo)
    assert nota.itens[0].valor_unitario == Decimal("38.500")


def test_golden_file(ler_fixture) -> None:
    import json
    from pathlib import Path

    nota = _extrair(ler_fixture)
    obtido = nota.model_dump(mode="json")
    obtido["extracao"]["duracao_ms"] = 0
    esperado = json.loads(
        (Path(__file__).parents[1] / "golden" / "nfe_4_00_simples.json").read_text(
            encoding="utf-8"
        )
    )
    assert obtido == esperado
