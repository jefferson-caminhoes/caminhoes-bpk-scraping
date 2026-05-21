import pytest
from src.ai.json_validator import extract_json_from_text, validate_extraction_result
from src.ai.schemas import ExtractionResult


def test_parse_clean_json():
    raw = '{"found": true, "confidence": 0.9, "external_status": "Em análise"}'
    result = extract_json_from_text(raw)
    assert result["found"] is True
    assert result["confidence"] == 0.9


def test_parse_json_with_markdown_fences():
    raw = '```json\n{"found": true, "confidence": 0.8}\n```'
    result = extract_json_from_text(raw)
    assert result["found"] is True


def test_parse_json_with_surrounding_text():
    raw = 'Aqui está o resultado: {"found": false, "confidence": 0.5} fim.'
    result = extract_json_from_text(raw)
    assert result["found"] is False


def test_raises_when_no_json_found():
    with pytest.raises(ValueError, match="No valid JSON"):
        extract_json_from_text("Não consigo extrair nada")


def test_validate_extraction_result_returns_model():
    data = {"found": True, "confidence": 0.91, "external_status": "Aprovado"}
    result = validate_extraction_result(data)
    assert isinstance(result, ExtractionResult)
    assert result.external_status == "Aprovado"


def test_validate_raises_on_invalid_confidence():
    data = {"found": True, "confidence": 5.0}
    with pytest.raises(Exception):
        validate_extraction_result(data)
