"""Limpeza de texto vindo de PDF e OCR."""

from nfscan.dominio.textos import limpar_texto


def test_colapsa_espacos_e_remove_bordas() -> None:
    assert limpar_texto("  FORNECEDOR   DE   MATERIAIS  ") == "FORNECEDOR DE MATERIAIS"


def test_remove_quebras_de_linha() -> None:
    assert limpar_texto("FORNECEDOR\nDE\tMATERIAIS") == "FORNECEDOR DE MATERIAIS"


def test_texto_vazio_vira_none() -> None:
    assert limpar_texto("") is None
    assert limpar_texto("   ") is None
    assert limpar_texto(None) is None
