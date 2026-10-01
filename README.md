# NF Scan

Lê notas fiscais brasileiras em qualquer formato e devolve um JSON padronizado,
com **confiança e proveniência por campo**. Roda 100% local: nenhum byte de nota
sai da máquina.

## Por que a confiança por campo importa

Um leitor de nota que só diz "deu certo" é inútil para quem vai pré-preencher um
formulário. O NF Scan devolve, para cada campo, de onde o valor veio e quanto se
pode confiar nele, mais uma lista de problemas encontrados. Com isso o seu
sistema decide o que grava direto e o que manda para conferência humana.

A resposta **sempre** vem completa. Nota ilegível não dá erro HTTP: dá `200`
com `confianca_global` baixa, `requer_revisao: true` e o motivo nos `problemas`.

## Formatos suportados

| Formato | Confiança | O que sai |
|---|---|---|
| NF-e / NFC-e em XML 4.00 | **1.0** | Tudo: documento, emitente, destinatário, itens com impostos, totais, pagamento, transporte |
| NFS-e nacional 1.0 (XML) | **1.0** | Documento, prestador, tomador, serviço, valores e retenções |
| NFS-e municipal ABRASF 2.0x (XML) | 0.90 | Idem, conforme o que o layout do município traz |
| DANFE em PDF com camada de texto | 0.75 na chave, 0.50 nos demais | Chave, emitente, data, totais. **Sem itens** |
| Foto ou PDF-imagem | 0.50 na chave, 0.30 nos demais | Chave, emitente, data, totais em melhor esforço. **Sem itens** |

XML é a única fonte de verdade. Como o serviço não consulta a SEFAZ, em PDF e
foto a extração é sempre por inferência e `documento.situacao` fica
`desconhecida`.

### A chave de acesso como âncora

Nos formatos não estruturados o sistema procura primeiro a **chave de acesso de
44 dígitos**. Ela é auto-descritiva — UF, período, CNPJ do emitente, modelo,
série e número — e tem dígito verificador mod-11. Uma chave cujo DV fecha foi
lida corretamente, mesmo vinda de uma foto, e por isso vale mais que o rótulo
impresso ao lado: **quando os dois discordam, vale a chave**. O campo registra
`origem: "chave:numero"` para você saber.

A NFS-e nacional usa chave de 50 dígitos com estrutura própria, que não passa
por esse dígito verificador.

## Instalação

