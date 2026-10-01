"""Log estruturado sem vazamento de dado fiscal."""

import json
import logging

from nfscan.log import registrar_leitura
from nfscan.pipeline import parse


def test_log_registra_a_metrica_da_leitura(ler_fixture, caplog) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    nota = parse(conteudo, "nfe.xml")
    with caplog.at_level(logging.INFO, logger="nfscan"):
        registrar_leitura(nota)
    registro = json.loads(caplog.records[-1].getMessage())
    assert registro["evento"] == "leitura"
    assert registro["dialeto"] == "nfe_4.00"
    assert registro["confianca"] == 1.0
    assert registro["requer_revisao"] is False
    assert registro["sha256"] == nota.extracao.arquivo.sha256
    assert registro["problemas"] == []


def test_log_nao_vaza_dado_da_nota(ler_fixture, caplog) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    nota = parse(conteudo, "nfe.xml")
    with caplog.at_level(logging.INFO, logger="nfscan"):
        registrar_leitura(nota)
    linha = caplog.records[-1].getMessage()
    # O serviço lê documento fiscal de terceiros: a linha de log registra
    # métrica, nunca conteúdo.
    assert "11222333000181" not in linha
    assert "Fornecedor" not in linha
    assert "5200.00" not in linha
    assert nota.documento.chave_acesso not in linha


def test_log_registra_os_codigos_dos_problemas(ler_fixture, caplog) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    adulterado = conteudo.replace(b"<vNF>5200.00</vNF>", b"<vNF>9999.00</vNF>")
    nota = parse(adulterado, "adulterado.xml")
    with caplog.at_level(logging.INFO, logger="nfscan"):
        registrar_leitura(nota)
    registro = json.loads(caplog.records[-1].getMessage())
    assert "TOTAL_DIVERGENTE" in registro["problemas"]
    # Só o código, não a mensagem: a mensagem cita valores da nota.
    assert "9999.00" not in caplog.records[-1].getMessage()


def test_configurar_e_idempotente() -> None:
    from nfscan.log import LOGGER, configurar

    configurar()
    quantos = len(LOGGER.handlers)
    configurar()
    assert len(LOGGER.handlers) == quantos
