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
    # Defaults allow LLM to omit fields without breaking validation
    auth_required: bool = False
    captcha_detected: bool = False
    # URL da página de login, se auth_required=True
    login_url: str | None = None
    steps: list[ProbeStep] = Field(default_factory=list)
    # 0.0–1.0: confiança da IA na receita gerada
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    # Explicação da IA sobre o que encontrou
    notes: str = ""
    analyzed_at: str | None = None
