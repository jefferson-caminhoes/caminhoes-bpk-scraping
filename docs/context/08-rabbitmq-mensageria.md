# 08 — RabbitMQ / Mensageria

## Objetivo

Desacoplar os serviços de scraping, limpeza, IA e persistência. A mensageria permite que cada etapa processe seu trabalho de forma independente, com rastreabilidade e tratamento de erro.

---

## Filas do MVP

### `scraping.jobs`

Jobs de consulta que o scraper deve executar.

Mensagem:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123"
}
```

Consumidor:

- Scraper.

Produtor:

- API ou Scheduler.

---

### `cleaner.jobs`

Jobs com HTML bruto já salvo no MongoDB, prontos para limpeza.

Mensagem:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "scraped_content_id": "content_123"
}
```

Consumidor:

- Cleaner/Parser.

Produtor:

- Scraper.

---

### `ai.extraction.jobs`

Jobs com texto limpo pronto para extração.

Mensagem:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "scraped_content_id": "content_123"
}
```

Consumidor:

- Serviço de IA Extratora.

Produtor:

- Cleaner/Parser.

---

### `ai.extraction.results`

Resultado estruturado da IA.

Mensagem:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "found": true,
  "external_status": "Aguardando documentação",
  "external_situation": "Pendente",
  "last_movement_date": "2026-05-20",
  "observation": "Enviar documentação complementar",
  "confidence": 0.91,
  "error": null
}
```

Consumidor:

- API worker ou serviço de persistência.

Produtor:

- Serviço de IA Extratora.

---

### `failed.jobs`

Fila de erros de qualquer etapa.

Mensagem:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stage": "scraping",
  "error_type": "TIMEOUT",
  "error_message": "Timeout ao consultar site",
  "occurred_at": "2026-05-20T12:00:00Z"
}
```

Consumidor:

- API worker de erro ou monitoramento.

Produtores:

- Scraper;
- Cleaner;
- IA;
- API.

---

## Exchanges sugeridas

Para MVP, pode usar direct exchange simples.

Sugestão:

```text
protocol.monitoring.exchange
```

Routing keys:

```text
scraping.jobs
cleaner.jobs
ai.extraction.jobs
ai.extraction.results
failed.jobs
```

---

## Regras de mensageria

### RB-MQ-001 — Mensagem deve carregar IDs, não HTML

HTML bruto e texto limpo devem ficar no MongoDB. RabbitMQ carrega referências.

### RB-MQ-002 — Toda mensagem precisa ter `job_id`

Sem `job_id`, não existe rastreabilidade.

### RB-MQ-003 — Usar ack somente após sucesso

O consumidor deve dar ack apenas depois de processar e salvar o próximo estado.

### RB-MQ-004 — Falha deve ir para `failed.jobs`

Se uma etapa falhar, publicar mensagem em `failed.jobs` e atualizar o job.

### RB-MQ-005 — Evitar loop infinito

Cada job deve ter contador de tentativas.

Campos sugeridos:

```json
{
  "attempt": 1,
  "max_attempts": 3
}
```

### RB-MQ-006 — Jobs encerrados não devem continuar

Antes de processar, cada worker deve verificar se o job ainda está válido.

---

## Estados do job

```text
pending
scraping_running
scraping_completed
cleaning_pending
cleaning_running
cleaning_completed
ai_pending
ai_running
ai_completed
persisting_result
completed
failed
ignored
```

---

## Baby steps de desenvolvimento

### Task MQ-001 — Subir RabbitMQ local

Descrição:

- criar docker-compose com RabbitMQ;
- habilitar management UI;
- configurar usuário e senha.

Critérios de aceite:

- RabbitMQ acessível localmente;
- painel web abre.

---

### Task MQ-002 — Criar exchange e filas

Descrição:

- criar exchange;
- criar filas do MVP;
- configurar bindings.

Critérios de aceite:

- filas aparecem no painel;
- mensagens publicadas chegam na fila correta.

---

### Task MQ-003 — Criar biblioteca comum de mensagens

Descrição:

- definir contratos de payload;
- criar helpers para publish/consume;
- padronizar `job_id`, `protocol_id`, `stakeholder_id`.

Critérios de aceite:

- serviços usam o mesmo formato de mensagem.

---

### Task MQ-004 — Implementar publicação de scraping.jobs

Descrição:

- API cria job;
- publica mensagem em `scraping.jobs`.

Critérios de aceite:

- ao clicar consultar agora, mensagem aparece na fila.

---

### Task MQ-005 — Implementar fluxo completo com mensagem fake

Descrição:

- publicar uma mensagem fake;
- scraper fake consome e publica cleaner;
- cleaner fake publica IA;
- IA fake publica resultado;
- API fake consome resultado.

Critérios de aceite:

- fluxo ponta a ponta funciona antes da lógica real.

---

### Task MQ-006 — Implementar failed.jobs

Descrição:

- criar função comum para publicar erro;
- todos os workers usam a função;
- API salva erro no job.

Critérios de aceite:

- erro de qualquer etapa aparece no MongoDB.
