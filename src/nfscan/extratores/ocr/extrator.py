"""Extrator por OCR, para PDF sem camada de texto e para foto.

Reusa o motor de âncoras do extrator de PDF com texto: escrever um segundo
motor duplicaria a parte mais difícil de acertar.

A chave de acesso lida por OCR sobe de confiança quando o mod-11 fecha, de
``ocr_bruto`` para ``ocr_confirmado``. O dígito verificador é verificação
independente da leitura: uma chave que fecha foi lida certa, mesmo vinda de uma
foto. É a única garantia forte que este caminho oferece.
"""

from __future__ import annotations

from nfscan.api.diagnostico import idiomas_tesseract
from nfscan.detect.dialeto import Dialeto
from nfscan.extratores.ocr.preparo import imagens_de
from nfscan.extratores.pdf_texto import extrair_de_texto
from nfscan.modelo import ArquivoOrigem, Documento, Extracao, NotaFiscal, Problema
from nfscan.modelo.coletor import CONFIANCA, Coletor, requer_revisao
from nfscan.sniff.container import Container, detectar_container

IDIOMA_PREFERIDO = "por"
IDIOMA_RESERVA = "eng"

# --psm 6 trata a página como um bloco uniforme de texto, que é a forma de um
# DANFE. preserve_interword_spaces mantém o espaçamento horizontal, sem o qual
# a âncora por coluna não funciona.
CONFIGURACAO = "--psm 6 -c preserve_interword_spaces=1"


def idioma_disponivel() -> str:
    """Idioma a usar: ``por`` se instalado, senão ``eng``, senão nenhum."""
    instalados = idiomas_tesseract()
    if IDIOMA_PREFERIDO in instalados:
        return IDIOMA_PREFERIDO
    if IDIOMA_RESERVA in instalados:
        return IDIOMA_RESERVA
    return ""


def texto_por_ocr(conteudo: bytes, container: Container) -> str:
    """Roda o OCR em cada página e junta o texto. Nunca levanta."""
    idioma = idioma_disponivel()
    if not idioma:
        return ""
    try:
        import pytesseract
    except ImportError:  # extra "ocr" não instalado
        return ""
    partes = []
    for imagem in imagens_de(conteudo, container):
        try:
            partes.append(pytesseract.image_to_string(imagem, lang=idioma, config=CONFIGURACAO))
        except Exception:
            continue
    return "\n".join(partes)


class ExtratorOcr:
    """Lê DANFE e cupom de imagem ou de PDF sem camada de texto."""

    motor = "tesseract"
    # O roteamento para este extrator é feito pelo container no pipeline, não
    # pelo dialeto: imagem e PDF-imagem chegam aqui mesmo que a detecção tenha
    # palpitado DANFE_PDF, que o extrator de texto também atende.
    dialetos: tuple[Dialeto, ...] = ()

    def extrair(self, conteudo: bytes, arquivo: ArquivoOrigem) -> NotaFiscal:
        container = detectar_container(conteudo)
        problemas = self._problemas_de_ambiente()
        texto = texto_por_ocr(conteudo, container)

        if not texto.strip():
            return self._vazia(arquivo, problemas)

        nota = extrair_de_texto(
            texto,
            arquivo,
            Dialeto.NFCE_CUPOM if "CUPOM" in texto.upper() else Dialeto.DANFE_PDF,
            CONFIANCA["ocr_bruto"],
            self.motor,
            confianca_chave=CONFIANCA["ocr_confirmado"],
        )
        nota.extracao.problemas = [*problemas, *nota.extracao.problemas]
        nota.extracao.requer_revisao = requer_revisao(
            nota.extracao.confianca_global, nota.extracao.problemas
        )
        return nota

    def _problemas_de_ambiente(self) -> list[Problema]:
        """Avisa quando o OCR vai rodar pior do que poderia."""
        instalados = idiomas_tesseract()
        if not instalados:
            return [
                Problema(
                    severidade="erro",
                    codigo="OCR_INDISPONIVEL",
                    campo=None,
                    mensagem=(
                        "Tesseract não está instalado ou não tem nenhum idioma. "
                        "Instale o tesseract e o pacote de idioma português."
                    ),
                )
            ]
        if IDIOMA_PREFERIDO not in instalados:
            return [
                Problema(
                    severidade="aviso",
                    codigo="OCR_IDIOMA_AUSENTE",
                    campo=None,
                    mensagem=(
                        f"O pacote de idioma '{IDIOMA_PREFERIDO}' do Tesseract não está "
                        f"instalado; a leitura usou '{IDIOMA_RESERVA}'. Dígitos e rótulos "
                        f"em caixa alta saem legíveis, mas texto acentuado perde precisão."
                    ),
                )
            ]
        return []

    def _vazia(self, arquivo: ArquivoOrigem, problemas: list[Problema]) -> NotaFiscal:
        todos = [
            *problemas,
            Problema(
                severidade="erro",
                codigo="ARQUIVO_ILEGIVEL",
                campo=None,
                mensagem="O OCR não encontrou texto legível na imagem.",
            ),
        ]
        return NotaFiscal(
            documento=Documento(),
            extracao=Extracao(
                dialeto=Dialeto.DANFE_PDF.value,
                motor=self.motor,
                arquivo=arquivo,
                confianca_global=0.0,
                requer_revisao=True,
                duracao_ms=0,
                campos=Coletor(CONFIANCA["ocr_bruto"]).campos,
                problemas=todos,
            ),
        )
