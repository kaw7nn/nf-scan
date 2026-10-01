"""Contrato do modelo canônico."""

import json
from decimal import Decimal

from nfscan.modelo import (
    ArquivoOrigem,
    Documento,
    Extracao,
    NotaFiscal,
    Participante,
    Problema,
    Totais,
)


def _extracao_minima() -> Extracao:
    return Extracao(
        dialeto="nfe_4.00",
        motor="nfelib",
        arquivo=ArquivoOrigem(nome="n.xml", mime="application/xml", bytes=10, sha256="a" * 64),
        confianca_global=1.0,
        requer_revisao=False,
        duracao_ms=1,
    )


def test_nota_minima_e_construivel() -> None:
    nota = NotaFiscal(documento=Documento(tipo="nfe"), extracao=_extracao_minima())
    assert nota.versao_schema == "1.1"
    assert nota.itens == []
    assert nota.destinatario is None


def test_campos_ausentes_viram_null_e_nao_desaparecem() -> None:
    nota = NotaFiscal(documento=Documento(tipo="nfe"), extracao=_extracao_minima())
    bruto = json.loads(nota.model_dump_json())
    assert bruto["destinatario"] is None
    assert bruto["documento"]["chave_acesso"] is None
    assert "informacoes_adicionais" in bruto


def test_dinheiro_serializa_como_string() -> None:
    nota = NotaFiscal(
        documento=Documento(tipo="nfe"),
        totais=Totais(valor_total=Decimal("4000.00"), valor_produtos=Decimal("3850.00")),
        extracao=_extracao_minima(),
    )
    bruto = json.loads(nota.model_dump_json())
    assert bruto["totais"]["valor_total"] == "4000.00"
    assert isinstance(bruto["totais"]["valor_total"], str)


def test_dinheiro_nunca_vira_float_no_json() -> None:
    nota = NotaFiscal(
        documento=Documento(tipo="nfe"),
        totais=Totais(valor_total=Decimal("0.07")),
        extracao=_extracao_minima(),
    )
    texto = nota.model_dump_json()
    assert '"valor_total":"0.07"' in texto.replace(" ", "")


def test_participante_aceita_cnpj_ou_cpf() -> None:
    emitente = Participante(cnpj="11222333000181", razao_social="Fornecedor Ltda")
    assert emitente.cpf is None
    assert emitente.razao_social == "Fornecedor Ltda"


def test_problema_tem_codigo_estavel_e_severidade() -> None:
    problema = Problema(
        severidade="aviso",
        codigo="TOTAL_DIVERGENTE",
        campo="totais.valor_produtos",
        mensagem="Soma dos itens não confere.",
    )
    assert problema.severidade == "aviso"


def test_schema_json_e_gerado() -> None:
    schema = NotaFiscal.model_json_schema()
    assert schema["title"] == "NotaFiscal"
    assert "documento" in schema["properties"]
