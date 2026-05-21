import json
import re
from src.ai.schemas import ExtractionResult


def _remove_incomplete_array_items(text: str) -> str:
    """
    Remove incomplete objects from JSON arrays.
    Handles phi3:mini truncation mid-step: keeps only complete {...} entries.
    """
    import re as _re
    # Find "steps": [...] and clean it
    def fix_array(m):
        content = m.group(1)
        # Find all complete objects (balanced braces)
        complete = []
        depth = 0
        start = None
        for i, ch in enumerate(content):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    complete.append(content[start:i+1])
                    start = None
        return '"steps": [' + ','.join(complete) + ']'

    return _re.sub(r'"steps"\s*:\s*\[(.*?)\]', fix_array, text, flags=_re.DOTALL)


def _repair_json(text: str) -> str:
    """
    Fix common phi3:mini hallucination patterns:
    - Bare number lines: '0,' or '1' on their own line
    - Numeric keys without quotes: '0: {' or '1: {' (Python-dict style steps)
    """
    # Fix pattern: "0: {" → collect as steps array if they appear at root level
    # Match: root-level numeric key entries like: \n0: { ... }
    numeric_step_pattern = re.compile(r'^\s*\d+\s*:\s*\{', re.MULTILINE)
    if numeric_step_pattern.search(text):
        text = _convert_numeric_steps_to_array(text)

    # Drop bare number lines (e.g. "0," or "1" alone)
    lines = text.splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"\d+,?", stripped):
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines)


def _convert_numeric_steps_to_array(text: str) -> str:
    """
    Convert phi3:mini numeric-key step format to proper steps array.

    Input:  {..., "captcha_detected": false,\n0: {...},\n1: {...}\n}
    Output: {..., "captcha_detected": false,\n"steps": [{...},{...}]\n}
    """
    # Extract the step objects (0: {...}, 1: {...}, ...)
    step_objects = re.findall(r'\d+\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', text, re.DOTALL)

    # Remove all numeric-key entries from the text
    cleaned = re.sub(r',?\s*\d+\s*:\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\},?', '', text, flags=re.DOTALL)

    # Remove trailing comma before closing brace if present
    cleaned = re.sub(r',(\s*\})', r'\1', cleaned)

    if step_objects:
        steps_json = "[" + ",".join(step_objects) + "]"
        # Inject before the last closing brace
        last_brace = cleaned.rfind("}")
        if last_brace != -1:
            before = cleaned[:last_brace].rstrip().rstrip(",")
            cleaned = before + ', "steps": ' + steps_json + "\n}"

    return cleaned


def _close_truncated_json(text: str) -> str:
    """Attempt to close a truncated JSON object by counting unclosed braces/brackets."""
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1

    # If truncated inside a string value, close it with a safe empty value
    if in_string:
        text = text + '"'
    closing = "]" * max(0, depth_bracket) + "}" * max(0, depth_brace)
    return text + closing


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
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 4. Repair garbage lines + incomplete steps array
    repaired = _repair_json(cleaned)
    repaired = _remove_incomplete_array_items(repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 5. Try repaired + re-extract {...}
    match = re.search(r"\{.*\}", repaired, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 6. Handle truncated JSON: try to close unclosed braces/brackets
    if "{" in repaired:
        start = repaired.index("{")
        fragment = repaired[start:]
        candidate = _close_truncated_json(fragment)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # 7. Strip trailing incomplete key-value pair (truncated key or missing value)
        # Walk backwards from last comma and retry
        last_comma = fragment.rfind(",")
        if last_comma > 0:
            trimmed = _close_truncated_json(fragment[:last_comma])
            try:
                return json.loads(trimmed)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON found in AI response: {text[:200]!r}")


def validate_extraction_result(data: dict) -> ExtractionResult:
    return ExtractionResult.model_validate(data)
