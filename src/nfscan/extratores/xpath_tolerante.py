"""Leitura de XML por nome local de tag.

Os layouts municipais de NFS-e usam namespaces diferentes, prefixos diferentes
e às vezes nenhum namespace. Amarrar o extrator a um namespace específico
significaria um extrator por prefeitura, então a busca é pelo nome local em
qualquer profundidade.
"""

from __future__ import annotations

from typing import Any

from lxml import etree

_BOM_UTF8 = b"\xef\xbb\xbf"


def carregar(conteudo: bytes) -> Any:
    """Devolve a raiz do XML, tolerando BOM, encoding declarado e lixo.

    ``recover=True`` permite ler documento com pequenas violações, comum em
    exportação de sistema municipal antigo. ``resolve_entities`` e ``no_network``
    desligados fecham a porta para XXE: o conteúdo vem de fora.
    """
    bruto = conteudo.removeprefix(_BOM_UTF8).lstrip()
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
    raiz = etree.fromstring(bruto, parser=parser)
    if raiz is None:
        raise ValueError("XML sem raiz legível")
    return raiz


def _local(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rpartition("}")[2]


def todos_elementos(raiz: Any, nome: str) -> list[Any]:
    """Todos os elementos cujo nome local é ``nome``, em qualquer nível."""
    return [elemento for elemento in raiz.iter() if _local(elemento.tag) == nome]


def primeiro_texto(raiz: Any, *nomes: str) -> str | None:
    """Texto do primeiro elemento que casa com algum dos nomes, na ordem dada.

    A ordem dos nomes importa: coloque primeiro o nome mais específico, para que
    ``NumeroNfse`` vença ``Numero`` quando os dois existirem.
    """
    for nome in nomes:
        for elemento in todos_elementos(raiz, nome):
            if elemento.text and elemento.text.strip():
                return str(elemento.text).strip()
    return None
