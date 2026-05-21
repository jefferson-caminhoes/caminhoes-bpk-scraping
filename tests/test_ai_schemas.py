import pytest
from pydantic import ValidationError
from src.ai.schemas import ExtractionResult


def test_valid_extraction_result():
    result = ExtractionResult(
        found=True,
        protocol_number="12345",
        external_status="Em análise",
        confidence=0.92,
    )
    assert result.found is True
    assert result.confidence == 0.92


def test_confidence_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        ExtractionResult(found=True, confidence=1.5)


def test_confidence_negative_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(found=True, confidence=-0.1)


def test_all_optional_fields_default_to_none():
    result = ExtractionResult(found=False, confidence=0.8)
    assert result.protocol_number is None
    assert result.external_status is None
    assert result.last_movement_date is None
    assert result.observation is None
    assert result.agency is None
    assert result.oficio is None
    assert result.error is None


def test_not_found_result():
    result = ExtractionResult(
        found=False,
        protocol_number="99999",
        observation="Protocolo não encontrado na origem",
        confidence=0.85,
    )
    assert result.found is False
    assert result.observation == "Protocolo não encontrado na origem"
