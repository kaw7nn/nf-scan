"""Limpeza de texto vindo de XML, PDF e OCR."""

from __future__ import annotations

import re

_ESPACOS = re.compile(r"\s+")


def limpar_texto(valor: str | None) -> str | None:
    """Colapsa espaços e devolve ``None`` para texto vazio.

    String vazia não é informação; ``None`` comunica ausência ao consumidor.
    """
    if valor is None:
        return None
    limpo = _ESPACOS.sub(" ", valor).strip()
    return limpo or None
