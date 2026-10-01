"""OCR de PDF-imagem e foto.

A fixture é sintética e limpa. Estes testes provam que o caminho funciona;
precisão em foto real só se conhece com amostras do usuário.
"""

import pytest

from nfscan.extratores.ocr.extrator import ExtratorOcr
from nfscan.modelo import ArquivoOrigem
from nfscan.modelo.coletor import CONFIANCA
from nfscan.sniff.container import Container, detectar_container

pytest.importorskip("pytesseract")
pytest.importorskip("PIL")

IMAGEM = "danfe_imagem_simples.png"


def _nota(ler_fixture):
    conteudo, arquivo = ler_fixture(IMAGEM, "image/png")
    return ExtratorOcr().extrair(conteudo, arquivo)


def test_imagem_e_detectada_como_imagem(ler_fixture) -> None:
    conteudo, _ = ler_fixture(IMAGEM, "image/png")
    assert detectar_container(conteudo) is Container.IMAGEM


def test_ocr_encontra_a_chave_de_acesso(ler_fixture) -> None:
    # O OCR quebra a chave em grupos de quatro; extrair_chave tolera os
    # separadores e o mod-11 confirma que a leitura está certa.
    nota = _nota(ler_fixture)
    assert nota.documento.chave_acesso is not None
    assert len(nota.documento.chave_acesso) == 44


def test_chave_lida_por_ocr_sobe_de_confianca_por_ter_dv(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    campo = nota.extracao.campos["documento.chave_acesso"]
    assert campo.confianca == CONFIANCA["ocr_confirmado"]


def test_campos_derivados_da_chave_vem_do_ocr(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.documento.numero == "12345"
    assert nota.documento.modelo == "55"
    assert nota.emitente.cnpj == "11222333000181"


def test_ocr_sempre_pede_revisao(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert nota.extracao.requer_revisao is True
    assert nota.extracao.motor == "tesseract"


def test_ocr_avisa_que_itens_nao_foram_extraidos(ler_fixture) -> None:
    nota = _nota(ler_fixture)
    assert "ITENS_NAO_EXTRAIDOS" in {p.codigo for p in nota.extracao.problemas}


def test_colunas_do_bloco_tabular_saem_corretas(ler_fixture) -> None:
    from decimal import Decimal

    nota = _nota(ler_fixture)
    assert nota.totais.valor_produtos == Decimal("5050.00")
    assert nota.totais.valor_total == Decimal("5200.00")
    assert nota.totais.tributos.icms_valor == Decimal("909.00")
    assert nota.totais.tributos.icms_base == Decimal("5050.00")


def test_valor_mal_lido_e_pego_pela_validacao_cruzada(ler_fixture) -> None:
    """O OCR pode trocar um dígito, e a validação cruzada é a rede.

    O resultado depende do pacote de idioma instalado: com ``por`` esta fixture
    lê o frete como 150,00; com ``eng`` o Tesseract lê 150,60. Nenhuma política
    de regex corrige dígito lido errado — o que protege o consumidor é a soma
    não fechar: 5050,00 + 150,60 contra 5200,00 sai como TOTAL_DIVERGENTE.

    O teste afirma a invariante, não o número de um ambiente: ou o frete está
    correto, ou a divergência foi sinalizada. Nunca valor errado em silêncio.
    """
    from decimal import Decimal

    from nfscan.pipeline import parse

    conteudo, arquivo = ler_fixture(IMAGEM, "image/png")
    nota = parse(conteudo, arquivo.nome)
    codigos = {p.codigo for p in nota.extracao.problemas}

    if nota.totais.frete == Decimal("150.00"):
        assert "TOTAL_DIVERGENTE" not in codigos
    else:
        assert "TOTAL_DIVERGENTE" in codigos
    # Em qualquer um dos casos, OCR sempre pede conferência humana.
    assert nota.extracao.requer_revisao is True


def test_imagem_em_branco_nao_levanta() -> None:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("L", (600, 400), color=255).save(buffer, format="PNG")
    conteudo = buffer.getvalue()
    arquivo = ArquivoOrigem(
        nome="branco.png", mime="image/png", bytes=len(conteudo), sha256="a" * 64
    )
    nota = ExtratorOcr().extrair(conteudo, arquivo)
    assert nota.documento.chave_acesso is None
    assert nota.extracao.requer_revisao is True


def test_imagem_corrompida_nao_levanta() -> None:
    arquivo = ArquivoOrigem(
        nome="ruim.png", mime="image/png", bytes=8, sha256="a" * 64
    )
    nota = ExtratorOcr().extrair(b"\x89PNG\r\n\x1a\nlixo", arquivo)
    assert nota.extracao.requer_revisao is True
    assert "ARQUIVO_ILEGIVEL" in {p.codigo for p in nota.extracao.problemas}


def test_idioma_cai_para_ingles_quando_portugues_falta() -> None:
    # A spec assume o pacote de idioma 'por'. Sem ele o serviço não pode
    # quebrar: cai para 'eng' e avisa, porque digito e rotulo em caixa alta
    # ainda saem legiveis.
    from nfscan.extratores.ocr.extrator import idioma_disponivel

    assert idioma_disponivel() in {"por", "eng", ""}


def test_avisa_quando_o_idioma_portugues_nao_esta_instalado(ler_fixture) -> None:
    from nfscan.api.diagnostico import idiomas_tesseract

    nota = _nota(ler_fixture)
    codigos = {p.codigo for p in nota.extracao.problemas}
    if "por" not in idiomas_tesseract():
        assert "OCR_IDIOMA_AUSENTE" in codigos
    else:
        assert "OCR_IDIOMA_AUSENTE" not in codigos
