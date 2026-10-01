"""Regressões da revisão final de branch.

Um teste por achado, nomeado pelo defeito que reproduz. Todos falhavam antes da
passada de correção.
"""

from decimal import Decimal

import pytest

from nfscan.detect.dialeto import Dialeto
from nfscan.extratores.ancoras.motor import valor_na_coluna
from nfscan.extratores.pdf_texto import extrair_de_texto
from nfscan.modelo import ArquivoOrigem
from nfscan.modelo.coletor import CONFIANCA
from nfscan.pipeline import parse

# DANFE com os valores ALINHADOS À DIREITA na coluna, que é como emissores reais
# imprimem. A fixture gerada centraliza os valores e escondia o defeito.
DANFE_DIREITA = """\
 CALCULO DO IMPOSTO
 BASE DE CALCULO DO ICMS   VALOR DO ICMS   VALOR TOTAL DOS PRODUTOS
                5.050,00          909,00                   5.050,00
 VALOR DO FRETE   VALOR DO SEGURO   DESCONTO   VALOR TOTAL DA NOTA
         150,00              0,00       0,00              5.200,00
"""


def _arquivo(nome: str = "x.pdf", mime: str = "application/pdf") -> ArquivoOrigem:
    return ArquivoOrigem(nome=nome, mime=mime, bytes=1, sha256="a" * 64)


# --- 1: vazamento de coluna com valores alinhados à direita ---


@pytest.mark.parametrize(
    ("rotulo", "esperado"),
    [
        ("VALOR TOTAL DA NOTA", "5.200,00"),
        ("VALOR TOTAL DOS PRODUTOS", "5.050,00"),
        ("VALOR DO ICMS", "909,00"),
        ("BASE DE CALCULO DO ICMS", "5.050,00"),
        ("VALOR DO FRETE", "150,00"),
        ("VALOR DO SEGURO", "0,00"),
    ],
)
def test_coluna_alinhada_a_direita_escolhe_a_maior_sobreposicao(
    rotulo: str, esperado: str
) -> None:
    # O primeiro número que apenas toca a faixa do rótulo é da coluna vizinha.
    # Vale o de maior sobreposição.
    assert valor_na_coluna(DANFE_DIREITA, rotulo) == esperado


def test_danfe_alinhado_a_direita_nao_troca_frete_por_seguro() -> None:
    nota = extrair_de_texto(
        DANFE_DIREITA, _arquivo(), Dialeto.DANFE_PDF, CONFIANCA["pdf_ancora"], "ancoras_pdf"
    )
    assert nota.totais.valor_total == Decimal("5200.00")
    assert nota.totais.valor_produtos == Decimal("5050.00")
    assert nota.totais.frete == Decimal("150.00")
    assert nota.totais.seguro == Decimal("0.00")
    assert nota.totais.tributos.icms_valor == Decimal("909.00")


# --- 11: a primeira ocorrência do rótulo não pode matar o campo ---


def test_mencao_anterior_do_rotulo_nao_descarta_o_campo() -> None:
    texto = "RESUMO: VALOR TOTAL DA NOTA CONFORME ABAIXO\n\n" + DANFE_DIREITA
    assert valor_na_coluna(texto, "VALOR TOTAL DA NOTA") == "5.200,00"


# --- 2: ABRASF mistura campos de notas diferentes e descarta as demais ---


def test_abrasf_com_duas_notas_nao_mistura_campos(ler_fixture) -> None:
    from nfscan.extratores.xml_abrasf import ExtratorAbrasf

    conteudo, arquivo = ler_fixture("abrasf_2_03_simples.xml", "application/xml")
    bruto = conteudo.decode("utf-8")
    inicio, fim = bruto.index("<CompNfse>"), bruto.index("</CompNfse>") + len("</CompNfse>")
    primeira = bruto[inicio:fim].replace("<ValorIss>600.00</ValorIss>", "")
    segunda = bruto[inicio:fim].replace("<Numero>4521</Numero>", "<Numero>4522</Numero>")
    duas = (bruto[:inicio] + primeira + segunda + bruto[fim:]).encode("utf-8")

    nota = ExtratorAbrasf().extrair(duas, arquivo)
    assert nota.documento.numero == "4521"
    # O ISS da segunda nota não pode aparecer na primeira.
    assert nota.totais.tributos.iss_valor is None
    assert "MULTIPLAS_NOTAS_NO_ARQUIVO" in {p.codigo for p in nota.extracao.problemas}


