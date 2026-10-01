"""Autenticação por chave de API.

O serviço roda em rede interna, então uma chave estática no cabeçalho é
proporcional. A comparação usa ``secrets.compare_digest`` para não vazar
informação por tempo de resposta.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status

VARIAVEL_CHAVES = "NFSCAN_API_KEYS"


def _chaves_validas() -> set[str]:
    bruto = os.environ.get(VARIAVEL_CHAVES, "")
    return {parte.strip() for parte in bruto.split(",") if parte.strip()}


def conferir_chave(x_api_key: str | None = Header(default=None)) -> None:
    """Dependência do FastAPI que exige uma chave de API válida."""
    chaves = _chaves_validas()
    if not chaves:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{VARIAVEL_CHAVES} não configurada no servidor.",
        )
    if x_api_key is None or not any(
        secrets.compare_digest(x_api_key, valida) for valida in chaves
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de API inválida."
        )
