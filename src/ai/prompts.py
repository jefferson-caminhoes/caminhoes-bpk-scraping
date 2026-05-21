EXTRACTION_SCHEMA = """{
  "found": boolean,
  "protocol_number": "string|null",
  "cnpj": "string|null",
  "external_status": "string|null",
  "external_situation": "string|null",
  "last_movement_date": "YYYY-MM-DD|null",
  "observation": "string|null",
  "agency": "string|null",
  "oficio": "string|null",
  "confidence": number between 0.0 and 1.0,
  "error": null
}"""

EXTRACTION_PROMPT_TEMPLATE = """Você é um extrator de informações de protocolos de órgãos públicos.

Sua tarefa é analisar o texto fornecido e retornar APENAS um JSON válido.

Regras obrigatórias:
- Não use markdown.
- Não escreva explicações fora do JSON.
- Não invente informações.
- Se uma informação não existir no texto, retorne null.
- Se o texto indicar que o protocolo não foi encontrado, use found=false.
- Datas devem estar no formato YYYY-MM-DD quando possível.
- O campo confidence deve ser um número entre 0 e 1.

Contexto da consulta:
- Número do protocolo buscado: {protocol_number}
- CNPJ: {cnpj}
- Órgão/Stakeholder: {stakeholder_name}

Retorne exatamente este schema:
{schema}

Texto para análise:
{clean_text}"""


def build_extraction_prompt(
    clean_text: str,
    protocol_number: str,
    cnpj: str | None,
    stakeholder_name: str,
) -> str:
    return EXTRACTION_PROMPT_TEMPLATE.format(
        protocol_number=protocol_number,
        cnpj=cnpj or "não informado",
        stakeholder_name=stakeholder_name,
        schema=EXTRACTION_SCHEMA,
        clean_text=clean_text,
    )


CORRECTION_PROMPT_TEMPLATE = """A resposta anterior não era um JSON válido ou não seguia o schema.
Corrija a resposta retornando apenas JSON válido, sem markdown e sem explicações.

Resposta anterior:
{previous_response}

Schema obrigatório:
{schema}"""


def build_correction_prompt(previous_response: str) -> str:
    return CORRECTION_PROMPT_TEMPLATE.format(
        previous_response=previous_response,
        schema=EXTRACTION_SCHEMA,
    )
