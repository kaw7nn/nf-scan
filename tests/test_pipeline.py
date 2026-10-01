"""Pipeline completo: bytes entram, NotaFiscal sai."""

import json

import pytest

from nfscan.pipeline import LIMITE_BYTES, ArquivoGrande, parse


def test_xml_de_nfe_percorre_o_pipeline(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    nota = parse(conteudo, "nfe_4_00_simples.xml")
    assert nota.extracao.dialeto == "nfe_4.00"
    assert nota.extracao.confianca_global == 1.0
    assert nota.extracao.requer_revisao is False
    assert nota.emitente.cnpj == "11222333000181"


def test_pipeline_preenche_o_arquivo_de_origem(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    nota = parse(conteudo, "nfe_4_00_simples.xml")
    assert nota.extracao.arquivo.nome == "nfe_4_00_simples.xml"
    assert nota.extracao.arquivo.bytes == len(conteudo)
    assert len(nota.extracao.arquivo.sha256) == 64


def test_pipeline_anexa_problemas_da_validacao(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    adulterado = conteudo.replace(b"<vNF>5200.00</vNF>", b"<vNF>9999.00</vNF>")
    nota = parse(adulterado, "adulterado.xml")
    assert "TOTAL_DIVERGENTE" in {p.codigo for p in nota.extracao.problemas}


def test_resultado_e_serializavel_em_json(ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    bruto = json.loads(parse(conteudo, "n.xml").model_dump_json())
    assert bruto["versao_schema"] == "1.0"


def test_arquivo_acima_do_limite_levanta() -> None:
    with pytest.raises(ArquivoGrande):
        parse(b"\x00" * (LIMITE_BYTES + 1), "gigante.pdf")


# --- Foco de Revisão 4: entradas ilegíveis não podem derrubar o serviço ---


def test_arquivo_de_zero_byte_nao_levanta() -> None:
    nota = parse(b"", "vazio.pdf")
    assert nota.extracao.dialeto == "desconhecido"
    assert nota.extracao.requer_revisao is True
    assert nota.extracao.confianca_global == 0.0
    assert "ARQUIVO_ILEGIVEL" in {p.codigo for p in nota.extracao.problemas}


def test_pdf_truncado_nao_levanta() -> None:
    nota = parse(b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog", "truncado.pdf")
    assert nota.extracao.requer_revisao is True
    assert nota.documento.tipo == "desconhecido"


def test_pdf_protegido_por_senha_nao_levanta() -> None:
    bruto = b"%PDF-1.7\ntrailer\n<< /Encrypt 1 0 R /Root 2 0 R >>\n%%EOF"
    nota = parse(bruto, "protegido.pdf")
    assert nota.extracao.requer_revisao is True


def test_xml_truncado_nao_levanta() -> None:
    bruto = (
        b'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">'
        b"<NFe><infNFe"
    )
    nota = parse(bruto, "truncado.xml")
    assert nota.extracao.requer_revisao is True
    assert "EXTRACAO_FALHOU" in {p.codigo for p in nota.extracao.problemas}


def test_arquivo_de_texto_qualquer_nao_levanta() -> None:
    nota = parse(b"planilha de compras do mes", "planilha.txt")
    assert nota.extracao.dialeto == "desconhecido"
    assert nota.extracao.requer_revisao is True
