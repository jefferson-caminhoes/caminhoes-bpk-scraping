# src/ai/probe_prompts.py
"""
Prompts LLM para análise de URLs e geração de receitas SiteProbe.
Projetado para funcionar com phi3:mini (3.8B, contexto ~4K tokens).
Prompt em inglês — evita que phi3:mini traduza os nomes dos campos JSON.
"""

# Compact single-step example — less tokens, easier to follow
PROBE_SCHEMA_EXAMPLE = '{"portal_type":"post_form","original_url":"URL","base_url":"https://site.com","auth_required":false,"captcha_detected":false,"login_url":null,"steps":[{"step":1,"type":"post","url":"{base_url}/consulta","form_data":{"protocolo":"{protocol_number}"},"extract":[],"result_selector":"#result","is_result_step":true}],"confidence":0.85,"notes":"reason"}'

PROBE_PROMPT_TEMPLATE = """Return JSON scraping recipe for this URL. ONLY JSON, no explanation.

Original URL: {original_url}
URL: {actual_url}
portal_type options: jsf_form (has ViewState), post_form, rest_api, simple_get, unknown
Placeholders: {{base_url}} {{protocol_number}} {{cnpj}}
JSF: step1 GET + extract viewstate, step2 POST with javax.faces.ViewState:{{var_vs}}
Set is_result_step:true on step that returns the protocol result.

Schema: {schema_example}

HTML: {html_snippet}"""


def build_probe_prompt(
    original_url: str,
    actual_url: str,
    html_snippet: str,
) -> str:
    # Limit HTML to 800 chars — phi3:mini needs ~2K tokens for output
    return PROBE_PROMPT_TEMPLATE.format(
        original_url=original_url,
        actual_url=actual_url,
        html_snippet=html_snippet[:800],
        schema_example=PROBE_SCHEMA_EXAMPLE,
    )
