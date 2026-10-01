"""Extrator de NFS-e no padrão nacional 1.0.

Usa os bindings da ``nfelib`` gerados do XSD do ADN, então é caminho de
confiança 1.0. Duas diferenças importantes em relação à NF-e:

- A chave da NFS-e nacional tem **50 dígitos** e estrutura própria. Não é a
  chave de 44 da NF-e e não passa pelo mod-11 dela.
- O XML já traz o ``cStat`` atribuído pelo ADN, então a situação da nota é
  conhecida sem consultar nada — ao contrário da NF-e, onde sem o ``protNFe``
  a situação fica desconhecida.
"""

from __future__ import annotations

import time
from decimal import Decimal
from enum import Enum
from typing import Any

from nfscan.detect.dialeto import Dialeto
from nfscan.dominio.codificacao import texto_de_xml
from nfscan.dominio.numeros import para_data, para_data_hora, para_decimal
from nfscan.dominio.textos import limpar_texto
from nfscan.extratores.xml_nfe import SITUACAO_POR_CSTAT
from nfscan.modelo import (
    ArquivoOrigem,
    Documento,
    Endereco,
    Extracao,
    Item,
    NotaFiscal,
    Participante,
    Retencoes,
    Totais,
    Tributos,
)
from nfscan.modelo.coletor import CONFIANCA, Coletor, requer_revisao

_PREFIXO_ID = "NFS"
TAMANHO_CHAVE_NFSE = 50


def _valor(bruto: Any) -> Any:
    return bruto.value if isinstance(bruto, Enum) else bruto


def _texto(bruto: Any) -> str | None:
    return limpar_texto(_valor(bruto))


def _dec(bruto: Any) -> Decimal | None:
    """No XML nacional o ponto é sempre decimal."""
    return para_decimal(_valor(bruto), formato="ponto_decimal")


def _soma(*valores: Decimal | None) -> Decimal | None:
    presentes = [valor for valor in valores if valor is not None]
    return sum(presentes, start=Decimal("0")) if presentes else None


