from unittest.mock import patch, MagicMock
from src.ai.prompts import build_extraction_prompt
from src.ai.ollama_client import call_ollama


def test_build_extraction_prompt_contains_clean_text():
    prompt = build_extraction_prompt(
        clean_text="Protocolo 12345 Status Em análise",
        protocol_number="12345",
        cnpj="12.345.678/0001-99",
        stakeholder_name="Prefeitura",
    )
    assert "12345" in prompt
    assert "Em análise" in prompt
    assert "12.345.678/0001-99" in prompt
    assert "Prefeitura" in prompt


def test_build_extraction_prompt_contains_schema():
    prompt = build_extraction_prompt(
        clean_text="texto",
        protocol_number="1",
        cnpj=None,
        stakeholder_name="Copel",
    )
    assert "found" in prompt
    assert "external_status" in prompt
    assert "confidence" in prompt


def test_call_ollama_returns_response_text():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": '{"found": true, "confidence": 0.9}'}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_response):
        result = call_ollama("Test prompt")

    assert result == '{"found": true, "confidence": 0.9}'


def test_call_ollama_raises_on_http_error():
    import httpx as _httpx
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "HTTP 500", request=MagicMock(), response=MagicMock(status_code=500)
    )

    with patch("httpx.post", return_value=mock_response):
        import pytest
        with pytest.raises(_httpx.HTTPStatusError):
            call_ollama("Test prompt")
