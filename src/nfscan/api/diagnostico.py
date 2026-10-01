"""Diagnóstico de dependências externas, usado pelo ``/healthz``."""

from __future__ import annotations

import shutil
import subprocess

AUSENTE = "ausente"
_TIMEOUT = 5


def versao_tesseract() -> str:
    """Primeira linha de ``tesseract --version``, ou ``"ausente"``."""
    caminho = shutil.which("tesseract")
    if caminho is None:
        return AUSENTE
    try:
        saida = subprocess.run(  # noqa: S603
            [caminho, "--version"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return AUSENTE
    bruto = saida.stdout or saida.stderr
    linhas = bruto.splitlines() if bruto else []
    return linhas[0].strip() if linhas else AUSENTE
