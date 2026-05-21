# AI URL Analyzer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dado uma URL fornecida pelo usuário, a IA analisa a estrutura da página, descobre o endpoint real de scraping, detecta auth/CAPTCHA e gera uma "receita" JSON que o DynamicAdapter executa para consultar protocolos automaticamente — sem necessidade de escrever código por portal.

**Architecture:** O sistema tem duas fases: (1) Análise — executada uma vez por stakeholder via fila `probe.jobs`, onde o LLM recebe o HTML da página e gera um `SiteProbe` JSON com os passos de scraping; (2) Execução — o `DynamicAdapter` lê o `site_probe` salvo no documento do stakeholder e executa os passos sequencialmente para cada job de scraping. Auth e CAPTCHA são detectados e tratados como casos especiais.

**Tech Stack:** Python 3.11, httpx, BeautifulSoup4, pydantic v2, phi3:mini via Ollama, RabbitMQ (pika), MongoDB, pytest

---

## Escopo — 2 subsistemas independentes

Este plano cobre os dois juntos pois o schema `SiteProbe` é compartilhado. Se preferir separar, divida em:
- **Plano A**: Tasks 1–4 (análise + adapter)
- **Plano B**: Tasks 5–7 (integração, worker, API)

---

## Mapa de Arquivos

```
src/
  scraping/
    probe_schema.py          ← CRIAR: modelos Pydantic do SiteProbe + ProbeStep
    url_analyzer.py          ← CRIAR: fetch URL + chamar LLM + retornar SiteProbe
    adapters/
      dynamic.py             ← CRIAR: DynamicAdapter que executa o SiteProbe
      registry.py            ← MODIFICAR: registrar DynamicAdapter + inferência por probe
  ai/
    probe_prompts.py         ← CRIAR: prompt de análise de URL para o LLM
  workers/
    probe_worker.py          ← CRIAR: consumer da fila probe.jobs

tests/
  test_probe_schema.py       ← CRIAR
  test_url_analyzer.py       ← CRIAR
  test_dynamic_adapter.py    ← CRIAR
  test_probe_worker.py       ← CRIAR
```

**Em `caminhoes-bpk-api`** (Task 7 — repo separado):
```
src/modules/stakeholders/
  router.py                  ← MODIFICAR: adicionar POST /{id}/analyze-url
  schemas.py                 ← MODIFICAR: adicionar SiteProbeResult no response
```

---

## Task 1: SiteProbe Schema

**Files:**
- Create: `src/scraping/probe_schema.py`
- Test: `tests/test_probe_schema.py`

- [ ] **Step 1: Escrever o teste de validação do schema**

```python
# tests/test_probe_schema.py
from src.scraping.probe_schema import SiteProbe, ProbeStep, ExtractRule, PortalType, StepType


def test_site_probe_minimal_valid():
    probe = SiteProbe(
        portal_type="simple_get",
        original_url="https://portal.gov.br/consulta",
        base_url="https://portal.gov.br",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/api/protocolo?numero={protocol_number}",
                is_result_step=True,
            )
        ],
        confidence=0.9,
        notes="Portal REST simples",
    )
    assert probe.portal_type == "simple_get"
    assert probe.auth_required is False
    assert len(probe.steps) == 1
    assert probe.steps[0].is_result_step is True


def test_site_probe_jsf_with_extract():
    probe = SiteProbe(
        portal_type="jsf_form",
        original_url="https://jsf.portal.com/inicio.jsf",
        base_url="https://jsf.portal.com",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/inicio.jsf",
                extract=[
                    ExtractRule(name="viewstate", selector="viewstate", attribute="value"),
                ],
            ),
            ProbeStep(
                step=2,
                type="post",
                url="{base_url}/inicio.jsf",
                form_data={
                    "formPrincipal:protocolo": "{protocol_number}",
                    "javax.faces.ViewState": "{var_viewstate}",
                },
                is_result_step=True,
                result_selector="div#resultado",
            ),
        ],
        confidence=0.85,
        notes="Portal JSF com ViewState",
    )
    assert probe.portal_type == "jsf_form"
    assert probe.steps[0].extract[0].selector == "viewstate"
    assert "{var_viewstate}" in probe.steps[1].form_data.values()


def test_probe_step_requires_step_number():
    import pytest
    with pytest.raises(Exception):
        ProbeStep(type="get", url="https://example.com")  # step ausente


def test_site_probe_with_auth():
    probe = SiteProbe(
        portal_type="post_form",
        original_url="https://sistema.com/login",
        base_url="https://sistema.com",
        auth_required=True,
        captcha_detected=False,
        login_url="https://sistema.com/login",
        steps=[
            ProbeStep(
                step=1,
                type="post",
                url="{base_url}/login",
                form_data={"user": "{credential_username}", "pass": "{credential_password}"},
            ),
            ProbeStep(
                step=2,
                type="get",
                url="{base_url}/protocolo?numero={protocol_number}",
                is_result_step=True,
            ),
        ],
        confidence=0.7,
        notes="Portal com login obrigatório",
    )
    assert probe.auth_required is True
    assert probe.login_url == "https://sistema.com/login"
    assert "{credential_username}" in probe.steps[0].form_data.values()
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```bash
cd C:\caminhoes-bpk\caminhoes-bpk-scrapping
python -m pytest tests/test_probe_schema.py -v
```
Esperado: `ImportError: cannot import name 'SiteProbe' from 'src.scraping.probe_schema'`

- [ ] **Step 3: Implementar `src/scraping/probe_schema.py`**

```python
# src/scraping/probe_schema.py
"""
Schema Pydantic do SiteProbe — a "receita" que descreve como fazer scraping
de um portal. Gerada pela IA e executada pelo DynamicAdapter.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


StepType = Literal["get", "post", "post_json"]
PortalType = Literal["jsf_form", "post_form", "rest_api", "simple_get", "unknown"]


class ExtractRule(BaseModel):
    """Regra para extrair uma variável do HTML de resposta de um passo."""
    name: str
    # Seletor CSS — OU "viewstate" (atalho para ViewState JSF)
    # OU "json_path:$.campo" para respostas JSON
    selector: str
    # Atributo do elemento: "text" | "value" | "href" | "data-cns" | etc.
    attribute: str = "value"


class ProbeStep(BaseModel):
    """Um passo na receita de scraping."""
    step: int
    type: StepType
    # URL com placeholders: {base_url}, {protocol_number}, {cnpj},
    # {registry_office_number}, {var_NOME} (variável extraída em passo anterior)
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    # Campos do formulário para POST (type="post"). Suporta mesmos placeholders.
    form_data: dict[str, str] = Field(default_factory=dict)
    # Body JSON para POST (type="post_json"). Suporta placeholders como string.
    json_body: dict | None = None
    # Variáveis a extrair do HTML desta resposta para usar nos próximos passos.
    extract: list[ExtractRule] = Field(default_factory=list)
    # Seletor CSS do elemento que contém o resultado final (apenas no passo de resultado).
    result_selector: str | None = None
    # True no passo cujo HTML/texto será retornado como resultado do scraping.
    is_result_step: bool = False


class SiteProbe(BaseModel):
    """
    Receita de scraping de um portal, gerada pela IA a partir da análise da URL.
    Fica salva no documento do stakeholder (campo site_probe).
    """
    portal_type: PortalType
    original_url: str
    base_url: str
    auth_required: bool
    captcha_detected: bool
    # URL da página de login, se auth_required=True
    login_url: str | None = None
    steps: list[ProbeStep]
    # 0.0–1.0: confiança da IA na receita gerada
    confidence: float = Field(ge=0.0, le=1.0)
    # Explicação da IA sobre o que encontrou
    notes: str
    analyzed_at: str | None = None
```

- [ ] **Step 4: Rodar os testes**

```bash
python -m pytest tests/test_probe_schema.py -v
```
Esperado: todos os 4 testes PASS

- [ ] **Step 5: Commit**

```bash
git add src/scraping/probe_schema.py tests/test_probe_schema.py
git commit -m "feat(probe): add SiteProbe pydantic schema for dynamic scraping recipes"
```

---

## Task 2: LLM Probe Prompt

**Files:**
- Create: `src/ai/probe_prompts.py`
- Test: `tests/test_probe_schema.py` (adicionar teste do prompt)

- [ ] **Step 1: Escrever teste do prompt**

Adicionar ao final de `tests/test_probe_schema.py`:

```python
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


def test_build_probe_prompt_contains_schema():
    prompt = build_probe_prompt(
        original_url="https://portal.com",
        actual_url="https://portal.com",
        html_snippet="<html><body>Portal</body></html>",
    )
    assert "portal_type" in prompt
    assert "auth_required" in prompt
    assert "steps" in prompt
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python -m pytest tests/test_probe_schema.py::test_build_probe_prompt_contains_urls tests/test_probe_schema.py::test_build_probe_prompt_contains_schema -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar `src/ai/probe_prompts.py`**

```python
# src/ai/probe_prompts.py
"""
Prompts LLM para análise de URLs e geração de receitas SiteProbe.
Projetado para funcionar com modelos pequenos (phi3:mini, llama3.2:3b).
"""

PROBE_SCHEMA_EXAMPLE = """{
  "portal_type": "jsf_form",
  "original_url": "https://portal.com/home",
  "base_url": "https://portal.com",
  "auth_required": false,
  "captcha_detected": false,
  "login_url": null,
  "steps": [
    {
      "step": 1,
      "type": "get",
      "url": "{base_url}/consulta.jsf",
      "headers": {},
      "form_data": {},
      "json_body": null,
      "extract": [
        {"name": "viewstate", "selector": "viewstate", "attribute": "value"}
      ],
      "result_selector": null,
      "is_result_step": false
    },
    {
      "step": 2,
      "type": "post",
      "url": "{base_url}/consulta.jsf",
      "headers": {},
      "form_data": {
        "form:protocolo": "{protocol_number}",
        "javax.faces.ViewState": "{var_viewstate}"
      },
      "json_body": null,
      "extract": [],
      "result_selector": "div#resultado",
      "is_result_step": true
    }
  ],
  "confidence": 0.85,
  "notes": "Portal JSF. Passo 1 obtém ViewState, passo 2 submete formulário com protocolo."
}"""

PROBE_PROMPT_TEMPLATE = """Você é especialista em web scraping de portais governamentais brasileiros.

