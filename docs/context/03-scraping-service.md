# 03 — Serviço de Scraping

## Objetivo

Consultar sites reais de stakeholders para buscar informações sobre protocolos, salvar o HTML bruto no MongoDB e disparar o fluxo de limpeza e extração.

---

## Entrada

O scraper consome mensagens da fila `scraping.jobs`.

Exemplo:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123"
}
```

Com esses IDs, o scraper consulta a API ou diretamente o MongoDB para obter:

- número do protocolo;
- CNPJ;
- stakeholder;
- URL de consulta;
- tipo do stakeholder;
- ofício/serventia, quando for cartório;
- flags como `requires_javascript`, `has_captcha`, `requires_cnpj`.

---

## Saída

O scraper deve salvar um documento em `scraped_contents`:

```json
{
  "_id": "content_123",
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "request_url": "https://...",
  "http_status": 200,
  "raw_html": "<html>...</html>",
  "content_hash": "abc123",
  "scraped_at": "2026-05-20T12:00:00Z",
  "error": null
}
```

Depois publica em `cleaner.jobs`:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "scraped_content_id": "content_123"
}
```

---

## Regras de negócio

### RB-SCRAPING-001 — Só consultar protocolos monitoráveis

O scraper não deve consultar protocolos com:

```text
monitoring_enabled=false
closed_manually=true
active=false
```

Idealmente essa filtragem já acontece na API antes de criar o job.

### RB-SCRAPING-002 — Usar CNPJ quando necessário

Se o stakeholder exigir CNPJ, a consulta deve incluir o CNPJ do protocolo.

### RB-SCRAPING-003 — Cartório pode exigir ofício/serventia

Se stakeholder for cartório, e a origem exigir ofício, o scraper deve usar o campo `oficio`/`serventia` do protocolo.

### RB-SCRAPING-004 — HTML bruto deve ser salvo

Mesmo que a extração falhe depois, o HTML bruto deve ser salvo para auditoria e reprocessamento.

### RB-SCRAPING-005 — Não jogar HTML gigante no RabbitMQ

A fila deve receber apenas IDs. O HTML fica no MongoDB.

### RB-SCRAPING-006 — Protocolo não encontrado não é erro fatal

Se o site responder corretamente, mas informar que o protocolo não foi encontrado, salvar como `not_found`, não como falha técnica.

### RB-SCRAPING-007 — Erro técnico deve ir para failed.jobs

Timeout, 500, conexão recusada e HTML vazio devem ser tratados como falha de scraping.

---

## Tipos de resultado

```text
success
not_found
site_unavailable
timeout
blocked
empty_response
unexpected_error
```

---

## Estratégias de consulta

### CURL / Requests

Usar quando:

- site aceita GET/POST simples;
- não depende de JavaScript;
- não tem captcha.

### Playwright / Navegador headless

Usar quando:

- site depende de JavaScript;
- precisa preencher formulário;
- precisa clicar em botão;
- resultado é renderizado dinamicamente.

### Simulação controlada

Usar somente quando:

- houver captcha;
- site bloquear automação;
- site estiver instável no dia da demo.

Mas, para o MVP, tentar pelo menos um site real.

---

## Baby steps de desenvolvimento

### Task SCRAPING-001 — Criar estrutura do serviço

Descrição:

- criar serviço separado;
- configurar conexão com RabbitMQ;
- configurar conexão com MongoDB ou API;
- criar consumidor da fila `scraping.jobs`.

Critérios de aceite:

- serviço consome mensagem fake;
- loga `job_id` recebido.

---

### Task SCRAPING-002 — Buscar dados do job

Descrição:

- ao receber `job_id`, buscar job no MongoDB/API;
- buscar protocolo;
- buscar stakeholder;
- validar se protocolo ainda é monitorável.

Critérios de aceite:

- se protocolo estiver encerrado, job é marcado como ignorado;
- se stakeholder não existir, job vai para erro.

---

### Task SCRAPING-003 — Montar URL de consulta

Descrição:

- usar `query_url_template` do stakeholder;
- substituir placeholders como:
  - `{protocol_number}`;
  - `{cnpj}`;
  - `{oficio}`;
- garantir encoding de parâmetros.

Critérios de aceite:

- URL final é salva em `request_url`;
- CNPJ é usado quando exigido.

---

### Task SCRAPING-004 — Implementar consulta via CURL/Requests

Descrição:

- fazer requisição HTTP;
- configurar timeout;
- configurar user-agent;
- capturar status code;
- capturar HTML.

Critérios de aceite:

- HTML bruto é salvo no MongoDB;
- status HTTP é salvo;
- timeout gera erro controlado.

---

### Task SCRAPING-005 — Detectar resposta vazia ou inválida

Descrição:

- se HTML vier vazio, marcar `empty_response`;
- se status code for 404/500/503, marcar erro apropriado;
- se site tiver mensagem de não encontrado, marcar `not_found`.

Critérios de aceite:

- protocolo não encontrado aparece como `not_found`;
- site fora do ar aparece como erro técnico.

---

### Task SCRAPING-006 — Salvar HTML bruto no MongoDB

Descrição:

- criar documento em `scraped_contents`;
- salvar `raw_html`;
- salvar hash do conteúdo;
- salvar URL e horário.

Critérios de aceite:

- conteúdo pode ser reprocessado depois sem refazer scraping;
- HTML não é publicado no RabbitMQ.

---

### Task SCRAPING-007 — Publicar para cleaner.jobs

Descrição:

- após salvar HTML, publicar mensagem com `scraped_content_id`;
- atualizar job para estágio `cleaning_pending`.

Critérios de aceite:

- cleaner recebe mensagem;
- job mantém rastreabilidade.

---

### Task SCRAPING-008 — Implementar tratamento de erro

Descrição:

- capturar exceptions;
- salvar erro em `consultation_jobs`;
- publicar em `failed.jobs`;
- nunca perder a mensagem sem ack correto.

Critérios de aceite:

- falha não derruba worker;
- erro aparece na tela de monitoramento.

---

### Task SCRAPING-009 — Criar modo manual para demo

Descrição:

- permitir executar scraper para um protocolo específico;
- útil para botão “consultar agora”.

Critérios de aceite:

- botão no detalhe do protocolo consegue disparar consulta;
- resultado aparece depois no protocolo.
