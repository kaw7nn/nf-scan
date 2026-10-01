"""Diagnóstico de dependências externas, usado pelo ``/healthz``."""

from __future__ import annotations

import shutil
import subprocess

AUSENTE = "ausente"
_TIMEOUT = 5


def _rodar(caminho: str, *argumentos: str) -> str:
    try:
        saida = subprocess.run(  # noqa: S603
            [caminho, *argumentos],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return saida.stdout or saida.stderr or ""


def idiomas_tesseract() -> tuple[str, ...]:
    """Idiomas de OCR instalados, pela saída de ``tesseract --list-langs``.

    A primeira linha da saída é um cabeçalho descritivo, não um idioma.
    """
    caminho = shutil.which("tesseract")
    if caminho is None:
        return ()
    linhas = _rodar(caminho, "--list-langs").splitlines()
    return tuple(
        linha.strip()
        for linha in linhas[1:]
        if linha.strip() and " " not in linha.strip()
    )


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
