"""Diagnóstico de dependências externas, usado pelo ``/healthz``."""

from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache

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


@lru_cache(maxsize=1)
def idiomas_tesseract() -> tuple[str, ...]:
    """Idiomas de OCR instalados, pela saída de ``tesseract --list-langs``.

    A primeira linha da saída é um cabeçalho descritivo, não um idioma.

    Em cache: o pacote de idioma é assado na imagem e não muda em tempo de
    execução, enquanto o ``/healthz`` é consultado a cada poucos segundos para
    sempre. Pagar dois ``fork`` por sonda é desperdício, e sob pressão de
    memória um ``fork`` que falha derruba justamente a verificação de saúde.
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


@lru_cache(maxsize=1)
def versao_tesseract() -> str:
    """Primeira linha de ``tesseract --version``, ou ``"ausente"``.

    Em cache pelo mesmo motivo de :func:`idiomas_tesseract`.
    """
    caminho = shutil.which("tesseract")
    if caminho is None:
        return AUSENTE
    linhas = _rodar(caminho, "--version").splitlines()
    return linhas[0].strip() if linhas else AUSENTE
