"""Registro de extratores por dialeto.

Acrescentar suporte a um formato novo é registrar um extrator; o pipeline não
muda. Isso é o que mantém o núcleo estável enquanto a cobertura cresce.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nfscan.detect.dialeto import Dialeto
from nfscan.modelo import ArquivoOrigem, NotaFiscal


@runtime_checkable
class Extrator(Protocol):
    """Contrato de um extrator."""

    motor: str
    dialetos: tuple[Dialeto, ...]

    def extrair(self, conteudo: bytes, arquivo: ArquivoOrigem) -> NotaFiscal: ...


_REGISTRO: dict[Dialeto, Extrator] = {}


def registrar(extrator: Extrator) -> None:
    """Associa o extrator a todos os dialetos que ele declara atender."""
    for dialeto in extrator.dialetos:
        _REGISTRO[dialeto] = extrator


def obter(dialeto: Dialeto) -> Extrator | None:
    """Devolve o extrator do dialeto, ou ``None``."""
    return _REGISTRO.get(dialeto)


def dialetos_suportados() -> tuple[Dialeto, ...]:
    """Dialetos com extrator registrado, para a rota ``/v1/dialetos``."""
    return tuple(_REGISTRO)
