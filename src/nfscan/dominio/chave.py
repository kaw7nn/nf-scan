"""Chave de acesso de 44 dígitos da NF-e/NFC-e.

Layout, da esquerda para a direita:

    2  código da UF (IBGE)
    4  AAMM da emissão
    14 CNPJ do emitente
    2  modelo (55 = NF-e, 65 = NFC-e)
    3  série
    9  número
    1  tipo de emissão
    8  código numérico
    1  dígito verificador (mod-11)

A chave é auto-descritiva: achá-la em um PDF ou em uma saída de OCR entrega
sete campos sem depender do layout, e o DV confirma a leitura.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nfscan.dominio.uf import sigla_por_codigo

TAMANHO = 44
_PESOS = (2, 3, 4, 5, 6, 7, 8, 9)

# Candidata: 44 dígitos admitindo espaço, ponto, hífen ou quebra de linha
# entre eles, porque emissores imprimem a chave em grupos de quatro e o
# pdftotext insere quebra de linha.
_CANDIDATA = re.compile(r"(?:\d[\s.\-]{0,3}){43}\d")
_NAO_DIGITO = re.compile(r"\D")


class ChaveInvalida(ValueError):
    """A string não é uma chave de acesso válida."""


@dataclass(frozen=True, slots=True)
class ChaveAcesso:
    """Chave de acesso já validada e decomposta."""

    valor: str
    codigo_uf: str
    sigla_uf: str | None
    ano: int
    mes: int
    cnpj_emitente: str
    modelo: str
    serie: str
    numero: str
    tipo_emissao: str
    codigo_numerico: str
    dv: str


def calcular_dv(primeiros_43: str) -> str:
    """Calcula o dígito verificador mod-11 dos 43 primeiros dígitos.

    Pesos 2 a 9 ciclando da direita para a esquerda. Resto 0 ou 1 resulta em
    dígito 0.
    """
    digitos = _NAO_DIGITO.sub("", primeiros_43)
    if len(digitos) != TAMANHO - 1:
        raise ChaveInvalida(
            f"esperados {TAMANHO - 1} dígitos para calcular o DV, recebidos {len(digitos)}"
        )
    soma = sum(
        int(digito) * _PESOS[indice % len(_PESOS)]
        for indice, digito in enumerate(reversed(digitos))
    )
    resto = soma % 11
    return "0" if resto in (0, 1) else str(11 - resto)


def chave_valida(valor: str) -> bool:
    """Informa se a string carrega 44 dígitos com DV correto."""
    digitos = _NAO_DIGITO.sub("", valor or "")
    if len(digitos) != TAMANHO:
        return False
    return calcular_dv(digitos[:-1]) == digitos[-1]


def parse_chave(valor: str) -> ChaveAcesso:
    """Valida e decompõe a chave, tolerando separadores.

    Levanta :class:`ChaveInvalida` se o tamanho ou o DV não fecharem.
    """
    digitos = _NAO_DIGITO.sub("", valor or "")
    if len(digitos) != TAMANHO:
        raise ChaveInvalida(f"a chave precisa ter {TAMANHO} dígitos, recebidos {len(digitos)}")
    if calcular_dv(digitos[:-1]) != digitos[-1]:
        raise ChaveInvalida("dígito verificador da chave não confere")

    codigo_uf = digitos[0:2]
    return ChaveAcesso(
        valor=digitos,
        codigo_uf=codigo_uf,
        sigla_uf=sigla_por_codigo(codigo_uf),
        ano=2000 + int(digitos[2:4]),
        mes=int(digitos[4:6]),
        cnpj_emitente=digitos[6:20],
        modelo=digitos[20:22],
        serie=digitos[22:25],
        numero=digitos[25:34],
        tipo_emissao=digitos[34:35],
        codigo_numerico=digitos[35:43],
        dv=digitos[43],
    )


def extrair_chave(texto: str) -> ChaveAcesso | None:
    """Procura no texto a primeira sequência de 44 dígitos com DV válido.

    Tolera separadores entre os dígitos. Devolve ``None`` quando nenhuma
    candidata passa no DV — assim ruído numérico não é confundido com chave.
    """
    for achado in _CANDIDATA.finditer(texto or ""):
        try:
            return parse_chave(achado.group())
        except ChaveInvalida:
            continue
    return None
