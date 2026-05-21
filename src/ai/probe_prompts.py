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

---

HTML da página (estrutura simplificada, até 4000 chars):
{html_snippet}
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
