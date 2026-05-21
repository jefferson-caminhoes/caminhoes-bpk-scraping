from src.cleaner.sufficiency_checker import is_sufficient

def test_sufficient_text_with_protocol_and_status():
    text = "Protocolo 12345 CNPJ 12.345.678/0001-99 Status Em análise Última movimentação 20/05/2026"
    assert is_sufficient(text) is True


def test_empty_text_is_not_sufficient():
    assert is_sufficient("") is False


def test_very_short_text_is_not_sufficient():
    assert is_sufficient("ok") is False


def test_text_without_keywords_is_not_sufficient():
    text = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor"
    assert is_sufficient(text) is False


def test_text_with_not_found_message_is_sufficient():
    text = "Protocolo não encontrado no sistema de consulta pública"
    assert is_sufficient(text) is True
