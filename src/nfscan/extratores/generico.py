"""Extrator de último recurso.

Devolve uma nota vazia com o problema registrado. Existe para que nenhuma
entrada derrube o serviço: arquivo ilegível é informação, não exceção.
"""

from __future__ import annotations

from nfscan.detect.dialeto import Dialeto
from nfscan.modelo import ArquivoOrigem, Documento, Extracao, NotaFiscal, Problema


class ExtratorGenerico:
    """Nota vazia com o motivo pelo qual nada foi lido."""

    motor = "generico"
    dialetos: tuple[Dialeto, ...] = (Dialeto.DESCONHECIDO,)

    def extrair(self, conteudo: bytes, arquivo: ArquivoOrigem) -> NotaFiscal:
        problema = Problema(
            severidade="erro",
            codigo="ARQUIVO_ILEGIVEL",
            campo=None,
            mensagem=(
                "Não foi possível reconhecer o formato do arquivo. "
                "Envie o XML da nota, ou um PDF/imagem legível."
            ),
        )
        return NotaFiscal(
            documento=Documento(tipo="desconhecido"),
            extracao=Extracao(
                dialeto=Dialeto.DESCONHECIDO.value,
                motor=self.motor,
                arquivo=arquivo,
                confianca_global=0.0,
                requer_revisao=True,
                duracao_ms=0,
                problemas=[problema],
            ),
        )
