"""Extração de NFS-e nacional e ABRASF."""

from decimal import Decimal

from nfscan.extratores.xml_abrasf import ExtratorAbrasf
from nfscan.extratores.xml_nfse_nacional import ExtratorNfseNacional

ABRASF = "abrasf_2_03_simples.xml"
NACIONAL = "nfse_nacional_oficial.xml"


def _abrasf(ler_fixture, nome: str = ABRASF):
    conteudo, arquivo = ler_fixture(nome, "application/xml")
    return ExtratorAbrasf().extrair(conteudo, arquivo)


def _nacional(ler_fixture):
    conteudo, arquivo = ler_fixture(NACIONAL, "application/xml")
    return ExtratorNfseNacional().extrair(conteudo, arquivo)


# --- ABRASF 2.0x (layouts municipais) ---


def test_abrasf_documento(ler_fixture) -> None:
    nota = _abrasf(ler_fixture)
    assert nota.documento.tipo == "nfse"
    assert nota.documento.numero == "4521"
    assert nota.documento.chave_acesso is None
    assert nota.documento.data_emissao.month == 9
    assert nota.documento.data_competencia.month == 9
    assert nota.documento.municipio_prestacao == "3550308"


def test_abrasf_prestador_vai_para_emitente(ler_fixture) -> None:
    nota = _abrasf(ler_fixture)
    assert nota.emitente.cnpj == "11222333000181"
    assert nota.emitente.razao_social == "Servicos de Engenharia Ltda"
    assert nota.emitente.inscricao_municipal == "987654"


def test_abrasf_tomador_vai_para_destinatario(ler_fixture) -> None:
    nota = _abrasf(ler_fixture)
    assert nota.destinatario.cnpj == "11444777000161"
    assert nota.destinatario.razao_social == "Construtora Exemplo Ltda"


def test_abrasf_cnpj_do_prestador_nao_vaza_para_o_tomador(ler_fixture) -> None:
    nota = _abrasf(ler_fixture)
    assert nota.emitente.cnpj != nota.destinatario.cnpj


def test_abrasf_valores_e_retencoes(ler_fixture) -> None:
    nota = _abrasf(ler_fixture)
    assert nota.totais.valor_servicos == Decimal("12000.00")
    assert nota.totais.valor_total == Decimal("11562.00")
    assert nota.totais.tributos.iss_valor == Decimal("600.00")
    assert nota.totais.tributos.retencoes.pis == Decimal("78.00")
    assert nota.totais.tributos.retencoes.cofins == Decimal("360.00")


def test_abrasf_servico_vira_item_unico(ler_fixture) -> None:
    nota = _abrasf(ler_fixture)
    assert len(nota.itens) == 1
    assert nota.itens[0].descricao.startswith("Execucao de alvenaria")
    assert nota.itens[0].codigo == "0702"
    assert nota.itens[0].valor_total == Decimal("12000.00")


def test_abrasf_confianca_e_a_de_xml_tolerante(ler_fixture) -> None:
    nota = _abrasf(ler_fixture)
    assert nota.extracao.confianca_global == 0.9
    assert nota.extracao.motor == "xpath_tolerante"


def test_abrasf_variante_sem_namespace_e_lida(ler_fixture) -> None:
    nota = _abrasf(ler_fixture, "abrasf_variante_sem_namespace.xml")
    assert nota.documento.numero == "4521"
    assert nota.emitente.cnpj == "11222333000181"


# --- NFS-e nacional 1.0 (sample oficial da nfelib) ---


def test_nacional_documento(ler_fixture) -> None:
    nota = _nacional(ler_fixture)
    assert nota.documento.tipo == "nfse"
    assert nota.documento.numero == "2"
    assert nota.documento.serie == "900"
    assert nota.documento.municipio_prestacao == "1400159"


def test_nacional_chave_tem_cinquenta_digitos(ler_fixture) -> None:
    # A chave da NFS-e nacional tem 50 dígitos e estrutura própria; não é a
    # chave de 44 da NF-e e não passa pelo mod-11 dela.
    nota = _nacional(ler_fixture)
    assert len(nota.documento.chave_acesso) == 50
    assert nota.documento.chave_acesso.isdigit()


def test_nacional_situacao_vem_do_cstat(ler_fixture) -> None:
    # Diferente da NF-e, o XML da NFS-e nacional já carrega o cStat do ADN.
    nota = _nacional(ler_fixture)
    assert nota.documento.situacao == "autorizada"


def test_nacional_emitente(ler_fixture) -> None:
    nota = _nacional(ler_fixture)
    assert nota.emitente.cnpj == "01761135000132"
    assert nota.emitente.razao_social == "LW SOFTWARES LTDA"
    assert nota.emitente.inscricao_municipal == "01761135000132"
    assert nota.emitente.endereco.uf == "RR"
    assert nota.emitente.endereco.codigo_municipio_ibge == "1400159"
    assert nota.emitente.endereco.cep == "69380000"


def test_nacional_sem_tomador_nao_inventa_destinatario(ler_fixture) -> None:
    nota = _nacional(ler_fixture)
    assert nota.destinatario is None


def test_nacional_datas(ler_fixture) -> None:
    nota = _nacional(ler_fixture)
    assert nota.documento.data_emissao.year == 2022
    assert nota.documento.data_competencia.isoformat() == "2022-09-28"


def test_nacional_valores_e_retencoes(ler_fixture) -> None:
    nota = _nacional(ler_fixture)
    assert nota.totais.valor_servicos == Decimal("999999999.99")
    assert nota.totais.valor_total == Decimal("989999961.04")
    assert nota.totais.tributos.retencoes.irrf == Decimal("9.99")
    assert nota.totais.tributos.retencoes.csll == Decimal("9.99")
    assert nota.totais.tributos.retencoes.inss == Decimal("8.99")


def test_nacional_servico_vira_item_unico(ler_fixture) -> None:
    nota = _nacional(ler_fixture)
    assert len(nota.itens) == 1
    assert nota.itens[0].codigo == "010101"
    assert nota.itens[0].valor_total == Decimal("999999999.99")


def test_nacional_confianca_plena(ler_fixture) -> None:
    nota = _nacional(ler_fixture)
    assert nota.extracao.confianca_global == 1.0
    assert nota.extracao.motor == "nfelib"
