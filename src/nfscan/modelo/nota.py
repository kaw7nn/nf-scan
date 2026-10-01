"""Modelo canônico da nota fiscal.

Todo campo é opcional por princípio: formato de origem diferente traz
subconjunto diferente. Ausência vira ``None`` e é informação para o
consumidor, não erro.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from nfscan.modelo.extracao import Extracao
from nfscan.modelo.tipos import VERSAO_SCHEMA, Dinheiro, Quantidade

TipoDocumento = Literal["nfe", "nfce", "nfse", "cupom", "desconhecido"]
Finalidade = Literal["normal", "complementar", "ajuste", "devolucao", "desconhecida"]
Situacao = Literal["autorizada", "cancelada", "denegada", "desconhecida"]
RegimeTributario = Literal["simples", "presumido", "real", "mei", "desconhecido"]
ModalidadeFrete = Literal["emitente", "destinatario", "terceiros", "sem_frete", "desconhecida"]
TipoPagamento = Literal["dinheiro", "pix", "credito", "debito", "boleto", "prazo", "outro"]


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Endereco(Base):
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    codigo_municipio_ibge: str | None = None
    uf: str | None = None
    cep: str | None = None
    pais: str | None = None
    telefone: str | None = None


class Participante(Base):
    """Emitente ou destinatário."""

    cnpj: str | None = None
    cpf: str | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    inscricao_estadual: str | None = None
    inscricao_municipal: str | None = None
    regime_tributario: RegimeTributario = "desconhecido"
    endereco: Endereco | None = None


class ImpostoItem(Base):
    cst: str | None = None
    base: Dinheiro | None = None
    aliquota: Dinheiro | None = None
    valor: Dinheiro | None = None


class Impostos(Base):
    icms: ImpostoItem | None = None
    ipi: ImpostoItem | None = None
    pis: ImpostoItem | None = None
    cofins: ImpostoItem | None = None
    iss: ImpostoItem | None = None


class Item(Base):
    ordem: int
    codigo: str | None = None
    descricao: str | None = None
    ncm: str | None = None
    cest: str | None = None
    cfop: str | None = None
    unidade: str | None = None
    quantidade: Quantidade | None = None
    valor_unitario: Dinheiro | None = None
    valor_total: Dinheiro | None = None
    desconto: Dinheiro | None = None
    frete: Dinheiro | None = None
    impostos: Impostos | None = None


class Retencoes(Base):
    pis: Dinheiro | None = None
    cofins: Dinheiro | None = None
    csll: Dinheiro | None = None
    irrf: Dinheiro | None = None
    inss: Dinheiro | None = None
    iss: Dinheiro | None = None


class Tributos(Base):
    icms_base: Dinheiro | None = None
    icms_valor: Dinheiro | None = None
    iss_valor: Dinheiro | None = None
    tributos_aproximados: Dinheiro | None = None
    retencoes: Retencoes | None = None


class Totais(Base):
    valor_produtos: Dinheiro | None = None
    valor_servicos: Dinheiro | None = None
    desconto: Dinheiro | None = None
    frete: Dinheiro | None = None
    seguro: Dinheiro | None = None
    outras_despesas: Dinheiro | None = None
    valor_total: Dinheiro | None = None
    tributos: Tributos | None = None


class FormaPagamento(Base):
    tipo: TipoPagamento = "outro"
    valor: Dinheiro | None = None


class Parcela(Base):
    numero: int | None = None
    vencimento: date | None = None
    valor: Dinheiro | None = None


class Pagamento(Base):
    formas: list[FormaPagamento] = Field(default_factory=list)
    parcelas: list[Parcela] = Field(default_factory=list)


class Volume(Base):
    quantidade: Quantidade | None = None
    especie: str | None = None
    peso_liquido: Quantidade | None = None
    peso_bruto: Quantidade | None = None


class Transporte(Base):
    modalidade_frete: ModalidadeFrete = "desconhecida"
    transportadora: Participante | None = None
    volumes: list[Volume] = Field(default_factory=list)


class Documento(Base):
    tipo: TipoDocumento = "desconhecido"
    modelo: str | None = None
    chave_acesso: str | None = None
    numero: str | None = None
    serie: str | None = None
    data_emissao: datetime | None = None
    data_competencia: date | None = None
    natureza_operacao: str | None = None
    finalidade: Finalidade = "desconhecida"
    situacao: Situacao = "desconhecida"
    protocolo_autorizacao: str | None = None
    municipio_prestacao: str | None = None


class NotaFiscal(Base):
    """Documento fiscal padronizado."""

    versao_schema: str = VERSAO_SCHEMA
    documento: Documento
    emitente: Participante | None = None
    destinatario: Participante | None = None
    itens: list[Item] = Field(default_factory=list)
    totais: Totais | None = None
    pagamento: Pagamento | None = None
    transporte: Transporte | None = None
    informacoes_adicionais: str | None = None
    extracao: Extracao
