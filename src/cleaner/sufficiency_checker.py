_MIN_LENGTH = 30

_KEYWORDS = [
    "protocolo",
    "status",
    "situação",
    "andamento",
    "movimentação",
    "pendente",
    "aprovado",
    "indeferido",
    "em análise",
    "aguardando",
    "documentação",
    "não encontrado",
    "não localizado",
    "cnpj",
]


def is_sufficient(clean_text: str) -> bool:
    if not clean_text or len(clean_text.strip()) < _MIN_LENGTH:
        return False
    text_lower = clean_text.lower()
    return any(kw in text_lower for kw in _KEYWORDS)