Precisa de Python 3.12, [uv](https://docs.astral.sh/uv/), e dois pacotes de
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
`OCR_IDIOMA_AUSENTE` e perde precisão em texto acentuado. Dígitos e rótulos em
caixa alta continuam legíveis. Confira com `GET /healthz`.

## Rodando

```bash
NFSCAN_API_KEYS=minha-chave uv run uvicorn nfscan.api.app:app --port 8000
```

Com Docker, que já traz o Tesseract em português e o poppler:

```bash
docker build -t nfscan .
docker run --rm -e NFSCAN_API_KEYS=minha-chave -p 8000:8000 nfscan
```

`NFSCAN_API_KEYS` aceita várias chaves separadas por vírgula. Sem ela, as rotas
respondem `503`.

## Rotas

Todas exigem o header `X-API-Key`, menos `/healthz`.

```bash
# Uma nota
curl -H 'X-API-Key: minha-chave' -F 'arquivo=@nota.xml' \
  http://127.0.0.1:8000/v1/notas

# Lote: vários arquivos ou um ZIP (até 50)
curl -H 'X-API-Key: minha-chave' \
  -F 'arquivos=@nota1.xml' -F 'arquivos=@nota2.pdf' \
  http://127.0.0.1:8000/v1/notas/lote

# JSON Schema do modelo canônico, para gerar seus tipos
curl -H 'X-API-Key: minha-chave' http://127.0.0.1:8000/v1/schema

# Dialetos suportados e limites
curl -H 'X-API-Key: minha-chave' http://127.0.0.1:8000/v1/dialetos

# Vida do serviço, versão do Tesseract e idiomas de OCR instalados
curl http://127.0.0.1:8000/healthz
```

Documentação interativa em `http://127.0.0.1:8000/docs`.

Códigos de resposta: `200` sempre que o arquivo foi processado, **inclusive
quando a leitura foi ruim**; `401` sem chave válida; `413` acima de 20 MB ou com
lote maior que 50; `422` requisição malformada; `503` servidor sem
`NFSCAN_API_KEYS`.

## A resposta

```json
{
  "versao_schema": "1.0",
  "documento": {
    "tipo": "nfe", "modelo": "55",
    "chave_acesso": "35260911222333000181550010000012341123456787",
    "numero": "1234", "serie": "1",
    "data_emissao": "2026-09-14T10:32:00-03:00",
    "natureza_operacao": "Venda de mercadoria",
    "finalidade": "normal", "situacao": "desconhecida"
  },
  "emitente": { "cnpj": "11222333000181", "razao_social": "Fornecedor de Materiais Ltda", "...": null },
  "destinatario": { "cnpj": "11444777000161", "...": null },
  "itens": [
    { "ordem": 1, "codigo": "MAT-001", "descricao": "Cimento CP-II 50kg",
      "ncm": "25232910", "cfop": "5102", "unidade": "SC",
      "quantidade": "100.0000", "valor_unitario": "38.5000", "valor_total": "3850.00",
      "impostos": { "icms": { "cst": "00", "aliquota": "18.00", "valor": "693.00" } } }
  ],
  "totais": { "valor_produtos": "5050.00", "frete": "150.00", "valor_total": "5200.00" },
  "extracao": {
    "dialeto": "nfe_4.00", "motor": "nfelib",
    "confianca_global": 1.0,
    "requer_revisao": false,
    "campos": {
      "emitente.cnpj": { "confianca": 1.0, "origem": "xml:/infNFe/emit/CNPJ" }
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

Esta é a parte que o integrador precisa entender.

`extracao.confianca_global` é a média das confianças dos campos efetivamente
extraídos. `extracao.campos["caminho.do.campo"]` dá a confiança e a proveniência
de cada um, e é por aí que você decide campo a campo.

`requer_revisao` é `true` quando a confiança global fica abaixo de **0.85** ou
quando existe algum problema de severidade `erro`. Trate como: *não grave sem
conferência humana*.

As faixas, por origem do valor:

| Origem | Confiança |
|---|---|
| XML oficial | 1.0 |
| XML municipal legado, lido por nome de tag | 0.90 |
| PDF, chave de acesso com DV válido | 0.75 |
| PDF, campo lido por âncora de rótulo ou coluna | 0.50 |
| OCR, chave confirmada pelo DV | 0.50 |
| OCR, campo sem confirmação | 0.30 |

`extracao.problemas` traz achados da validação cruzada. O `codigo` é estável e
serve para tratar em código; a `mensagem` é para humano e pode mudar.

Códigos: `ARQUIVO_ILEGIVEL`, `EXTRACAO_FALHOU`, `CHAVE_INVALIDA`,
`CHAVE_DV_INVALIDO`, `EMITENTE_AUSENTE`, `CNPJ_EMITENTE_INVALIDO`,
`CNPJ_DESTINATARIO_INVALIDO`, `CNPJ_ILEGIVEL`, `SOMA_ITENS_DIVERGENTE`,
`TOTAL_DIVERGENTE`, `VALOR_TOTAL_AUSENTE`, `DATA_INCOERENTE_COM_CHAVE`,
`ITENS_NAO_EXTRAIDOS`, `OCR_IDIOMA_AUSENTE`, `OCR_INDISPONIVEL`.

A validação cruzada é a rede de segurança do OCR. Se a leitura trocar um dígito
de valor, a soma não fecha e sai `TOTAL_DIVERGENTE` — foi assim que um
`150,00` lido como `150,60` apareceu nos testes.

Há um exemplo completo de consumo em
[`exemplos/integrar.py`](exemplos/integrar.py).

## Acrescentar um emissor de DANFE

Cada emissor com layout peculiar é um arquivo YAML em
`src/nfscan/extratores/ancoras/perfis/`, sem tocar no código. Sem perfil
cadastrado o perfil `generico` ainda roda, com confiança menor.

```yaml
nome: meu_emissor
marcadores: ["NOME QUE SÓ APARECE NESSE LAYOUT"]
campos:
  totais.valor_total:
    coluna: ["VALOR TOTAL DA NOTA"]   # rótulo acima, valor alinhado abaixo
  emitente.cnpj:
    regex: ["CNPJ[:\\s]*(\\d{14})"]   # rótulo e valor na mesma linha
```

Use `coluna` no bloco tabular do DANFE, onde os rótulos ficam numa linha e os
valores alinhados abaixo. Ali um regex de "primeiro número depois do rótulo"
devolveria o valor da coluna vizinha. Use `regex` quando rótulo e valor estão
juntos e não há vizinho que confunda.

O perfil é escolhido pelo maior número de marcadores presentes no texto.

## Limitações declaradas

- **Não consulta a SEFAZ nem a prefeitura.** Por isso não valida autenticidade e
  `situacao` fica `desconhecida` fora do XML que já traz protocolo.
- **Itens não são extraídos de PDF nem de foto.** A lista vem vazia com o aviso
  `ITENS_NAO_EXTRAIDOS` — é limitação da leitura, não ausência de itens na nota.
  Extrair tabela de produtos exige um perfil por emissor, feito contra amostras
  reais.
- **A precisão do OCR em nota real é desconhecida.** As fixtures de PDF e de
  imagem são sintéticas e limpas: provam que o caminho funciona, não medem
  acerto em cupom amassado ou foto torta. Ponha notas de verdade em
  `tests/fixtures/` para medir.
- **O pacote de idioma muda o resultado de forma mensurável.** Na mesma imagem
  de teste, o Tesseract com `por` lê o valor do frete como `150,00`; com `eng`
  lê `150,60`. Nos dois casos a nota sai com `requer_revisao`, e no segundo a
  validação cruzada acusa `TOTAL_DIVERGENTE` — mas instale
  `tesseract-data-por`, ou use a imagem Docker, que já traz.
- **Não emite nota, não persiste nada.** O serviço é *stateless*; quem guarda é
  o consumidor.
- O log registra métrica (dialeto, confiança, duração, sha256 e códigos de
  problema), **nunca conteúdo da nota**.

## Estrutura

```
src/nfscan/
  dominio/      chave de acesso, CNPJ/CPF, decimais, datas, UF, município
  modelo/       modelo canônico Pydantic, coletor de confiança e proveniência
  sniff/        detecção do container por conteúdo
  detect/       detecção do dialeto fiscal
  extratores/   um por dialeto, registrados em um registry
    ancoras/    motor de regex e de coluna, perfis YAML por emissor
    ocr/        pré-processo de imagem e Tesseract
  validar/      regras cruzadas
  pipeline.py   parse(bytes, nome) -> NotaFiscal
  api/          FastAPI
```
