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
