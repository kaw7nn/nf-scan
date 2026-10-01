"""Extratores por dialeto fiscal."""

from nfscan.extratores.generico import ExtratorGenerico
from nfscan.extratores.registro import Extrator, dialetos_suportados, obter, registrar
from nfscan.extratores.xml_nfe import ExtratorNfe

registrar(ExtratorNfe())
registrar(ExtratorGenerico())

__all__ = [
    "Extrator",
    "ExtratorGenerico",
    "ExtratorNfe",
    "dialetos_suportados",
    "obter",
    "registrar",
]
