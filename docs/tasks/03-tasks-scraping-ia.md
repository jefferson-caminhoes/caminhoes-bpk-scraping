# Tasks baby steps — `caminhoes-bpk-scraping`

Este arquivo deve ficar em:

```txt
caminhoes-bpk-scraping/docs/tasks/03-tasks-scraping-ia.md
```

Este repo contém scraping, cleaner/parser, IA extratora e workers RabbitMQ.

---

## SCRAP-001 — Inicializar estrutura base do serviço

### Objetivo

Criar a estrutura do projeto de scraping.

### Estrutura sugerida

```txt
src/
  config/
  workers/
  scraping/
  cleaner/
  ai/
  database/
  queues/
  shared/
```

### Arquivos de ambiente

Criar `.env.example`:

```env
MONGODB_URI=mongodb://localhost:27017/caminhoes_bpk
RABBITMQ_URL=amqp://localhost:5672
API_BASE_URL=http://localhost:3000
API_INTEGRATION_TOKEN=change-me
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### Critério de aceite

- Projeto roda localmente com comando simples.
- Existe health/log inicial no console.
- Configurações são lidas do ambiente.

---

## SCRAP-002 — Configurar conexão com MongoDB

### Objetivo

Permitir salvar e buscar `scraped_contents` e `consultation_jobs`.

### Comportamento

- Conectar no MongoDB.
- Criar camada repository simples.
- Implementar funções:

```txt
saveRawContent
getScrapedContentById
updateScrapedContentCleanText
updateJobStatus
```

### Critério de aceite

- Serviço conecta ao MongoDB.
- Consegue salvar um documento fake em `scraped_contents`.

---

## SCRAP-003 — Configurar RabbitMQ

### Objetivo

Criar infraestrutura de filas.

### Filas do MVP

```txt
scraping.jobs
ai.extraction.jobs
ai.extraction.results
failed.jobs
```

### Implementar

- conexão com RabbitMQ;
- função para publicar mensagem;
- função para consumir mensagem;
- retry simples ou nack em caso de erro;
- envio para `failed.jobs` quando falhar definitivamente.

### Critério de aceite

- Serviço conecta ao RabbitMQ.
- Consegue publicar mensagem de teste.
- Consegue consumir mensagem de teste.

---

## SCRAP-004 — Criar worker consumidor de `scraping.jobs`

### Objetivo

Consumir jobs criados pela API.

### Mensagem esperada

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123"
}
```

### Comportamento inicial

1. Consumir mensagem.
2. Validar campos obrigatórios.
3. Atualizar job para `running`, se possível.
4. Buscar dados necessários no MongoDB ou API.
5. Logar dados do job.

### Critério de aceite

- Worker consome a fila.
- Mensagem inválida vai para `failed.jobs`.
- Mensagem válida avança no fluxo.

---

## SCRAP-005 — Buscar dados do protocolo e stakeholder

### Objetivo

Antes de fazer scraping, obter URL e dados do protocolo.

### Dados necessários

```txt
protocol_number
cnpj
stakeholder.base_url
stakeholder.query_url_template
stakeholder.requires_javascript
stakeholder.has_captcha
stakeholder.type
stakeholder.registry_office_number, se cartório
```

### Fonte dos dados

Preferência:

1. Buscar via API interna, se endpoints existirem.
2. Ou buscar direto no MongoDB para MVP, se mais rápido.

### Regras

- Se protocolo estiver sem monitoramento, não consultar.
- Se stakeholder estiver inativo, não consultar.
- Se stakeholder for cartório, considerar ofício/serventia.

### Critério de aceite

- Worker monta um objeto `ScrapingTarget` completo.
- Se faltar URL, envia erro controlado para `failed.jobs`.

---

## SCRAP-006 — Implementar scraping via HTTP/curl/request

### Objetivo

Consultar sites reais simples via HTTP.

### Comportamento

- Montar URL usando `query_url_template` quando existir.
- Substituir placeholders:

```txt
{protocol_number}
{cnpj}
{registry_office_number}
```

- Fazer request HTTP.
- Capturar status code.
- Capturar HTML bruto.

### Resultado

Salvar em `scraped_contents`:

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "raw_html": "<html>...</html>",
  "http_status": 200,
  "created_at": "date"
}
```

### Critério de aceite

- Consegue consultar pelo menos uma URL real.
- Salva HTML bruto no MongoDB.
- Não manda HTML bruto no RabbitMQ.

---

## SCRAP-007 — Publicar job para cleaner/parser/IA

### Objetivo

Depois de salvar raw HTML, enviar referência para próxima etapa.

### Fila

```txt
ai.extraction.jobs
```

### Mensagem

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "content_id": "content_123"
}
```

