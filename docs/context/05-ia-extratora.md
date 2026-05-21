# 05 — Serviço de IA Extratora

## Objetivo

Receber texto limpo de uma consulta de protocolo e transformar em dados estruturados no formato JSON esperado pela API.

A IA extratora não deve decidir regra de negócio. Ela apenas extrai informações presentes no texto.

---

## Stack sugerida

- Ollama;
- Qwen como modelo local;
- Python;
- Pydantic para validação de schema;
- RabbitMQ para consumo e publicação;
- MongoDB para buscar texto limpo.

---

## Entrada

Consome `ai.extraction.jobs`:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "scraped_content_id": "content_123"
}
```

Busca no MongoDB:

- `clean_text`;
- dados do protocolo;
- stakeholder;
- CNPJ;
- número do protocolo;
- ofício/serventia, se aplicável.

---

## Saída

Publica em `ai.extraction.results`:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "found": true,
  "protocol_number": "12345",
  "external_status": "Aguardando documentação",
  "external_situation": "Pendente",
  "last_movement_date": "2026-05-20",
  "observation": "Enviar documentação complementar",
  "confidence": 0.91,
  "error": null
}
```

---

## Schema obrigatório

```json
{
  "found": true,
  "protocol_number": "string|null",
  "cnpj": "string|null",
  "external_status": "string|null",
  "external_situation": "string|null",
  "last_movement_date": "YYYY-MM-DD|null",
  "observation": "string|null",
  "agency": "string|null",
  "oficio": "string|null",
  "confidence": 0.0,
  "error": {
    "type": "string",
    "message": "string"
  }
}
```

Se o protocolo não for encontrado no texto, usar:

```json
{
  "found": false,
  "protocol_number": "12345",
  "external_status": null,
  "external_situation": null,
  "last_movement_date": null,
  "observation": "O texto indica que o protocolo não foi encontrado",
  "confidence": 0.85,
  "error": null
}
```

---

## Prompt base

```text
Você é um extrator de informações de protocolos de órgãos públicos.

Sua tarefa é analisar o texto fornecido e retornar APENAS um JSON válido.

Regras obrigatórias:
- Não use markdown.
- Não escreva explicações fora do JSON.
- Não invente informações.
- Se uma informação não existir no texto, retorne null.
- Se o texto indicar que o protocolo não foi encontrado, use found=false.
- Datas devem estar no formato YYYY-MM-DD quando possível.
- O campo confidence deve ser um número entre 0 e 1.

Dados esperados:
- número do protocolo;
- CNPJ, se aparecer;
- status externo;
- situação externa;
- data da última movimentação;
- observação ou andamento;
- órgão/agência;
- ofício/serventia, se for cartório.

Retorne exatamente este schema:
{
  "found": boolean,
  "protocol_number": string|null,
  "cnpj": string|null,
  "external_status": string|null,
  "external_situation": string|null,
  "last_movement_date": "YYYY-MM-DD"|null,
  "observation": string|null,
  "agency": string|null,
  "oficio": string|null,
  "confidence": number,
  "error": null|{"type": string, "message": string}
}
```

---

## Regras de negócio

### RB-IA-001 — IA não pode inventar dados

Se a informação não estiver no texto, retornar `null`.

### RB-IA-002 — IA não deve comparar status

A comparação entre status manual e status externo é responsabilidade da API.

### RB-IA-003 — IA não salva diretamente no MongoDB operacional

Para manter controle, a IA publica resultado em fila ou chama endpoint da API. A API valida e salva.

### RB-IA-004 — JSON inválido deve gerar retry

Se o modelo retornar texto fora do JSON, o serviço deve tentar extrair o JSON ou pedir correção uma vez.

### RB-IA-005 — Falha permanente deve virar erro rastreável

Se após retry não houver JSON válido, publicar erro em `failed.jobs` e atualizar job.

### RB-IA-006 — Confiança baixa deve ser sinalizada

Se `confidence < 0.6`, a API pode salvar como resultado, mas marcar para revisão.

---

## Estratégia para garantir JSON

1. Prompt fechado.
2. Temperatura baixa.
3. Resposta sem markdown.
4. Parser JSON robusto.
5. Validação Pydantic.
6. Retry de correção.
7. Fallback de erro.

---

## Exemplo de prompt de correção

```text
A resposta anterior não era um JSON válido ou não seguia o schema.
Corrija a resposta retornando apenas JSON válido, sem markdown e sem explicações.

Resposta anterior:
{{previous_response}}

Schema obrigatório:
{{schema}}
```

---

## Baby steps de desenvolvimento

### Task IA-001 — Criar serviço consumidor

Descrição:

- criar projeto do serviço;
- conectar ao RabbitMQ;
- consumir `ai.extraction.jobs`;
- buscar texto limpo no MongoDB.

Critérios de aceite:

- serviço recebe job e carrega `clean_text`.

---

### Task IA-002 — Configurar Ollama

Descrição:

- definir modelo inicial, preferencialmente Qwen;
- criar wrapper para chamada local;
- configurar timeout;
- configurar temperatura baixa.

Critérios de aceite:

- serviço consegue enviar prompt e receber resposta local.

---

### Task IA-003 — Criar prompt de extração

Descrição:

- implementar prompt base;
- incluir dados auxiliares do protocolo;
- incluir texto limpo;
- limitar tamanho do contexto.

Critérios de aceite:

- para texto fake, modelo retorna JSON com status e observação.

---

### Task IA-004 — Criar schema Pydantic

Descrição:

- definir modelo de validação;
- validar tipos;
- validar `confidence` entre 0 e 1;
- validar data no formato esperado.

Critérios de aceite:

- JSON inválido é rejeitado;
- JSON válido é aceito.

---

### Task IA-005 — Implementar parser de JSON

Descrição:

- tentar fazer `json.loads` direto;
- se falhar, tentar extrair bloco JSON da resposta;
- se falhar, enviar prompt de correção.

Critérios de aceite:

- resposta com texto antes/depois do JSON ainda pode ser recuperada;
- resposta irrecuperável gera erro controlado.

---

### Task IA-006 — Publicar resultado

Descrição:

- publicar payload validado em `ai.extraction.results`;
- incluir `job_id`, `protocol_id`, `stakeholder_id`;
- incluir resultado extraído.

Critérios de aceite:

- API/worker recebe resultado estruturado.

---

### Task IA-007 — Tratar protocolo não encontrado

Descrição:

- criar exemplos no prompt;
- detectar mensagens como “não encontrado”, “protocolo inexistente”, “nenhum resultado”.

Critérios de aceite:

- IA retorna `found=false` quando texto indicar ausência.

---

### Task IA-008 — Registrar erro de extração

Descrição:

- se a IA falhar, publicar em `failed.jobs`;
- salvar tipo de erro:
  - `INVALID_JSON`;
  - `AI_TIMEOUT`;
  - `SCHEMA_VALIDATION_FAILED`;
  - `LOW_CONFIDENCE` quando aplicável.

Critérios de aceite:

- erro aparece no histórico do job;
- mensagem não some silenciosamente.
