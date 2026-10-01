"""Ponto de entrada do núcleo: bytes entram, ``NotaFiscal`` sai.

Regra central do serviço: nenhuma nota ruim levanta exceção. Falha de extração
vira problema registrado, confiança zero e ``requer_revisao``. A única exceção
que sai daqui é :class:`ArquivoGrande`, que é defesa de recurso e não
julgamento sobre a nota.
"""

from __future__ import annotations

import hashlib
import io
import mimetypes
import time
import zipfile

from nfscan.detect.dialeto import detectar_dialeto
from nfscan.extratores import obter
from nfscan.extratores.generico import ExtratorGenerico
from nfscan.extratores.pdf_texto import ExtratorPdfTexto
from nfscan.extratores.registro import Extrator
from nfscan.modelo import ArquivoOrigem, NotaFiscal, Problema
from nfscan.modelo.coletor import requer_revisao
from nfscan.sniff.container import Container, analisar, detectar_container
from nfscan.validar import validar

LIMITE_BYTES = 20 * 1024 * 1024


class ArquivoGrande(ValueError):
    """O arquivo excede o limite aceito pelo serviço."""


def _origem(conteudo: bytes, nome: str, mime: str | None) -> ArquivoOrigem:
    if mime is None:
        mime = mimetypes.guess_type(nome)[0] or "application/octet-stream"
    return ArquivoOrigem(
        nome=nome,
        mime=mime,
        bytes=len(conteudo),
        sha256=hashlib.sha256(conteudo).hexdigest(),
    )


def parse(conteudo: bytes, nome: str, mime: str | None = None) -> NotaFiscal:
    """Lê a nota e devolve o modelo canônico."""
    if len(conteudo) > LIMITE_BYTES:
        raise ArquivoGrande(
            f"arquivo de {len(conteudo)} bytes excede o limite de {LIMITE_BYTES}"
        )

    inicio = time.perf_counter()
    arquivo = _origem(conteudo, nome, mime)
    # Uma única extração de texto por PDF, reaproveitada na detecção de dialeto
    # e no extrator.
    container, texto_pdf = analisar(conteudo)
    dialeto, confianca_deteccao = detectar_dialeto(conteudo, container, texto_pdf)

    # Imagem e PDF sem camada de texto vão para o OCR pelo container, não pelo
    # dialeto: a detecção palpita DANFE_PDF para os dois, e o extrator de texto
    # devolveria nota vazia.
    if container in (Container.IMAGEM, Container.PDF_IMAGEM):
        from nfscan.extratores.ocr.extrator import ExtratorOcr

        extrator: Extrator = ExtratorOcr()
    else:
        extrator = obter(dialeto) or ExtratorGenerico()
    extras: list[Problema] = []
    try:
        if isinstance(extrator, ExtratorPdfTexto):
            nota = extrator.extrair(conteudo, arquivo, texto=texto_pdf)
        else:
            nota = extrator.extrair(conteudo, arquivo)
    except Exception as erro:
        # O extrator do dialeto não deu conta: devolve nota vazia explicando,
        # em vez de propagar para o cliente.
        nota = ExtratorGenerico().extrair(conteudo, arquivo)
        extras.append(
            Problema(
                severidade="erro",
                codigo="EXTRACAO_FALHOU",
                campo=None,
                mensagem=f"O extrator de {dialeto.value} não conseguiu ler o arquivo: {erro}",
            )
        )

    problemas = [*nota.extracao.problemas, *extras, *validar(nota)]

    confianca = nota.extracao.confianca_global
    if container is Container.DESCONHECIDO:
        confianca = 0.0
    elif confianca_deteccao > 0:
        confianca = min(confianca, confianca_deteccao)

    nota.extracao.problemas = problemas
    nota.extracao.confianca_global = round(confianca, 4)
    nota.extracao.requer_revisao = requer_revisao(confianca, problemas)
    nota.extracao.duracao_ms = int((time.perf_counter() - inicio) * 1000)
    return nota


MAXIMO_ENTRADAS_ZIP = 50


def parse_zip(conteudo: bytes, nome: str) -> list[NotaFiscal]:
    """Lê cada entrada de um ZIP, preservando a ordem do arquivo.

    Entrada ilegível vira nota com ``ARQUIVO_ILEGIVEL``, não exceção, para que
    um arquivo solto no pacote não invalide o lote inteiro. ZIP corrompido
    devolve uma única nota ilegível.
    """
    try:
        pacote = zipfile.ZipFile(io.BytesIO(conteudo))
        entradas = [item for item in pacote.infolist() if not item.is_dir()]
    except zipfile.BadZipFile:
        return [ExtratorGenerico().extrair(conteudo, _origem(conteudo, nome, "application/zip"))]

    if len(entradas) > MAXIMO_ENTRADAS_ZIP:
        raise ArquivoGrande(
            f"o ZIP traz {len(entradas)} entradas, acima do limite de {MAXIMO_ENTRADAS_ZIP}"
        )

    notas: list[NotaFiscal] = []
    for entrada in entradas:
        notas.append(_ler_entrada_do_zip(pacote, entrada))
    return notas


def _ler_entrada_do_zip(pacote: zipfile.ZipFile, entrada: zipfile.ZipInfo) -> NotaFiscal:
    """Lê uma entrada do ZIP com limite de tamanho.

    O tamanho é checado **antes** de materializar os bytes, e a leitura é
    limitada: um ZIP de poucos KB pode declarar centenas de MB descomprimidos, e
    ler sem teto é um estouro de memória remoto trivial. O cabeçalho pode mentir,
    então a leitura também é limitada, não só a checagem.

    Entrada grande demais vira nota com problema, nunca exceção: recusar o lote
    inteiro descartaria as notas legíveis que vieram no mesmo pacote.
    """
    if entrada.file_size > LIMITE_BYTES:
        return _nota_recusada(entrada.filename, entrada.file_size)
    try:
        with pacote.open(entrada) as fluxo:
            bruto = fluxo.read(LIMITE_BYTES + 1)
    except Exception:
        bruto = b""
    if len(bruto) > LIMITE_BYTES:
        return _nota_recusada(entrada.filename, len(bruto))
    return parse(bruto, entrada.filename)


def _nota_recusada(nome: str, tamanho: int) -> NotaFiscal:
    """Nota vazia explicando que a entrada excedeu o limite."""
    arquivo = ArquivoOrigem(
        nome=nome,
        mime="application/octet-stream",
        bytes=tamanho,
        # Nada do conteúdo foi aceito, então o hash é o do vazio.
        sha256=hashlib.sha256(b"").hexdigest(),
    )
    nota = ExtratorGenerico().extrair(b"", arquivo)
    nota.extracao.problemas = [
        Problema(
            severidade="erro",
            codigo="ENTRADA_GRANDE_DEMAIS",
            campo=None,
            mensagem=(
                f"A entrada '{nome}' tem {tamanho} bytes descomprimidos e excede o "
                f"limite de {LIMITE_BYTES}. As demais notas do pacote foram lidas."
            ),
        )
    ]
    return nota


def parse_entrada(conteudo: bytes, nome: str, mime: str | None = None) -> list[NotaFiscal]:
    """Lê um arquivo, expandindo-o se for ZIP. Sempre devolve lista."""
    if detectar_container(conteudo) is Container.ZIP:
        return parse_zip(conteudo, nome)
    return [parse(conteudo, nome, mime)]
