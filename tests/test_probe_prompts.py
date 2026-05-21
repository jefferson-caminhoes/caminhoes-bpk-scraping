# tests/test_probe_prompts.py
from src.ai.probe_prompts import build_probe_prompt


def test_build_probe_prompt_contains_urls():
    prompt = build_probe_prompt(
        original_url="https://portal.com/consulta?utm_source=home",
        actual_url="https://portal.com/api/protocolo",
        html_snippet="<form id='search'><input name='protocolo'/></form>",
    )
    assert "https://portal.com/consulta" in prompt
    assert "https://portal.com/api/protocolo" in prompt
    assert "<form" in prompt
    assert "JSON" in prompt


def test_build_probe_prompt_contains_schema_fields():
    prompt = build_probe_prompt(
        original_url="https://portal.com",
        actual_url="https://portal.com",
        html_snippet="<html><body>Portal</body></html>",
    )
    assert "portal_type" in prompt
    assert "auth_required" in prompt
    assert "captcha_detected" in prompt
    assert "steps" in prompt
    assert "is_result_step" in prompt


def test_build_probe_prompt_truncates_long_html():
    long_html = "<p>" + "x" * 10000 + "</p>"
    prompt = build_probe_prompt(
        original_url="https://portal.com",
        actual_url="https://portal.com",
        html_snippet=long_html,
    )
    # HTML in prompt should not exceed 4000 chars of the original snippet
    # (the prompt itself is longer, but the html section is bounded)
    html_in_prompt = prompt[prompt.find("<p>"):prompt.find("<p>") + 5000]
    assert len(html_in_prompt) < 5000


def test_build_probe_prompt_contains_example_json():
    prompt = build_probe_prompt(
        original_url="https://portal.com",
        actual_url="https://portal.com",
        html_snippet="<html></html>",
    )
    # Should contain a JSON example so the LLM knows the expected format
    assert '"portal_type"' in prompt
    assert '"steps"' in prompt
    assert '"confidence"' in prompt
