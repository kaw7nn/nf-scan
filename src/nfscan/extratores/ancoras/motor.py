"""Motor de âncoras: rótulo conhecido, depois valor próximo.

Serve tanto o texto de PDF quanto a saída de OCR — escrever dois motores
duplicaria a parte mais difícil de acertar. Os padrões moram em YAML para que
um emissor com layout peculiar seja um arquivo novo, não uma mudança de código.

Há dois tipos de âncora, porque o DANFE tem duas formas de apresentar dado:

``regex``
    Para rótulo e valor na mesma linha ou na linha seguinte, sem vizinho que
    confunda: ``CNPJ 11.222.333/0001-81``.

``coluna``
    Para o bloco tabular, onde os rótulos ficam numa linha e os valores
    alinhados abaixo::

        VALOR DO FRETE   VALOR DO SEGURO   DESCONTO   VALOR TOTAL DA NOTA
              150,00            0,00         0,00           5.200,00

    Aqui "o primeiro número depois do rótulo" é o valor da coluna errada —
    pegaria 150,00 para o total da nota. A âncora de coluna localiza a faixa
    horizontal do rótulo e lê o número que se sobrepõe a ela nas linhas
    seguintes. É a diferença entre ler a nota e inventá-la.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DIRETORIO_PERFIS = Path(__file__).parent / "perfis"
NOME_GENERICO = "generico"

# Número no formato brasileiro, com ou sem ponto de milhar.
_NUMERO_BR = re.compile(r"-?\d{1,3}(?:\.\d{3})+,\d{2}|-?\d+,\d{2}")

LINHAS_ABAIXO = 3
TOLERANCIA_COLUNA = 5


@dataclass(frozen=True, slots=True)
class Ancora:
    """Como achar um campo: por expressão, por coluna, ou por ambos."""

    regex: tuple[str, ...] = ()
    coluna: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Perfil:
    """Conjunto de âncoras de um emissor, ou o genérico."""

    nome: str
    marcadores: tuple[str, ...] = ()
    campos: dict[str, Ancora] = field(default_factory=dict)


def _ancora_de(bruto: object) -> Ancora:
    """Aceita a forma completa ``{regex: [...], coluna: [...]}``."""
    if isinstance(bruto, dict):
        return Ancora(
            regex=tuple(bruto.get("regex") or ()),
            coluna=tuple(bruto.get("coluna") or ()),
        )
    if isinstance(bruto, list):
        # Forma abreviada: uma lista solta é entendida como expressões.
        return Ancora(regex=tuple(bruto))
    return Ancora()


def carregar_perfis() -> list[Perfil]:
    """Lê todos os ``*.yaml`` do diretório de perfis."""
    perfis: list[Perfil] = []
    for caminho in sorted(DIRETORIO_PERFIS.glob("*.yaml")):
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
        perfis.append(
            Perfil(
                nome=str(bruto.get("nome", caminho.stem)),
                marcadores=tuple(bruto.get("marcadores") or ()),
                campos={
                    campo: _ancora_de(definicao)
                    for campo, definicao in (bruto.get("campos") or {}).items()
                },
            )
        )
    return perfis


def escolher_perfil(texto: str, perfis: list[Perfil]) -> Perfil:
    """Perfil com mais marcadores presentes; ``generico`` como último recurso.

    Sem perfil cadastrado o genérico ainda roda, com confiança menor: perfil é
    otimização, não requisito.
    """
    alto = texto.upper()
    melhor: Perfil | None = None
    melhor_pontos = 0
    for perfil in perfis:
        if not perfil.marcadores:
            continue
        pontos = sum(1 for marcador in perfil.marcadores if marcador.upper() in alto)
        if pontos > melhor_pontos:
            melhor, melhor_pontos = perfil, pontos
    if melhor is not None:
        return melhor
    return next(perfil for perfil in perfis if perfil.nome == NOME_GENERICO)


def valor_na_coluna(texto: str, rotulo: str) -> str | None:
    """Lê o número alinhado sob o rótulo, nas linhas seguintes.

    Devolve o primeiro número cuja faixa horizontal se sobrepõe à do rótulo,
    com folga de :data:`TOLERANCIA_COLUNA` caracteres para cada lado — a
    centralização do valor na coluna raramente é exata.
    """
    linhas = texto.splitlines()
    alvo = rotulo.upper()
    for indice, linha in enumerate(linhas):
        posicao = linha.upper().find(alvo)
        if posicao == -1:
            continue
        inicio = posicao - TOLERANCIA_COLUNA
        fim = posicao + len(alvo) + TOLERANCIA_COLUNA
        for seguinte in linhas[indice + 1 : indice + 1 + LINHAS_ABAIXO]:
            for achado in _NUMERO_BR.finditer(seguinte):
                if achado.start() < fim and achado.end() > inicio:
                    return achado.group()
    return None


def aplicar(perfil: Perfil, texto: str) -> dict[str, str]:
    """Aplica as âncoras do perfil e devolve os valores crus encontrados.

    A âncora de coluna é tentada primeiro quando existe, porque é a precisa no
    bloco tabular. Campo sem casamento simplesmente não aparece no resultado:
    ausência é informação, e inventar valor seria pior.
    """
    encontrados: dict[str, str] = {}
    for campo, ancora in perfil.campos.items():
        achado = next(
            (valor for rotulo in ancora.coluna if (valor := valor_na_coluna(texto, rotulo))),
            None,
        )
        if achado is None:
            for padrao in ancora.regex:
                casamento = re.search(padrao, texto, re.IGNORECASE | re.MULTILINE)
                if casamento and casamento.group(1).strip():
                    achado = casamento.group(1).strip()
                    break
        if achado:
            encontrados[campo] = achado.strip()
    return encontrados
