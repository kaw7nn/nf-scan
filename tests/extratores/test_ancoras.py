"""Motor de âncoras sobre texto de DANFE."""

from pathlib import Path

from nfscan.extratores.ancoras.motor import aplicar, carregar_perfis, escolher_perfil


def _texto() -> str:
    caminho = Path(__file__).parents[1] / "fixtures" / "danfe_texto_simples.txt"
    return caminho.read_text(encoding="utf-8")


def test_carrega_pelo_menos_o_perfil_generico() -> None:
    assert any(perfil.nome == "generico" for perfil in carregar_perfis())


def test_escolhe_o_generico_quando_nada_mais_casa() -> None:
    assert escolher_perfil("texto sem marcador algum", carregar_perfis()).nome == "generico"


def test_aplica_e_encontra_cnpj_do_emitente() -> None:
    valores = aplicar(escolher_perfil(_texto(), carregar_perfis()), _texto())
    limpo = valores["emitente.cnpj"].translate(str.maketrans("", "", "./- "))
    assert limpo == "11222333000181"


def test_aplica_e_encontra_total_da_nota() -> None:
    valores = aplicar(escolher_perfil(_texto(), carregar_perfis()), _texto())
    assert valores["totais.valor_total"] == "5.200,00"


def test_aplica_e_encontra_total_dos_produtos_e_nao_o_do_icms() -> None:
    valores = aplicar(escolher_perfil(_texto(), carregar_perfis()), _texto())
    assert valores["totais.valor_produtos"] == "5.050,00"
    assert valores["totais.frete"] == "150,00"


def test_campo_ausente_nao_aparece_no_resultado() -> None:
    valores = aplicar(escolher_perfil("DANFE vazio", carregar_perfis()), "DANFE vazio")
    assert "totais.valor_total" not in valores


# --- A âncora de coluna não pode atravessar a fronteira da tabela ---

TABELAS = """\
BASE DE CALCULO DO ICMS      VALOR DO ICMS      VALOR TOTAL DOS PRODUTOS
         ilegivel                 ilegivel              ilegivel
VALOR DO FRETE   VALOR DO SEGURO   DESCONTO   VALOR TOTAL DA NOTA
      150,00            0,00         0,00           5.200,00
"""


def test_nao_puxa_valor_da_tabela_seguinte() -> None:
    from nfscan.extratores.ancoras.motor import valor_na_coluna

    # A linha de valores da primeira tabela é ilegível. Descer mais faria o
    # rótulo do ICMS pegar um número da tabela de baixo: valor plausível e
    # errado, pior que ausente.
    assert valor_na_coluna(TABELAS, "VALOR DO ICMS") is None
    assert valor_na_coluna(TABELAS, "BASE DE CALCULO DO ICMS") is None
    # A segunda tabela, com valores legíveis, continua funcionando.
    assert valor_na_coluna(TABELAS, "VALOR TOTAL DA NOTA") == "5.200,00"
    assert valor_na_coluna(TABELAS, "VALOR DO FRETE") == "150,00"


def test_tolera_o_espaco_que_o_ocr_insere_apos_a_virgula() -> None:
    from nfscan.extratores.ancoras.motor import valor_na_coluna

    bruto = "VALOR TOTAL DA NOTA\n     5.050, 00\n"
    assert valor_na_coluna(bruto, "VALOR TOTAL DA NOTA") == "5.050, 00"


def test_aplicar_normaliza_o_espaco_pos_virgula() -> None:
    perfis = carregar_perfis()
    bruto = "VALOR TOTAL DA NOTA\n     5.050, 00\n"
    assert aplicar(escolher_perfil(bruto, perfis), bruto)["totais.valor_total"] == "5.050,00"
