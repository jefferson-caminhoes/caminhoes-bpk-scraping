# src/scraping/url_analyzer.py
"""
Serviço de análise de URL: busca a página, passa para o LLM e retorna SiteProbe.
"""
from urllib.parse import urlparse
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.ai.ollama_client import call_ollama
from src.ai.probe_prompts import build_probe_prompt
from src.ai.json_validator import extract_json_from_text
from src.scraping.probe_schema import SiteProbe
from src.scraping.http_scraper import _HEADERS, _TIMEOUT
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _clean_html_for_llm(html: str) -> str:
    """Remove scripts/styles e retorna HTML limpo truncado em 4000 chars."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "noscript", "svg", "img"]):
        tag.decompose()
    body = soup.find("body") or soup
    text = body.prettify()
    return text[:4000]


def _extract_base_url(url: str) -> str:
    """Retorna scheme://host de uma URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def analyze_url(url: str) -> SiteProbe:
    """
    Analisa uma URL via LLM e retorna um SiteProbe com a receita de scraping.

    Raises:
        ValueError: se o LLM não retornar JSON válido.
        httpx.ConnectError: se a URL não responder.
    """
    logger.info(f"Analyzing URL: {url}")

    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        actual_url = str(response.url)
        html = response.text

    logger.info(f"Fetched URL. Actual URL after redirects: {actual_url}")

    clean = _clean_html_for_llm(html)

    prompt = build_probe_prompt(
        original_url=url,
        actual_url=actual_url,
        html_snippet=clean,
    )

    logger.info("Calling LLM for URL analysis...")
    raw_response = call_ollama(prompt)
    logger.info(f"LLM response (first 200 chars): {raw_response[:200]}")

    data = extract_json_from_text(raw_response)

    # Always use the real extracted values — don't trust the model for these
    data["original_url"] = url
    data["base_url"] = _extract_base_url(actual_url)
    data["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    # Fill missing root fields with safe defaults
    data.setdefault("portal_type", "unknown")
    data.setdefault("auth_required", False)
    data.setdefault("captcha_detected", False)
    data.setdefault("confidence", 0.5)
    data.setdefault("notes", "")

    # Normalize extract rules: some models output ["viewstate"] instead of [{"name":...}]
    for step in data.get("steps", []):
        normalized = []
        for rule in step.get("extract") or []:
            if isinstance(rule, str):
                # shorthand: "viewstate" → full ExtractRule
                normalized.append({"name": rule, "selector": rule, "attribute": "value"})
            else:
                normalized.append(rule)
        step["extract"] = normalized

    probe = SiteProbe(**data)
    logger.info(
        f"Probe generated: type={probe.portal_type}, confidence={probe.confidence}, "
        f"captcha={probe.captcha_detected}, auth={probe.auth_required}"
    )
    return probe