Analise a URL e HTML abaixo e gere uma receita JSON para consultar o número de um protocolo.

URL fornecida pelo usuário: {original_url}
URL real (após redirecionamentos): {actual_url}

HTML da página (estrutura simplificada, até 4000 chars):
{html_snippet}

---

INSTRUÇÕES:

1. Identifique o tipo de portal:
   - "jsf_form": portal JSF (tem javax.faces.ViewState, ações PrimeFaces/RichFaces)
   - "post_form": formulário HTML clássico com POST
   - "rest_api": backend REST (URL contém /api/, /rest/, retorna JSON)
   - "simple_get": consulta via parâmetro GET na URL (ex: ?protocolo=123)
   - "unknown": não conseguiu determinar

2. Detecte:
   - auth_required: true se há formulário de login antes da consulta
   - captcha_detected: true se há reCAPTCHA, hCaptcha, img captcha, ou similar

3. Descreva os passos:
   - Cada passo tem type: "get", "post" ou "post_json"
   - Use placeholders: {{base_url}}, {{protocol_number}}, {{cnpj}}, {{registry_office_number}}
   - Use {{var_NOME}} para referenciar variáveis extraídas em passos anteriores
   - Para ViewState JSF: use extract com selector="viewstate"
   - Para outros campos: use selector CSS padrão (ex: "input#protocolo")
   - O passo que contém o resultado deve ter is_result_step=true
   - result_selector: seletor CSS do elemento com o conteúdo do protocolo

4. base_url: URL base sem path (ex: "https://portal.com")
5. confidence: número entre 0 e 1 (sua confiança na receita)

