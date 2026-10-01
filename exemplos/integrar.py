#!/usr/bin/env python3
"""Exemplo de integração: envia uma nota ao NF Scan e usa a resposta.

Demonstra o uso correto do contrato: ler os campos, **e olhar
``requer_revisao`` antes de aceitar**. Um integrador que ignora esse campo
grava no banco o que o OCR adivinhou.

    python exemplos/integrar.py caminho/da/nota.xml

Variáveis de ambiente: ``NFSCAN_URL`` (padrão http://127.0.0.1:8000) e
``NFSCAN_API_KEY``.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path

URL = os.environ.get("NFSCAN_URL", "http://127.0.0.1:8000").rstrip("/")
CHAVE = os.environ.get("NFSCAN_API_KEY", "local")
CONFIANCA_MINIMA_POR_CAMPO = 0.85


def enviar(caminho: Path) -> dict:
    """Faz o upload multipart sem dependência externa."""
    limite = f"----nfscan{uuid.uuid4().hex}"
    corpo = b"".join(
        [
            f"--{limite}\r\n".encode(),
            f'Content-Disposition: form-data; name="arquivo"; '
            f'filename="{caminho.name}"\r\n'.encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            caminho.read_bytes(),
            f"\r\n--{limite}--\r\n".encode(),
        ]
    )
    requisicao = urllib.request.Request(
        f"{URL}/v1/notas",
        data=corpo,
        headers={
            "Content-Type": f"multipart/form-data; boundary={limite}",
            "X-API-Key": CHAVE,
        },
    )
    with urllib.request.urlopen(requisicao, timeout=120) as resposta:  # noqa: S310
        return json.loads(resposta.read())


def _confianca(nota: dict, campo: str) -> float:
    return nota["extracao"]["campos"].get(campo, {}).get("confianca", 0.0)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    nota = enviar(Path(sys.argv[1]))
    emitente = nota.get("emitente") or {}
    documento = nota["documento"]
    totais = nota.get("totais") or {}
    extracao = nota["extracao"]

    print("Lançamento sugerido")
    print(f"  Fornecedor ...... {emitente.get('razao_social') or '(não lido)'}")
    print(f"  CNPJ ............ {emitente.get('cnpj') or '(não lido)'}")
    print(f"  Documento ....... {documento.get('numero') or '(não lido)'}"
          f" série {documento.get('serie') or '-'}")
    print(f"  Emissão ......... {documento.get('data_emissao') or '(não lido)'}")
    print(f"  Valor total ..... {totais.get('valor_total') or '(não lido)'}")
    print(f"  Chave ........... {documento.get('chave_acesso') or '(não lido)'}")
    print()
    print(f"Confiança global: {extracao['confianca_global']} ({extracao['motor']})")

    # Campo a campo: o que pode entrar direto e o que precisa de olho humano.
    duvidosos = [
        campo
        for campo in ("emitente.cnpj", "documento.numero", "totais.valor_total")
        if _confianca(nota, campo) < CONFIANCA_MINIMA_POR_CAMPO
    ]
    if duvidosos:
        print("Campos abaixo do limiar, confira antes de gravar:")
        for campo in duvidosos:
            print(f"  - {campo} (confiança {_confianca(nota, campo)})")

    for problema in extracao["problemas"]:
        print(f"[{problema['severidade']}] {problema['codigo']}: {problema['mensagem']}")

    if extracao["requer_revisao"]:
        print()
        print("REQUER REVISÃO: não grave este lançamento sem conferência humana.")
        return 1

    print()
    print("Pode ser gravado sem revisão.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
