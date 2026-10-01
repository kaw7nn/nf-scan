"""Tipos escalares do modelo canônico.

Dinheiro e quantidade são ``Decimal`` e serializam como string. Um ``float``
em JSON perde precisão no consumidor — em JavaScript, 0.1 + 0.2 não é 0.3 — e
nota fiscal é documento contábil.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

Dinheiro = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]
Quantidade = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]

VERSAO_SCHEMA = "1.0"
