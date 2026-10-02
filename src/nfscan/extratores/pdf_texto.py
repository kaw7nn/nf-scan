"""Extrator de DANFE e cupom a partir do texto do PDF.

A decisão de projeto central está em :func:`extrair_de_texto`: **a chave de
acesso vence o layout**. A chave tem dígito verificador mod-11, então uma chave
que fecha foi lida certa; o rótulo impresso ao lado não tem como ser
verificado. Quando os dois discordam, vale a chave, e o campo registra
``origem="chave:..."`` para o consumidor saber de onde veio.

A mesma função serve o OCR da camada de imagem, com confiança base menor.
"""

from __future__ import annotations

import time
from decimal import Decimal

from nfscan.detect.dialeto import Dialeto
from nfscan.dominio.chave import ChaveAcesso, chave_rejeitada, extrair_chave
from nfscan.dominio.documentos import normalizar_cnpj_cpf
from nfscan.dominio.numeros import para_data_hora, para_decimal
from nfscan.dominio.textos import limpar_texto
from nfscan.extratores.ancoras.motor import aplicar, carregar_perfis, escolher_perfil
from nfscan.modelo import (
    ArquivoOrigem,
    Documento,
    Extracao,
    NotaFiscal,
    Participante,
    Problema,
    TipoDocumento,
    Totais,
    Tributos,
)
from nfscan.modelo.coletor import CONFIANCA, Coletor, requer_revisao
from nfscan.sniff.container import texto_de_pdf

MODELO_PARA_TIPO: dict[str, TipoDocumento] = {"55": "nfe", "65": "nfce"}


def _sem_zeros(valor: str | None) -> str | None:
    """Remove zeros à esquerda sem transformar "000" em string vazia."""
    if valor is None:
        return None
    limpo = valor.lstrip("0")
    return limpo or "0"


def _numero_normalizado(valor: str | None) -> str | None:
    """Descarta pontuação de milhar e zeros à esquerda do número impresso.

    Emissores imprimem o número de formas diferentes: ``12345``, ``000.012.345``,
    ``000012345``. Todas designam a mesma nota, e o consumidor precisa de uma.
    """
    if valor is None:
        return None
    digitos = "".join(caractere for caractere in valor if caractere.isdigit())
    return _sem_zeros(digitos) if digitos else None


def _dec(bruto: str | None) -> Decimal | None:
    """Texto impresso usa o formato brasileiro, então o formato é "auto"."""
    return para_decimal(bruto, formato="auto")


def _campos_da_chave(
    chave: ChaveAcesso, coletor: Coletor, confianca: float
) -> tuple[str, TipoDocumento]:
    """Registra os sete campos que a chave entrega de graça."""
    coletor.registrar("documento.chave_acesso", chave.valor, "chave:valor", confianca=confianca)
    coletor.registrar("documento.modelo", chave.modelo, "chave:modelo", confianca=confianca)
    coletor.registrar(
        "documento.numero", _sem_zeros(chave.numero), "chave:numero", confianca=confianca
    )
    coletor.registrar(
        "documento.serie", _sem_zeros(chave.serie), "chave:serie", confianca=confianca
    )
    coletor.registrar(
        "emitente.cnpj", chave.cnpj_emitente, "chave:cnpj_emitente", confianca=confianca
    )
    return chave.modelo, MODELO_PARA_TIPO.get(chave.modelo, "desconhecido")


