"""Utilitários compartilhados pelos testes."""

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest

from nfscan.modelo import ArquivoOrigem

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ler_fixture() -> Callable[[str, str], tuple[bytes, ArquivoOrigem]]:
    """Devolve ``(bytes, ArquivoOrigem)`` de um arquivo em tests/fixtures."""

    def _ler(nome: str, mime: str) -> tuple[bytes, ArquivoOrigem]:
        conteudo = (FIXTURES / nome).read_bytes()
        arquivo = ArquivoOrigem(
            nome=nome,
            mime=mime,
            bytes=len(conteudo),
            sha256=hashlib.sha256(conteudo).hexdigest(),
        )
        return conteudo, arquivo

    return _ler
