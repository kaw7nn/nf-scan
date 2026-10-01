"""Garante que o pacote está instalável e importável."""


def test_pacote_importavel_e_tem_versao() -> None:
    import nfscan

    assert isinstance(nfscan.__version__, str)
    assert nfscan.__version__ != ""
