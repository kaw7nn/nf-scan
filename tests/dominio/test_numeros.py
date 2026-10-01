"""Conversão de números e datas vindos de XML, PDF e OCR."""

from datetime import date, datetime
from decimal import Decimal

from nfscan.dominio.numeros import para_data, para_data_hora, para_decimal


def test_decimal_de_formato_xml() -> None:
    assert para_decimal("1234.56") == Decimal("1234.56")


def test_decimal_de_inteiro_e_none() -> None:
    assert para_decimal(10) == Decimal("10")
    assert para_decimal(None) is None
    assert para_decimal("") is None
    assert para_decimal("   ") is None


def test_decimal_arredonda_para_as_casas_pedidas() -> None:
    assert para_decimal("1234.567", casas=2) == Decimal("1234.57")
    assert para_decimal("1234.561", casas=2) == Decimal("1234.56")


def test_decimal_de_valor_nao_numerico_e_none() -> None:
    assert para_decimal("R$ sem valor") is None
    assert para_decimal("--") is None


def test_decimal_aceita_negativo() -> None:
    assert para_decimal("-150.00") == Decimal("-150.00")
    assert para_decimal("(150,00)") == Decimal("-150.00")


# --- Foco de Revisão 2: formato brasileiro impresso no DANFE ---


def test_decimal_de_formato_brasileiro_com_milhar() -> None:
    assert para_decimal("1.234,56") == Decimal("1234.56")


def test_decimal_de_formato_brasileiro_com_varios_milhares() -> None:
    assert para_decimal("1.234.567,89") == Decimal("1234567.89")


def test_decimal_de_formato_brasileiro_sem_milhar() -> None:
    assert para_decimal("1234,56") == Decimal("1234.56")


def test_decimal_com_prefixo_de_moeda_e_espacos() -> None:
    assert para_decimal(" R$ 1.234,56 ") == Decimal("1234.56")


def test_decimal_com_ponto_de_milhar_e_sem_decimais() -> None:
    # Parte inteira de 1 a 3 dígitos e grupo de exatamente 3 à direita: milhar.
    assert para_decimal("1.234") == Decimal("1234")


def test_decimal_com_ponto_decimal_e_duas_casas_nao_e_milhar() -> None:
    assert para_decimal("1234.56") == Decimal("1234.56")


def test_decimal_com_parte_inteira_longa_nao_e_milhar() -> None:
    # "1234" não pode ser um grupo de milhar, então o ponto é decimal.
    assert para_decimal("1234.567") == Decimal("1234.567")


# --- A ambiguidade do ponto: quem chama sabe o formato de origem ---


def test_decimal_em_formato_xml_nunca_trata_ponto_como_milhar() -> None:
    # No XML da NF-e o ponto é sempre decimal. vUnCom aceita 3 decimais, e
    # adivinhar "milhar" aqui multiplicaria o preço unitário por mil.
    assert para_decimal("38.500", formato="ponto_decimal") == Decimal("38.500")
    assert para_decimal("1.234", formato="ponto_decimal") == Decimal("1.234")


def test_decimal_em_formato_xml_ignora_virgula_como_decimal() -> None:
    assert para_decimal("1234.5678", formato="ponto_decimal") == Decimal("1234.5678")


def test_decimal_auto_e_o_padrao() -> None:
    assert para_decimal("1.234") == para_decimal("1.234", formato="auto")


def test_data_hora_iso_com_fuso() -> None:
    lido = para_data_hora("2026-09-14T10:32:00-03:00")
    assert lido == datetime.fromisoformat("2026-09-14T10:32:00-03:00")


def test_data_hora_iso_sem_fuso() -> None:
    assert para_data_hora("2026-09-14T10:32:00") == datetime(2026, 9, 14, 10, 32)


def test_data_hora_formato_brasileiro() -> None:
    assert para_data_hora("14/09/2026 10:32:00") == datetime(2026, 9, 14, 10, 32)
    assert para_data_hora("14/09/2026") == datetime(2026, 9, 14, 0, 0)


def test_data_hora_invalida_e_none() -> None:
    assert para_data_hora("32/13/2026") is None
    assert para_data_hora(None) is None
    assert para_data_hora("sem data") is None


def test_data_simples() -> None:
    assert para_data("2026-09-14") == date(2026, 9, 14)
    assert para_data("14/09/2026") == date(2026, 9, 14)
    assert para_data(None) is None
