# NF Scan

Serviço HTTP que lê uma nota fiscal brasileira em **qualquer formato** — XML,
PDF ou foto — e devolve **um único JSON padronizado**, com indicação de
confiança e de origem para cada campo. Roda 100% local: nenhum byte de nota sai
da máquina.

## O que é, e que problema resolve

Quem integra leitura de nota fiscal normalmente enfrenta três coisas ao mesmo
tempo: formatos diferentes (NF-e, NFS-e nacional, NFS-e municipal, DANFE
impresso, foto de cupom), layouts que variam por emissor e por prefeitura, e a
pergunta que nenhum leitor costuma responder — *posso confiar neste campo?*

O NF Scan resolve as três:

- **Um formato de saída.** Todo documento vira o mesmo JSON canônico, com os
  mesmos nomes de campo, independentemente de ter chegado como XML ou como foto.
- **Layout não quebra o serviço.** Em formatos não estruturados, a extração se
  ancora na chave de acesso de 44 dígitos — que tem dígito verificador e não
  depende de layout — e só depois recorre a âncoras de rótulo e coluna.
- **Cada campo diz quanto vale.** A resposta traz, por campo, a confiança e a
  proveniência (`xml:/infNFe/emit/CNPJ`, `chave:numero`, `regex:generico:frete`),
  mais uma lista de problemas e um `requer_revisao` booleano.

Esse último ponto é o que torna o serviço usável para **pré-preencher
formulários**: o sistema consumidor decide o que grava direto e o que manda para
conferência humana, campo a campo, em vez de confiar ou desconfiar do todo.

A resposta **sempre** vem completa. Nota ilegível não devolve erro HTTP: devolve
`200` com confiança baixa, `requer_revisao: true` e o motivo nos `problemas`.

## Notas fiscais contempladas

| Documento | Formato | Dialeto interno | Confiança | O que é extraído |
|---|---|---|---|---|
| **NF-e** (mercadoria, modelo 55) | XML 4.00 | `nfe_4.00` | **1.0** | Tudo: documento, emitente, destinatário, itens com impostos, totais, pagamento, transporte |
| **NFC-e** (consumidor, modelo 65) | XML 4.00 | `nfe_4.00` | **1.0** | Idem |
| **NFS-e nacional** (serviço) | XML 1.0 (padrão ADN) | `nfse_nacional_1.0` | **1.0** | Documento, prestador, tomador, serviço, valores e retenções federais e municipais |
| **NFS-e municipal** (serviço) | XML ABRASF 2.0x | `abrasf_2.0x` | 0.90 | Idem, conforme o que o layout do município traz |
| **DANFE** (representação impressa da NF-e) | PDF com camada de texto | `danfe_pdf` | 0.75 na chave, 0.50 nos demais | Chave, emitente, data, totais e tributos. **Sem itens** |
| **Cupom NFC-e / DANFE** | PDF-imagem ou foto (PNG, JPG, TIFF, BMP, GIF) | `nfce_cupom`, `danfe_pdf` | 0.50 na chave, 0.30 nos demais | Chave, emitente, data, totais em melhor esforço. **Sem itens** |

**Não contempla:** CT-e, MDF-e, BP-e, cupom não fiscal, recibo, fatura avulsa e
nota de outros países. Também não **emite** nota — o serviço só lê.

Sobre a NFS-e: o padrão nacional é obrigatório para todos os municípios desde
01/01/2026, mas notas antigas em layout municipal ABRASF continuam circulando
por anos, então os dois caminhos existem. Um layout municipal que fuja do ABRASF
cai no extrator tolerante com confiança reduzida, nunca em erro.

### A chave de acesso como âncora

Nos formatos não estruturados o sistema procura primeiro a **chave de acesso de
44 dígitos**. Ela é auto-descritiva — UF, período, CNPJ do emitente, modelo,
série e número — e tem dígito verificador mod-11. Uma chave cujo DV fecha foi
lida corretamente, mesmo vinda de uma foto, e por isso vale mais que o rótulo
impresso ao lado: **quando os dois discordam, vale a chave**. O campo registra
`origem: "chave:numero"` para você saber de onde veio.

A NFS-e nacional usa chave de 50 dígitos com estrutura própria, que não passa
por esse dígito verificador.

## Funcionalidades

- **Detecção automática de formato** pelo conteúdo do arquivo, nunca pela
  extensão — que o cliente erra com frequência.
- **Modelo canônico versionado** (`versao_schema`, hoje `1.1`), com JSON Schema
  exposto em `/v1/schema` para você gerar seus próprios tipos.
