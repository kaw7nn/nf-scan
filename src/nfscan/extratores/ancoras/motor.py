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

# Número no formato brasileiro, com ou sem ponto de milhar. O espaço opcional
# depois da vírgula tolera um artefato comum do OCR, que lê "5.050,00" como
# "5.050, 00". A estrutura continua inequívoca: vírgula e exatamente duas casas.
_NUMERO_BR = re.compile(r"-?\d{1,3}(?:\.\d{3})+,\s?\d{2}|-?\d+,\s?\d{2}")

LINHAS_ABAIXO = 3
TOLERANCIA_COLUNA = 5

# Palavra com três letras ou mais, para reconhecer linha de rótulos.
_PALAVRA = re.compile(r"[^\W\d_]{3,}")
_MINIMO_PALAVRAS_CABECALHO = 2

# Célula de uma linha tabular: texto separado por duas ou mais espaços.
_CELULA = re.compile(r"\S(?:.*?\S)?(?=\s{2,}|$)")


# O que conta como valor, por tipo de campo. Sob os rótulos de um DANFE ficam
# também texto, data, CNPJ e inteiro simples — não só dinheiro —, e procurar
# sempre por dinheiro fazia oito campos sumirem em silêncio.
_PADRAO_POR_TIPO: dict[str, re.Pattern[str]] = {
    "moeda": _NUMERO_BR,
    "data": re.compile(r"\d{2}/\d{2}/\d{4}"),
    "documento": re.compile(r"\d{2}\.?\d{3}\.?\d{3}/\d{4}-?\d{2}|\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),
    "inteiro": re.compile(r"\b\d{4,}\b"),
}
# Tabela de dobra de acento, 1 para 1: um DANFE escreve "NATUREZA DA OPERAÇÃO"
# e outro "NATUREZA DA OPERACAO". Enumerar variantes no perfil é frágil, e
# unicodedata.normalize mudaria o comprimento da linha — o que destruiria as
# posições de coluna de que a âncora depende.
_SEM_ACENTO = str.maketrans(
    "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ",
    "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN",
)


def dobrar(texto: str) -> str:
    """Caixa alta sem acento, preservando o comprimento e as colunas."""
    return texto.translate(_SEM_ACENTO).upper()


TIPO_TEXTO = "texto"
TIPO_PADRAO = "moeda"


@dataclass(frozen=True, slots=True)
class Ancora:
    """Como achar um campo: por expressão, por coluna, ou por ambos.

    ``tipo`` diz o que conta como valor sob o rótulo: ``moeda`` (padrão),
    ``data``, ``documento``, ``inteiro`` ou ``texto``.
    """

    regex: tuple[str, ...] = ()
    coluna: tuple[str, ...] = ()
    tipo: str = TIPO_PADRAO


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
            tipo=str(bruto.get("tipo") or TIPO_PADRAO),
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
    alto = dobrar(texto)
    melhor: Perfil | None = None
    melhor_pontos = 0
    for perfil in perfis:
        if not perfil.marcadores:
            continue
        pontos = sum(1 for marcador in perfil.marcadores if dobrar(marcador) in alto)
        if pontos > melhor_pontos:
            melhor, melhor_pontos = perfil, pontos
    if melhor is not None:
        return melhor
    return next(perfil for perfil in perfis if perfil.nome == NOME_GENERICO)


def _e_cabecalho(linha: str) -> bool:
    """Reconhece uma linha de rótulos, que marca o início de outra tabela.

    Sem número algum e com duas ou mais palavras: é cabeçalho, não valor.
    """
    if _NUMERO_BR.search(linha):
        return False
    return len(_PALAVRA.findall(linha)) >= _MINIMO_PALAVRAS_CABECALHO


def _celula_na_coluna(
    linhas: list[str], indice: int, posicao: int, comprimento: int
) -> str | None:
    """Valor de TEXTO sob o rótulo: a célula correspondente da linha abaixo.

    Texto não tem formato reconhecível por expressão, então a posição é a única
    pista. Vale a célula de mesmo índice quando as contagens batem, e a de maior
    sobreposição quando não batem — uma coluna vazia desalinha a contagem.
    """
    celulas = _celulas(linhas[indice])
    posicao_na_tabela = _indice_da_celula(celulas, posicao)
    inicio = posicao - TOLERANCIA_COLUNA
    fim = posicao + comprimento + TOLERANCIA_COLUNA

    for seguinte in linhas[indice + 1 : indice + 1 + LINHAS_ABAIXO]:
        abaixo = _celulas(seguinte)
        if not abaixo:
            continue
        if posicao_na_tabela is not None and len(abaixo) == len(celulas):
            comeco, termino = abaixo[posicao_na_tabela]
            return seguinte[comeco:termino].strip() or None
        melhor = max(
            abaixo, key=lambda faixa: min(faixa[1], fim) - max(faixa[0], inicio)
        )
        if min(melhor[1], fim) - max(melhor[0], inicio) > 0:
            return seguinte[melhor[0] : melhor[1]].strip() or None
        return None
    return None


def valor_na_coluna(texto: str, rotulo: str, tipo: str = TIPO_PADRAO) -> str | None:
    """Lê o número alinhado sob o rótulo, na linha de valores dessa tabela.

    Devolve o primeiro número cuja faixa horizontal se sobrepõe à do rótulo,
    com folga de :data:`TOLERANCIA_COLUNA` caracteres para cada lado — a
    centralização do valor na coluna raramente é exata.

    A busca **para na primeira linha abaixo que contenha algum número**, mesmo
    que nenhum deles caia na coluna do rótulo. Continuar descendo faria o rótulo
    de uma tabela puxar valor da tabela seguinte, e o resultado seria um valor
    plausível e errado — pior que campo ausente em documento fiscal.
    """
    linhas = texto.splitlines()
    alvo = dobrar(rotulo)
    for indice, linha in enumerate(linhas):
        posicao = dobrar(linha).find(alvo)
        if posicao == -1:
            continue
        if tipo == TIPO_TEXTO:
            valor = _celula_na_coluna(linhas, indice, posicao, len(alvo))
        else:
            valor = _abaixo_do_rotulo(
                linhas, indice, posicao, len(alvo), _PADRAO_POR_TIPO[tipo]
            )
        if valor is not None:
            return valor
        # Esta ocorrência do rótulo não tinha valor sob ela — uma menção em
        # legenda, cabeçalho repetido ou "dados adicionais". Tenta a próxima
        # em vez de desistir do campo.
    return None


def _celulas(linha: str) -> list[tuple[int, int]]:
    """Faixas das células da linha, separadas por duas ou mais espaços."""
    return [(achado.start(), achado.end()) for achado in _CELULA.finditer(linha)]


def _indice_da_celula(celulas: list[tuple[int, int]], posicao: int) -> int | None:
    for indice, (inicio, fim) in enumerate(celulas):
        if inicio <= posicao < fim:
            return indice
    return None


def _por_sobreposicao(
    achados: list[re.Match[str]], posicao: int, comprimento: int
) -> str | None:
    """Alternativa geométrica, para quando a linha de valores é incompleta.

    Vale o número de maior sobreposição com a faixa do rótulo, desempatando por
    distância de centro. Menos confiável que a ordinal, porque sobreposição
    crua favorece número largo: um ``5.200,00`` da coluna vizinha vence um
    ``0,00`` da coluna certa.
    """
    inicio = posicao - TOLERANCIA_COLUNA
    fim = posicao + comprimento + TOLERANCIA_COLUNA
    centro_rotulo = posicao + comprimento / 2

    def pontuacao(achado: re.Match[str]) -> tuple[int, float]:
        sobreposicao = min(achado.end(), fim) - max(achado.start(), inicio)
        centro = (achado.start() + achado.end()) / 2
        return sobreposicao, -abs(centro - centro_rotulo)

    melhor = max(achados, key=pontuacao)
    return melhor.group() if pontuacao(melhor)[0] > 0 else None


def _abaixo_do_rotulo(
    linhas: list[str],
    indice: int,
    posicao: int,
    comprimento: int,
    padrao: re.Pattern[str] = _NUMERO_BR,
) -> str | None:
    """Procura o valor da coluna sob uma ocorrência específica do rótulo.

    A regra principal é **ordinal**: quando a linha de valores traz exatamente
    um número por célula do cabeçalho, o n-ésimo número é o valor da n-ésima
    coluna. É a única regra imune a deslocamento uniforme entre as duas linhas,
    e isso acontece de verdade — o OCR engole a indentação da linha de valores e
    desloca tudo alguns caracteres à esquerda do cabeçalho, situação em que
    casar por posição horizontal erra a coluna.

    Quando as contagens não batem (coluna sem valor, número de ruído), cai para
    a comparação geométrica.
    """
    celulas = _celulas(linhas[indice])
    posicao_na_tabela = _indice_da_celula(celulas, posicao)

    for seguinte in linhas[indice + 1 : indice + 1 + LINHAS_ABAIXO]:
        achados = list(padrao.finditer(seguinte))
        if not achados:
            # A barreira de cabeçalho só vale para dinheiro: ela reconhece uma
            # linha "sem número e com palavras", que é exatamente a forma de um
            # valor de texto ou de uma linha com data e CNPJ.
            if padrao is _NUMERO_BR and _e_cabecalho(seguinte):
                return None
            continue
        if posicao_na_tabela is not None and len(achados) == len(celulas):
            return achados[posicao_na_tabela].group()
        return _por_sobreposicao(achados, posicao, comprimento)
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
            (
                valor
                for rotulo in ancora.coluna
                if (valor := valor_na_coluna(texto, rotulo, ancora.tipo))
            ),
            None,
        )
        if achado is None:
            for padrao in ancora.regex:
                casamento = re.search(padrao, texto, re.IGNORECASE | re.MULTILINE)
                if casamento and casamento.group(1).strip():
                    achado = casamento.group(1).strip()
                    break
        if achado:
            # Remove o espaço que o OCR insere depois da vírgula decimal.
            encontrados[campo] = re.sub(r",\s+(\d{2})\b", r",\1", achado.strip())
    return encontrados