### Critério de aceite

- Após scraping bem-sucedido, mensagem é publicada.
- Mensagem contém ID do MongoDB, não HTML.

---

## SCRAP-008 — Implementar cleaner/parser HTML

### Objetivo

Limpar HTML antes de mandar para IA.

### Remover

```txt
<head>
<script>
<style>
css inline irrelevante
menus
footer
header repetitivo
comentários HTML
conteúdo vazio
múltiplos espaços
```

### Manter

```txt
número do protocolo
CNPJ
status
situação
movimentações
datas
observações
mensagens de erro
nome do órgão
conteúdo principal
```

### Função esperada

```txt
cleanHtml(rawHtml) -> cleanText
```

### Critério de aceite

- Dado um HTML fake com script/style/menu/footer, retorna apenas texto útil.
- Salva `clean_text` em `scraped_contents`.

---

## SCRAP-009 — Criar worker consumidor de `ai.extraction.jobs`

### Objetivo

Consumir conteúdos prontos para IA.

### Fluxo

1. Consumir mensagem.
2. Buscar `scraped_contents` pelo `content_id`.
3. Se não existir `clean_text`, rodar cleaner.
4. Enviar texto limpo para IA extratora.
5. Validar retorno.
6. Publicar resultado ou erro.

### Critério de aceite

- Worker consome jobs de extração.
- Busca conteúdo no MongoDB.
- Roda cleaner se necessário.

---

## SCRAP-010 — Criar prompt da IA extratora

### Objetivo

Definir prompt fechado para extrair JSON.

### Prompt base

```txt
Você é um extrator de informações de protocolos de órgãos públicos.

Analise o texto fornecido e retorne apenas um JSON válido.
Não use markdown.
Não escreva explicações.
Não invente informações.
Se uma informação não existir no texto, retorne null.

O JSON deve seguir exatamente este formato:
{
  "protocol_number": "string|null",
  "cnpj": "string|null",
  "found": true,
  "external_status": "string|null",
  "situation": "string|null",
  "last_movement_date": "YYYY-MM-DD|null",
  "observation": "string|null",
  "agency": "string|null",
  "confidence": 0.0,
  "error": null
}
```

### Critério de aceite

- Prompt está em arquivo separado.
- Prompt pode receber variáveis: protocolo, CNPJ, stakeholder e texto limpo.

---

## SCRAP-011 — Integrar IA local via Ollama

### Objetivo

Chamar modelo local para extração.

### Configuração

```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### Comportamento

- Enviar prompt para Ollama.
- Receber resposta.
- Extrair JSON da resposta.
- Não aceitar texto explicativo como resultado final.

### Critério de aceite

- Serviço chama Ollama local.
- Recebe resposta.
- Consegue extrair JSON válido em caso simples.

---

## SCRAP-012 — Validar schema do JSON retornado pela IA

### Objetivo

Garantir que a saída da IA seja confiável.

### Validação

Campos esperados:

```txt
protocol_number
cnpj
found
external_status
situation
last_movement_date
observation
agency
confidence
error
```

### Regras

- `found` deve ser booleano.
- `confidence` deve ser número entre 0 e 1.
- `last_movement_date` deve ser data válida ou null.
- Se JSON inválido, tentar correção uma vez.
- Se ainda inválido, enviar erro controlado.

### Critério de aceite

- JSON válido passa.
- JSON inválido gera erro controlado.
- Existe retry de correção uma vez.

---

## SCRAP-013 — Implementar etapa “IA avalia se precisa cortar mais”

### Objetivo

Adicionar uma etapa opcional onde a IA avalia se o texto limpo ainda tem muito ruído.

### Fluxo

1. Após cleaner, calcular tamanho do texto.
2. Se texto for muito grande ou parecer ruidoso, perguntar para IA:
   - “Este texto contém informações suficientes e relevantes para extrair status de protocolo?”
3. IA responde JSON:

```json
{
  "is_good_enough": true,
  "reason": "Texto contém status e movimentações",
  "suggested_focus": "Usar trecho de movimentações"
}
```

4. Se `is_good_enough=false`, aplicar corte adicional simples:
   - manter linhas próximas de palavras-chave.

### Palavras-chave

```txt
protocolo
status
situação
andamento
movimentação
pendente
aprovado
indeferido
em análise
aguardando
documentação
```

### Regras

- Não criar loop infinito.
- Máximo 1 ciclo de melhoria no MVP.
- Se mesmo assim não ficar bom, tentar extração normal.

### Critério de aceite

- Existe função de avaliação.
- Existe limite de loop.
- Logs mostram se houve refinamento.

---

## SCRAP-014 — Publicar resultado em `ai.extraction.results`

### Objetivo

Enviar dados tabulados para próxima etapa.

### Mensagem

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stakeholder_id": "stake_123",
  "found": true,
  "external_status": "Aguardando documentação",
  "situation": "Aberto",
  "observation": "Enviar documentação complementar",
  "last_movement_date": "2026-05-20",
  "confidence": 0.91,
  "error": null
}
```

