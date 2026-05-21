import json
import re
from src.ai.schemas import ExtractionResult


def extract_json_from_text(text: str) -> dict:
    """Try to extract a JSON object from raw LLM output."""
    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in AI response: {text[:200]!r}")


def validate_extraction_result(data: dict) -> ExtractionResult:
    return ExtractionResult.model_validate(data)
