"""Metadados da extração: proveniência, confiança e problemas.

Este bloco é o que torna o serviço usável por quem pré-preenche formulário:
sem ele, o consumidor não sabe em qual campo pode confiar sem revisão humana.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Problema(BaseModel):
    """Achado da validação. ``codigo`` é estável; ``mensagem`` pode mudar."""

    model_config = ConfigDict(extra="forbid")

    severidade: Literal["erro", "aviso"]
    codigo: str
    campo: str | None = None
    mensagem: str


class CampoExtraido(BaseModel):
    """Confiança e proveniência de um campo.

    ``origem`` identifica de onde o valor saiu, por exemplo
    ``xml:/nfeProc/NFe/infNFe/emit/CNPJ``, ``regex:ancora_chave`` ou
    ``ocr:bbox=120,340,480,362``. É o que permite diagnosticar um emissor novo
    sem adivinhar.
    """

    model_config = ConfigDict(extra="forbid")

    confianca: float = Field(ge=0.0, le=1.0)
    origem: str


class ArquivoOrigem(BaseModel):
    """Identificação do arquivo recebido."""

    model_config = ConfigDict(extra="forbid")

    nome: str
    mime: str
    bytes: int
    sha256: str


class Extracao(BaseModel):
    """Como a nota foi lida."""

    model_config = ConfigDict(extra="forbid")

    dialeto: str
    motor: str
    arquivo: ArquivoOrigem
    confianca_global: float = Field(ge=0.0, le=1.0)
    requer_revisao: bool
    duracao_ms: int
    campos: dict[str, CampoExtraido] = Field(default_factory=dict)
    problemas: list[Problema] = Field(default_factory=list)
