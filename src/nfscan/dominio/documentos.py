"""Validação e normalização de CNPJ e CPF.

Os dois usam dígito verificador mod-11, com pesos diferentes. Sequências de
dígitos repetidos passam no cálculo mas não existem na prática, então são
rejeitadas explicitamente.
"""

from __future__ import annotations

import re

_NAO_DIGITO = re.compile(r"\D")

_PESOS_CNPJ_PRIMEIRO = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_CNPJ_SEGUNDO = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def limpar_digitos(valor: str | None) -> str:
    """Remove tudo que não é dígito."""
    return _NAO_DIGITO.sub("", valor or "")


def _dv_mod11(digitos: str, pesos: tuple[int, ...]) -> str:
    soma = sum(int(digito) * peso for digito, peso in zip(digitos, pesos, strict=True))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(valor: str | None) -> bool:
    """Informa se o CNPJ tem 14 dígitos e DVs corretos."""
    digitos = limpar_digitos(valor)
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    primeiro = _dv_mod11(digitos[:12], _PESOS_CNPJ_PRIMEIRO)
    segundo = _dv_mod11(digitos[:12] + primeiro, _PESOS_CNPJ_SEGUNDO)
    return digitos[12:] == primeiro + segundo


def cpf_valido(valor: str | None) -> bool:
    """Informa se o CPF tem 11 dígitos e DVs corretos."""
    digitos = limpar_digitos(valor)
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    primeiro = _dv_mod11(digitos[:9], tuple(range(10, 1, -1)))
    segundo = _dv_mod11(digitos[:9] + primeiro, tuple(range(11, 1, -1)))
    return digitos[9:] == primeiro + segundo


def normalizar_cnpj_cpf(valor: str | None) -> tuple[str | None, str | None]:
    """Classifica o identificador em ``(cnpj, cpf)``.

    Devolve ``(None, None)`` quando o valor não é um dos dois — nunca
    adivinha, porque campo inventado é pior que campo ausente.
    """
    digitos = limpar_digitos(valor)
    if cnpj_valido(digitos):
        return digitos, None
    if cpf_valido(digitos):
        return None, digitos
    return None, None