# --- 3: documento truncado reportado como plenamente confiável ---


def test_xml_truncado_nao_e_reportado_como_confiavel(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    nota = parse(conteudo[:900], "truncado.xml")
    assert "VALOR_TOTAL_AUSENTE" in {p.codigo for p in nota.extracao.problemas}
    assert nota.extracao.requer_revisao is True


def test_confianca_global_nao_sobe_ao_acrescentar_campo_mais_fraco() -> None:
    from nfscan.modelo.coletor import Coletor

    # A média invertia o sinal: só a chave dava 0.75, e a chave mais cinco
    # âncoras mais fracas dava 0.625 — extração mais completa com confiança
    # maior. A confiança global passa a ser o elo mais fraco.
    so_chave = Coletor(CONFIANCA["pdf_ancora"])
    so_chave.registrar("documento.chave_acesso", "x", "chave:valor", confianca=0.75)

    com_ancoras = Coletor(CONFIANCA["pdf_ancora"])
    com_ancoras.registrar("documento.chave_acesso", "x", "chave:valor", confianca=0.75)
    for indice in range(5):
        com_ancoras.registrar(f"campo{indice}", "y", "regex:generico")

    assert com_ancoras.confianca_global() <= so_chave.confianca_global()


# --- 4: XML declarado latin-1 virava mojibake com confiança 1.0 ---


def test_xml_latin1_e_decodificado_corretamente(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    bruto = (
        conteudo.decode("utf-8")
        .replace('encoding="UTF-8"', 'encoding="ISO-8859-1"')
        .replace("Fornecedor de Materiais Ltda", "Construções JOSÉ Ltda")
        .encode("latin-1")
    )
    nota = parse(bruto, "latin1.xml")
    assert nota.emitente.razao_social == "Construções JOSÉ Ltda"
    assert "�" not in (nota.emitente.razao_social or "")


# --- 5: chave perdida por um dígito solto à esquerda dela ---


@pytest.mark.parametrize(
    "prefixo",
    ["SERIE 1   ", "0001234 ", "1", "No 12345  "],
)
def test_digito_antes_da_chave_nao_faz_perder_a_chave(prefixo: str) -> None:
    from nfscan.dominio.chave import calcular_dv, extrair_chave

    base = "35" + "2609" + "11222333000181" + "55" + "001" + "000012345" + "1" + "87654321"
    chave = base + calcular_dv(base)
    assert extrair_chave(prefixo + chave).valor == chave


# --- 6: TOTAL_DIVERGENTE falso em toda NFS-e e em NF-e com IPI ---


def test_nfse_abrasf_nao_gera_total_divergente_falso(ler_fixture) -> None:
    conteudo, _ = ler_fixture("abrasf_2_03_simples.xml", "application/xml")
    nota = parse(conteudo, "abrasf.xml")
    assert "TOTAL_DIVERGENTE" not in {p.codigo for p in nota.extracao.problemas}


def test_nfse_nacional_nao_gera_total_divergente_falso(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfse_nacional_oficial.xml", "application/xml")
    nota = parse(conteudo, "nacional.xml")
    assert "TOTAL_DIVERGENTE" not in {p.codigo for p in nota.extracao.problemas}


def test_nfe_com_ipi_fecha_o_total_e_preserva_o_ipi(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    # vNF = vProd + vIPI + vFrete - vDesc: 5050 + 355 + 150 = 5555
    bruto = conteudo.replace(b"<vIPI>0.00</vIPI>", b"<vIPI>355.00</vIPI>").replace(
        b"<vNF>5200.00</vNF>", b"<vNF>5555.00</vNF>"
    )
    nota = parse(bruto, "com_ipi.xml")
    assert nota.totais.ipi == Decimal("355.00")
    assert "TOTAL_DIVERGENTE" not in {p.codigo for p in nota.extracao.problemas}


def test_divergencia_real_de_total_exige_revisao(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    bruto = conteudo.replace(b"<vNF>5200.00</vNF>", b"<vNF>9999.00</vNF>")
    nota = parse(bruto, "divergente.xml")
    assert "TOTAL_DIVERGENTE" in {p.codigo for p in nota.extracao.problemas}
    assert nota.extracao.requer_revisao is True


# --- 7: dinheiro multiplicado por mil no ABRASF ---


def test_abrasf_com_ponto_decimal_nao_multiplica_por_mil(ler_fixture) -> None:
    from nfscan.extratores.xml_abrasf import ExtratorAbrasf

    conteudo, arquivo = ler_fixture("abrasf_2_03_simples.xml", "application/xml")
    bruto = conteudo.replace(b"<ValorIss>600.00</ValorIss>", b"<ValorIss>1.500</ValorIss>")
    nota = ExtratorAbrasf().extrair(bruto, arquivo)
    assert nota.totais.tributos.iss_valor == Decimal("1.500")


def test_abrasf_ainda_le_virgula_decimal_de_municipio(ler_fixture) -> None:
    from nfscan.extratores.xml_abrasf import ExtratorAbrasf

    conteudo, arquivo = ler_fixture("abrasf_2_03_simples.xml", "application/xml")
    bruto = conteudo.replace(
        b"<ValorServicos>12000.00</ValorServicos>", b"<ValorServicos>12.000,00</ValorServicos>"
    )
    nota = ExtratorAbrasf().extrair(bruto, arquivo)
    assert nota.totais.valor_servicos == Decimal("12000.00")


def test_parte_inteira_com_zero_a_esquerda_nao_e_milhar() -> None:
    from nfscan.dominio.numeros import para_decimal

    # Um grupo de milhar nunca começa com zero: "0.500" é meio, não quinhentos.
    assert para_decimal("0.500") == Decimal("0.500")
    assert para_decimal("0.025") == Decimal("0.025")
    # E o milhar legítimo continua funcionando.
    assert para_decimal("1.500") == Decimal("1500")


# --- 8: chave de API não-ASCII derrubava a requisição com 500 ---


def test_chave_de_api_nao_ascii_responde_401_e_nao_500(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from nfscan.api.app import criar_app

    monkeypatch.setenv("NFSCAN_API_KEYS", "chave-de-teste")
    cliente = TestClient(criar_app())
    resposta = cliente.get("/v1/dialetos", headers={"X-API-Key": "señor".encode("latin-1")})
    assert resposta.status_code == 401


# --- 9: ZIP com entrada enorme descartava o lote inteiro ---


def test_zip_com_entrada_gigante_nao_descarta_as_notas_legiveis(ler_fixture) -> None:
    import io
    import zipfile

    from nfscan.pipeline import LIMITE_BYTES, parse_entrada

    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as pacote:
        pacote.writestr("boa.xml", conteudo)
        pacote.writestr("bomba.bin", b"\x00" * (LIMITE_BYTES + 1024))

    notas = parse_entrada(buffer.getvalue(), "lote.zip", "application/zip")
    assert len(notas) == 2
    assert notas[0].emitente.cnpj == "11222333000181"
    assert "ENTRADA_GRANDE_DEMAIS" in {p.codigo for p in notas[1].extracao.problemas}


# --- data: o fallback sem restrição reportava data errada em silêncio ---


def test_nao_inventa_data_de_emissao_a_partir_de_qualquer_data_do_documento() -> None:
    texto = (
        "DANFE\n"
        "CHAVE DE ACESSO\n"
        "FATURA / DUPLICATA\n"
        "VENCIMENTO 30/11/2027   VALOR 100,00\n"
        "VALOR TOTAL DA NOTA\n"
        "          100,00\n"
    )
    nota = extrair_de_texto(
        texto, _arquivo(), Dialeto.DANFE_PDF, CONFIANCA["pdf_ancora"], "ancoras_pdf"
    )
    # Sem o rótulo de emissão, melhor ausente que o vencimento no lugar errado.
    assert nota.documento.data_emissao is None
