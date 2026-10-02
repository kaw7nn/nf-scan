"""O /healthz não pode custar subprocesso a cada chamada.

O orquestrador bate nessa rota a cada poucos segundos, para sempre. Versão e
idiomas do Tesseract são assados na imagem e não mudam em tempo de execução, e
sob pressão de memória um fork que falha derruba o healthcheck — provocando
justamente o restart que a sonda deveria evitar.
"""

from nfscan.api import diagnostico


def test_versao_e_consultada_uma_vez_so(monkeypatch) -> None:
    chamadas = []
    original = diagnostico._rodar

    def contando(caminho: str, *argumentos: str) -> str:
        chamadas.append(argumentos)
        return original(caminho, *argumentos)

    diagnostico.versao_tesseract.cache_clear()
    monkeypatch.setattr(diagnostico, "_rodar", contando)

    primeira = diagnostico.versao_tesseract()
    segunda = diagnostico.versao_tesseract()

    assert primeira == segunda
    assert len(chamadas) == 1, f"subprocesso rodou {len(chamadas)} vezes"


def test_idiomas_sao_consultados_uma_vez_so(monkeypatch) -> None:
    chamadas = []
    original = diagnostico._rodar

    def contando(caminho: str, *argumentos: str) -> str:
        chamadas.append(argumentos)
        return original(caminho, *argumentos)

    diagnostico.idiomas_tesseract.cache_clear()
    monkeypatch.setattr(diagnostico, "_rodar", contando)

    primeira = diagnostico.idiomas_tesseract()
    segunda = diagnostico.idiomas_tesseract()

    assert primeira == segunda
    assert len(chamadas) == 1, f"subprocesso rodou {len(chamadas)} vezes"
