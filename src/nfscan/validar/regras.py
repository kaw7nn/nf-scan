"""Regras cruzadas sobre a nota já extraída.

Nenhuma regra levanta exceção: o resultado é sempre uma lista de problemas.
Nota ruim é informação para o consumidor, não falha do serviço.

As comparações de dinheiro usam tolerância absoluta de um centavo, porque
emissores arredondam item a item e a soma raramente fecha ao centavo. Toda
comparação é feita no valor absoluto da diferença, nunca por proporção, para
não dividir por zero em nota de valor zero nem inverter sinal em devolução.
"""

from __future__ import annotations

from decimal import Decimal

from nfscan.dominio.chave import chave_valida, parse_chave
from nfscan.dominio.documentos import cnpj_valido, cpf_valido
from nfscan.modelo import NotaFiscal, Problema

TOLERANCIA = Decimal("0.01")

CODIGOS = frozenset(
    {
        "CHAVE_DV_INVALIDO",
        "CNPJ_EMITENTE_INVALIDO",
        "CNPJ_DESTINATARIO_INVALIDO",
        "TOTAL_DIVERGENTE",
        "SOMA_ITENS_DIVERGENTE",
        "DATA_INCOERENTE_COM_CHAVE",
        "EMITENTE_AUSENTE",
        "VALOR_TOTAL_AUSENTE",
    }
)

_ZERO = Decimal("0")


def _ou_zero(valor: Decimal | None) -> Decimal:
    return _ZERO if valor is None else valor


def _validar_participantes(nota: NotaFiscal, problemas: list[Problema]) -> None:
    emitente = nota.emitente
    if emitente is None or (emitente.cnpj is None and emitente.cpf is None):
        problemas.append(
            Problema(
                severidade="erro",
                codigo="EMITENTE_AUSENTE",
                campo="emitente",
                mensagem="A nota não traz identificação do emitente.",
            )
        )
    elif emitente.cnpj and not cnpj_valido(emitente.cnpj):
        problemas.append(
            Problema(
                severidade="erro",
                codigo="CNPJ_EMITENTE_INVALIDO",
                campo="emitente.cnpj",
                mensagem=f"CNPJ do emitente inválido: {emitente.cnpj}.",
            )
        )

    destinatario = nota.destinatario
    if destinatario is None:
        return
    if destinatario.cnpj and not cnpj_valido(destinatario.cnpj):
        problemas.append(
            Problema(
                severidade="erro",
                codigo="CNPJ_DESTINATARIO_INVALIDO",
                campo="destinatario.cnpj",
                mensagem=f"CNPJ do destinatário inválido: {destinatario.cnpj}.",
            )
        )
    if destinatario.cpf and not cpf_valido(destinatario.cpf):
        problemas.append(
            Problema(
                severidade="erro",
                codigo="CNPJ_DESTINATARIO_INVALIDO",
                campo="destinatario.cpf",
                mensagem=f"CPF do destinatário inválido: {destinatario.cpf}.",
            )
        )


def _validar_chave(nota: NotaFiscal, problemas: list[Problema]) -> None:
    chave = nota.documento.chave_acesso
    if not chave:
        return
    if not chave_valida(chave):
        problemas.append(
            Problema(
                severidade="erro",
                codigo="CHAVE_DV_INVALIDO",
                campo="documento.chave_acesso",
                mensagem="O dígito verificador da chave de acesso não confere.",
            )
        )
        return
    emissao = nota.documento.data_emissao
    if emissao is None:
        return
    decomposta = parse_chave(chave)
    if (emissao.year, emissao.month) != (decomposta.ano, decomposta.mes):
        problemas.append(
            Problema(
                severidade="aviso",
                codigo="DATA_INCOERENTE_COM_CHAVE",
                campo="documento.data_emissao",
                mensagem=(
                    f"Data de emissão {emissao:%m/%Y} não corresponde ao período "
                    f"{decomposta.mes:02d}/{decomposta.ano} gravado na chave."
                ),
            )
        )


def _validar_soma_dos_itens(nota: NotaFiscal, problemas: list[Problema]) -> None:
    totais = nota.totais
    if totais is None or not nota.itens:
        return
    if any(item.valor_total is None for item in nota.itens):
        return
    soma = sum((item.valor_total for item in nota.itens if item.valor_total), start=_ZERO)
    produtos = totais.valor_produtos
    if produtos is not None and abs(soma - produtos) > TOLERANCIA:
        problemas.append(
            Problema(
                severidade="aviso",
                codigo="SOMA_ITENS_DIVERGENTE",
                campo="totais.valor_produtos",
                mensagem=(
                    f"Soma dos itens ({soma}) não confere com o valor de produtos "
                    f"informado ({produtos})."
                ),
            )
        )


def _validar_totais(nota: NotaFiscal, problemas: list[Problema]) -> None:
    totais = nota.totais
    if totais is None or totais.valor_total is None:
        problemas.append(
            Problema(
                severidade="aviso",
                codigo="VALOR_TOTAL_AUSENTE",
                campo="totais.valor_total",
                mensagem="A nota não traz valor total legível.",
            )
        )
        return

    _validar_soma_dos_itens(nota, problemas)

    esperado = (
        _ou_zero(totais.valor_produtos)
        + _ou_zero(totais.valor_servicos)
        + _ou_zero(totais.frete)
        + _ou_zero(totais.seguro)
        + _ou_zero(totais.outras_despesas)
        - _ou_zero(totais.desconto)
    )
    if abs(esperado - totais.valor_total) > TOLERANCIA:
        problemas.append(
            Problema(
                severidade="aviso",
                codigo="TOTAL_DIVERGENTE",
                campo="totais.valor_total",
                mensagem=(
                    f"Total informado ({totais.valor_total}) não confere com o cálculo "
                    f"a partir dos componentes ({esperado})."
                ),
            )
        )


def validar(nota: NotaFiscal) -> list[Problema]:
    """Aplica todas as regras cruzadas e devolve os problemas encontrados."""
    problemas: list[Problema] = []
    _validar_participantes(nota, problemas)
    _validar_chave(nota, problemas)
    _validar_totais(nota, problemas)
    return problemas
