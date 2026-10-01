"""Coletor de confiança e proveniência."""

from nfscan.modelo import Problema
from nfscan.modelo.coletor import CONFIANCA, Coletor, requer_revisao


def test_registrar_devolve_o_valor_intacto() -> None:
    coletor = Coletor(CONFIANCA["xml_oficial"])
    valor = coletor.registrar("emitente.cnpj", "11222333000181", "xml:/emit/CNPJ")
    assert valor == "11222333000181"


def test_registrar_grava_confianca_base_e_origem() -> None:
    coletor = Coletor(CONFIANCA["xml_oficial"])
    coletor.registrar("emitente.cnpj", "11222333000181", "xml:/emit/CNPJ")
    campo = coletor.campos["emitente.cnpj"]
    assert campo.confianca == 1.0
    assert campo.origem == "xml:/emit/CNPJ"


def test_confianca_explicita_sobrepoe_a_base() -> None:
    coletor = Coletor(CONFIANCA["pdf_ancora"])
    coletor.registrar(
        "documento.chave_acesso", "x", "regex:chave", confianca=CONFIANCA["pdf_chave"]
    )
    assert coletor.campos["documento.chave_acesso"].confianca == 0.75


def test_valor_none_nao_e_registrado() -> None:
    coletor = Coletor(CONFIANCA["xml_oficial"])
    assert coletor.registrar("emitente.cnpj", None, "xml:/emit/CNPJ") is None
    assert "emitente.cnpj" not in coletor.campos


def test_confianca_global_e_o_elo_mais_fraco() -> None:
    # A média permitia que uma extração mais completa reportasse confiança
    # maior que uma extração parcial, invertendo o sinal.
    coletor = Coletor(CONFIANCA["pdf_ancora"])
    coletor.registrar("a", "x", "o", confianca=1.0)
    coletor.registrar("b", "y", "o", confianca=0.5)
    assert coletor.confianca_global() == 0.5


def test_confianca_global_nunca_sobe_com_campo_novo() -> None:
    coletor = Coletor(CONFIANCA["pdf_ancora"])
    coletor.registrar("a", "x", "o", confianca=1.0)
    antes = coletor.confianca_global()
    coletor.registrar("b", "y", "o", confianca=0.5)
    assert coletor.confianca_global() <= antes


def test_confianca_global_sem_campos_e_zero() -> None:
    assert Coletor(CONFIANCA["xml_oficial"]).confianca_global() == 0.0


def test_requer_revisao_abaixo_do_limite() -> None:
    assert requer_revisao(0.84, []) is True
    assert requer_revisao(0.85, []) is False


def test_requer_revisao_com_problema_de_erro() -> None:
    erro = Problema(severidade="erro", codigo="CNPJ_INVALIDO", mensagem="x")
    aviso = Problema(severidade="aviso", codigo="TOTAL_DIVERGENTE", mensagem="x")
    assert requer_revisao(1.0, [erro]) is True
    assert requer_revisao(1.0, [aviso]) is False
