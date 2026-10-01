"""Extrator de NF-e e NFC-e 4.00 a partir do XML.

Usa os bindings da ``nfelib``, gerados dos XSD oficiais. É o caminho de
confiança 1.0: o XML é a única fonte de verdade do sistema, porque sem acesso
à SEFAZ nada mais pode ser confirmado.

Dois detalhes da ``nfelib`` que moldam o código: os valores numéricos chegam
como ``str`` e vários campos de domínio chegam como ``Enum``, então tudo passa
por :func:`_valor` antes de ser convertido. E todo número vai para
``para_decimal`` com ``formato="ponto_decimal"``, porque no XML o ponto é
sempre decimal — ``vUnCom`` aceita três decimais, e adivinhar "milhar" ali
multiplicaria o preço unitário por mil.
"""

from __future__ import annotations

import time
from decimal import Decimal
from enum import Enum
from typing import Any

from nfscan.detect.dialeto import Dialeto
from nfscan.dominio.chave import ChaveInvalida, parse_chave
from nfscan.dominio.codificacao import texto_de_xml
from nfscan.dominio.numeros import para_data_hora, para_decimal
from nfscan.dominio.textos import limpar_texto
from nfscan.modelo import (
    ArquivoOrigem,
    Documento,
    Endereco,
    Extracao,
    Finalidade,
    FormaPagamento,
    ImpostoItem,
    Impostos,
    Item,
    ModalidadeFrete,
    NotaFiscal,
    Pagamento,
    Participante,
    Problema,
    RegimeTributario,
    Situacao,
    TipoDocumento,
    TipoPagamento,
    Totais,
    Transporte,
    Tributos,
)
from nfscan.modelo.coletor import CONFIANCA, Coletor, requer_revisao

MODELO_PARA_TIPO: dict[str, TipoDocumento] = {"55": "nfe", "65": "nfce"}

FINALIDADE_POR_CODIGO: dict[str, Finalidade] = {
    "1": "normal",
    "2": "complementar",
    "3": "ajuste",
    "4": "devolucao",
}

REGIME_POR_CRT: dict[str, RegimeTributario] = {
    "1": "simples",
    "2": "simples",
    "3": "real",
    "4": "mei",
}

MODALIDADE_FRETE_POR_CODIGO: dict[str, ModalidadeFrete] = {
    "0": "emitente",
    "1": "destinatario",
    "2": "terceiros",
    "3": "emitente",
    "4": "destinatario",
    "9": "sem_frete",
}

# tPag do layout 4.00
PAGAMENTO_POR_CODIGO: dict[str, TipoPagamento] = {
    "01": "dinheiro",
    "02": "outro",
    "03": "credito",
    "04": "debito",
    "05": "prazo",
    "15": "boleto",
    "17": "pix",
    "99": "outro",
}

SITUACAO_POR_CSTAT: dict[str, Situacao] = {
    "100": "autorizada",
    "150": "autorizada",
    "101": "cancelada",
    "151": "cancelada",
    "110": "denegada",
    "301": "denegada",
    "302": "denegada",
    "303": "denegada",
}

_PREFIXO_ID = "NFe"


def _valor(bruto: Any) -> Any:
    """Desembrulha o ``Enum`` que o ``xsdata`` gera para campos de domínio."""
    return bruto.value if isinstance(bruto, Enum) else bruto


def _texto(bruto: Any) -> str | None:
    return limpar_texto(_valor(bruto))


def _dec(bruto: Any) -> Decimal | None:
    """Converte número de XML, onde o ponto é sempre decimal."""
    return para_decimal(_valor(bruto), formato="ponto_decimal")


def _grupo_icms(icms: Any) -> Any:
    """Primeiro grupo de ICMS preenchido.

    O layout 4.00 tem 21 grupos mutuamente exclusivos (ICMS00, ICMS10,
    ICMSSN101, ICMSPart, ICMSST...). Percorrer os campos da dataclass em vez de
    listá-los à mão evita que um grupo novo do layout passe em branco.
    """
    if icms is None:
        return None
    for nome in icms.__dataclass_fields__:
        grupo = getattr(icms, nome, None)
        if grupo is not None:
            return grupo
    return None


