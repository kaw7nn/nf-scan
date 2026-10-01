"""Códigos de UF do IBGE, usados nos dois primeiros dígitos da chave."""

SIGLA_POR_CODIGO: dict[str, str] = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}


def sigla_por_codigo(codigo: str) -> str | None:
    """Devolve a sigla da UF, ou ``None`` se o código não existir."""
    return SIGLA_POR_CODIGO.get(codigo)
