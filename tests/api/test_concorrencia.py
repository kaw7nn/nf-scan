"""A leitura não pode bloquear o event loop.

``parse`` é trabalho síncrono e pesado: subprocessos de pdftotext, pdftoppm e
Tesseract, com dezenas de segundos de teto. Chamá-lo direto de uma rota
``async`` serializa o serviço inteiro — inclusive ``/healthz``, que o
orquestrador usa para decidir se reinicia o container.
"""

import asyncio
import io
import time

import pytest
from httpx2 import ASGITransport, AsyncClient

from nfscan.api.app import criar_app

CHAVE = "chave-de-teste"
BLOQUEIO = 0.3


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def chaves_configuradas(monkeypatch) -> None:
    monkeypatch.setenv("NFSCAN_API_KEYS", CHAVE)


@pytest.fixture
def parse_lento(monkeypatch, ler_fixture):
    """Substitui parse por uma versão que bloqueia a thread, como o OCR faz."""
    conteudo, _ = ler_fixture("nfe_4_00_simples.xml", "application/xml")
    from importlib import import_module

    from nfscan import pipeline

    # nfscan/api/__init__.py reexporta `app`, sombreando o submódulo de mesmo
    # nome; import_module resolve pelo sys.modules e devolve o módulo.
    modulo_app = import_module("nfscan.api.app")
    original = pipeline.parse

    def lento(*args, **kwargs):
        time.sleep(BLOQUEIO)
        return original(conteudo, "nota.xml", "application/xml")

    monkeypatch.setattr(modulo_app, "parse", lento)
    return lento


@pytest.mark.anyio
async def test_leituras_simultaneas_nao_serializam(parse_lento) -> None:
    app = criar_app()
    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url="http://teste") as cliente:

        async def ler() -> int:
            resposta = await cliente.post(
                "/v1/notas",
                files={"arquivo": ("n.xml", io.BytesIO(b"<x/>"), "application/xml")},
                headers={"X-API-Key": CHAVE},
            )
            return resposta.status_code

        inicio = time.perf_counter()
        status = await asyncio.gather(ler(), ler(), ler())
        decorrido = time.perf_counter() - inicio

    assert status == [200, 200, 200]
    # Serializado, três leituras de 0.3s levariam ~0.9s. Em paralelo, ~0.3s.
    assert decorrido < BLOQUEIO * 2, (
        f"as leituras serializaram: {decorrido:.2f}s para três de {BLOQUEIO}s"
    )
