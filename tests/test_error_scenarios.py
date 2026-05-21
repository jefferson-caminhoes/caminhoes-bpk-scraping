from tests.conftest import (
    PROTOCOL_NOT_FOUND_HTML,
    STATUS_EM_ANALISE_HTML,
    EMPTY_HTML,
    NOISY_HTML,
)
from src.cleaner.html_cleaner import clean_html
from src.cleaner.sufficiency_checker import is_sufficient


def test_not_found_html_cleans_to_sufficient_text():
    clean = clean_html(PROTOCOL_NOT_FOUND_HTML)
    assert "não encontrado" in clean.lower()
    assert is_sufficient(clean)


def test_status_em_analise_html_preserves_status():
    clean = clean_html(STATUS_EM_ANALISE_HTML)
    assert "Em análise" in clean
    assert "12345" in clean
    assert "20/05/2026" in clean
    assert is_sufficient(clean)


def test_empty_html_is_not_sufficient():
    clean = clean_html(EMPTY_HTML)
    assert not is_sufficient(clean)


def test_noisy_html_removes_noise_and_preserves_content():
    clean = clean_html(NOISY_HTML)
    assert "var x=1" not in clean
    assert "color:red" not in clean
    assert "Home Projetos Sair" not in clean
    assert "© 2026" not in clean
    assert "Aprovado" in clean
    assert "99999" in clean
    assert is_sufficient(clean)


def test_noisy_html_removes_nav():
    clean = clean_html(NOISY_HTML)
    assert "Home Projetos Sair" not in clean
