"""Acumula confiança e proveniência durante a extração.

As faixas de confiança vêm da spec, seção 3.6. Um único lugar define os
números para que os extratores não divirjam entre si.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from nfscan.modelo.extracao import CampoExtraido, Problema

T = TypeVar("T")

CONFIANCA: dict[str, float] = {
    "xml_oficial": 1.0,
    "xml_tolerante": 0.90,
    "pdf_chave": 0.75,
    "pdf_ancora": 0.50,
    "ocr_confirmado": 0.50,
    "ocr_bruto": 0.30,
}

LIMITE_REVISAO = 0.85


class Coletor:
    """Registra o que foi extraído, de onde e com quanta confiança."""

    def __init__(self, confianca_base: float) -> None:
        self._base = confianca_base
        self._campos: dict[str, CampoExtraido] = {}

    def registrar(self, caminho: str, valor: T, origem: str, confianca: float | None = None) -> T:
        """Registra o campo e devolve o valor, para uso em linha.

        Valor ``None`` não é registrado: campo ausente não tem confiança nem
        proveniência, e inflar a média com ausências mentiria sobre a
        qualidade da extração.
        """
        if valor is not None:
            self._campos[caminho] = CampoExtraido(
                confianca=self._base if confianca is None else confianca, origem=origem
            )
        return valor

    @property
    def campos(self) -> dict[str, CampoExtraido]:
        return dict(self._campos)

    def confianca_global(self) -> float:
        """Confiança do elo mais fraco entre os campos extraídos.

        A média invertia o sinal: um DANFE em que só a chave foi lida pontuava
        0.75, e o mesmo DANFE com a chave mais cinco âncoras mais fracas
        pontuava 0.625 — extração mais completa com confiança menor, o oposto
        do que o número deve comunicar.

        O mínimo é monótono e conservador: acrescentar campo nunca sobe a
        confiança global, e ela nunca afirma mais do que o campo menos
        confiável sustenta. A decisão campo a campo é feita em
        ``extracao.campos``, que é onde a informação fina mora.
        """
        if not self._campos:
            return 0.0
        return round(min(campo.confianca for campo in self._campos.values()), 4)


def requer_revisao(confianca_global: float, problemas: Sequence[Problema]) -> bool:
    """Decide se a nota precisa de olho humano antes de ser aceita."""
    if confianca_global < LIMITE_REVISAO:
        return True
    return any(problema.severidade == "erro" for problema in problemas)