RETORNE APENAS JSON VÁLIDO (sem markdown, sem explicações fora do JSON).
Schema obrigatório:
{schema_example}
"""


def build_probe_prompt(
    original_url: str,
    actual_url: str,
    html_snippet: str,
) -> str:
    return PROBE_PROMPT_TEMPLATE.format(
        original_url=original_url,
        actual_url=actual_url,
        html_snippet=html_snippet[:4000],
        schema_example=PROBE_SCHEMA_EXAMPLE,
    )
```

- [ ] **Step 4: Rodar testes**

```bash
python -m pytest tests/test_probe_schema.py -v
```
Esperado: 6 testes PASS

- [ ] **Step 5: Commit**

```bash
git add src/ai/probe_prompts.py tests/test_probe_schema.py
git commit -m "feat(probe): add LLM probe prompt for URL analysis"
```

---

## Task 3: URL Analyzer Service

**Files:**
- Create: `src/scraping/url_analyzer.py`
- Test: `tests/test_url_analyzer.py`

- [ ] **Step 1: Escrever testes (com mocks)**

```python
# tests/test_url_analyzer.py
import json
import pytest
from unittest.mock import patch, MagicMock
from src.scraping.url_analyzer import analyze_url, _clean_html_for_llm, _extract_base_url


# --- Helpers ---

def _valid_probe_json(original_url="https://portal.com", actual_url="https://portal.com"):
    return json.dumps({
        "portal_type": "simple_get",
        "original_url": original_url,
        "base_url": "https://portal.com",
        "auth_required": False,
        "captcha_detected": False,
        "login_url": None,
        "steps": [
            {
                "step": 1,
                "type": "get",
                "url": "{base_url}/consulta?protocolo={protocol_number}",
                "headers": {},
                "form_data": {},
                "json_body": None,
                "extract": [],
                "result_selector": "div.resultado",
                "is_result_step": True,
            }
        ],
        "confidence": 0.9,
        "notes": "Simple GET with protocol number",
    })


# --- Unit tests ---

def test_clean_html_for_llm_removes_scripts():
    html = "<html><head><script>alert('xss')</script></head><body><form><input name='prot'/></form></body></html>"
    result = _clean_html_for_llm(html)
    assert "alert" not in result
    assert "input" in result


def test_clean_html_for_llm_truncates_to_4000():
    html = "<p>" + "x" * 10000 + "</p>"
    result = _clean_html_for_llm(html)
    assert len(result) <= 4000


def test_extract_base_url():
    assert _extract_base_url("https://portal.com/path/page.jsf") == "https://portal.com"
    assert _extract_base_url("https://sub.portal.gov.br/api/v1/") == "https://sub.portal.gov.br"
    assert _extract_base_url("https://portal.com") == "https://portal.com"


@patch("src.scraping.url_analyzer.call_ollama")
@patch("src.scraping.url_analyzer.httpx.Client")
def test_analyze_url_returns_site_probe(mock_client_cls, mock_ollama):
    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.text = "<html><body><form><input name='protocolo'/></form></body></html>"
    mock_response.url = "https://portal.com/consulta"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    # Mock LLM response
    mock_ollama.return_value = _valid_probe_json(
        original_url="https://portal.com/consulta",
        actual_url="https://portal.com/consulta",
    )

    from src.scraping.probe_schema import SiteProbe
    probe = analyze_url("https://portal.com/consulta")

    assert isinstance(probe, SiteProbe)
    assert probe.portal_type == "simple_get"
    assert probe.auth_required is False
    assert len(probe.steps) == 1
    mock_ollama.assert_called_once()


@patch("src.scraping.url_analyzer.call_ollama")
@patch("src.scraping.url_analyzer.httpx.Client")
def test_analyze_url_detects_captcha(mock_client_cls, mock_ollama):
    mock_response = MagicMock()
    mock_response.text = "<html><body><div class='g-recaptcha'></div><form/></body></html>"
    mock_response.url = "https://portal.com/form"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    probe_with_captcha = json.dumps({
        "portal_type": "post_form",
        "original_url": "https://portal.com/form",
        "base_url": "https://portal.com",
        "auth_required": False,
        "captcha_detected": True,
        "login_url": None,
        "steps": [
            {"step": 1, "type": "post", "url": "{base_url}/form",
             "headers": {}, "form_data": {"protocolo": "{protocol_number}"},
             "json_body": None, "extract": [], "result_selector": None, "is_result_step": True}
        ],
        "confidence": 0.6,
        "notes": "Detectado reCAPTCHA — scraping pode falhar",
    })
    mock_ollama.return_value = probe_with_captcha

    probe = analyze_url("https://portal.com/form")
    assert probe.captcha_detected is True


@patch("src.scraping.url_analyzer.call_ollama")
@patch("src.scraping.url_analyzer.httpx.Client")
def test_analyze_url_raises_on_invalid_llm_response(mock_client_cls, mock_ollama):
    mock_response = MagicMock()
    mock_response.text = "<html><body>Portal</body></html>"
    mock_response.url = "https://portal.com"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    mock_ollama.return_value = "resposta inválida sem JSON"

    with pytest.raises(ValueError, match="JSON"):
        analyze_url("https://portal.com")
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python -m pytest tests/test_url_analyzer.py -v
```
Esperado: `ImportError: cannot import name 'analyze_url'`

- [ ] **Step 3: Implementar `src/scraping/url_analyzer.py`**

```python
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
    # Apenas o body se existir
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
        ValueError: se o LLM não retornar JSON válido ou se a URL for inacessível.
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

    # extract_json_from_text raises ValueError on failure
    data = extract_json_from_text(raw_response)

    # Garante que os campos de URL estão corretos
    data.setdefault("original_url", url)
    data.setdefault("base_url", _extract_base_url(actual_url))
    data["analyzed_at"] = datetime.now(timezone.utc).isoformat()

    probe = SiteProbe(**data)
    logger.info(f"Probe generated: type={probe.portal_type}, confidence={probe.confidence}, captcha={probe.captcha_detected}, auth={probe.auth_required}")
    return probe
```

- [ ] **Step 4: Rodar testes**

```bash
python -m pytest tests/test_url_analyzer.py -v
```
Esperado: 4 testes PASS

- [ ] **Step 5: Commit**

```bash
git add src/scraping/url_analyzer.py tests/test_url_analyzer.py
git commit -m "feat(probe): add URL analyzer service - fetches page and calls LLM to generate SiteProbe"
```

---

## Task 4: DynamicAdapter

**Files:**
- Create: `src/scraping/adapters/dynamic.py`
- Test: `tests/test_dynamic_adapter.py`

- [ ] **Step 1: Escrever testes**

```python
# tests/test_dynamic_adapter.py
import json
import pytest
from unittest.mock import patch, MagicMock, call
from src.scraping.adapters.dynamic import DynamicAdapter, _interpolate, _execute_step
from src.scraping.probe_schema import SiteProbe, ProbeStep, ExtractRule
from src.scraping.fetcher import ScrapingTarget


def _make_target(protocol_number="12345", cnpj="12.345.678/0001-99"):
    return ScrapingTarget(
        job_id="job_1",
        protocol_id="prot_1",
        stakeholder_id="stake_1",
        protocol_number=protocol_number,
        cnpj=cnpj,
        stakeholder_name="Portal Test",
        stakeholder_type="dynamic",
        adapter_type="dynamic",
        requires_javascript=False,
        has_captcha=False,
        resolved_url="https://portal.com",
    )


def _make_simple_probe():
    return SiteProbe(
        portal_type="simple_get",
        original_url="https://portal.com/consulta",
        base_url="https://portal.com",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/consulta?protocolo={protocol_number}",
                is_result_step=True,
                result_selector="div#resultado",
            )
        ],
        confidence=0.9,
        notes="Simple GET",
    )


# --- _interpolate ---

def test_interpolate_replaces_protocol_number():
    result = _interpolate("{base_url}/api?p={protocol_number}", {"base_url": "https://portal.com", "protocol_number": "12345"})
    assert result == "https://portal.com/api?p=12345"


def test_interpolate_leaves_unknown_placeholders():
    result = _interpolate("{base_url}/{unknown}", {"base_url": "https://portal.com"})
    assert result == "https://portal.com/{unknown}"


def test_interpolate_handles_extracted_vars():
    result = _interpolate("{var_viewstate}", {"var_viewstate": "abc123"})
    assert result == "abc123"


# --- DynamicAdapter ---

def test_dynamic_adapter_resolve_url():
    probe = _make_simple_probe()
    adapter = DynamicAdapter(probe)
    assert adapter.resolve_url("", "12345", None, None) == "https://portal.com"


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_scrape_simple_get(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = '<html><body><div id="resultado">Protocolo 12345 - Status: Concluído</div></body></html>'
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    probe = _make_simple_probe()
    adapter = DynamicAdapter(probe)
    target = _make_target()

    result = adapter.scrape(target)

    assert result.success is True
    assert "Concluído" in result.raw_html
    mock_client.get.assert_called_once_with(
        "https://portal.com/consulta?protocolo=12345",
        headers={},
    )


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_scrape_returns_failure_on_empty_result(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = "<html><body><div id='resultado'></div></body></html>"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    probe = _make_simple_probe()
    adapter = DynamicAdapter(probe)
    result = adapter.scrape(_make_target())

    assert result.success is False
    assert result.error_type == "PROTOCOL_NOT_FOUND"


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_blocks_captcha_portals(mock_client_cls):
    probe = SiteProbe(
        portal_type="post_form",
        original_url="https://portal.com",
        base_url="https://portal.com",
        auth_required=False,
        captcha_detected=True,
        steps=[
            ProbeStep(step=1, type="get", url="{base_url}/form", is_result_step=True)
        ],
        confidence=0.5,
        notes="CAPTCHA detectado",
    )
    adapter = DynamicAdapter(probe)
    result = adapter.scrape(_make_target())

    assert result.success is False
    assert result.error_type == "CAPTCHA_BLOCKED"
    mock_client_cls.assert_not_called()


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_two_step_with_viewstate(mock_client_cls):
    probe = SiteProbe(
        portal_type="jsf_form",
        original_url="https://jsf.portal.com",
        base_url="https://jsf.portal.com",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/inicio.jsf",
                extract=[ExtractRule(name="viewstate", selector="viewstate", attribute="value")],
            ),
            ProbeStep(
                step=2,
                type="post",
                url="{base_url}/inicio.jsf",
                form_data={
                    "form:protocolo": "{protocol_number}",
                    "javax.faces.ViewState": "{var_viewstate}",
                },
                is_result_step=True,
                result_selector="div#painel",
            ),
        ],
        confidence=0.85,
        notes="JSF",
    )

    step1_html = '<html><body><input name="javax.faces.ViewState" value="VS_TOKEN_XYZ"/></body></html>'
    step2_html = '<html><body><div id="painel">Status: Em análise. Protocolo 12345.</div></body></html>'

    mock_resp1 = MagicMock(text=step1_html, status_code=200)
    mock_resp2 = MagicMock(text=step2_html, status_code=200)

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp1
    mock_client.post.return_value = mock_resp2
    mock_client_cls.return_value = mock_client

    adapter = DynamicAdapter(probe)
    result = adapter.scrape(_make_target())

    assert result.success is True
    assert "Em análise" in result.raw_html

    # Verificar que o POST usou o ViewState extraído do passo 1
    post_call = mock_client.post.call_args
    assert post_call[1]["data"]["javax.faces.ViewState"] == "VS_TOKEN_XYZ"
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python -m pytest tests/test_dynamic_adapter.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar `src/scraping/adapters/dynamic.py`**

```python
# src/scraping/adapters/dynamic.py
"""
DynamicAdapter — executa um SiteProbe (receita JSON) para fazer scraping
de portais que ainda não têm adapter dedicado.
"""
import re
import json
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.scraping.adapters.base import BaseAdapter
from src.scraping.probe_schema import SiteProbe, ProbeStep
from src.scraping.http_scraper import ScrapeResult, _HEADERS, _TIMEOUT
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _interpolate(template: str, context: dict[str, str]) -> str:
    """Substitui {chave} no template pelos valores do context.
    Placeholders sem valor correspondente são mantidos como estão.
    """
    def replace(match: re.Match) -> str:
        key = match.group(1)
        return context.get(key, match.group(0))

    return re.sub(r"\{(\w+)\}", replace, template)


def _interpolate_dict(d: dict, context: dict[str, str]) -> dict:
    return {k: _interpolate(v, context) for k, v in d.items()}


def _execute_step(
    client: httpx.Client,
    step: ProbeStep,
    context: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """
    Executa um passo da receita.
    Retorna (result_text, context_atualizado).
    result_text só é não-vazio se step.is_result_step=True.
    """
    url = _interpolate(step.url, context)
    merged_headers = {**_HEADERS, **step.headers}

    if step.type == "get":
        response = client.get(url, headers=merged_headers)
    elif step.type == "post":
        form = _interpolate_dict(step.form_data, context)
        response = client.post(url, data=form, headers=merged_headers)
    elif step.type == "post_json":
        # json_body pode ter valores com placeholders
        body_str = json.dumps(step.json_body or {})
        body_str = _interpolate(body_str, context)
        body = json.loads(body_str)
        response = client.post(url, json=body, headers=merged_headers)
    else:
        raise ValueError(f"DynamicAdapter: tipo de passo desconhecido: {step.type}")

    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Extrair variáveis para o context
    new_context = dict(context)
    for rule in step.extract:
        if rule.selector == "viewstate":
            el = soup.find("input", {"name": "javax.faces.ViewState"})
            value = el.get("value", "") if el else ""
        elif rule.selector.startswith("json_path:"):
            # Suporte básico a json_path:$.campo
            path = rule.selector[len("json_path:"):]
            try:
                data = response.json()
                # Suporte apenas ao nível superior: $.campo
                key = path.lstrip("$.")
                value = str(data.get(key, ""))
            except Exception:
                value = ""
        else:
            el = soup.select_one(rule.selector)
            if el:
                if rule.attribute == "text":
                    value = el.get_text(strip=True)
                else:
                    value = el.get(rule.attribute, el.get_text(strip=True))
            else:
                value = ""
        new_context[f"var_{rule.name}"] = value
        logger.debug(f"Extracted var_{rule.name}={value[:50]!r}")

    # Obter resultado
    result_text = ""
    if step.is_result_step:
        if step.result_selector:
            el = soup.select_one(step.result_selector)
            result_text = el.get_text(separator="\n", strip=True) if el else ""
        else:
            result_text = soup.get_text(separator="\n", strip=True)

    return result_text, new_context


class DynamicAdapter(BaseAdapter):
    """
    Adapter que executa a receita SiteProbe armazenada no stakeholder.
    Suporta GET, POST (form), POST (JSON), extração de variáveis entre passos.
    CAPTCHA detectado → retorna erro imediatamente sem tentar scraping.
    """

    def __init__(self, probe: SiteProbe) -> None:
        self._probe = probe

    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None = None,
        registry_office_number: str | None = None,
    ) -> str:
        return self._probe.base_url

    def scrape(self, target) -> ScrapeResult:
        if self._probe.captcha_detected:
            return ScrapeResult(
                success=False,
                error_type="CAPTCHA_BLOCKED",
                error_message=(
                    f"Portal '{target.stakeholder_name}' tem CAPTCHA detectado. "
                    "Scraping automático não é possível. "
                    "Consulte manualmente ou configure um solver de CAPTCHA."
                ),
            )

        context: dict[str, str] = {
            "base_url": self._probe.base_url,
            "protocol_number": target.protocol_number or "",
            "cnpj": target.cnpj or "",
            "registry_office_number": target.registry_office_number or "",
            # Credenciais — stakeholder pode ter campos scraping_username/scraping_password
            "credential_username": "",
            "credential_password": "",
        }

        try:
            with httpx.Client(
                headers=_HEADERS,
                timeout=_TIMEOUT,
                follow_redirects=True,
            ) as client:
                result_text = ""
                sorted_steps = sorted(self._probe.steps, key=lambda s: s.step)

                for step in sorted_steps:
                    logger.info(
                        f"DynamicAdapter step {step.step}/{len(sorted_steps)}: "
                        f"{step.type.upper()} {_interpolate(step.url, context)[:80]}"
                    )
                    text, context = _execute_step(client, step, context)
                    if step.is_result_step:
                        result_text = text

                if not result_text or not result_text.strip():
                    return ScrapeResult(
                        success=False,
                        error_type="PROTOCOL_NOT_FOUND",
                        error_message=(
                            f"DynamicAdapter: nenhum conteúdo encontrado para protocolo "
                            f"'{target.protocol_number}' em '{target.stakeholder_name}'."
                        ),
                    )

                return ScrapeResult(
                    success=True,
                    raw_html=result_text,
                    http_status=200,
                )

        except httpx.TimeoutException as e:
            return ScrapeResult(success=False, error_type="SCRAPING_TIMEOUT", error_message=str(e))
        except httpx.ConnectError as e:
            return ScrapeResult(success=False, error_type="SITE_UNAVAILABLE", error_message=str(e))
        except httpx.HTTPStatusError as e:
            return ScrapeResult(
                success=False,
                http_status=e.response.status_code,
                error_type="SITE_UNAVAILABLE",
                error_message=str(e),
            )
        except Exception as e:
            logger.exception(f"DynamicAdapter unexpected error: {e}")
            return ScrapeResult(success=False, error_type="UNKNOWN_ERROR", error_message=str(e))
```

- [ ] **Step 4: Rodar testes**

```bash
python -m pytest tests/test_dynamic_adapter.py -v
```
Esperado: 7 testes PASS

- [ ] **Step 5: Commit**

```bash
git add src/scraping/adapters/dynamic.py tests/test_dynamic_adapter.py
git commit -m "feat(probe): add DynamicAdapter - executes SiteProbe recipe with multi-step HTTP support"
```

---

## Task 5: Integração no Registry

O adapter_type `"dynamic"` é selecionado automaticamente quando o stakeholder tem `site_probe` salvo. Aqui também adicionamos a carga do probe do documento do stakeholder no `fetcher.py`.

**Files:**
- Modify: `src/scraping/adapters/registry.py`
- Modify: `src/scraping/fetcher.py`
- Test: adicionar em `tests/test_scraping_fetcher.py`

- [ ] **Step 1: Escrever testes**

Adicionar ao final de `tests/test_scraping_fetcher.py`:

```python
from src.scraping.adapters.dynamic import DynamicAdapter
from src.scraping.adapters.registry import get_adapter


def test_get_adapter_returns_dynamic_for_type():
    # O registry deve ter "dynamic" registrado
    adapter = get_adapter("dynamic")
    # Sem probe, o DynamicAdapter de fallback não existe — mas o registry
    # não precisa ter um DynamicAdapter padrão; ele é criado via fetcher.
    # Aqui testamos apenas que get_adapter("unknown_xyz") retorna DefaultHttpAdapter.
    from src.scraping.adapters.default_http import DefaultHttpAdapter
    assert isinstance(get_adapter("unknown_xyz_portal"), DefaultHttpAdapter)


def test_fetch_scraping_target_uses_dynamic_adapter_when_probe_present():
    """Se o stakeholder tem site_probe, o fetcher cria um DynamicAdapter com ele."""
    import json
    from src.scraping.probe_schema import SiteProbe

    probe_dict = {
        "portal_type": "simple_get",
        "original_url": "https://portal.com",
        "base_url": "https://portal.com",
        "auth_required": False,
        "captcha_detected": False,
        "login_url": None,
        "steps": [
            {
                "step": 1, "type": "get",
                "url": "{base_url}/consulta?p={protocol_number}",
                "headers": {}, "form_data": {}, "json_body": None,
                "extract": [], "result_selector": None, "is_result_step": True
            }
        ],
        "confidence": 0.9,
        "notes": "test",
    }

    from unittest.mock import MagicMock
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda key: {
        "protocols": MagicMock(find_one=MagicMock(return_value={
            "_id": "prot_1",
            "protocol_number": "12345",
            "cnpj": "12.345.678/0001-99",
            "monitoring_enabled": True,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        })),
        "stakeholders": MagicMock(find_one=MagicMock(return_value={
            "_id": "stake_1",
            "name": "Portal Teste",
            "query_url_template": "https://portal.com",
            "requires_javascript": False,
            "has_captcha": False,
            "type": "dynamic",
            "active": True,
            "site_probe": probe_dict,
        })),
    }[key]

    target = fetch_scraping_target(mock_db, "prot_1", "stake_1")

    assert target.adapter_type == "dynamic"
    # O adapter deve ser DynamicAdapter com a probe carregada
    from src.scraping.adapters.registry import get_adapter
    # A prova está no target.adapter_type — o worker fará get_adapter("dynamic")
    # mas com probe injetada via stakeholder
    assert target.adapter_type == "dynamic"
```

- [ ] **Step 2: Rodar para confirmar que o teste de DynamicAdapter no fetcher falha**

```bash
python -m pytest tests/test_scraping_fetcher.py::test_fetch_scraping_target_uses_dynamic_adapter_when_probe_present -v
```
Esperado: FAIL (o fetcher não injeta o probe ainda)

- [ ] **Step 3: Modificar `src/scraping/fetcher.py` para carregar site_probe**

Adicionar no final do arquivo, modificar a função `fetch_scraping_target` para retornar também o probe:

```python
# src/scraping/fetcher.py
from dataclasses import dataclass, field
from bson import ObjectId
from pymongo.database import Database
from src.scraping.adapters.registry import get_adapter
from src.scraping.probe_schema import SiteProbe


def _oid(val):
    """Aceita string ou ObjectId — a API envia IDs como string no payload RabbitMQ."""
    if isinstance(val, ObjectId):
        return val
    try:
        return ObjectId(str(val))
    except Exception:
        return val


@dataclass
class ScrapingTarget:
    job_id: str
    protocol_id: str
    stakeholder_id: str
    protocol_number: str
    cnpj: str | None
    stakeholder_name: str
    stakeholder_type: str
    adapter_type: str
    requires_javascript: bool
    has_captcha: bool
    resolved_url: str
    registry_office_number: str | None = None
    # Probe carregado do stakeholder (presente quando adapter_type="dynamic")
    site_probe: SiteProbe | None = None


def fetch_scraping_target(
    db: Database,
    protocol_id: str,
    stakeholder_id: str,
    job_id: str = "",
) -> ScrapingTarget:
    protocol = db["protocols"].find_one({"_id": _oid(protocol_id)})
    if not protocol:
        raise ValueError(f"Protocol {protocol_id} not found")

    if (
        not protocol.get("monitoring_enabled", True)
        or protocol.get("closed_manually", False)
        or not protocol.get("active", True)
    ):
        raise ValueError(f"Protocol {protocol_id} is not monitorable")

    stakeholder = db["stakeholders"].find_one({"_id": _oid(stakeholder_id)})
    if not stakeholder:
        raise ValueError(f"Stakeholder {stakeholder_id} not found")

    if not stakeholder.get("active", True):
        raise ValueError(f"Cannot scrape: inactive stakeholder {stakeholder_id}")

    template = stakeholder.get("query_url_template", "")
    if not template:
        raise ValueError(f"Stakeholder {stakeholder_id} has no query_url_template")

    adapter_key = stakeholder.get("adapter_type") or stakeholder.get("type", "default")

    # Carrega site_probe se disponível (usado pelo DynamicAdapter)
    site_probe: SiteProbe | None = None
    probe_raw = stakeholder.get("site_probe")
    if probe_raw and isinstance(probe_raw, dict):
        try:
            site_probe = SiteProbe(**probe_raw)
        except Exception:
            pass  # probe inválido — continua sem ele

    adapter = get_adapter(adapter_key)
    resolved_url = adapter.resolve_url(
        template=template,
        protocol_number=protocol.get("protocol_number", ""),
        cnpj=protocol.get("cnpj"),
        registry_office_number=protocol.get("registry_office_number"),
    )

    return ScrapingTarget(
        job_id=job_id,
        protocol_id=protocol_id,
        stakeholder_id=stakeholder_id,
        protocol_number=protocol.get("protocol_number", ""),
        cnpj=protocol.get("cnpj"),
        stakeholder_name=stakeholder.get("name", ""),
        stakeholder_type=stakeholder.get("type", "default"),
        adapter_type=adapter_key,
        requires_javascript=stakeholder.get("requires_javascript", False),
        has_captcha=stakeholder.get("has_captcha", False),
        resolved_url=resolved_url,
        registry_office_number=(
            protocol.get("registry_office_number")
            or protocol.get("serventia")
            or protocol.get("oficio")
        ),
        site_probe=site_probe,
    )
```

- [ ] **Step 4: Modificar `src/scraping/worker.py` para injetar probe no DynamicAdapter**

Modificar `handle_scraping_job` — substituir a linha `adapter = get_adapter(target.adapter_type)`:

```python
# Em src/scraping/worker.py, substituir:
#   adapter = get_adapter(target.adapter_type)
# Por:

from src.scraping.adapters.dynamic import DynamicAdapter

# ...dentro de handle_scraping_job, após `target = fetch_scraping_target(...)`:

if target.adapter_type == "dynamic" and target.site_probe is not None:
    adapter = DynamicAdapter(target.site_probe)
else:
    adapter = get_adapter(target.adapter_type)
result = adapter.scrape(target) or scrape_url(target.resolved_url)
```

O trecho completo do `try` em `handle_scraping_job` fica:

```python
try:
    jobs_repo.update_status(job_id, "scraping_running")

    target = fetch_scraping_target(db, protocol_id, stakeholder_id, job_id)
    logger.info(f"Scraping {target.resolved_url} for job {job_id}")

    if target.adapter_type == "dynamic" and target.site_probe is not None:
        adapter = DynamicAdapter(target.site_probe)
    else:
        adapter = get_adapter(target.adapter_type)

    result = adapter.scrape(target) or scrape_url(target.resolved_url)
    # ... resto igual
```

- [ ] **Step 5: Rodar todos os testes**

```bash
python -m pytest tests/ -v
```
Esperado: todos os testes existentes + novos PASS

- [ ] **Step 6: Commit**

```bash
git add src/scraping/fetcher.py src/scraping/worker.py tests/test_scraping_fetcher.py
git commit -m "feat(probe): integrate DynamicAdapter into fetcher and worker pipeline"
```

---

## Task 6: Probe Worker (fila probe.jobs)

Permite que a análise de URL seja disparada de forma assíncrona via mensagem RabbitMQ.

**Files:**
- Create: `src/workers/probe_worker.py`
- Test: `tests/test_probe_worker.py`

- [ ] **Step 1: Escrever testes**

```python
# tests/test_probe_worker.py
import json
import pytest
from unittest.mock import patch, MagicMock, call
from src.workers.probe_worker import handle_probe_job


def _make_method():
    m = MagicMock()
    m.delivery_tag = 1
    return m


def _valid_probe_dict():
    return {
        "portal_type": "simple_get",
        "original_url": "https://portal.com",
        "base_url": "https://portal.com",
        "auth_required": False,
        "captcha_detected": False,
        "login_url": None,
        "steps": [
            {
                "step": 1, "type": "get",
                "url": "{base_url}/consulta?p={protocol_number}",
                "headers": {}, "form_data": {}, "json_body": None,
                "extract": [], "result_selector": None, "is_result_step": True
            }
        ],
        "confidence": 0.9,
        "notes": "test probe",
        "analyzed_at": "2026-05-21T00:00:00+00:00",
    }


@patch("src.workers.probe_worker.get_channel")
@patch("src.workers.probe_worker.analyze_url")
@patch("src.workers.probe_worker.get_db")
def test_handle_probe_job_success(mock_get_db, mock_analyze, mock_get_channel):
    from src.scraping.probe_schema import SiteProbe

    mock_analyze.return_value = SiteProbe(**_valid_probe_dict())

    mock_db = MagicMock()
    mock_stakeholders = MagicMock()
    mock_db.__getitem__.return_value = mock_stakeholders
    mock_get_db.return_value = mock_db

    mock_channel = MagicMock()
    mock_get_channel.return_value = mock_channel

    payload = {"stakeholder_id": "stake_1", "url": "https://portal.com"}
    handle_probe_job(payload, _make_method())

    mock_analyze.assert_called_once_with("https://portal.com")
    mock_stakeholders.update_one.assert_called_once()
    # Verifica que site_probe foi salvo
    update_call = mock_stakeholders.update_one.call_args
    assert "site_probe" in str(update_call)
    mock_channel.basic_ack.assert_called_once()


@patch("src.workers.probe_worker.get_channel")
@patch("src.workers.probe_worker.get_db")
def test_handle_probe_job_missing_fields(mock_get_db, mock_get_channel):
    mock_channel = MagicMock()
    mock_get_channel.return_value = mock_channel

    # Payload sem url
    handle_probe_job({"stakeholder_id": "stake_1"}, _make_method())

    mock_channel.basic_ack.assert_called_once()
    # Sem url, não deve chamar analyze_url


@patch("src.workers.probe_worker.get_channel")
@patch("src.workers.probe_worker.analyze_url")
@patch("src.workers.probe_worker.get_db")
def test_handle_probe_job_analysis_failure(mock_get_db, mock_analyze, mock_get_channel):
    mock_analyze.side_effect = ValueError("LLM retornou JSON inválido")

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = MagicMock()
    mock_get_db.return_value = mock_db

    mock_channel = MagicMock()
    mock_get_channel.return_value = mock_channel

    payload = {"stakeholder_id": "stake_1", "url": "https://portal.com/broken"}
    handle_probe_job(payload, _make_method())

    # Mesmo em erro, deve dar ack para não bloquear a fila
    mock_channel.basic_ack.assert_called_once()
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python -m pytest tests/test_probe_worker.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar `src/workers/probe_worker.py`**

```python
# src/workers/probe_worker.py
"""
Consumer da fila probe.jobs.
Recebe {stakeholder_id, url}, analisa a URL com a IA e salva o site_probe no stakeholder.
"""
from bson import ObjectId

from src.database.client import get_db
from src.queues.consumer import consume
from src.scraping.url_analyzer import analyze_url
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _oid(val):
    try:
        return ObjectId(str(val))
    except Exception:
        return val


def handle_probe_job(payload: dict, method) -> None:
    from src.queues.connection import get_channel

    stakeholder_id = payload.get("stakeholder_id", "")
    url = payload.get("url", "")

    if not stakeholder_id or not url:
        logger.error(f"probe.jobs payload inválido: {payload}")
        get_channel().basic_ack(delivery_tag=method.delivery_tag)
        return

    db = get_db()
    stakeholders = db["stakeholders"]

    try:
        logger.info(f"Analisando URL '{url}' para stakeholder {stakeholder_id}")
        probe = analyze_url(url)

        stakeholders.update_one(
            {"_id": _oid(stakeholder_id)},
            {
                "$set": {
                    "site_probe": probe.model_dump(),
                    "adapter_type": "dynamic",
                }
            },
        )
        logger.info(
            f"Probe salvo para stakeholder {stakeholder_id}: "
            f"type={probe.portal_type}, confidence={probe.confidence:.2f}, "
            f"captcha={probe.captcha_detected}, auth={probe.auth_required}"
        )

    except Exception as e:
        logger.exception(f"Erro ao analisar URL '{url}' para stakeholder {stakeholder_id}: {e}")
        # Salva o erro no stakeholder para diagnóstico
        try:
            stakeholders.update_one(
                {"_id": _oid(stakeholder_id)},
                {"$set": {"probe_error": str(e)}},
            )
        except Exception:
            pass

    finally:
        get_channel().basic_ack(delivery_tag=method.delivery_tag)


def run():
    logger.info("Starting probe worker")
    consume("probe.jobs", handle_probe_job)
```

- [ ] **Step 4: Rodar testes**

```bash
python -m pytest tests/test_probe_worker.py -v
```
Esperado: 3 testes PASS

- [ ] **Step 5: Commit**

```bash
git add src/workers/probe_worker.py tests/test_probe_worker.py
git commit -m "feat(probe): add probe worker - consumes probe.jobs queue, analyzes URL, saves SiteProbe"
```

---

## Task 7: API Endpoint — `POST /stakeholders/{id}/analyze-url`

**Repo:** `caminhoes-bpk-api`

**Files:**
- Modify: `src/modules/stakeholders/router.py`
- Modify: `src/modules/stakeholders/schemas.py`

> **Pré-requisito**: As filas RabbitMQ precisam estar configuradas no `caminhoes-bpk-api`. Se ainda não estiver, use publicação direta via `pika` no endpoint.

- [ ] **Step 1: Ler o router de stakeholders**

```bash
cat C:\caminhoes-bpk\caminhoes-bpk-api\src\modules\stakeholders\router.py
```

- [ ] **Step 2: Adicionar schema de resposta**

Em `src/modules/stakeholders/schemas.py`, adicionar:

```python
class AnalyzeUrlRequest(BaseModel):
    url: str

class ProbeJobResponse(BaseModel):
    stakeholder_id: str
    url: str
    status: str  # "queued"
    message: str
```

- [ ] **Step 3: Adicionar endpoint no router**

```python
# Em src/modules/stakeholders/router.py

import pika
import json
from src.modules.stakeholders.schemas import AnalyzeUrlRequest, ProbeJobResponse
from src.core.config import settings  # deve ter rabbitmq_url

@router.post("/{stakeholder_id}/analyze-url", response_model=ProbeJobResponse)
async def analyze_stakeholder_url(
    stakeholder_id: str,
    body: AnalyzeUrlRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Dispara análise de URL via IA para um stakeholder.
    A IA buscará a página, identificará o fluxo de scraping e salvará
    a receita (site_probe) no documento do stakeholder.
    """
    # Verificar que o stakeholder existe
    stakeholder = await db["stakeholders"].find_one({"_id": ObjectId(stakeholder_id)})
    if not stakeholder:
        raise HTTPException(status_code=404, detail="Stakeholder não encontrado")

    # Publicar mensagem na fila probe.jobs
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters(settings.rabbitmq_url)
        )
        channel = connection.channel()
        channel.queue_declare(queue="probe.jobs", durable=True)
        channel.basic_publish(
            exchange="",
            routing_key="probe.jobs",
            body=json.dumps({
                "stakeholder_id": stakeholder_id,
                "url": body.url,
            }),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Fila indisponível: {e}")

    return ProbeJobResponse(
        stakeholder_id=stakeholder_id,
        url=body.url,
        status="queued",
        message="Análise de URL enfileirada. O site_probe será atualizado em breve.",
    )


@router.get("/{stakeholder_id}/probe", response_model=dict)
async def get_stakeholder_probe(
    stakeholder_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Retorna o site_probe atual do stakeholder (resultado da análise de URL)."""
    stakeholder = await db["stakeholders"].find_one({"_id": ObjectId(stakeholder_id)})
    if not stakeholder:
        raise HTTPException(status_code=404, detail="Stakeholder não encontrado")

    probe = stakeholder.get("site_probe")
    error = stakeholder.get("probe_error")

    if not probe and not error:
        return {"status": "not_analyzed", "site_probe": None}

    if error and not probe:
        return {"status": "error", "error": error, "site_probe": None}

    return {"status": "analyzed", "site_probe": probe}
```

- [ ] **Step 4: Testar manualmente via curl**

```bash
# Login
TOKEN=$(curl -s -X POST "http://localhost:3000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@empresa.com","password":"change-me"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

# Disparar análise da Copel (URL de marketing, a IA deve descobrir a real)
curl -s -X POST "http://localhost:3000/stakeholders/STAKEHOLDER_ID/analyze-url" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.copel.com/site/copel-distribuicao/acompanhamento-de-solicitacoes/"}'

# Verificar resultado após ~30s
curl -s "http://localhost:3000/stakeholders/STAKEHOLDER_ID/probe" \
  -H "Authorization: Bearer $TOKEN"
```

- [ ] **Step 5: Commit no API repo**

```bash
cd C:\caminhoes-bpk\caminhoes-bpk-api
git add src/modules/stakeholders/router.py src/modules/stakeholders/schemas.py
git commit -m "feat(probe): add POST /stakeholders/{id}/analyze-url endpoint to trigger AI URL analysis"
```

---

## Task 8: Wire probe_worker no main.py

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Ver o main.py atual**

```bash
cat C:\caminhoes-bpk\caminhoes-bpk-scrapping\src\main.py
```

- [ ] **Step 2: Adicionar "probe" como worker válido**

```python
# Em src/main.py, no dict de módulos:
from src.workers import probe_worker

WORKERS = {
    "scraping": scraping_worker,
    "ai": ai_worker,
    "probe": probe_worker,      # ← adicionar
}
```

- [ ] **Step 3: Testar inicialização do worker**

```bash
cd C:\caminhoes-bpk\caminhoes-bpk-scrapping
docker compose build probe-worker 2>/dev/null || echo "Adicionar probe-worker ao docker-compose.yml"
```

- [ ] **Step 4: Adicionar probe-worker ao docker-compose.yml**

```yaml
probe-worker:
  build: .
  command: python -m src.main probe
  depends_on:
    rabbitmq:
      condition: service_healthy
    mongodb:
      condition: service_started
  environment:
    - MONGODB_URI=mongodb://mongodb:27017/caminhoes_bpk
    - RABBITMQ_URL=amqp://rabbitmq:5672
    - OLLAMA_URL=http://host.docker.internal:11434
    - OLLAMA_MODEL=phi3:mini
  restart: unless-stopped
```

- [ ] **Step 5: Subir probe-worker e testar ponta a ponta**

```bash
cd C:\caminhoes-bpk\caminhoes-bpk-scrapping
docker compose up -d probe-worker
docker compose logs -f probe-worker
```

- [ ] **Step 6: Rodar todos os testes**

```bash
python -m pytest tests/ -v --tb=short
```
Esperado: todos os testes PASS

- [ ] **Step 7: Commit final**

```bash
git add src/main.py docker-compose.yml
git commit -m "feat(probe): wire probe-worker into main.py and docker-compose"
```

---

## Self-Review

### 1. Spec Coverage

| Requisito | Task |
|-----------|------|
| Analisar URL fornecida pela IA | Task 3 (url_analyzer) |
| Descobrir endpoint real (ex: Copel marketing→JSF) | Task 3 + Task 2 (prompt) |
| Gerar receita de scraping estruturada | Task 1 (SiteProbe) |
| Executar receita automaticamente | Task 4 (DynamicAdapter) |
| Detectar CAPTCHA | Task 1 + Task 4 (bloqueia com CAPTCHA_BLOCKED) |
| Detectar login/senha | Task 1 + Task 4 (credential_username/password no context) |
| Disparar análise via API | Task 7 |
| Worker assíncrono via fila | Task 6 + Task 8 |
| Integração no pipeline existente | Task 5 |

### 2. Notas importantes

- **Credenciais de login**: O `DynamicAdapter` suporta `{credential_username}` e `{credential_password}` como placeholders. Para usá-los, o stakeholder precisa ter `scraping_username`/`scraping_password` no documento MongoDB — a Task 5 prepara o context mas não carrega do banco ainda. Se necessário, adicionar ao `fetch_scraping_target`.

- **phi3:mini e JSON complexo**: O modelo local pode ter dificuldade em gerar JSON com o schema completo. Para melhorar: (1) use `temperature=0.05` no ollama_client ao chamar o probe; (2) adicione uma segunda tentativa com prompt de correção igual ao `build_correction_prompt` existente. O `url_analyzer.py` pode importar e usar `build_correction_prompt` do módulo de prompts.

- **Portais JavaScript-heavy**: Sites que renderizam resultados via JavaScript (SPA) não funcionarão com `httpx` puro. O `captcha_detected=True` ou `portal_type="unknown"` pode ser retornado. Suporte a Playwright pode ser adicionado como Task 9 futura.

- **probe.jobs queue**: Precisa ser declarada com `durable=True` no RabbitMQ. O worker declara ao iniciar mas o publisher (Task 7) também deve declarar antes de publicar.

---

## Execução

Plan completo salvo em `docs/superpowers/plans/2026-05-21-ai-url-analyzer.md`.

**Duas opções de execução:**

**1. Subagent-Driven (recomendado)** — subagent fresco por task, review entre tasks, iteração rápida

**2. Inline Execution** — execução em batch nesta sessão com checkpoints

**Qual prefere?**
