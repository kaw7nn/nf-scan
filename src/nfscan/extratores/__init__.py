"""Extratores por dialeto fiscal."""

from nfscan.extratores.generico import ExtratorGenerico
from nfscan.extratores.pdf_texto import ExtratorPdfTexto
from nfscan.extratores.registro import Extrator, dialetos_suportados, obter, registrar
from nfscan.extratores.xml_abrasf import ExtratorAbrasf
from nfscan.extratores.xml_nfe import ExtratorNfe
from nfscan.extratores.xml_nfse_nacional import ExtratorNfseNacional

registrar(ExtratorNfe())
registrar(ExtratorNfseNacional())
registrar(ExtratorAbrasf())
registrar(ExtratorPdfTexto())
registrar(ExtratorGenerico())

__all__ = [
    "Extrator",
    "ExtratorAbrasf",
    "ExtratorGenerico",
    "ExtratorNfe",
    "ExtratorNfseNacional",
    "ExtratorPdfTexto",
    "dialetos_suportados",
    "obter",
    "registrar",
]
