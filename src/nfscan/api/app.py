"""API HTTP do NF Scan.

Casca fina: nenhuma regra de negócio aqui. A decisão de contrato que importa é
o código de status — uma nota mal extraída responde ``200``, porque a qualidade
da leitura é dado da resposta, não erro de protocolo. Só erro de protocolo de
verdade sai como 4xx.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import anyio
from fastapi import Depends, FastAPI, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from nfscan import __version__
from nfscan.api.diagnostico import idiomas_tesseract, versao_tesseract
from nfscan.api.seguranca import conferir_chave
from nfscan.extratores import dialetos_suportados
from nfscan.log import configurar, registrar_leitura
from nfscan.modelo import NotaFiscal
from nfscan.pipeline import LIMITE_BYTES, ArquivoGrande, parse, parse_entrada

MAXIMO_LOTE = 50

VARIAVEL_MAX_LEITURAS = "NFSCAN_MAX_LEITURAS"
# Teto de leituras pesadas em paralelo. Cada uma renderiza páginas a 300 dpi e
# roda Tesseract, então o limite real é CPU e memória, não conexões: medido,
# seis leituras simultâneas saturaram sete núcleos. Sem teto, o threadpool
# aceitaria dezenas e o container morreria por memória antes de responder.
MAXIMO_LEITURAS_PADRAO = 4


def _maximo_leituras() -> int:
    bruto = os.environ.get(VARIAVEL_MAX_LEITURAS, "")
    if bruto.strip().isdigit() and int(bruto) > 0:
        return int(bruto)
    return min(os.cpu_count() or 1, MAXIMO_LEITURAS_PADRAO)


def _recusar_se_grande(arquivo: UploadFile) -> None:
    """Recusa pelo tamanho declarado, antes de carregar os bytes na memória.

    ``parse`` também confere, mas só depois de o upload inteiro estar em
    memória; checar aqui evita gastar memória com o que já se sabe que será
    recusado.
    """
    if arquivo.size is not None and arquivo.size > LIMITE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"{arquivo.filename}: {arquivo.size} bytes excedem o limite de "
                f"{LIMITE_BYTES}"
            ),
        )


def criar_app() -> FastAPI:
    """Monta a aplicação. Função em vez de módulo para os testes isolarem estado."""
    configurar()
    porteiro = anyio.Semaphore(_maximo_leituras())

    @asynccontextmanager
    async def leitura_limitada() -> Any:
        """Serializa o excesso de leituras em vez de deixar o container morrer."""
        async with porteiro:
            yield

    app = FastAPI(
        title="NF Scan",
        version=__version__,
        description=(
            "Lê notas fiscais brasileiras em qualquer formato e devolve um JSON "
            "canônico com confiança e proveniência por campo."
        ),
    )

    @app.get("/healthz", tags=["servico"])
    def healthz() -> dict[str, Any]:
        """Verificação de vida, aberta e sem chave de API.

        Reporta os idiomas de OCR instalados: sem o pacote 'por' a leitura de
        foto perde precisão, e o operador precisa saber disso sem adivinhar.
        """
        return {
            "status": "ok",
            "versao": __version__,
            "tesseract": versao_tesseract(),
            "idiomas_ocr": list(idiomas_tesseract()),
        }

    @app.post(
        "/v1/notas",
        response_model=NotaFiscal,
        tags=["notas"],
        dependencies=[Depends(conferir_chave)],
    )
    async def ler_nota(arquivo: UploadFile) -> NotaFiscal:
        """Lê uma nota e devolve o JSON canônico.

        Responde ``200`` mesmo quando a extração foi ruim: a qualidade se
        comunica por ``confianca_global``, ``problemas`` e ``requer_revisao``.
        """
        _recusar_se_grande(arquivo)
        conteudo = await arquivo.read()
        try:
            # Fora do event loop: parse roda pdftotext, pdftoppm e Tesseract
            # como subprocessos, com dezenas de segundos de teto. Chamá-lo
            # direto serializaria o serviço inteiro, inclusive o /healthz que o
            # orquestrador usa para decidir se reinicia o container.
            async with leitura_limitada():
                nota = await run_in_threadpool(
                    parse, conteudo, arquivo.filename or "sem-nome", arquivo.content_type
                )
        except ArquivoGrande as erro:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(erro)
            ) from erro
        registrar_leitura(nota)
        return nota

    @app.post(
        "/v1/notas/lote",
        response_model=list[NotaFiscal],
        tags=["notas"],
        dependencies=[Depends(conferir_chave)],
    )
    async def ler_lote(arquivos: list[UploadFile]) -> list[NotaFiscal]:
        """Lê até ``MAXIMO_LOTE`` arquivos, ou um ZIP, preservando a ordem."""
        if len(arquivos) > MAXIMO_LOTE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"o lote aceita no máximo {MAXIMO_LOTE} arquivos",
            )
        notas: list[NotaFiscal] = []
        for item in arquivos:
            _recusar_se_grande(item)
            conteudo = await item.read()
            try:
                async with leitura_limitada():
                    lidas = await run_in_threadpool(
                        parse_entrada, conteudo, item.filename or "sem-nome", item.content_type
                    )
            except ArquivoGrande as erro:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"{item.filename}: {erro}",
                ) from erro
            for nota in lidas:
                registrar_leitura(nota)
            notas.extend(lidas)
        return notas

    @app.get("/v1/schema", tags=["servico"], dependencies=[Depends(conferir_chave)])
    def schema() -> JSONResponse:
        """JSON Schema do modelo canônico, para o consumidor gerar seus tipos."""
        return JSONResponse(NotaFiscal.model_json_schema())

    @app.get("/v1/dialetos", tags=["servico"], dependencies=[Depends(conferir_chave)])
    def dialetos() -> dict[str, Any]:
        """Dialetos com extrator registrado e os limites aceitos."""
        return {
            "dialetos": sorted(dialeto.value for dialeto in dialetos_suportados()),
            "limite_bytes": LIMITE_BYTES,
            "maximo_lote": MAXIMO_LOTE,
            "maximo_leituras_simultaneas": _maximo_leituras(),
        }

    return app


app = criar_app()
