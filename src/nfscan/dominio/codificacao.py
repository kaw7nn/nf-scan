"""Decodificação de XML respeitando a declaração de encoding.

Decodificar sempre como UTF-8 com ``errors="replace"`` é o caminho fácil e
errado: um XML declarado ``ISO-8859-1``, que ERP legado ainda exporta, vira
mojibake — e, pior, vira mojibake com a confiança máxima que o sistema sabe
expressar, porque nada falhou. Aqui a declaração é lida antes de decidir.
"""

from __future__ import annotations

import re

_BOM_UTF8 = b"\xef\xbb\xbf"
_JANELA_DECLARACAO = 256
_ENCODING_DECLARADO = re.compile(rb"""encoding\s*=\s*["']([\w.\-]+)["']""")
# O atributo tem de sair do texto decodificado: tanto o lxml quanto o xsdata
# recusam uma str que ainda declara encoding.
_LIMPAR_DECLARACAO = re.compile(r"""(<\?xml[^>]*?)\s+encoding\s*=\s*["'][^"']+["']""")


def texto_de_xml(conteudo: bytes) -> tuple[str, bool]:
    """Devolve ``(texto, degradado)`` do XML.

    Tenta, em ordem: o encoding declarado, UTF-8, latin-1. ``degradado`` é
    ``True`` só quando nenhum deles serviu e houve substituição de caractere,
    para o chamador registrar um problema em vez de entregar lixo silencioso.
    """
    bruto = conteudo.removeprefix(_BOM_UTF8)
    achado = _ENCODING_DECLARADO.search(bruto[:_JANELA_DECLARACAO])

    candidatos: list[str] = []
    if achado is not None:
        candidatos.append(achado.group(1).decode("ascii", errors="replace"))
    candidatos += ["utf-8", "latin-1"]

    for codec in candidatos:
        try:
            return _sem_declaracao(bruto.decode(codec)), False
        except (LookupError, UnicodeDecodeError):
            continue
    return _sem_declaracao(bruto.decode("utf-8", errors="replace")), True


def _sem_declaracao(texto: str) -> str:
    return _LIMPAR_DECLARACAO.sub(r"\1", texto, count=1)