def extrair_de_texto(
    texto: str,
    arquivo: ArquivoOrigem,
    dialeto: Dialeto,
    confianca_base: float,
    motor: str,
    confianca_chave: float | None = None,
) -> NotaFiscal:
    """Monta a nota a partir de texto livre: chave primeiro, perfil depois.

    ``confianca_chave`` permite ao OCR declarar confiança maior para a chave do
    que para o resto, porque o mod-11 é verificação independente: uma chave que
    fecha foi lida certa, mesmo vinda de uma foto.
    """
    inicio = time.perf_counter()
    coletor = Coletor(confianca_base)
    problemas: list[Problema] = []
    peso_chave = CONFIANCA["pdf_chave"] if confianca_chave is None else confianca_chave

    if not texto.strip():
        problemas.append(
            Problema(
                severidade="erro",
                codigo="ARQUIVO_ILEGIVEL",
                campo=None,
                mensagem="Não foi possível extrair texto do arquivo.",
            )
        )
        return _montar(
            Documento(), None, None, None, coletor, problemas, arquivo, dialeto, motor, inicio
        )

    chave = extrair_chave(texto)
    modelo: str | None = None
    tipo: TipoDocumento = "desconhecido"
    if chave is not None:
        modelo, tipo = _campos_da_chave(chave, coletor, peso_chave)
    else:
        _relatar_chave_rejeitada(texto, problemas)

    perfil = escolher_perfil(texto, carregar_perfis())
    valores = aplicar(perfil, texto)

    def do_perfil(campo: str) -> str | None:
        """Só usa o perfil quando o campo ainda não veio da chave."""
        if campo in coletor.campos:
            return None
        return valores.get(campo)

    documento = Documento(
        tipo=tipo,
        modelo=modelo,
        chave_acesso=chave.valor if chave is not None else None,
        numero=_sem_zeros(chave.numero)
        if chave is not None
        else coletor.registrar(
            "documento.numero",
            _numero_normalizado(do_perfil("documento.numero")),
            f"regex:{perfil.nome}:numero",
        ),
        serie=_sem_zeros(chave.serie)
        if chave is not None
        else coletor.registrar(
            "documento.serie", do_perfil("documento.serie"), f"regex:{perfil.nome}:serie"
        ),
        data_emissao=coletor.registrar(
            "documento.data_emissao",
            para_data_hora(valores.get("documento.data_emissao")),
            f"regex:{perfil.nome}:data_emissao",
        ),
        natureza_operacao=coletor.registrar(
            "documento.natureza_operacao",
            limpar_texto(valores.get("documento.natureza_operacao")),
            f"regex:{perfil.nome}:natureza_operacao",
        ),
        # Sem consulta à SEFAZ, um PDF não prova que a nota está autorizada.
        situacao="desconhecida",
    )

    emitente = _emitente(chave, valores, perfil.nome, coletor, problemas)
    totais = _totais(valores, perfil.nome, coletor)
    adicionais = coletor.registrar(
        "informacoes_adicionais",
        limpar_texto(valores.get("informacoes_adicionais")),
        f"regex:{perfil.nome}:informacoes_adicionais",
    )

    problemas.append(
        Problema(
            severidade="aviso",
            codigo="ITENS_NAO_EXTRAIDOS",
            campo="itens",
            mensagem=(
                "A lista de itens não foi extraída deste formato. A lista vazia é "
                "limitação da leitura, não ausência de itens na nota."
            ),
        )
    )

    return _montar(
        documento, emitente, totais, adicionais, coletor, problemas, arquivo, dialeto, motor, inicio
    )


def _relatar_chave_rejeitada(texto: str, problemas: list[Problema]) -> None:
    """Explica a ausência da chave quando havia uma candidata com DV quebrado.

    Sem isso o campo some em silêncio, e quem integra não consegue distinguir
    "o documento não traz chave" de "a chave está corrompida" — que pedem ações
    diferentes: a primeira é limitação do formato, a segunda é documento
    suspeito ou leitura ruim.
    """
    rejeitada = chave_rejeitada(texto)
    if rejeitada is None:
        return
    problemas.append(
        Problema(
            severidade="erro",
            codigo="CHAVE_DV_INVALIDO",
            campo="documento.chave_acesso",
            mensagem=(
                f"Foi encontrada uma sequência de 44 dígitos cujo dígito verificador "
                f"não confere, e por isso ela não foi aceita como chave de acesso: "
                f"{rejeitada}."
            ),
        )
    )