class ExtratorNfseNacional:
    """Lê NFS-e nacional 1.0, com confiança 1.0."""

    motor = "nfelib"
    dialetos: tuple[Dialeto, ...] = (Dialeto.NFSE_NACIONAL_1_0,)

    def extrair(self, conteudo: bytes, arquivo: ArquivoOrigem) -> NotaFiscal:
        from nfelib.nfse.bindings.v1_0.nfse_v1_00 import Nfse

        inicio = time.perf_counter()
        coletor = Coletor(CONFIANCA["xml_oficial"])
        texto, _ = texto_de_xml(conteudo)
        inf = Nfse.from_xml(texto).infNFSe
        dps = inf.DPS.infDPS if inf.DPS is not None else None

        documento = self._documento(inf, dps, coletor)
        emitente = self._emitente(inf, coletor)
        destinatario = self._tomador(dps, coletor)
        totais = self._totais(inf, dps, coletor)
        itens = self._itens(dps, totais, coletor)

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
                requer_revisao=requer_revisao(confianca, []),
                duracao_ms=int((time.perf_counter() - inicio) * 1000),
                campos=coletor.campos,
            ),
        )

    def _documento(self, inf: Any, dps: Any, coletor: Coletor) -> Documento:
        bruto_id = _valor(inf.Id)
        chave = str(bruto_id).removeprefix(_PREFIXO_ID) if bruto_id else None
        cstat = _texto(inf.cStat)
        servico = getattr(dps, "serv", None) if dps is not None else None
        descricao = (
            _texto(getattr(servico.cServ, "xDescServ", None))
            if servico is not None and servico.cServ is not None
            else None
        )

        return Documento(
            tipo="nfse",
            chave_acesso=coletor.registrar("documento.chave_acesso", chave, "xml:/infNFSe@Id"),
            numero=coletor.registrar(
                "documento.numero", _texto(inf.nNFSe), "xml:/infNFSe/nNFSe"
            ),
            serie=coletor.registrar(
                "documento.serie",
                _texto(getattr(dps, "serie", None)),
                "xml:/infNFSe/DPS/infDPS/serie",
            ),
            data_emissao=coletor.registrar(
                "documento.data_emissao",
                para_data_hora(_valor(getattr(dps, "dhEmi", None))),
                "xml:/infNFSe/DPS/infDPS/dhEmi",
            ),
            data_competencia=coletor.registrar(
                "documento.data_competencia",
                para_data(_valor(getattr(dps, "dCompet", None))),
                "xml:/infNFSe/DPS/infDPS/dCompet",
            ),
            natureza_operacao=coletor.registrar(
                "documento.natureza_operacao",
                descricao,
                "xml:/infNFSe/DPS/infDPS/serv/cServ/xDescServ",
            ),
            situacao=SITUACAO_POR_CSTAT.get(cstat or "", "desconhecida"),
            protocolo_autorizacao=coletor.registrar(
                "documento.protocolo_autorizacao", _texto(inf.nDFSe), "xml:/infNFSe/nDFSe"
            ),
            municipio_prestacao=coletor.registrar(
                "documento.municipio_prestacao",
                _texto(inf.cLocIncid),
                "xml:/infNFSe/cLocIncid",
            ),
        )

    def _emitente(self, inf: Any, coletor: Coletor) -> Participante | None:
        emit = inf.emit
        if emit is None:
            return None
        raiz = "xml:/infNFSe/emit"
        return Participante(
            cnpj=coletor.registrar("emitente.cnpj", _texto(emit.CNPJ), f"{raiz}/CNPJ"),
            cpf=coletor.registrar(
                "emitente.cpf", _texto(getattr(emit, "CPF", None)), f"{raiz}/CPF"
            ),
            razao_social=coletor.registrar(
                "emitente.razao_social", _texto(emit.xNome), f"{raiz}/xNome"
            ),
            nome_fantasia=coletor.registrar(
                "emitente.nome_fantasia", _texto(getattr(emit, "xFant", None)), f"{raiz}/xFant"
            ),
            inscricao_municipal=coletor.registrar(
                "emitente.inscricao_municipal", _texto(emit.IM), f"{raiz}/IM"
            ),
            endereco=self._endereco(getattr(emit, "enderNac", None), "emitente", coletor, raiz),
        )

    def _tomador(self, dps: Any, coletor: Coletor) -> Participante | None:
        """Sem bloco ``toma`` não há destinatário; não inventa um."""
        toma = getattr(dps, "toma", None) if dps is not None else None
        if toma is None:
            return None
        raiz = "xml:/infNFSe/DPS/infDPS/toma"
        return Participante(
            cnpj=coletor.registrar(
                "destinatario.cnpj", _texto(getattr(toma, "CNPJ", None)), f"{raiz}/CNPJ"
            ),
            cpf=coletor.registrar(
                "destinatario.cpf", _texto(getattr(toma, "CPF", None)), f"{raiz}/CPF"
            ),
            razao_social=coletor.registrar(
                "destinatario.razao_social", _texto(getattr(toma, "xNome", None)), f"{raiz}/xNome"
            ),
            inscricao_municipal=coletor.registrar(
                "destinatario.inscricao_municipal",
                _texto(getattr(toma, "IM", None)),
                f"{raiz}/IM",
            ),
            endereco=self._endereco(
                getattr(toma, "end", None) or getattr(toma, "enderNac", None),
                "destinatario",
                coletor,
                raiz,
            ),
        )

    def _endereco(
        self, bloco: Any, papel: str, coletor: Coletor, raiz: str
    ) -> Endereco | None:
        if bloco is None:
            return None
        return Endereco(
            logradouro=coletor.registrar(
                f"{papel}.endereco.logradouro",
                _texto(getattr(bloco, "xLgr", None)),
                f"{raiz}/enderNac/xLgr",
            ),
            numero=coletor.registrar(
                f"{papel}.endereco.numero",
                _texto(getattr(bloco, "nro", None)),
                f"{raiz}/enderNac/nro",
            ),
            complemento=coletor.registrar(
                f"{papel}.endereco.complemento",
                _texto(getattr(bloco, "xCpl", None)),
                f"{raiz}/enderNac/xCpl",
            ),
            bairro=coletor.registrar(
                f"{papel}.endereco.bairro",
                _texto(getattr(bloco, "xBairro", None)),
                f"{raiz}/enderNac/xBairro",
            ),
            codigo_municipio_ibge=coletor.registrar(
                f"{papel}.endereco.codigo_municipio_ibge",
                _texto(getattr(bloco, "cMun", None)),
                f"{raiz}/enderNac/cMun",
            ),
            uf=coletor.registrar(
                f"{papel}.endereco.uf",
                _texto(getattr(bloco, "UF", None)),
                f"{raiz}/enderNac/UF",
            ),
            cep=coletor.registrar(
                f"{papel}.endereco.cep",
                _texto(getattr(bloco, "CEP", None)),
                f"{raiz}/enderNac/CEP",
            ),
        )

    def _totais(self, inf: Any, dps: Any, coletor: Coletor) -> Totais:
        nfse_valores = inf.valores
        dps_valores = getattr(dps, "valores", None) if dps is not None else None
        serv_prest = getattr(dps_valores, "vServPrest", None)
        descontos = getattr(dps_valores, "vDescCondIncond", None)
        trib = getattr(dps_valores, "trib", None)
        trib_mun = getattr(trib, "tribMun", None)
        trib_fed = getattr(trib, "tribFed", None)
        tot_trib = getattr(trib, "totTrib", None)
        raiz_dps = "xml:/infNFSe/DPS/infDPS/valores"

        return Totais(
            valor_servicos=coletor.registrar(
                "totais.valor_servicos",
                _dec(getattr(serv_prest, "vServ", None)),
                f"{raiz_dps}/vServPrest/vServ",
            ),
            desconto=coletor.registrar(
                "totais.desconto",
                _soma(
                    _dec(getattr(descontos, "vDescIncond", None)),
                    _dec(getattr(descontos, "vDescCond", None)),
                ),
                f"{raiz_dps}/vDescCondIncond",
            ),
            valor_total=coletor.registrar(
                "totais.valor_total",
                _dec(getattr(nfse_valores, "vLiq", None)),
                "xml:/infNFSe/valores/vLiq",
            ),
            tributos=Tributos(
                iss_valor=coletor.registrar(
                    "totais.tributos.iss_valor",
                    _dec(getattr(nfse_valores, "vISSQN", None)),
                    "xml:/infNFSe/valores/vISSQN",
                ),
                tributos_aproximados=coletor.registrar(
                    "totais.tributos.tributos_aproximados",
                    _dec(getattr(tot_trib, "vTotTrib", None)),
                    f"{raiz_dps}/trib/totTrib/vTotTrib",
                ),
                retencoes=Retencoes(
                    irrf=coletor.registrar(
                        "totais.tributos.retencoes.irrf",
                        _dec(getattr(trib_fed, "vRetIRRF", None)),
                        f"{raiz_dps}/trib/tribFed/vRetIRRF",
                    ),
                    csll=coletor.registrar(
                        "totais.tributos.retencoes.csll",
                        _dec(getattr(trib_fed, "vRetCSLL", None)),
                        f"{raiz_dps}/trib/tribFed/vRetCSLL",
                    ),
                    # vRetCP é a retenção de contribuição previdenciária (INSS).
                    inss=coletor.registrar(
                        "totais.tributos.retencoes.inss",
                        _dec(getattr(trib_fed, "vRetCP", None)),
                        f"{raiz_dps}/trib/tribFed/vRetCP",
                    ),
                    iss=coletor.registrar(
                        "totais.tributos.retencoes.iss",
                        _dec(getattr(trib_mun, "vRetISSQN", None)),
                        f"{raiz_dps}/trib/tribMun/vRetISSQN",
                    ),
                ),
            ),
        )

    def _itens(self, dps: Any, totais: Totais, coletor: Coletor) -> list[Item]:
        """O serviço inteiro vira um item único: NFS-e não tem lista de itens."""
        servico = getattr(dps, "serv", None) if dps is not None else None
        cserv = getattr(servico, "cServ", None) if servico is not None else None
        if cserv is None and totais.valor_servicos is None:
            return []
        raiz = "xml:/infNFSe/DPS/infDPS/serv/cServ"
        return [
            Item(
                ordem=1,
                codigo=coletor.registrar(
                    "itens[1].codigo",
                    _texto(getattr(cserv, "cTribNac", None)),
                    f"{raiz}/cTribNac",
                ),
                descricao=coletor.registrar(
                    "itens[1].descricao",
                    _texto(getattr(cserv, "xDescServ", None)),
                    f"{raiz}/xDescServ",
                ),
                cest=None,
                valor_total=coletor.registrar(
                    "itens[1].valor_total",
                    totais.valor_servicos,
                    f"{raiz}/../../valores/vServPrest/vServ",
                ),
            )
        ]
