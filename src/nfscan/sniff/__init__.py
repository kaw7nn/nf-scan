"""Detecção do container físico do arquivo."""

from nfscan.sniff.container import (
    MINIMO_CARACTERES_POR_PAGINA,
    Container,
    detectar_container,
    texto_de_pdf,
)

__all__ = [
    "MINIMO_CARACTERES_POR_PAGINA",
    "Container",
    "detectar_container",
    "texto_de_pdf",
]