def _emitente(
    chave: ChaveAcesso | None,
    valores: dict[str, str],
    perfil: str,
    coletor: Coletor,
    problemas: list[Problema],
) -> Participante | None:
    cnpj = chave.cnpj_emitente if chave is not None else None
    if cnpj is None:
        bruto = valores.get("emitente.cnpj")
        if bruto is not None:
            cnpj, cpf = normalizar_cnpj_cpf(bruto)
            if cnpj is None and cpf is None:
                problemas.append(
                    Problema(
                        severidade="aviso",
                        codigo="CNPJ_ILEGIVEL",
                        campo="emitente.cnpj",
                        mensagem=(
                            f"O identificador lido para o emitente não passou no dígito "
                            f"verificador e foi descartado: {bruto}."
                        ),
                    )
                )
            else:
                coletor.registrar("emitente.cnpj", cnpj or cpf, f"regex:{perfil}:cnpj")

    inscricao = coletor.registrar(
        "emitente.inscricao_estadual",
        limpar_texto(valores.get("emitente.inscricao_estadual")),
        f"regex:{perfil}:inscricao_estadual",
    )
    if cnpj is None and inscricao is None:
        return None
    return Participante(cnpj=cnpj, inscricao_estadual=inscricao)


def _totais(valores: dict[str, str], perfil: str, coletor: Coletor) -> Totais | None:
    total = coletor.registrar(
        "totais.valor_total", _dec(valores.get("totais.valor_total")), f"regex:{perfil}:valor_total"
    )
    produtos = coletor.registrar(
        "totais.valor_produtos",
        _dec(valores.get("totais.valor_produtos")),
        f"regex:{perfil}:valor_produtos",
    )
    if total is None and produtos is None:
        return None
    return Totais(
        valor_produtos=produtos,
        valor_total=total,
        frete=coletor.registrar(
            "totais.frete", _dec(valores.get("totais.frete")), f"regex:{perfil}:frete"
        ),
        desconto=coletor.registrar(
            "totais.desconto", _dec(valores.get("totais.desconto")), f"regex:{perfil}:desconto"
        ),
        seguro=coletor.registrar(
            "totais.seguro", _dec(valores.get("totais.seguro")), f"regex:{perfil}:seguro"
        ),
        tributos=Tributos(
            icms_base=coletor.registrar(
                "totais.tributos.icms_base",
                _dec(valores.get("tributos.icms_base")),
                f"regex:{perfil}:icms_base",
            ),
            icms_valor=coletor.registrar(
                "totais.tributos.icms_valor",
                _dec(valores.get("tributos.icms_valor")),
                f"regex:{perfil}:icms_valor",
            ),
        ),
    )


def _montar(
    documento: Documento,
    emitente: Participante | None,
    totais: Totais | None,
    adicionais: str | None,
    coletor: Coletor,
    problemas: list[Problema],
    arquivo: ArquivoOrigem,
    dialeto: Dialeto,
    motor: str,
    inicio: float,
) -> NotaFiscal:
    confianca = coletor.confianca_global()
    return NotaFiscal(
        documento=documento,
        emitente=emitente,
        totais=totais,
        informacoes_adicionais=adicionais,
        extracao=Extracao(
            dialeto=dialeto.value,
            motor=motor,
            arquivo=arquivo,
            confianca_global=confianca,
            requer_revisao=requer_revisao(confianca, problemas),
            duracao_ms=int((time.perf_counter() - inicio) * 1000),
            campos=coletor.campos,
            problemas=problemas,
        ),
    )


class ExtratorPdfTexto:
    """Lê DANFE e cupom de PDF que tem camada de texto."""

    motor = "ancoras_pdf"
    dialetos: tuple[Dialeto, ...] = (Dialeto.DANFE_PDF, Dialeto.NFCE_CUPOM)

    def extrair(
        self, conteudo: bytes, arquivo: ArquivoOrigem, texto: str | None = None
    ) -> NotaFiscal:
        if texto is None:
            texto = texto_de_pdf(conteudo)
        dialeto = Dialeto.NFCE_CUPOM if "CUPOM" in texto.upper() else Dialeto.DANFE_PDF
        return extrair_de_texto(
            texto, arquivo, dialeto, CONFIANCA["pdf_ancora"], self.motor
        )
