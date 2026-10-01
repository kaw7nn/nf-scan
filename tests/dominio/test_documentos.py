"""CNPJ e CPF: dígitos verificadores e normalização."""

from nfscan.dominio.documentos import (
    cnpj_valido,
    cpf_valido,
    limpar_digitos,
    normalizar_cnpj_cpf,
)

CNPJ_OK = "11222333000181"
CPF_OK = "52998224725"


def test_limpar_digitos_remove_mascara() -> None:
    assert limpar_digitos("11.222.333/0001-81") == CNPJ_OK
    assert limpar_digitos(None) == ""


def test_cnpj_valido() -> None:
    assert cnpj_valido(CNPJ_OK) is True
    assert cnpj_valido("11.222.333/0001-81") is True


def test_cnpj_com_dv_errado() -> None:
    assert cnpj_valido(CNPJ_OK[:-1] + "0") is False


def test_cnpj_com_tamanho_errado() -> None:
    assert cnpj_valido("1122233300018") is False
    assert cnpj_valido("") is False
    assert cnpj_valido(None) is False


def test_cnpj_com_todos_digitos_iguais_e_invalido() -> None:
    assert cnpj_valido("00000000000000") is False
    assert cnpj_valido("11111111111111") is False


def test_cpf_valido() -> None:
    assert cpf_valido(CPF_OK) is True
    assert cpf_valido("529.982.247-25") is True


def test_cpf_com_dv_errado() -> None:
    assert cpf_valido(CPF_OK[:-1] + "0") is False


def test_cpf_com_todos_digitos_iguais_e_invalido() -> None:
    assert cpf_valido("11111111111") is False


def test_normalizar_identifica_cnpj() -> None:
    assert normalizar_cnpj_cpf("11.222.333/0001-81") == (CNPJ_OK, None)


def test_normalizar_identifica_cpf() -> None:
    assert normalizar_cnpj_cpf("529.982.247-25") == (None, CPF_OK)


def test_normalizar_rejeita_invalido() -> None:
    assert normalizar_cnpj_cpf("12345678901234") == (None, None)
    assert normalizar_cnpj_cpf(None) == (None, None)
