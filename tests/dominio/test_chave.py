"""Chave de acesso de 44 dígitos: estrutura e dígito verificador mod-11."""

import pytest

from nfscan.dominio.chave import (
    ChaveInvalida,
    calcular_dv,
    chave_valida,
    extrair_chave,
    parse_chave,
)

# NF-e modelo 55, SP (35), set/2026, CNPJ 12345678000195, série 1, número 1234.
# Os 43 primeiros dígitos; o DV é calculado no teste para não fixar número mágico.
BASE_43 = "3526" + "09" + "12345678000195" + "55" + "001" + "000001234" + "1" + "12345678"
CHAVE = BASE_43 + calcular_dv(BASE_43)


def test_base_tem_43_digitos() -> None:
    assert len(BASE_43) == 43


def test_dv_e_um_digito() -> None:
    dv = calcular_dv(BASE_43)
    assert len(dv) == 1
    assert dv.isdigit()


def test_chave_com_dv_correto_e_valida() -> None:
    assert chave_valida(CHAVE) is True


def test_chave_com_dv_trocado_e_invalida() -> None:
    dv_errado = str((int(CHAVE[-1]) + 1) % 10)
    assert chave_valida(BASE_43 + dv_errado) is False


def test_chave_com_tamanho_errado_e_invalida() -> None:
    assert chave_valida(CHAVE[:-1]) is False
    assert chave_valida(CHAVE + "0") is False


def test_chave_nao_numerica_e_invalida() -> None:
    assert chave_valida("x" * 44) is False


def test_parse_decompoe_os_campos() -> None:
    chave = parse_chave(CHAVE)
    assert chave.valor == CHAVE
    assert chave.codigo_uf == "35"
    assert chave.sigla_uf == "SP"
    assert chave.ano == 2026
    assert chave.mes == 9
    assert chave.cnpj_emitente == "12345678000195"
    assert chave.modelo == "55"
    assert chave.serie == "001"
    assert chave.numero == "000001234"
    assert chave.tipo_emissao == "1"
    assert chave.codigo_numerico == "12345678"
    assert chave.dv == CHAVE[-1]


def test_parse_de_chave_invalida_levanta() -> None:
    with pytest.raises(ChaveInvalida):
        parse_chave("123")


def test_parse_aceita_separadores() -> None:
    espacada = " ".join(CHAVE[i : i + 4] for i in range(0, 44, 4))
    assert parse_chave(espacada).valor == CHAVE


def test_uf_desconhecida_vira_sigla_none() -> None:
    base = "99" + BASE_43[2:]
    chave = parse_chave(base + calcular_dv(base))
    assert chave.sigla_uf is None


# --- Foco de Revisão 1: chave impressa com separadores em texto livre ---


def test_extrai_chave_de_texto_corrido() -> None:
    texto = f"DANFE\nCHAVE DE ACESSO\n{CHAVE}\nConsulta em www.nfe.fazenda.gov.br"
    assert extrair_chave(texto).valor == CHAVE


def test_extrai_chave_quebrada_em_grupos_de_quatro() -> None:
    grupos = " ".join(CHAVE[i : i + 4] for i in range(0, 44, 4))
    assert extrair_chave(f"Chave de acesso\n{grupos}\n").valor == CHAVE


def test_extrai_chave_quebrada_por_newline_no_meio() -> None:
    texto = f"CHAVE\n{CHAVE[:20]}\n{CHAVE[20:]}\nPROTOCOLO"
    assert extrair_chave(texto).valor == CHAVE


def test_extrai_chave_com_pontos_como_separador() -> None:
    pontuada = ".".join(CHAVE[i : i + 4] for i in range(0, 44, 4))
    assert extrair_chave(pontuada).valor == CHAVE


def test_ignora_sequencia_de_44_digitos_com_dv_errado() -> None:
    dv_errado = str((int(CHAVE[-1]) + 1) % 10)
    assert extrair_chave(f"ruido {BASE_43 + dv_errado} ruido") is None


def test_texto_sem_chave_retorna_none() -> None:
    assert extrair_chave("NOTA FISCAL DE SERVICOS\nValor total R$ 1.234,56") is None


def test_escolhe_a_chave_valida_entre_candidatas() -> None:
    dv_errado = str((int(CHAVE[-1]) + 1) % 10)
    texto = f"{BASE_43 + dv_errado}\noutra linha\n{CHAVE}"
    assert extrair_chave(texto).valor == CHAVE
