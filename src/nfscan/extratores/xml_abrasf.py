"""Extrator de NFS-e em layout municipal ABRASF 2.0x.

O padrão nacional é obrigatório desde 01/01/2026, mas notas antigas em layouts
municipais continuam circulando por anos. Esses layouts são um conjunto aberto:
cada prefeitura batizou os campos de um jeito. Por isso a leitura é por nome
local de tag, com nomes alternativos por campo, e a confiança é 0.90 e não 1.0.

Uma NFS-e não tem chave de acesso de 44 dígitos nem lista de itens. O serviço
inteiro vira um item único, porque devolver lista vazia deixaria o consumidor
sem nada para exibir.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from nfscan.detect.dialeto import Dialeto
from nfscan.dominio.numeros import para_data, para_data_hora, para_decimal
from nfscan.extratores.xpath_tolerante import carregar, primeiro_texto, todos_elementos
from nfscan.modelo import (
    ArquivoOrigem,
    Documento,
    Endereco,
    Extracao,
    Item,
    NotaFiscal,
    Participante,
    Problema,
    Retencoes,
    Totais,
    Tributos,
)
from nfscan.modelo.coletor import CONFIANCA, Coletor, requer_revisao

# Nomes alternativos por campo, do mais específico para o mais genérico.
NOMES = {
    "numero": ("NumeroNfse", "Numero"),
    "verificacao": ("CodigoVerificacao",),
    "emissao": ("DataEmissaoNfse", "DataEmissao"),
    "competencia": ("Competencia", "DataCompetencia"),
    "servicos": ("ValorServicos",),
    "liquido": ("ValorLiquidoNfse", "ValorLiquido"),
    "deducoes": ("ValorDeducoes",),
    "iss": ("ValorIss", "ValorISS"),
    "aliquota": ("Aliquota",),
    "pis": ("ValorPis",),
    "cofins": ("ValorCofins",),
    "csll": ("ValorCsll",),
    "irrf": ("ValorIr", "ValorIrrf"),
    "inss": ("ValorInss",),
    "discriminacao": ("Discriminacao",),
    "item_lista": ("ItemListaServico",),
    "municipio": ("CodigoMunicipio", "MunicipioPrestacaoServico"),
}


def _dec(bruto: str | None) -> Decimal | None:
    """Converte valor de ABRASF, decidindo o formato pelo próprio conteúdo.

    O XSD manda ``xsd:decimal``, com ponto decimal, mas parte dos municípios
    emite ``12.000,00``. Aplicar ``"auto"`` em tudo fazia ``<ValorIss>1.500``
    virar mil e quinhentos reais em vez de um e cinquenta. A vírgula é o
    discriminador: havendo vírgula, é notação brasileira; sem vírgula, o ponto
    é decimal como o XSD determina.
    """
    if bruto is None:
        return None
    return para_decimal(bruto, formato="auto" if "," in bruto else "ponto_decimal")


class ExtratorAbrasf:
    """Lê NFS-e municipal em ABRASF 2.0x, com confiança 0.90."""

    motor = "xpath_tolerante"
    dialetos: tuple[Dialeto, ...] = (Dialeto.ABRASF_2_0X,)

    def extrair(self, conteudo: bytes, arquivo: ArquivoOrigem) -> NotaFiscal:
        inicio = time.perf_counter()
        coletor = Coletor(CONFIANCA["xml_tolerante"])
        documento_xml = carregar(conteudo)
        raiz, problemas = self._escopo_da_nota(documento_xml)

        documento = self._documento(raiz, coletor)
        emitente = self._participante(raiz, "PrestadorServico", "emitente", coletor)
        destinatario = self._participante(raiz, "TomadorServico", "destinatario", coletor)
        totais = self._totais(raiz, coletor)
        itens = self._itens(raiz, totais, coletor)

        confianca = coletor.confianca_global()
        return NotaFiscal(
            documento=documento,
            emitente=emitente,
            destinatario=destinatario,
            itens=itens,
            totais=totais,
            extracao=Extracao(
                dialeto=self.dialetos[0].value,
                motor=self.motor,
                arquivo=arquivo,
                confianca_global=confianca,
                requer_revisao=requer_revisao(confianca, problemas),
                duracao_ms=int((time.perf_counter() - inicio) * 1000),
                campos=coletor.campos,
                problemas=problemas,
            ),
        )

    def _escopo_da_nota(self, documento_xml: Any) -> tuple[Any, list[Problema]]:
        """Restringe a extração à primeira nota do envelope.

        ``ConsultarNfseResposta`` carrega de zero a N ``CompNfse`` — e é um dos
        marcadores de detecção deste dialeto, então é entrada esperada. Ler por
        nome local a partir da raiz pegava o primeiro elemento com aquele nome
        em **qualquer** nota: um campo ausente na primeira era preenchido com o
        valor da segunda, misturando dinheiro de notas diferentes.
        """
        blocos = todos_elementos(documento_xml, "InfNfse") or todos_elementos(
            documento_xml, "CompNfse"
        )
        if not blocos:
            return documento_xml, []
        if len(blocos) > 1:
            return blocos[0], [
                Problema(
                    severidade="aviso",
                    codigo="MULTIPLAS_NOTAS_NO_ARQUIVO",
                    campo=None,
                    mensagem=(
                        f"O arquivo traz {len(blocos)} notas; apenas a primeira foi "
                        f"extraída. Envie uma nota por requisição, ou um ZIP."
                    ),
                )
            ]
        return blocos[0], []

    def _documento(self, raiz: Any, coletor: Coletor) -> Documento:
        def ler(chave: str) -> str | None:
            return primeiro_texto(raiz, *NOMES[chave])

        return Documento(
            tipo="nfse",
            numero=coletor.registrar(
                "documento.numero", ler("numero"), "xml:local-name()=Numero|NumeroNfse"
            ),
            data_emissao=coletor.registrar(
                "documento.data_emissao",
                para_data_hora(ler("emissao")),
                "xml:local-name()=DataEmissao",
            ),
            data_competencia=coletor.registrar(
                "documento.data_competencia",
                para_data(ler("competencia")),
                "xml:local-name()=Competencia",
            ),
            natureza_operacao=coletor.registrar(
                "documento.natureza_operacao",
                ler("discriminacao"),
                "xml:local-name()=Discriminacao",
            ),
            protocolo_autorizacao=coletor.registrar(
                "documento.protocolo_autorizacao",
                ler("verificacao"),
                "xml:local-name()=CodigoVerificacao",
            ),
            municipio_prestacao=coletor.registrar(
                "documento.municipio_prestacao",
                ler("municipio"),
                "xml:local-name()=CodigoMunicipio",
            ),
        )

    def _participante(
        self, raiz: Any, bloco_nome: str, papel: str, coletor: Coletor
    ) -> Participante | None:
        """Restringe a busca ao subárvore do participante.

        Sem isso o CNPJ do prestador vazaria para o tomador, porque a busca por
        nome local varre o documento inteiro.
        """
        blocos = todos_elementos(raiz, bloco_nome)
        if not blocos:
            return None
        bloco = blocos[0]
        origem = f"xml:{bloco_nome}/"
        endereco_blocos = todos_elementos(bloco, "Endereco")
        return Participante(
            cnpj=coletor.registrar(
                f"{papel}.cnpj", primeiro_texto(bloco, "Cnpj", "CNPJ"), f"{origem}Cnpj"
            ),
            cpf=coletor.registrar(
                f"{papel}.cpf", primeiro_texto(bloco, "Cpf", "CPF"), f"{origem}Cpf"
            ),
            razao_social=coletor.registrar(
                f"{papel}.razao_social",
                primeiro_texto(bloco, "RazaoSocial", "NomeFantasia"),
                f"{origem}RazaoSocial",
            ),
            inscricao_municipal=coletor.registrar(
                f"{papel}.inscricao_municipal",
                primeiro_texto(bloco, "InscricaoMunicipal"),
                f"{origem}InscricaoMunicipal",
            ),
            endereco=self._endereco(endereco_blocos[0], papel, coletor, origem)
            if endereco_blocos
            else None,
        )

    def _endereco(self, bloco: Any, papel: str, coletor: Coletor, origem: str) -> Endereco:
        # O bloco externo chama-se Endereco e tem um filho Endereco com o
        # logradouro; primeiro_texto ignora o externo porque seu texto é vazio.
        return Endereco(
            logradouro=coletor.registrar(
                f"{papel}.endereco.logradouro",
                primeiro_texto(bloco, "Endereco", "Logradouro"),
                f"{origem}Endereco/Endereco",
            ),
            numero=coletor.registrar(
                f"{papel}.endereco.numero",
                primeiro_texto(bloco, "Numero"),
                f"{origem}Endereco/Numero",
            ),
            complemento=coletor.registrar(
                f"{papel}.endereco.complemento",
                primeiro_texto(bloco, "Complemento"),
                f"{origem}Endereco/Complemento",
            ),
            bairro=coletor.registrar(
                f"{papel}.endereco.bairro",
                primeiro_texto(bloco, "Bairro"),
                f"{origem}Endereco/Bairro",
            ),
            codigo_municipio_ibge=coletor.registrar(
                f"{papel}.endereco.codigo_municipio_ibge",
                primeiro_texto(bloco, "CodigoMunicipio"),
                f"{origem}Endereco/CodigoMunicipio",
            ),
            uf=coletor.registrar(
                f"{papel}.endereco.uf",
                primeiro_texto(bloco, "Uf", "UF"),
                f"{origem}Endereco/Uf",
            ),
            cep=coletor.registrar(
                f"{papel}.endereco.cep",
                primeiro_texto(bloco, "Cep", "CEP"),
                f"{origem}Endereco/Cep",
            ),
        )

    def _totais(self, raiz: Any, coletor: Coletor) -> Totais:
        def ler(chave: str) -> Decimal | None:
            return _dec(primeiro_texto(raiz, *NOMES[chave]))

        return Totais(
            valor_servicos=coletor.registrar(
                "totais.valor_servicos", ler("servicos"), "xml:local-name()=ValorServicos"
            ),
            desconto=coletor.registrar(
                "totais.desconto", ler("deducoes"), "xml:local-name()=ValorDeducoes"
            ),
            valor_total=coletor.registrar(
                "totais.valor_total", ler("liquido"), "xml:local-name()=ValorLiquidoNfse"
            ),
            tributos=Tributos(
                iss_valor=coletor.registrar(
                    "totais.tributos.iss_valor", ler("iss"), "xml:local-name()=ValorIss"
                ),
                retencoes=Retencoes(
                    pis=coletor.registrar(
                        "totais.tributos.retencoes.pis", ler("pis"), "xml:local-name()=ValorPis"
                    ),
                    cofins=coletor.registrar(
                        "totais.tributos.retencoes.cofins",
                        ler("cofins"),
                        "xml:local-name()=ValorCofins",
                    ),
                    csll=coletor.registrar(
                        "totais.tributos.retencoes.csll", ler("csll"), "xml:local-name()=ValorCsll"
                    ),
                    irrf=coletor.registrar(
                        "totais.tributos.retencoes.irrf", ler("irrf"), "xml:local-name()=ValorIr"
                    ),
                    inss=coletor.registrar(
                        "totais.tributos.retencoes.inss", ler("inss"), "xml:local-name()=ValorInss"
                    ),
                ),
            ),
        )

    def _itens(self, raiz: Any, totais: Totais, coletor: Coletor) -> list[Item]:
        descricao = primeiro_texto(raiz, *NOMES["discriminacao"])
        codigo = primeiro_texto(raiz, *NOMES["item_lista"])
        if descricao is None and codigo is None and totais.valor_servicos is None:
            return []
        return [
            Item(
                ordem=1,
                codigo=coletor.registrar(
                    "itens[1].codigo", codigo, "xml:local-name()=ItemListaServico"
                ),
                descricao=coletor.registrar(
                    "itens[1].descricao", descricao, "xml:local-name()=Discriminacao"
                ),
                valor_total=coletor.registrar(
                    "itens[1].valor_total",
                    totais.valor_servicos,
                    "xml:local-name()=ValorServicos",
                ),
            )
        ]