class ExtratorNfe:
    """Lê NF-e e NFC-e 4.00 do XML, com confiança 1.0."""

    motor = "nfelib"
    dialetos: tuple[Dialeto, ...] = (Dialeto.NFE_4_00,)

    def extrair(self, conteudo: bytes, arquivo: ArquivoOrigem) -> NotaFiscal:
        inicio = time.perf_counter()
        coletor = Coletor(CONFIANCA["xml_oficial"])
        problemas: list[Problema] = []

        inf, protocolo = self._carregar(conteudo)

        documento = self._documento(inf, protocolo, coletor, problemas)
        emitente = self._participante(inf.emit, "emitente", coletor, prefixo_endereco="enderEmit")
        destinatario = (
            self._participante(inf.dest, "destinatario", coletor, prefixo_endereco="enderDest")
            if inf.dest is not None
            else None
        )
        itens = [self._item(det, coletor) for det in (inf.det or [])]
        totais = self._totais(inf, coletor)
        pagamento = self._pagamento(inf, coletor)
        transporte = self._transporte(inf, coletor)
        adicionais = coletor.registrar(
            "informacoes_adicionais",
            _texto(inf.infAdic.infCpl) if inf.infAdic is not None else None,
            "xml:/infNFe/infAdic/infCpl",
        )

        confianca = coletor.confianca_global()
        return NotaFiscal(
            documento=documento,
            emitente=emitente,
            destinatario=destinatario,
            itens=itens,
            totais=totais,
            pagamento=pagamento,
            transporte=transporte,
            informacoes_adicionais=adicionais,
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

    def _carregar(self, conteudo: bytes) -> tuple[Any, Any]:
        """Aceita a raiz ``nfeProc`` ou a ``NFe`` solta.

        Emissores exportam das duas formas, e recusar uma delas rejeitaria XML
        legítimo.
        """
        from nfelib.nfe.bindings.v4_0.nfe_v4_00 import Nfe
        from nfelib.nfe.bindings.v4_0.proc_nfe_v4_00 import NfeProc

        texto, _ = texto_de_xml(conteudo)
        try:
            proc = NfeProc.from_xml(texto)
            if proc.NFe is not None:
                return proc.NFe.infNFe, proc.protNFe
        except Exception:
            pass
        return Nfe.from_xml(texto).infNFe, None

    def _documento(
        self, inf: Any, protocolo: Any, coletor: Coletor, problemas: list[Problema]
    ) -> Documento:
        ide = inf.ide
        modelo = coletor.registrar("documento.modelo", _texto(ide.mod), "xml:/infNFe/ide/mod")
        chave = self._chave(inf, coletor, problemas)

        return Documento(
            tipo=MODELO_PARA_TIPO.get(modelo or "", "desconhecido"),
            modelo=modelo,
            chave_acesso=chave,
            numero=coletor.registrar("documento.numero", _texto(ide.nNF), "xml:/infNFe/ide/nNF"),
            serie=coletor.registrar("documento.serie", _texto(ide.serie), "xml:/infNFe/ide/serie"),
            data_emissao=coletor.registrar(
                "documento.data_emissao",
                para_data_hora(_valor(ide.dhEmi)),
                "xml:/infNFe/ide/dhEmi",
            ),
            natureza_operacao=coletor.registrar(
                "documento.natureza_operacao", _texto(ide.natOp), "xml:/infNFe/ide/natOp"
            ),
            finalidade=FINALIDADE_POR_CODIGO.get(_texto(ide.finNFe) or "", "desconhecida"),
            situacao=self._situacao(protocolo, coletor),
            protocolo_autorizacao=self._protocolo(protocolo, coletor),
        )

    def _chave(self, inf: Any, coletor: Coletor, problemas: list[Problema]) -> str | None:
        """Lê a chave do atributo ``Id``, no formato ``NFe<44 dígitos>``.

        Chave com DV quebrado é registrada do mesmo jeito, com confiança
        rebaixada e um problema: descartar o valor lido tiraria do consumidor a
        única pista de qual nota é.
        """
        bruto = _valor(inf.Id)
        if not bruto:
            return None
        digitos = str(bruto).removeprefix(_PREFIXO_ID)
        try:
            parse_chave(digitos)
        except ChaveInvalida as erro:
            problemas.append(
                Problema(
                    severidade="erro",
                    codigo="CHAVE_INVALIDA",
                    campo="documento.chave_acesso",
                    mensagem=f"A chave gravada no atributo Id não é válida: {erro}.",
                )
            )
            return coletor.registrar(
                "documento.chave_acesso",
                digitos,
                "xml:/infNFe@Id",
                confianca=CONFIANCA["pdf_ancora"],
            )
        return coletor.registrar("documento.chave_acesso", digitos, "xml:/infNFe@Id")

    def _situacao(self, protocolo: Any, coletor: Coletor) -> Situacao:
        """Sem protocolo de autorização, a situação é desconhecida.

        O serviço roda local e não consulta a SEFAZ, então afirmar
        "autorizada" a partir do XML sozinho seria inventar.
        """
        if protocolo is None or getattr(protocolo, "infProt", None) is None:
            return "desconhecida"
        cstat = _texto(protocolo.infProt.cStat)
        situacao = SITUACAO_POR_CSTAT.get(cstat or "", "desconhecida")
        coletor.registrar("documento.situacao", situacao, "xml:/protNFe/infProt/cStat")
        return situacao

    def _protocolo(self, protocolo: Any, coletor: Coletor) -> str | None:
        if protocolo is None or getattr(protocolo, "infProt", None) is None:
            return None
        return coletor.registrar(
            "documento.protocolo_autorizacao",
            _texto(protocolo.infProt.nProt),
            "xml:/protNFe/infProt/nProt",
        )

    def _participante(
        self, bloco: Any, papel: str, coletor: Coletor, prefixo_endereco: str
    ) -> Participante:
        raiz = f"xml:/infNFe/{'emit' if papel == 'emitente' else 'dest'}"
        endereco_bruto = getattr(bloco, prefixo_endereco, None)
        crt = _texto(getattr(bloco, "CRT", None))

        return Participante(
            cnpj=coletor.registrar(f"{papel}.cnpj", _texto(bloco.CNPJ), f"{raiz}/CNPJ"),
            cpf=coletor.registrar(f"{papel}.cpf", _texto(bloco.CPF), f"{raiz}/CPF"),
            razao_social=coletor.registrar(
                f"{papel}.razao_social", _texto(bloco.xNome), f"{raiz}/xNome"
            ),
            nome_fantasia=coletor.registrar(
                f"{papel}.nome_fantasia", _texto(getattr(bloco, "xFant", None)), f"{raiz}/xFant"
            ),
            inscricao_estadual=coletor.registrar(
                f"{papel}.inscricao_estadual", _texto(getattr(bloco, "IE", None)), f"{raiz}/IE"
            ),
            inscricao_municipal=coletor.registrar(
                f"{papel}.inscricao_municipal", _texto(getattr(bloco, "IM", None)), f"{raiz}/IM"
            ),
            regime_tributario=REGIME_POR_CRT.get(crt or "", "desconhecido"),
            endereco=self._endereco(endereco_bruto, papel, coletor, f"{raiz}/{prefixo_endereco}"),
        )

    def _endereco(
        self, bloco: Any, papel: str, coletor: Coletor, raiz: str
    ) -> Endereco | None:
        if bloco is None:
            return None
        return Endereco(
            logradouro=coletor.registrar(
                f"{papel}.endereco.logradouro", _texto(bloco.xLgr), f"{raiz}/xLgr"
            ),
            numero=coletor.registrar(
                f"{papel}.endereco.numero", _texto(bloco.nro), f"{raiz}/nro"
            ),
            complemento=coletor.registrar(
                f"{papel}.endereco.complemento",
                _texto(getattr(bloco, "xCpl", None)),
                f"{raiz}/xCpl",
            ),
            bairro=coletor.registrar(
                f"{papel}.endereco.bairro", _texto(bloco.xBairro), f"{raiz}/xBairro"
            ),
            municipio=coletor.registrar(
                f"{papel}.endereco.municipio", _texto(bloco.xMun), f"{raiz}/xMun"
            ),
            codigo_municipio_ibge=coletor.registrar(
                f"{papel}.endereco.codigo_municipio_ibge", _texto(bloco.cMun), f"{raiz}/cMun"
            ),
            uf=coletor.registrar(f"{papel}.endereco.uf", _texto(bloco.UF), f"{raiz}/UF"),
            cep=coletor.registrar(
                f"{papel}.endereco.cep", _texto(getattr(bloco, "CEP", None)), f"{raiz}/CEP"
            ),
            pais=coletor.registrar(
                f"{papel}.endereco.pais", _texto(getattr(bloco, "xPais", None)), f"{raiz}/xPais"
            ),
            telefone=coletor.registrar(
                f"{papel}.endereco.telefone", _texto(getattr(bloco, "fone", None)), f"{raiz}/fone"
            ),
        )

    def _item(self, det: Any, coletor: Coletor) -> Item:
        prod = det.prod
        ordem = int(_valor(det.nItem) or 0)
        raiz = f"xml:/infNFe/det[{ordem}]/prod"
        return Item(
            ordem=ordem,
            codigo=coletor.registrar(f"itens[{ordem}].codigo", _texto(prod.cProd), f"{raiz}/cProd"),
            descricao=coletor.registrar(
                f"itens[{ordem}].descricao", _texto(prod.xProd), f"{raiz}/xProd"
            ),
            ncm=coletor.registrar(f"itens[{ordem}].ncm", _texto(prod.NCM), f"{raiz}/NCM"),
            cest=coletor.registrar(
                f"itens[{ordem}].cest", _texto(getattr(prod, "CEST", None)), f"{raiz}/CEST"
            ),
            cfop=coletor.registrar(f"itens[{ordem}].cfop", _texto(prod.CFOP), f"{raiz}/CFOP"),
            unidade=coletor.registrar(
                f"itens[{ordem}].unidade", _texto(prod.uCom), f"{raiz}/uCom"
            ),
            quantidade=coletor.registrar(
                f"itens[{ordem}].quantidade", _dec(prod.qCom), f"{raiz}/qCom"
            ),
            valor_unitario=coletor.registrar(
                f"itens[{ordem}].valor_unitario", _dec(prod.vUnCom), f"{raiz}/vUnCom"
            ),
            valor_total=coletor.registrar(
                f"itens[{ordem}].valor_total", _dec(prod.vProd), f"{raiz}/vProd"
            ),
            desconto=coletor.registrar(
                f"itens[{ordem}].desconto", _dec(getattr(prod, "vDesc", None)), f"{raiz}/vDesc"
            ),
            frete=coletor.registrar(
                f"itens[{ordem}].frete", _dec(getattr(prod, "vFrete", None)), f"{raiz}/vFrete"
            ),
            impostos=self._impostos(det, ordem, coletor),
        )

    def _impostos(self, det: Any, ordem: int, coletor: Coletor) -> Impostos | None:
        imposto = getattr(det, "imposto", None)
        if imposto is None:
            return None
        return Impostos(
            icms=self._icms(imposto, ordem, coletor),
            ipi=self._imposto_simples(getattr(imposto, "IPI", None), ordem, "ipi", coletor),
            pis=self._imposto_simples(getattr(imposto, "PIS", None), ordem, "pis", coletor),
            cofins=self._imposto_simples(
                getattr(imposto, "COFINS", None), ordem, "cofins", coletor
            ),
            iss=self._imposto_simples(getattr(imposto, "ISSQN", None), ordem, "iss", coletor),
        )

    def _icms(self, imposto: Any, ordem: int, coletor: Coletor) -> ImpostoItem | None:
        grupo = _grupo_icms(getattr(imposto, "ICMS", None))
        if grupo is None:
            return None
        raiz = f"xml:/infNFe/det[{ordem}]/imposto/ICMS"
        base = f"itens[{ordem}].impostos.icms"
        # Regime normal grava CST; Simples Nacional grava CSOSN.
        cst = _texto(getattr(grupo, "CST", None)) or _texto(getattr(grupo, "CSOSN", None))
        return ImpostoItem(
            cst=coletor.registrar(f"{base}.cst", cst, f"{raiz}/CST|CSOSN"),
            base=coletor.registrar(
                f"{base}.base", _dec(getattr(grupo, "vBC", None)), f"{raiz}/vBC"
            ),
            aliquota=coletor.registrar(
                f"{base}.aliquota", _dec(getattr(grupo, "pICMS", None)), f"{raiz}/pICMS"
            ),
            valor=coletor.registrar(
                f"{base}.valor", _dec(getattr(grupo, "vICMS", None)), f"{raiz}/vICMS"
            ),
        )

    def _imposto_simples(
        self, bloco: Any, ordem: int, nome: str, coletor: Coletor
    ) -> ImpostoItem | None:
        """Lê IPI, PIS, COFINS e ISSQN, cujos grupos variam por CST.

        Procura o primeiro subgrupo preenchido, pelo mesmo motivo do ICMS.
        """
        if bloco is None:
            return None
        grupo = bloco
        if hasattr(bloco, "__dataclass_fields__"):
            for campo in bloco.__dataclass_fields__:
                candidato = getattr(bloco, campo, None)
                if candidato is not None and hasattr(candidato, "__dataclass_fields__"):
                    grupo = candidato
                    break
        raiz = f"xml:/infNFe/det[{ordem}]/imposto/{nome.upper()}"
        base = f"itens[{ordem}].impostos.{nome}"
        valor = _dec(getattr(grupo, f"v{nome.upper()}", None))
        aliquota = _dec(getattr(grupo, f"p{nome.upper()}", None))
        cst = _texto(getattr(grupo, "CST", None))
        if valor is None and aliquota is None and cst is None:
            return None
        return ImpostoItem(
            cst=coletor.registrar(f"{base}.cst", cst, f"{raiz}/CST"),
            base=coletor.registrar(
                f"{base}.base", _dec(getattr(grupo, "vBC", None)), f"{raiz}/vBC"
            ),
            aliquota=coletor.registrar(f"{base}.aliquota", aliquota, f"{raiz}/p{nome.upper()}"),
            valor=coletor.registrar(f"{base}.valor", valor, f"{raiz}/v{nome.upper()}"),
        )

    def _totais(self, inf: Any, coletor: Coletor) -> Totais | None:
        total = getattr(inf, "total", None)
        tot = getattr(total, "ICMSTot", None) if total is not None else None
        if tot is None:
            return None
        raiz = "xml:/infNFe/total/ICMSTot"
        return Totais(
            valor_produtos=coletor.registrar(
                "totais.valor_produtos", _dec(tot.vProd), f"{raiz}/vProd"
            ),
            valor_servicos=coletor.registrar(
                "totais.valor_servicos", _dec(getattr(tot, "vServ", None)), f"{raiz}/vServ"
            ),
            desconto=coletor.registrar("totais.desconto", _dec(tot.vDesc), f"{raiz}/vDesc"),
            frete=coletor.registrar("totais.frete", _dec(tot.vFrete), f"{raiz}/vFrete"),
            seguro=coletor.registrar("totais.seguro", _dec(tot.vSeg), f"{raiz}/vSeg"),
            outras_despesas=coletor.registrar(
                "totais.outras_despesas", _dec(tot.vOutro), f"{raiz}/vOutro"
            ),
            ipi=coletor.registrar("totais.ipi", _dec(getattr(tot, "vIPI", None)), f"{raiz}/vIPI"),
            icms_st=coletor.registrar(
                "totais.icms_st", _dec(getattr(tot, "vST", None)), f"{raiz}/vST"
            ),
            valor_total=coletor.registrar("totais.valor_total", _dec(tot.vNF), f"{raiz}/vNF"),
            tributos=Tributos(
                icms_base=coletor.registrar(
                    "totais.tributos.icms_base", _dec(tot.vBC), f"{raiz}/vBC"
                ),
                icms_valor=coletor.registrar(
                    "totais.tributos.icms_valor", _dec(tot.vICMS), f"{raiz}/vICMS"
                ),
                tributos_aproximados=coletor.registrar(
                    "totais.tributos.tributos_aproximados",
                    _dec(getattr(tot, "vTotTrib", None)),
                    f"{raiz}/vTotTrib",
                ),
            ),
        )

    def _pagamento(self, inf: Any, coletor: Coletor) -> Pagamento | None:
        pag = getattr(inf, "pag", None)
        if pag is None or not getattr(pag, "detPag", None):
            return None
        formas = []
        for indice, det in enumerate(pag.detPag, start=1):
            codigo = _texto(det.tPag)
            formas.append(
                FormaPagamento(
                    tipo=PAGAMENTO_POR_CODIGO.get(codigo or "", "outro"),
                    valor=coletor.registrar(
                        f"pagamento.formas[{indice}].valor",
                        _dec(det.vPag),
                        f"xml:/infNFe/pag/detPag[{indice}]/vPag",
                    ),
                )
            )
        return Pagamento(formas=formas)

    def _transporte(self, inf: Any, coletor: Coletor) -> Transporte | None:
        transp = getattr(inf, "transp", None)
        if transp is None:
            return None
        codigo = coletor.registrar(
            "transporte.modalidade_frete", _texto(transp.modFrete), "xml:/infNFe/transp/modFrete"
        )
        return Transporte(
            modalidade_frete=MODALIDADE_FRETE_POR_CODIGO.get(codigo or "", "desconhecida")
        )
