"""Contrato da API HTTP."""

import io

import pytest
from fastapi.testclient import TestClient

from nfscan.api.app import criar_app

CHAVE = "chave-de-teste"


@pytest.fixture(autouse=True)
def chaves_configuradas(monkeypatch) -> None:
    monkeypatch.setenv("NFSCAN_API_KEYS", CHAVE)


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(criar_app())


def _enviar(cliente, conteudo: bytes, nome: str, mime: str, chave: str | None = CHAVE):
    cabecalhos = {"X-API-Key": chave} if chave else {}
    return cliente.post(
        "/v1/notas",
        files={"arquivo": (nome, io.BytesIO(conteudo), mime)},
        headers=cabecalhos,
    )


def test_healthz_e_aberto(cliente) -> None:
    resposta = cliente.get("/healthz")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"
    assert "versao" in resposta.json()


def test_sem_chave_de_api_responde_401(cliente, ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    resposta = _enviar(cliente, conteudo, "n.xml", "application/xml", chave=None)
    assert resposta.status_code == 401


def test_chave_errada_responde_401(cliente, ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    resposta = _enviar(cliente, conteudo, "n.xml", "application/xml", chave="errada")
    assert resposta.status_code == 401


def test_xml_de_nfe_responde_200_com_nota(cliente, ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    resposta = _enviar(cliente, conteudo, "nfe.xml", "application/xml")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["versao_schema"] == "1.1"
    assert corpo["emitente"]["cnpj"] == "11222333000181"
    assert corpo["totais"]["valor_total"] == "5200.00"
    assert corpo["extracao"]["requer_revisao"] is False


def test_arquivo_ilegivel_responde_200_e_nao_500(cliente) -> None:
    resposta = _enviar(cliente, b"isso nao e nota", "x.txt", "text/plain")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["extracao"]["requer_revisao"] is True
    assert corpo["extracao"]["problemas"][0]["codigo"] == "ARQUIVO_ILEGIVEL"


def test_arquivo_grande_responde_413(cliente) -> None:
    from nfscan.pipeline import LIMITE_BYTES

    resposta = _enviar(cliente, b"\x00" * (LIMITE_BYTES + 1), "g.pdf", "application/pdf")
    assert resposta.status_code == 413


def test_requisicao_sem_arquivo_responde_422(cliente) -> None:
    resposta = cliente.post("/v1/notas", headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 422


def test_lote_responde_array_na_ordem_do_envio(cliente, ler_fixture) -> None:
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    resposta = cliente.post(
        "/v1/notas/lote",
        files=[
            ("arquivos", ("a.xml", io.BytesIO(conteudo), "application/xml")),
            ("arquivos", ("b.txt", io.BytesIO(b"ruido"), "text/plain")),
        ],
        headers={"X-API-Key": CHAVE},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 2
    assert corpo[0]["extracao"]["arquivo"]["nome"] == "a.xml"
    assert corpo[1]["extracao"]["problemas"][0]["codigo"] == "ARQUIVO_ILEGIVEL"


def test_lote_acima_do_maximo_responde_413(cliente) -> None:
    arquivos = [("arquivos", (f"{i}.txt", io.BytesIO(b"x"), "text/plain")) for i in range(51)]
    resposta = cliente.post("/v1/notas/lote", files=arquivos, headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 413


def test_schema_expoe_json_schema(cliente) -> None:
    resposta = cliente.get("/v1/schema", headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 200
    assert resposta.json()["title"] == "NotaFiscal"


def test_dialetos_lista_os_suportados(cliente) -> None:
    resposta = cliente.get("/v1/dialetos", headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 200
    assert "nfe_4.00" in resposta.json()["dialetos"]


def test_openapi_e_gerado(cliente) -> None:
    assert cliente.get("/openapi.json").status_code == 200


def test_lote_aceita_zip_com_varias_notas(cliente, ler_fixture) -> None:
    import zipfile

    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as pacote:
        pacote.writestr("nota1.xml", conteudo)
        pacote.writestr("nota2.xml", conteudo)
        pacote.writestr("leia-me.txt", b"ignorar")
    resposta = cliente.post(
        "/v1/notas/lote",
        files={"arquivos": ("notas.zip", io.BytesIO(buffer.getvalue()), "application/zip")},
        headers={"X-API-Key": CHAVE},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 3
    nomes = [item["extracao"]["arquivo"]["nome"] for item in corpo]
    assert nomes == ["nota1.xml", "nota2.xml", "leia-me.txt"]
    assert corpo[2]["extracao"]["problemas"][0]["codigo"] == "ARQUIVO_ILEGIVEL"


def test_zip_corrompido_nao_derruba_o_servico(cliente) -> None:
    resposta = cliente.post(
        "/v1/notas/lote",
        files={"arquivos": ("ruim.zip", io.BytesIO(b"PK\x03\x04lixo"), "application/zip")},
        headers={"X-API-Key": CHAVE},
    )
    assert resposta.status_code == 200
    assert resposta.json()[0]["extracao"]["requer_revisao"] is True
