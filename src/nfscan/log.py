"""Log estruturado.

O serviço lê documento fiscal de terceiros, então o log registra **métrica**,
nunca conteúdo: dialeto, confiança, duração e o sha256 do arquivo. O hash
permite correlacionar com o arquivo que o cliente guardou sem reter nada da
nota. Dos problemas vai só o código, porque a mensagem cita valores da nota.
"""

from __future__ import annotations

import json
import logging

from nfscan.modelo import NotaFiscal

LOGGER = logging.getLogger("nfscan")


def configurar(nivel: str = "INFO") -> None:
    """Configura o handler de saída em linha única. Idempotente."""
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(nivel)


def registrar_leitura(nota: NotaFiscal) -> None:
    """Emite uma linha por leitura, sem dado da nota."""
    LOGGER.info(
        json.dumps(
            {
                "evento": "leitura",
                "dialeto": nota.extracao.dialeto,
                "motor": nota.extracao.motor,
                "confianca": nota.extracao.confianca_global,
                "requer_revisao": nota.extracao.requer_revisao,
                "duracao_ms": nota.extracao.duracao_ms,
                "bytes": nota.extracao.arquivo.bytes,
                "sha256": nota.extracao.arquivo.sha256,
                "problemas": [problema.codigo for problema in nota.extracao.problemas],
            },
            ensure_ascii=False,
        )
    )