### Critério de aceite

- Resultado válido é publicado na fila.
- Resultado contém campos necessários para API atualizar protocolo.

---

## SCRAP-015 — Enviar resultado tabulado para API

### Objetivo

Além da fila, chamar API para salvar resultado.

### Endpoint

```http
POST /integrations/extraction-results
```

### Regras

- Usar token de integração se existir.
- Se API falhar, publicar erro ou manter retry.
- Não perder resultado.

### Critério de aceite

- Serviço envia payload para API.
- API atualiza MongoDB.
- Erro de API fica registrado.

---

## SCRAP-016 — Implementar tratamento de protocolo não encontrado

### Objetivo

Quando o site não retornar o protocolo, marcar isso corretamente.

### Sinais possíveis

```txt
protocolo não encontrado
nenhum resultado encontrado
não localizado
sem dados para consulta
```

### Saída esperada

```json
{
  "found": false,
  "external_status": null,
  "observation": "Protocolo não encontrado na origem",
  "error": null
}
```

### Critério de aceite

- Se texto indicar não encontrado, IA ou parser retorna `found=false`.
- API recebe e marca `not_found_on_source=true`.

---

## SCRAP-017 — Implementar tratamento de falhas controladas

### Objetivo

Padronizar erros.

### Tipos de erro

```txt
SCRAPING_TIMEOUT
SITE_UNAVAILABLE
PROTOCOL_NOT_FOUND
HTML_EMPTY
AI_EXTRACTION_FAILED
INVALID_JSON
VALIDATION_FAILED
API_DELIVERY_FAILED
UNKNOWN_ERROR
```

### Fila de erro

Publicar em:

```txt
failed.jobs
```

### Mensagem

```json
{
  "job_id": "job_123",
  "protocol_id": "prot_123",
  "stage": "scraping|cleaning|ai_extraction|api_delivery",
  "error_type": "SCRAPING_TIMEOUT",
  "error_message": "Timeout ao consultar site",
  "created_at": "date"
}
```

### Critério de aceite

- Erros não derrubam worker.
- Erros vão para `failed.jobs`.
- Logs são claros.

---

## SCRAP-018 — Criar scheduler de consultas

### Objetivo

Rodar consultas automaticamente.

### Opções

Para MVP, pode ser cron interno ou script:

```txt
npm run schedule
python scheduler.py
```

### Fluxo

1. Buscar na API ou MongoDB protocolos com `monitoring_enabled=true` e `active=true`.
2. Criar/publicar jobs em `scraping.jobs`.
3. Ignorar protocolos finalizados.
4. Ignorar stakeholders inativos.

### Frequência

Para demo, permitir configuração:

```env
SCRAPING_CRON=*/30 * * * *
```

### Critério de aceite

- Scheduler publica jobs automaticamente.
- Não publica para protocolo finalizado.
- Logs mostram quantos jobs foram criados.

---

## SCRAP-019 — Criar adapters por stakeholder/site

### Objetivo

Permitir estratégias diferentes por origem de dados.

### Estrutura sugerida

```txt
scraping/adapters/
  default-http.adapter
  copel.adapter
  cartorio.adapter
```

### Comportamento

- Adapter default usa `query_url_template`.
- Adapter Copel pode ter lógica específica.
- Adapter cartório considera `registry_office_number`.

### Critério de aceite

- Existe adapter default.
- É possível registrar adapter específico por tipo/nome.

---

## SCRAP-020 — Criar testes com HTML fake

### Objetivo

Garantir que cleaner e IA/parser funcionam em cenários básicos.

### Cenários

1. HTML com status “Em análise”.
2. HTML com status “Aguardando documentação”.
3. HTML com “protocolo não encontrado”.
4. HTML vazio.
5. HTML com muito script/style/menu.

### Critério de aceite

- Cleaner remove ruído.
- Parser/IA retorna schema esperado.
- Casos de erro são controlados.

---

## SCRAP-021 — Criar README de execução local

### Objetivo

Documentar como rodar o serviço.

### Incluir

- dependências;
- variáveis de ambiente;
- como subir RabbitMQ;
- como subir MongoDB;
- como rodar Ollama/Qwen;
- como iniciar worker de scraping;
- como iniciar worker de IA;
- como iniciar scheduler;
- exemplo de mensagem na fila.

### Critério de aceite

- Qualquer dev consegue rodar localmente seguindo README.
