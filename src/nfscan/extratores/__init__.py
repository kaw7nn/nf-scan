"""Extratores por dialeto fiscal."""

from nfscan.extratores.generico import ExtratorGenerico
from nfscan.extratores.registro import Extrator, dialetos_suportados, obter, registrar
from nfscan.extratores.xml_abrasf import ExtratorAbrasf
from nfscan.extratores.xml_nfe import ExtratorNfe
from nfscan.extratores.xml_nfse_nacional import ExtratorNfseNacional

registrar(ExtratorNfe())
registrar(ExtratorNfseNacional())
registrar(ExtratorAbrasf())
registrar(ExtratorGenerico())

__all__ = [
    "Extrator",
    "ExtratorAbrasf",
    "ExtratorGenerico",
    "ExtratorNfe",
    "ExtratorNfseNacional",
    "dialetos_suportados",
    "obter",
    "registrar",
]
