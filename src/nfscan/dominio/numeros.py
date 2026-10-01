"""Conversão de números e datas para os tipos canônicos.

Dinheiro é sempre ``Decimal``. O formato de origem varia: o XML da NF-e usa
ponto decimal, o DANFE impresso usa o formato brasileiro com ponto de milhar
e vírgula decimal. Confundir os dois é o erro mais caro do sistema.

O ponto sozinho é genuinamente ambíguo: ``"1.234"`` é mil duzentos e trinta
e quatro em um DANFE e um e duzentos e trinta e quatro milésimos em um XML,
onde ``vUnCom`` aceita três decimais. Nenhuma heurística resolve isso a
partir da string. Quem chama sabe de onde o valor veio, então o formato é
parâmetro: os extratores de XML passam ``"ponto_decimal"``, os de texto e
OCR usam ``"auto"``.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

_LIXO = re.compile(r"[^\d,.\-()]")
_SO_DIGITOS_E_SEPARADORES = re.compile(r"^-?[\d.,]+$")

Formato = Literal["auto", "ponto_decimal"]

_FORMATOS_DATA_HORA = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)

_TAMANHO_GRUPO_MILHAR = 3


def _desambiguar_separadores(texto: str, formato: Formato) -> str:
    """Converte a notação de origem para ponto decimal sem milhar.

    Em ``"ponto_decimal"`` o texto passa intacto: o ponto é sempre decimal.

    Em ``"auto"``, na ordem:

    1. Havendo vírgula, ela é o separador decimal e o ponto é milhar.
    2. Mais de um ponto só faz sentido como milhar.
    3. Um ponto é milhar quando a parte à esquerda tem de 1 a 3 dígitos, não
       começa com zero, e a da direita tem exatamente 3 — a forma de um grupo
       de milhar. Com parte inteira mais longa, como ``"1234.567"``, não há
       grupo possível, e com zero à esquerda, como ``"0.500"``, o grupo seria
       impossível: nos dois casos o ponto é decimal.
    """
    if formato == "ponto_decimal":
        return texto
    if "," in texto:
        return texto.replace(".", "").replace(",", ".")
    if texto.count(".") > 1:
        return texto.replace(".", "")
    if "." in texto:
        inteiro, _, fracao = texto.rpartition(".")
        milhar_possivel = (
            len(fracao) == _TAMANHO_GRUPO_MILHAR
            and 1 <= len(inteiro) <= _TAMANHO_GRUPO_MILHAR
            # Um grupo de milhar nunca começa com zero: "0.500" é meio, não
            # quinhentos, e "0.025" é a alíquota de 2,5%, não vinte e cinco.
            and not inteiro.startswith("0")
        )
        if milhar_possivel:
            return texto.replace(".", "")
    return texto


def para_decimal(
    valor: str | int | float | Decimal | None,
    casas: int | None = None,
    formato: Formato = "auto",
) -> Decimal | None:
    """Converte para ``Decimal``, ou ``None`` quando não há número legível.

    Aceita ``1234.56``, ``1.234,56``, ``1234,56``, ``R$ 1.234,56`` e
    ``(150,00)`` como negativo. Nunca levanta: valor ilegível é ausência de
    informação, e o chamador registra a confiança.
    """
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        bruto = valor
    elif isinstance(valor, int):
        bruto = Decimal(valor)
    elif isinstance(valor, float):
        bruto = Decimal(str(valor))
    else:
        texto = _LIXO.sub("", valor).strip()
        if not texto:
            return None
        negativo = texto.startswith("-") or (texto.startswith("(") and texto.endswith(")"))
        texto = texto.strip("()").lstrip("-")
        if not _SO_DIGITOS_E_SEPARADORES.match(texto) or not any(c.isdigit() for c in texto):
            return None
        try:
            bruto = Decimal(_desambiguar_separadores(texto, formato))
        except InvalidOperation:
            return None
        if negativo:
            bruto = -bruto

    if casas is None:
        return bruto
    return bruto.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)


def para_data_hora(valor: str | None) -> datetime | None:
    """Converte para ``datetime``, preservando o fuso quando informado."""
    if not valor or not valor.strip():
        return None
    texto = valor.strip()
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        pass
    for formato in _FORMATOS_DATA_HORA:
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def para_data(valor: str | None) -> date | None:
    """Converte para ``date``, descartando a hora se houver."""
    lido = para_data_hora(valor)
    return lido.date() if lido else None
