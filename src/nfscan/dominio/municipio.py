"""Coerência do código IBGE de município com a UF.

Os dois primeiros dos sete dígitos são o código da UF. Devolver ``None`` em
vez de ``False`` quando falta informação é deliberado: o chamador não pode
confundir "não sei" com "está errado".
"""

from __future__ import annotations

from nfscan.dominio.uf import codigo_por_sigla

TAMANHO_CODIGO_IBGE = 7


def codigo_ibge_coerente(codigo: str | None, uf: str | None) -> bool | None:
    """Informa se o código de município casa com a UF."""
    codigo_uf = codigo_por_sigla(uf)
    if codigo is None or codigo_uf is None:
        return None
    limpo = codigo.strip()
    if len(limpo) != TAMANHO_CODIGO_IBGE or not limpo.isdigit():
        return False
    return limpo[:2] == codigo_uf
