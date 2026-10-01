"""Coerência entre código IBGE de município e UF."""

from nfscan.dominio.municipio import codigo_ibge_coerente


def test_codigo_coerente_com_a_uf() -> None:
    assert codigo_ibge_coerente("3550308", "SP") is True


def test_codigo_incoerente_com_a_uf() -> None:
    assert codigo_ibge_coerente("3550308", "RJ") is False


def test_codigo_com_tamanho_errado_e_incoerente() -> None:
    assert codigo_ibge_coerente("355030", "SP") is False


def test_sem_informacao_suficiente_nao_julga() -> None:
    assert codigo_ibge_coerente(None, "SP") is None
    assert codigo_ibge_coerente("3550308", None) is None
    assert codigo_ibge_coerente("3550308", "ZZ") is None