- **Confiança e proveniência por campo**, mais `confianca_global` e
  `requer_revisao`.
- **Validação cruzada**: dígito verificador da chave, CNPJ e CPF, soma dos itens
  contra o total de produtos, reconciliação do total do documento pela fórmula
  do tipo, coerência entre a data de emissão e o período gravado na chave.
- **Lote**: até 50 arquivos por requisição, ou um ZIP.
- **Perfis de emissor declarativos**: um layout peculiar é um arquivo YAML, sem
  tocar no código. Sem perfil cadastrado, o genérico ainda funciona.
- **Degradação sem exceção**: PDF corrompido, protegido por senha, XML truncado
  ou arquivo de zero byte devolvem nota vazia com o motivo, nunca `500`.
- **Dinheiro em `Decimal`**, serializado como string, nunca `float`.
- **Log estruturado sem conteúdo fiscal** — só dialeto, confiança, duração,
  sha256 e códigos de problema.
- **Stateless**: não persiste nada; quem guarda é o consumidor.

## Tecnologias utilizadas

| Tecnologia | Para quê | Por que esta |
|---|---|---|
| **Python 3.12** | Linguagem | Pinado em `>=3.12,<3.13`: versões mais novas ainda não têm wheel de `lxml`/`xsdata` |
| **[uv](https://docs.astral.sh/uv/)** | Dependências e ambiente | Resolve e instala o projeto inteiro, com lockfile |
| **[Pydantic](https://docs.pydantic.dev/) 2** | Modelo canônico, validação e JSON Schema | Serializa `Decimal` como string e gera o schema da rota `/v1/schema` |
| **[FastAPI](https://fastapi.tiangolo.com/)** + **Uvicorn** | Camada HTTP e OpenAPI | Casca fina; a documentação interativa sai de graça |
| **[nfelib](https://github.com/akretion/nfelib)** (MIT) | Bindings de NF-e 4.00 e NFS-e nacional 1.0 | Gerada por `xsdata` a partir dos XSD oficiais — não reescrevemos o layout à mão |
| **[lxml](https://lxml.de/)** | XPath tolerante para NFS-e municipal | Lê por nome local de tag, ignorando namespace, com `resolve_entities` e rede desligados |
| **poppler** (`pdftotext`, `pdftoppm`) | Texto de PDF e renderização de PDF-imagem | `pdftotext -layout` preserva as colunas; nada mais reproduz isso com fidelidade |
| **[pdfplumber](https://github.com/jsvine/pdfplumber)** | Alternativa quando o poppler falta | Modo `layout=True`, menos preciso nas colunas |
| **[Tesseract](https://github.com/tesseract-ocr/tesseract)** + **pytesseract** + **Pillow** | OCR de foto e PDF-imagem | Local, sem nuvem, com pacote de idioma português |
| **PyYAML** | Perfis de emissor | Perfil é dado, não código |
| **pytest**, **ruff**, **mypy --strict** | Qualidade | 228 testes, tipagem estrita |

Nenhuma dependência faz chamada de rede em tempo de execução, e nenhum teste
acessa a internet.

## Instalação

Precisa de Python 3.12, [uv](https://docs.astral.sh/uv/) e dois pacotes de
sistema:

```bash
# Arch / Omarchy
sudo pacman -S tesseract tesseract-data-por poppler

# Debian / Ubuntu
sudo apt install tesseract-ocr tesseract-ocr-por poppler-utils
```

```bash
uv sync --all-extras --group dev
uv run pytest
```

Sem o pacote `tesseract-data-por` o OCR cai para inglês, avisa com
`OCR_IDIOMA_AUSENTE` e perde precisão. Confira os idiomas instalados em
`GET /healthz`.

## Como rodar

```bash
NFSCAN_API_KEYS=minha-chave uv run uvicorn nfscan.api.app:app --port 8000
```

Com Docker, que já traz Tesseract em português e poppler, e roda sem privilégio:

```bash
docker build -t nfscan .
docker run --rm -e NFSCAN_API_KEYS=minha-chave -p 8000:8000 nfscan
```

`NFSCAN_API_KEYS` aceita várias chaves separadas por vírgula. Sem ela, as rotas
protegidas respondem `503`.

## Endpoints

Todos exigem o header `X-API-Key`, menos `/healthz`. Documentação interativa em
`/docs`; OpenAPI em `/openapi.json`.

| Método | Rota | Função |
|---|---|---|
| `POST` | `/v1/notas` | Um arquivo multipart (campo `arquivo`) → um JSON de nota |
| `POST` | `/v1/notas/lote` | Até 50 arquivos (campo `arquivos`), ou um ZIP → array de notas, na ordem do envio |
| `GET` | `/v1/schema` | JSON Schema do modelo canônico |
| `GET` | `/v1/dialetos` | Dialetos suportados e os limites vigentes |
| `GET` | `/healthz` | Vida do serviço, versão do Tesseract e idiomas de OCR instalados. Aberto |

```bash
# Uma nota
curl -H 'X-API-Key: minha-chave' -F 'arquivo=@nota.xml' \
  http://127.0.0.1:8000/v1/notas

# Lote com vários arquivos
curl -H 'X-API-Key: minha-chave' \
  -F 'arquivos=@nota1.xml' -F 'arquivos=@nota2.pdf' \
  http://127.0.0.1:8000/v1/notas/lote

# Lote com um ZIP
curl -H 'X-API-Key: minha-chave' -F 'arquivos=@notas.zip' \
  http://127.0.0.1:8000/v1/notas/lote

curl -H 'X-API-Key: minha-chave' http://127.0.0.1:8000/v1/schema
curl -H 'X-API-Key: minha-chave' http://127.0.0.1:8000/v1/dialetos
curl http://127.0.0.1:8000/healthz
```

### Códigos de resposta

| Código | Quando |
|---|---|
| `200` | O arquivo foi processado — **inclusive quando a leitura foi ruim**. A qualidade está em `confianca_global`, `problemas` e `requer_revisao` |
| `401` | `X-API-Key` ausente ou inválida |
| `413` | Arquivo acima de 20 MB, ou lote com mais de 50 arquivos |
| `422` | Requisição malformada (sem o campo de arquivo, por exemplo) |
| `503` | Servidor sem `NFSCAN_API_KEYS` configurada |

Qualidade de leitura não é erro de protocolo. Um `500` daqui é bug, não nota
ruim.

### Limites

20 MB por arquivo · 50 arquivos por lote · 50 entradas por ZIP · 10 páginas por
PDF-imagem no OCR, a 300 dpi, com 60 s de teto por página. Uma entrada de ZIP
acima do limite vira nota com `ENTRADA_GRANDE_DEMAIS` e **não** descarta as
demais notas do pacote.

## Como integrar

### 1. Gere seus tipos a partir do schema

`GET /v1/schema` devolve o JSON Schema do modelo. Use-o para gerar tipos no seu
projeto e para detectar mudança de contrato sem reler esta documentação.
`versao_schema` acompanha cada resposta.

### 2. Envie o arquivo

```python
import httpx

with open("nota.xml", "rb") as arquivo:
    resposta = httpx.post(
        "http://127.0.0.1:8000/v1/notas",
        files={"arquivo": ("nota.xml", arquivo, "application/xml")},
        headers={"X-API-Key": "minha-chave"},
        timeout=180,
    )
resposta.raise_for_status()
nota = resposta.json()
```

### 3. Decida campo a campo antes de gravar

Este é o passo que diferencia uma integração correta de uma que grava o que o
OCR adivinhou.

```python
LIMIAR = 0.85
CAMPOS_CRITICOS = ("emitente.cnpj", "documento.numero", "totais.valor_total")

campos = nota["extracao"]["campos"]
duvidosos = [
    campo
    for campo in CAMPOS_CRITICOS
    if campos.get(campo, {}).get("confianca", 0.0) < LIMIAR
]

if nota["extracao"]["requer_revisao"] or duvidosos:
    enviar_para_conferencia(nota, duvidosos)
else:
    gravar_lancamento(
        fornecedor=nota["emitente"]["razao_social"],
        cnpj=nota["emitente"]["cnpj"],
        numero=nota["documento"]["numero"],
        emissao=nota["documento"]["data_emissao"],
        # String, não float: converta para Decimal, nunca para float.
        valor=Decimal(nota["totais"]["valor_total"]),
    )
```

### 4. Trate os problemas pelo código, nunca pela mensagem

```python
for problema in nota["extracao"]["problemas"]:
    if problema["severidade"] == "erro":
        registrar_pendencia(problema["codigo"], problema["campo"])
```

O `codigo` é estável e faz parte do contrato; a `mensagem` é para humano e pode
mudar entre versões.

Há um exemplo executável completo em
[`exemplos/integrar.py`](exemplos/integrar.py), que imprime o lançamento
sugerido, nomeia os campos abaixo do limiar e sai com código 1 quando a nota
exige revisão.

## A resposta

```json
{
  "versao_schema": "1.1",
  "documento": {
    "tipo": "nfe", "modelo": "55",
    "chave_acesso": "35260911222333000181550010000012341123456787",
    "numero": "1234", "serie": "1",
    "data_emissao": "2026-09-14T10:32:00-03:00",
    "data_competencia": null,
    "natureza_operacao": "Venda de mercadoria",
    "finalidade": "normal", "situacao": "desconhecida",
    "protocolo_autorizacao": null, "municipio_prestacao": null
  },
  "emitente": {
    "cnpj": "11222333000181", "cpf": null,
    "razao_social": "Fornecedor de Materiais Ltda",
    "nome_fantasia": "Fornecedora",
    "inscricao_estadual": "123456789", "inscricao_municipal": null,
    "regime_tributario": "real",
    "endereco": { "logradouro": "Rua A", "numero": "100", "municipio": "Sao Paulo",
                  "codigo_municipio_ibge": "3550308", "uf": "SP", "cep": "01001000" }
  },
  "destinatario": { "cnpj": "11444777000161", "razao_social": "Construtora Exemplo Ltda" },
  "itens": [
    { "ordem": 1, "codigo": "MAT-001", "descricao": "Cimento CP-II 50kg",
      "ncm": "25232910", "cfop": "5102", "unidade": "SC",
      "quantidade": "100.0000", "valor_unitario": "38.5000", "valor_total": "3850.00",
      "impostos": { "icms": { "cst": "00", "base": "3850.00",
                              "aliquota": "18.00", "valor": "693.00" } } }
  ],
  "totais": {
    "valor_produtos": "5050.00", "valor_servicos": null,
    "desconto": "0.00", "frete": "150.00", "seguro": "0.00",
    "ipi": "0.00", "icms_st": "0.00", "valor_total": "5200.00",
    "tributos": { "icms_base": "5050.00", "icms_valor": "909.00",
                  "retencoes": null }
  },
  "pagamento": { "formas": [ { "tipo": "boleto", "valor": "5200.00" } ], "parcelas": [] },
  "transporte": { "modalidade_frete": "emitente", "volumes": [] },
  "informacoes_adicionais": "Obra Residencial Alfa - bloco 2",
  "extracao": {
    "dialeto": "nfe_4.00", "motor": "nfelib",
    "arquivo": { "nome": "nota.xml", "mime": "application/xml",
                 "bytes": 3495, "sha256": "df1dd7f8…" },
    "confianca_global": 1.0, "requer_revisao": false, "duracao_ms": 42,
    "campos": {
      "emitente.cnpj": { "confianca": 1.0, "origem": "xml:/infNFe/emit/CNPJ" },
      "totais.valor_total": { "confianca": 1.0, "origem": "xml:/infNFe/total/ICMSTot/vNF" }
    },
    "problemas": []
  }
}
```

**Dinheiro e quantidade vêm como string**, não número. `Decimal` serializado em
`float` perde centavo no consumidor, e nota fiscal é documento contábil.

**Campo ausente vem `null`, nunca omitido e nunca inventado.** Ausência é
informação.

## Como interpretar `confianca` e `requer_revisao`

`extracao.confianca_global` é a confiança do **elo mais fraco**: o mínimo entre
os campos extraídos. Acrescentar campo nunca sobe esse número, e ele nunca
afirma mais do que o campo menos confiável sustenta. Para decidir campo a campo,
use `extracao.campos["caminho.do.campo"]`.

`requer_revisao` é `true` quando a confiança global fica abaixo de **0.85** ou
quando existe algum problema de severidade `erro`. Trate como: *não grave sem
conferência humana*.

Faixas por origem do valor:

| Origem | Confiança |
|---|---|
| XML oficial (NF-e, NFS-e nacional) | 1.0 |
| XML municipal legado, lido por nome de tag | 0.90 |
| PDF, chave de acesso com DV válido | 0.75 |
| PDF, campo lido por âncora de rótulo ou de coluna | 0.50 |
| OCR, chave confirmada pelo DV | 0.50 |
| OCR, campo sem confirmação | 0.30 |

### Códigos de problema

Severidade `erro` (força `requer_revisao`): `ARQUIVO_ILEGIVEL`,
`EXTRACAO_FALHOU`, `CHAVE_INVALIDA`, `CHAVE_DV_INVALIDO`, `EMITENTE_AUSENTE`,
`CNPJ_EMITENTE_INVALIDO`, `CNPJ_DESTINATARIO_INVALIDO`, `VALOR_TOTAL_AUSENTE`,
`TOTAL_DIVERGENTE`, `ENTRADA_GRANDE_DEMAIS`, `OCR_INDISPONIVEL`.

Severidade `aviso`: `SOMA_ITENS_DIVERGENTE`, `DATA_INCOERENTE_COM_CHAVE`,
`CNPJ_ILEGIVEL`, `ITENS_NAO_EXTRAIDOS`, `MULTIPLAS_NOTAS_NO_ARQUIVO`,
`OCR_IDIOMA_AUSENTE`.

`TOTAL_DIVERGENTE` e `VALOR_TOTAL_AUSENTE` são **erro**, não aviso: o consumidor
vai lançar esse valor na contabilidade. A soma do documento é reconciliada pela
fórmula do próprio tipo — `vProd + vIPI + vST + vFrete + vSeg + vOutro − vDesc`
para mercadoria, e serviços menos deduções menos retenções para NFS-e, cujo
`ValorLiquidoNfse` a fórmula de mercadoria nunca reproduziria.

Essa conferência é a rede de segurança do OCR: se a leitura trocar um dígito de
valor, a soma não fecha e a nota sai com `TOTAL_DIVERGENTE`.

## Acrescentar um emissor de DANFE

Cada emissor com layout peculiar é um arquivo YAML em
`src/nfscan/extratores/ancoras/perfis/`, sem tocar no código. O perfil é
escolhido pelo maior número de marcadores presentes no texto; sem nenhum perfil
casando, o `generico` roda com confiança menor.

```yaml
nome: meu_emissor
marcadores: ["NOME QUE SO APARECE NESSE LAYOUT"]
campos:
  totais.valor_total:
    coluna: ["VALOR TOTAL DA NOTA"]   # rótulo acima, valor alinhado abaixo
  emitente.cnpj:
    regex: ["CNPJ[:\\s]*(\\d{14})"]   # rótulo e valor na mesma linha
```

Use `coluna` no bloco tabular do DANFE, onde os rótulos ficam numa linha e os
valores alinhados abaixo: a âncora casa o n-ésimo número com a n-ésima coluna do
cabeçalho, o que sobrevive ao deslocamento que o OCR introduz. Use `regex`
quando rótulo e valor estão juntos e não há coluna vizinha que confunda.

## Limitações declaradas

- **Não consulta a SEFAZ nem a prefeitura.** Por isso não valida autenticidade,
  e `documento.situacao` fica `desconhecida` fora do XML que já traz protocolo.
- **Itens não são extraídos de PDF nem de foto.** A lista vem vazia com o aviso
  `ITENS_NAO_EXTRAIDOS` — é limitação da leitura, não ausência de itens na nota.
  Extrair tabela de produtos exige um perfil por emissor, feito contra amostras
  reais.
- **A precisão do OCR em nota real é desconhecida.** As fixtures de PDF e de
  imagem são sintéticas e limpas: provam que o caminho funciona, não medem
  acerto em cupom amassado ou foto torta. Ponha notas de verdade em
  `tests/fixtures/` para medir.
- **O pacote de idioma muda o resultado de forma mensurável.** Na mesma imagem
  de teste, o Tesseract com `por` lê o valor do frete como `150,00`; com `eng`,
  `150,60` — e nesse caso a validação cruzada acusa `TOTAL_DIVERGENTE`. Instale
  `tesseract-data-por`, ou use a imagem Docker.
- **Um arquivo por nota.** Um envelope ABRASF `ConsultarNfseResposta` com várias
  notas tem só a primeira extraída, com o aviso `MULTIPLAS_NOTAS_NO_ARQUIVO`.
  Para ler várias, mande um ZIP em `/v1/notas/lote`.
- **Não emite nota, não persiste nada.** O serviço é *stateless*.
- O log registra métrica (dialeto, confiança, duração, sha256 e códigos de
  problema), **nunca conteúdo da nota**.

## Estrutura do projeto

```
src/nfscan/
  dominio/      chave de acesso, CNPJ/CPF, decimais, datas, UF, município, encoding
  modelo/       modelo canônico Pydantic, coletor de confiança e proveniência
  sniff/        detecção do container por conteúdo
  detect/       detecção do dialeto fiscal
  extratores/   um por dialeto, registrados em um registry
    ancoras/    motor de regex e de coluna, perfis YAML por emissor
    ocr/        pré-processo de imagem e Tesseract
  validar/      regras cruzadas
  pipeline.py   parse(bytes, nome) -> NotaFiscal
  api/          FastAPI
  log.py        log estruturado
```

O pipeline tem seis estágios:
`sniff → detect → extract → normalize → validate → NotaFiscal`.

## Desenvolvimento

```bash
uv run pytest            # suíte completa
uv run ruff check .      # lint
uv run mypy src          # tipagem estrita
```

Documentação de projeto em [`docs/`](docs/): a spec de
design e o plano de implementação.
