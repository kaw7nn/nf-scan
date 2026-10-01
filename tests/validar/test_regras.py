"""Regras cruzadas de validação."""

from datetime import datetime
from decimal import Decimal

from nfscan.modelo import (
    ArquivoOrigem,
    Documento,
    Extracao,
    Item,
    NotaFiscal,
    Participante,
    Totais,
)
from nfscan.validar.regras import validar


def _nota(**kwargs) -> NotaFiscal:
    base = dict(
        documento=Documento(tipo="nfe"),
        emitente=Participante(cnpj="11222333000181", razao_social="F Ltda"),
        extracao=Extracao(
            dialeto="nfe_4.00",
            motor="nfelib",
            arquivo=ArquivoOrigem(
                nome="n.xml", mime="application/xml", bytes=1, sha256="a" * 64
            ),
            confianca_global=1.0,
            requer_revisao=False,
            duracao_ms=1,
        ),
    )
    base.update(kwargs)
    return NotaFiscal(**base)


def _codigos(nota: NotaFiscal) -> set[str]:
    return {problema.codigo for problema in validar(nota)}


def test_nota_coerente_nao_gera_problema() -> None:
    nota = _nota(
        itens=[Item(ordem=1, valor_total=Decimal("100.00"))],
        totais=Totais(
            valor_produtos=Decimal("100.00"),
            frete=Decimal("0.00"),
            desconto=Decimal("0.00"),
            valor_total=Decimal("100.00"),
        ),
    )
    assert validar(nota) == []


def test_emitente_ausente_e_erro() -> None:
    assert "EMITENTE_AUSENTE" in _codigos(_nota(emitente=None))


def test_cnpj_do_emitente_invalido() -> None:
    assert "CNPJ_EMITENTE_INVALIDO" in _codigos(
        _nota(emitente=Participante(cnpj="12345678901234"))
    )


def test_cnpj_do_destinatario_invalido() -> None:
    assert "CNPJ_DESTINATARIO_INVALIDO" in _codigos(
        _nota(destinatario=Participante(cnpj="12345678901234"))
    )


def test_soma_dos_itens_divergente() -> None:
    nota = _nota(
        itens=[Item(ordem=1, valor_total=Decimal("90.00"))],
        totais=Totais(valor_produtos=Decimal("100.00"), valor_total=Decimal("100.00")),
    )
    assert "SOMA_ITENS_DIVERGENTE" in _codigos(nota)


def test_soma_dos_itens_tolera_um_centavo_de_arredondamento() -> None:
    nota = _nota(
        itens=[Item(ordem=1, valor_total=Decimal("99.99"))],
        totais=Totais(valor_produtos=Decimal("100.00"), valor_total=Decimal("100.00")),
    )
    assert "SOMA_ITENS_DIVERGENTE" not in _codigos(nota)


def test_total_do_documento_divergente() -> None:
    nota = _nota(
        totais=Totais(
            valor_produtos=Decimal("100.00"),
            frete=Decimal("10.00"),
            desconto=Decimal("0.00"),
            valor_total=Decimal("150.00"),
        )
    )
    assert "TOTAL_DIVERGENTE" in _codigos(nota)


def test_chave_com_dv_invalido() -> None:
    nota = _nota(documento=Documento(tipo="nfe", chave_acesso="3" * 44))
    assert "CHAVE_DV_INVALIDO" in _codigos(nota)


def test_data_incoerente_com_a_chave() -> None:
    from nfscan.dominio.chave import calcular_dv

    base = "3526" + "09" + "11222333000181" + "55" + "001" + "000001234" + "1" + "12345678"
    chave = base + calcular_dv(base)
    nota = _nota(
        documento=Documento(tipo="nfe", chave_acesso=chave, data_emissao=datetime(2025, 3, 1))
    )
    assert "DATA_INCOERENTE_COM_CHAVE" in _codigos(nota)


def test_valor_total_ausente_e_aviso() -> None:
    problemas = {p.codigo: p for p in validar(_nota(totais=Totais()))}
    assert problemas["VALOR_TOTAL_AUSENTE"].severidade == "aviso"


# --- Foco de Revisão 5: devolução com valores negativos ---


def test_devolucao_com_valores_negativos_nao_gera_falso_problema() -> None:
    nota = _nota(
        documento=Documento(tipo="nfe", finalidade="devolucao"),
        itens=[Item(ordem=1, valor_total=Decimal("-500.00"))],
        totais=Totais(
            valor_produtos=Decimal("-500.00"),
            frete=Decimal("0.00"),
            desconto=Decimal("0.00"),
            valor_total=Decimal("-500.00"),
        ),
    )
    assert validar(nota) == []


def test_desconto_maior_que_produtos_nao_quebra() -> None:
    nota = _nota(
        itens=[Item(ordem=1, valor_total=Decimal("100.00"))],
        totais=Totais(
            valor_produtos=Decimal("100.00"),
            desconto=Decimal("150.00"),
            frete=Decimal("0.00"),
            valor_total=Decimal("-50.00"),
        ),
    )
    assert "TOTAL_DIVERGENTE" not in _codigos(nota)


def test_total_zerado_nao_divide_por_zero() -> None:
    nota = _nota(
        totais=Totais(
            valor_produtos=Decimal("0.00"),
            frete=Decimal("0.00"),
            desconto=Decimal("0.00"),
            valor_total=Decimal("0.00"),
        )
    )
    assert "TOTAL_DIVERGENTE" not in _codigos(nota)
