# caminhoes-bpk-scrapping

Serviço de scraping, limpeza e extração de dados por IA para o sistema de protocolos.

## Requisitos

- Python 3.11+
- MongoDB rodando na porta 27017
- RabbitMQ rodando na porta 5672
- Ollama rodando na porta 11434 com modelo `qwen2.5:7b`

## Setup

### 1. Subir infraestrutura

```bash
docker compose up -d
```

Isso sobe MongoDB (27017), RabbitMQ (5672 + UI em 15672) e ChromaDB (8000).

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Editar .env conforme necessário
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Baixar modelo Ollama

```bash
ollama pull qwen2.5:7b
```

## Rodar workers

### Worker de scraping

```bash
python -m src.main scraping
```

### Worker de extração IA

```bash
python -m src.main ai
```

### Scheduler (cria jobs automaticamente)

```bash
python -m src.main scheduler
```

## Rodar testes

```bash
python -m pytest tests/ -v
```

## Estrutura de filas

| Fila | Produtor | Consumidor |
|------|---------|------------|
| `scraping.jobs` | API / Scheduler | Scraping worker |
| `ai.extraction.jobs` | Scraping worker | AI worker |
| `ai.extraction.results` | AI worker | API |
| `failed.jobs` | Qualquer worker | API (monitoramento) |

## Publicar job manual para teste

```bash
python -c "
from src.queues.publisher import publish_message
publish_message('scraping.jobs', {
  'job_id': 'test_job_1',
  'protocol_id': 'SEU_PROTOCOL_ID',
  'stakeholder_id': 'SEU_STAKEHOLDER_ID'
})
print('Publicado!')
"
```

## Estrutura do projeto

```
src/
  config/         # Settings via pydantic-settings
  database/       # MongoDB client e repositories
  queues/         # RabbitMQ connection, publisher, consumer, schemas
  scraping/       # HTTP scraper, fetcher, adapters
  cleaner/        # HTML cleaner e sufficiency checker
  ai/             # Ollama client, prompts, JSON validator, worker
  scheduler/      # APScheduler cron
  shared/         # Logger e error helpers
tests/            # Pytest unit tests
docker-compose.yml
```
