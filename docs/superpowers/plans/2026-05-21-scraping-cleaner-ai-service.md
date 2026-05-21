# Scraping + Cleaner + AI Extraction Service — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python worker service that scrapes stakeholder sites, cleans HTML, extracts structured data via Ollama/Qwen, and publishes results back to the API — all connected via RabbitMQ with MongoDB as storage.

**Architecture:** Three independent worker processes (scraping, cleaner, AI extractor) that communicate via RabbitMQ queues. MongoDB stores raw HTML and cleaned text. A shared library handles DB connections, queue I/O, error types, and logging. A scheduler creates periodic scraping jobs. The AI worker calls Ollama locally and validates the response with Pydantic before publishing.

**Tech Stack:** Python 3.11+, pydantic + pydantic-settings, pymongo, pika (RabbitMQ), httpx (HTTP scraping), beautifulsoup4 + lxml (HTML cleaning), pytest + pytest-mock, python-dotenv, apscheduler

---

## File Structure

```
caminhoes-bpk-scrapping/
├── src/
│   ├── config/
│   │   └── settings.py                  # All env vars via pydantic-settings
│   ├── database/
│   │   ├── client.py                    # MongoClient singleton
│   │   └── repositories/
│   │       ├── scraped_contents.py      # save/get/update scraped_contents collection
│   │       └── consultation_jobs.py     # update job status
│   ├── queues/
│   │   ├── connection.py                # pika BlockingConnection singleton
│   │   ├── publisher.py                 # publish(queue, payload)
│   │   ├── consumer.py                  # consume(queue, handler)
│   │   └── schemas.py                   # TypedDicts for every queue message shape
│   ├── scraping/
│   │   ├── worker.py                    # Entry point: consumes scraping.jobs
│   │   ├── fetcher.py                   # Fetches protocol+stakeholder data
│   │   ├── http_scraper.py              # Makes HTTP request, returns raw HTML
│   │   └── adapters/
│   │       ├── base.py                  # Abstract adapter interface
│   │       ├── default_http.py          # Default: template URL + httpx GET
│   │       └── registry.py             # Maps stakeholder type/name → adapter
│   ├── cleaner/
│   │   ├── worker.py                    # Entry: consumes cleaner.jobs (optional – see note)
│   │   ├── html_cleaner.py              # cleanHtml(raw_html) → clean_text
│   │   └── sufficiency_checker.py       # Is the clean text enough for AI?
│   ├── ai/
│   │   ├── worker.py                    # Entry: consumes ai.extraction.jobs
│   │   ├── ollama_client.py             # Thin wrapper around Ollama HTTP API
│   │   ├── prompts.py                   # Extraction prompt template
│   │   ├── schemas.py                   # Pydantic model ExtractionResult
│   │   └── json_validator.py            # parse/retry logic for AI JSON output
│   ├── scheduler/
│   │   └── scheduler.py                 # APScheduler cron: publish scraping.jobs
│   └── shared/
│       ├── errors.py                    # Error type constants + publish_failure()
│       └── logger.py                    # Structured logger setup
├── tests/
│   ├── conftest.py
│   ├── test_settings.py
│   ├── test_db_repositories.py
│   ├── test_html_cleaner.py
│   ├── test_sufficiency_checker.py
│   ├── test_ai_schemas.py
│   ├── test_json_validator.py
│   └── test_scraping_fetcher.py
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── pytest.ini
└── README.md
```

> **Note on cleaner worker:** In the MVP, the AI worker (`ai/worker.py`) runs the cleaner inline before calling Ollama. A separate `cleaner/worker.py` that listens on `cleaner.jobs` is scaffolded but not wired to RabbitMQ unless you want the 3-stage pipeline. The scraper publishes directly to `ai.extraction.jobs` for simplicity (matching `SCRAP-007` in the task spec which references `ai.extraction.jobs`).

---

## Task 1: Project Bootstrap

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `pytest.ini`
- Create: `src/__init__.py`
- Create: `src/config/settings.py`
- Create: `src/shared/logger.py`
- Create: `tests/__init__.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings.py
import pytest
from src.config.settings import Settings


def test_settings_default_values():
    s = Settings(
        _env_file=None,
        mongodb_uri="mongodb://localhost:27017/test_db",
        rabbitmq_url="amqp://localhost:5672",
        api_base_url="http://localhost:3000",
        ollama_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
    )
    assert s.mongodb_uri == "mongodb://localhost:27017/test_db"
    assert s.ollama_model == "qwen2.5:7b"
    assert s.scraping_cron == "*/30 * * * *"


def test_settings_integration_token_defaults_empty():
    s = Settings(
        _env_file=None,
        mongodb_uri="m",
        rabbitmq_url="a",
        api_base_url="h",
        ollama_url="h",
        ollama_model="q",
    )
    assert s.api_integration_token == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/caminhoes-bpk/caminhoes-bpk-scrapping
python -m pytest tests/test_settings.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 3: Create requirements.txt**

```text
# requirements.txt
pydantic>=2.0,<3.0
pydantic-settings>=2.0,<3.0
pymongo>=4.6,<5.0
pika>=1.3,<2.0
httpx>=0.27,<1.0
beautifulsoup4>=4.12,<5.0
lxml>=5.0,<6.0
python-dotenv>=1.0,<2.0
apscheduler>=3.10,<4.0
pytest>=8.0,<9.0
pytest-mock>=3.12,<4.0
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: `Successfully installed pydantic-settings-2.x ...`

- [ ] **Step 5: Create pytest.ini**

```ini
# pytest.ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 6: Create settings module**

```python
# src/__init__.py
# (empty)
```

```python
# src/config/__init__.py
# (empty)
```

```python
# src/config/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017/caminhoes_bpk"
    rabbitmq_url: str = "amqp://localhost:5672"
    api_base_url: str = "http://localhost:3000"
    api_integration_token: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    scraping_cron: str = "*/30 * * * *"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 7: Create logger**

```python
# src/shared/__init__.py
# (empty)
```

```python
# src/shared/logger.py
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
```

- [ ] **Step 8: Create .env.example**

```env
# .env.example
MONGODB_URI=mongodb://localhost:27017/caminhoes_bpk
RABBITMQ_URL=amqp://localhost:5672
API_BASE_URL=http://localhost:3000
API_INTEGRATION_TOKEN=change-me
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
SCRAPING_CRON=*/30 * * * *
```

- [ ] **Step 9: Create missing __init__ files**

```bash
touch tests/__init__.py src/database/__init__.py src/database/repositories/__init__.py src/queues/__init__.py src/scraping/__init__.py src/scraping/adapters/__init__.py src/cleaner/__init__.py src/ai/__init__.py src/scheduler/__init__.py
```

- [ ] **Step 10: Run test to verify it passes**

```bash
python -m pytest tests/test_settings.py -v
```

Expected:
```
tests/test_settings.py::test_settings_default_values PASSED
tests/test_settings.py::test_settings_integration_token_defaults_empty PASSED
2 passed in 0.xx s
```

- [ ] **Step 11: Commit**

```bash
git add requirements.txt .env.example pytest.ini src/ tests/
git commit -m "chore: bootstrap scraping service — settings, logger, project structure"
```

---

## Task 2: MongoDB Client + Repositories

**Files:**
- Create: `src/database/client.py`
- Create: `src/database/repositories/scraped_contents.py`
- Create: `src/database/repositories/consultation_jobs.py`
- Create: `tests/test_db_repositories.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db_repositories.py
from unittest.mock import MagicMock, call
from bson import ObjectId
from src.database.repositories.scraped_contents import ScrapedContentsRepository
from src.database.repositories.consultation_jobs import ConsultationJobsRepository


def test_save_raw_content_returns_inserted_id():
    mock_col = MagicMock()
    inserted_id = ObjectId()
    mock_col.insert_one.return_value = MagicMock(inserted_id=inserted_id)
    repo = ScrapedContentsRepository(mock_col)

    result = repo.save_raw_content(
        job_id="job_123",
        protocol_id="prot_123",
        stakeholder_id="stake_123",
        raw_html="<html><body>Protocolo 99</body></html>",
        http_status=200,
        request_url="https://example.com/consulta?prot=99",
    )

    assert result == str(inserted_id)
    mock_col.insert_one.assert_called_once()
    doc = mock_col.insert_one.call_args[0][0]
    assert doc["job_id"] == "job_123"
    assert doc["raw_html"] == "<html><body>Protocolo 99</body></html>"
    assert doc["http_status"] == 200
    assert doc["error"] is None


def test_get_by_id_returns_document():
    mock_col = MagicMock()
    mock_col.find_one.return_value = {"_id": "abc", "clean_text": "texto limpo"}
    repo = ScrapedContentsRepository(mock_col)

    doc = repo.get_by_id("abc")

    assert doc["clean_text"] == "texto limpo"
    mock_col.find_one.assert_called_once_with({"_id": "abc"})


def test_update_clean_text():
    mock_col = MagicMock()
    repo = ScrapedContentsRepository(mock_col)

    repo.update_clean_text("content_123", "Texto limpo aqui", "generic_html_text_extractor")

    mock_col.update_one.assert_called_once()
    args = mock_col.update_one.call_args
    assert args[0][0] == {"_id": "content_123"}
    update_doc = args[0][1]["$set"]
    assert update_doc["clean_text"] == "Texto limpo aqui"
    assert update_doc["cleaning_strategy"] == "generic_html_text_extractor"


def test_update_job_status():
    mock_col = MagicMock()
    repo = ConsultationJobsRepository(mock_col)

    repo.update_status("job_123", "scraping_running")

    mock_col.update_one.assert_called_once_with(
        {"_id": "job_123"},
        {"$set": {"status": "scraping_running"}},
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_db_repositories.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src.database.repositories.scraped_contents'`

- [ ] **Step 3: Implement database client**

```python
# src/database/client.py
from pymongo import MongoClient
from pymongo.database import Database
from src.config.settings import settings
from src.shared.logger import get_logger

logger = get_logger(__name__)
_client: MongoClient | None = None


def get_db() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri)
        logger.info("MongoDB connected")
    return _client.get_default_database()
```

- [ ] **Step 4: Implement scraped_contents repository**

```python
# src/database/repositories/scraped_contents.py
from datetime import datetime, timezone
from typing import Any
from bson import ObjectId
from pymongo.collection import Collection


class ScrapedContentsRepository:
    def __init__(self, collection: Collection):
        self._col = collection

    def save_raw_content(
        self,
        job_id: str,
        protocol_id: str,
        stakeholder_id: str,
        raw_html: str,
        http_status: int,
        request_url: str,
    ) -> str:
        doc = {
            "job_id": job_id,
            "protocol_id": protocol_id,
            "stakeholder_id": stakeholder_id,
            "request_url": request_url,
            "http_status": http_status,
            "raw_html": raw_html,
            "clean_text": None,
            "cleaning_strategy": None,
            "cleaned_at": None,
            "scraped_at": datetime.now(timezone.utc),
            "error": None,
        }
        result = self._col.insert_one(doc)
        return str(result.inserted_id)

    def get_by_id(self, content_id: str) -> dict[str, Any] | None:
        return self._col.find_one({"_id": content_id})

    def update_clean_text(
        self, content_id: str, clean_text: str, strategy: str
    ) -> None:
        self._col.update_one(
            {"_id": content_id},
            {
                "$set": {
                    "clean_text": clean_text,
                    "cleaning_strategy": strategy,
                    "cleaned_at": datetime.now(timezone.utc),
                }
            },
        )
```

- [ ] **Step 5: Implement consultation_jobs repository**

```python
# src/database/repositories/consultation_jobs.py
from datetime import datetime, timezone
from pymongo.collection import Collection


class ConsultationJobsRepository:
    def __init__(self, collection: Collection):
        self._col = collection

    def update_status(self, job_id: str, status: str) -> None:
        self._col.update_one(
            {"_id": job_id},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )

    def get_by_id(self, job_id: str) -> dict | None:
        return self._col.find_one({"_id": job_id})
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_db_repositories.py -v
```

Expected:
```
tests/test_db_repositories.py::test_save_raw_content_returns_inserted_id PASSED
tests/test_db_repositories.py::test_get_by_id_returns_document PASSED
tests/test_db_repositories.py::test_update_clean_text PASSED
tests/test_db_repositories.py::test_update_job_status PASSED
4 passed in 0.xx s
```

- [ ] **Step 7: Commit**

```bash
git add src/database/ tests/test_db_repositories.py
git commit -m "feat: add MongoDB client and scraped_contents/consultation_jobs repositories"
```

---

## Task 3: RabbitMQ Connection + Queue Schemas

**Files:**
- Create: `src/queues/schemas.py`
- Create: `src/queues/connection.py`
- Create: `src/queues/publisher.py`
- Create: `src/queues/consumer.py`
- Create: `tests/test_queues.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_queues.py
import json
from unittest.mock import MagicMock, patch
from src.queues.schemas import (
    ScrapingJobMessage,
    AiExtractionJobMessage,
    AiExtractionResultMessage,
    FailedJobMessage,
)
from src.queues.publisher import publish_message


def test_scraping_job_message_schema():
    msg = ScrapingJobMessage(
        job_id="job_1",
        protocol_id="prot_1",
        stakeholder_id="stake_1",
    )
    assert msg.job_id == "job_1"
    d = msg.model_dump()
    assert set(d.keys()) == {"job_id", "protocol_id", "stakeholder_id"}


def test_ai_extraction_job_message_schema():
    msg = AiExtractionJobMessage(
        job_id="job_1",
        protocol_id="prot_1",
        stakeholder_id="stake_1",
        content_id="content_1",
    )
    assert msg.content_id == "content_1"


def test_failed_job_message_has_required_fields():
    msg = FailedJobMessage(
        job_id="job_1",
        protocol_id="prot_1",
        stage="scraping",
        error_type="SCRAPING_TIMEOUT",
        error_message="Timeout ao consultar site",
    )
    assert msg.stage == "scraping"
    assert msg.error_type == "SCRAPING_TIMEOUT"


def test_publish_message_calls_basic_publish():
    mock_channel = MagicMock()
    with patch("src.queues.publisher.get_channel", return_value=mock_channel):
        publish_message("scraping.jobs", {"job_id": "j1"})

    mock_channel.basic_publish.assert_called_once()
    args = mock_channel.basic_publish.call_args[1]
    assert args["routing_key"] == "scraping.jobs"
    body = json.loads(args["body"])
    assert body["job_id"] == "j1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_queues.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src.queues.schemas'`

- [ ] **Step 3: Implement queue schemas**

```python
# src/queues/schemas.py
from datetime import datetime
from pydantic import BaseModel


class ScrapingJobMessage(BaseModel):
    job_id: str
    protocol_id: str
    stakeholder_id: str


class AiExtractionJobMessage(BaseModel):
    job_id: str
    protocol_id: str
    stakeholder_id: str
    content_id: str


class AiExtractionResultMessage(BaseModel):
    job_id: str
    protocol_id: str
    stakeholder_id: str
    found: bool
    protocol_number: str | None = None
    external_status: str | None = None
    external_situation: str | None = None
    last_movement_date: str | None = None
    observation: str | None = None
    confidence: float = 0.0
    error: dict | None = None


class FailedJobMessage(BaseModel):
    job_id: str
    protocol_id: str
    stage: str  # scraping | cleaning | ai_extraction | api_delivery
    error_type: str
    error_message: str
```

- [ ] **Step 4: Implement RabbitMQ connection**

```python
# src/queues/connection.py
import pika
from src.config.settings import settings
from src.shared.logger import get_logger

logger = get_logger(__name__)
_channel = None

QUEUES = [
    "scraping.jobs",
    "ai.extraction.jobs",
    "ai.extraction.results",
    "failed.jobs",
]


def get_channel():
    global _channel
    if _channel is None or _channel.is_closed:
        connection = pika.BlockingConnection(
            pika.URLParameters(settings.rabbitmq_url)
        )
        _channel = connection.channel()
        for queue in QUEUES:
            _channel.queue_declare(queue=queue, durable=True)
        logger.info("RabbitMQ channel ready")
    return _channel
```

- [ ] **Step 5: Implement publisher**

```python
# src/queues/publisher.py
import json
import pika
from src.queues.connection import get_channel
from src.shared.logger import get_logger

logger = get_logger(__name__)


def publish_message(queue: str, payload: dict) -> None:
    channel = get_channel()
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(payload),
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent
        ),
    )
    logger.info(f"Published to {queue}: job_id={payload.get('job_id')}")
```

- [ ] **Step 6: Implement consumer**

```python
# src/queues/consumer.py
import json
from typing import Callable
from src.queues.connection import get_channel
from src.shared.logger import get_logger

logger = get_logger(__name__)


def consume(queue: str, handler: Callable[[dict, object], None]) -> None:
    """
    handler(body: dict, method) — call channel.basic_ack(method.delivery_tag) on success.
    On unhandled exception, message is nacked (requeued=False) → goes to dead-letter or lost.
    """
    channel = get_channel()

    def _callback(ch, method, properties, body):
        try:
            payload = json.loads(body)
            handler(payload, method)
        except Exception as e:
            logger.error(f"Unhandled error in {queue} handler: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue, on_message_callback=_callback)
    logger.info(f"Consuming {queue} ...")
    channel.start_consuming()
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
python -m pytest tests/test_queues.py -v
```

Expected:
```
tests/test_queues.py::test_scraping_job_message_schema PASSED
tests/test_queues.py::test_ai_extraction_job_message_schema PASSED
tests/test_queues.py::test_failed_job_message_has_required_fields PASSED
tests/test_queues.py::test_publish_message_calls_basic_publish PASSED
4 passed in 0.xx s
```

- [ ] **Step 8: Commit**

```bash
git add src/queues/ tests/test_queues.py
git commit -m "feat: add RabbitMQ connection, publisher, consumer and message schemas"
```

---

## Task 4: Shared Error Helpers

**Files:**
- Create: `src/shared/errors.py`
- Test coverage added to `tests/test_queues.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_queues.py

def test_publish_failure_sends_to_failed_jobs():
    mock_channel = MagicMock()
    with patch("src.queues.publisher.get_channel", return_value=mock_channel):
        from src.shared.errors import publish_failure
        publish_failure(
            job_id="job_1",
            protocol_id="prot_1",
            stage="scraping",
            error_type="SCRAPING_TIMEOUT",
            error_message="Timeout ao consultar site",
        )

    mock_channel.basic_publish.assert_called_once()
    args = mock_channel.basic_publish.call_args[1]
    assert args["routing_key"] == "failed.jobs"
    body = json.loads(args["body"])
    assert body["error_type"] == "SCRAPING_TIMEOUT"
    assert body["stage"] == "scraping"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_queues.py::test_publish_failure_sends_to_failed_jobs -v
```

Expected: `ImportError: cannot import name 'publish_failure' from 'src.shared.errors'`

- [ ] **Step 3: Implement errors module**

```python
# src/shared/errors.py

# Error type constants
SCRAPING_TIMEOUT = "SCRAPING_TIMEOUT"
SITE_UNAVAILABLE = "SITE_UNAVAILABLE"
PROTOCOL_NOT_FOUND = "PROTOCOL_NOT_FOUND"
HTML_EMPTY = "HTML_EMPTY"
AI_EXTRACTION_FAILED = "AI_EXTRACTION_FAILED"
INVALID_JSON = "INVALID_JSON"
VALIDATION_FAILED = "VALIDATION_FAILED"
API_DELIVERY_FAILED = "API_DELIVERY_FAILED"
UNKNOWN_ERROR = "UNKNOWN_ERROR"


def publish_failure(
    job_id: str,
    protocol_id: str,
    stage: str,
    error_type: str,
    error_message: str,
) -> None:
    from src.queues.publisher import publish_message
    from datetime import datetime, timezone

    publish_message(
        "failed.jobs",
        {
            "job_id": job_id,
            "protocol_id": protocol_id,
            "stage": stage,
            "error_type": error_type,
            "error_message": error_message,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_queues.py -v
```

Expected: all 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/shared/errors.py tests/test_queues.py
git commit -m "feat: add shared error types and publish_failure helper"
```

---

## Task 5: HTML Cleaner / Parser

**Files:**
- Create: `src/cleaner/html_cleaner.py`
- Create: `src/cleaner/sufficiency_checker.py`
- Create: `tests/test_html_cleaner.py`
- Create: `tests/test_sufficiency_checker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_html_cleaner.py
from src.cleaner.html_cleaner import clean_html

DIRTY_HTML = """
<html>
<head><title>Consulta</title><script>alert('hack')</script><style>body{color:red}</style></head>
<body>
  <nav>Menu Home Projetos Logout</nav>
  <header>Sistema de Protocolos</header>
  <!-- comentário irrelevante -->
  <main>
    <h2>Consulta de Protocolo</h2>
    <p>Protocolo: 12345</p>
    <p>CNPJ: 12.345.678/0001-99</p>
    <table>
      <tr><th>Data</th><th>Status</th><th>Observação</th></tr>
      <tr><td>20/05/2026</td><td>Em análise</td><td>Aguardando documentação</td></tr>
    </table>
  </main>
  <footer>Rodapé: termos de uso, cookies, privacidade</footer>
</body>
</html>
"""


def test_removes_script_tags():
    result = clean_html(DIRTY_HTML)
    assert "alert" not in result
    assert "hack" not in result


def test_removes_style_tags():
    result = clean_html(DIRTY_HTML)
    assert "color:red" not in result


def test_removes_nav_and_footer():
    result = clean_html(DIRTY_HTML)
    assert "termos de uso" not in result
    assert "Menu Home" not in result


def test_preserves_protocol_number():
    result = clean_html(DIRTY_HTML)
    assert "12345" in result


def test_preserves_status():
    result = clean_html(DIRTY_HTML)
    assert "Em análise" in result


def test_preserves_table_content():
    result = clean_html(DIRTY_HTML)
    assert "20/05/2026" in result
    assert "Aguardando documentação" in result


def test_removes_html_comments():
    result = clean_html(DIRTY_HTML)
    assert "comentário irrelevante" not in result


def test_returns_string():
    result = clean_html("<html><body><p>Protocolo 99</p></body></html>")
    assert isinstance(result, str)
    assert len(result) > 0


def test_empty_html_returns_empty_string():
    result = clean_html("")
    assert result == ""
```

```python
# tests/test_sufficiency_checker.py
from src.cleaner.sufficiency_checker import is_sufficient

def test_sufficient_text_with_protocol_and_status():
    text = "Protocolo 12345 CNPJ 12.345.678/0001-99 Status Em análise Última movimentação 20/05/2026"
    assert is_sufficient(text) is True


def test_empty_text_is_not_sufficient():
    assert is_sufficient("") is False


def test_very_short_text_is_not_sufficient():
    assert is_sufficient("ok") is False


def test_text_without_keywords_is_not_sufficient():
    text = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor"
    assert is_sufficient(text) is False


def test_text_with_not_found_message_is_sufficient():
    text = "Protocolo não encontrado no sistema de consulta pública"
    assert is_sufficient(text) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_html_cleaner.py tests/test_sufficiency_checker.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src.cleaner.html_cleaner'`

- [ ] **Step 3: Implement HTML cleaner**

```python
# src/cleaner/__init__.py
# (empty)
```

```python
# src/cleaner/html_cleaner.py
import re
from bs4 import BeautifulSoup, Comment


_REMOVE_TAGS = ["script", "style", "head", "nav", "footer", "header", "svg", "noscript"]


def clean_html(raw_html: str) -> str:
    if not raw_html or not raw_html.strip():
        return ""

    soup = BeautifulSoup(raw_html, "lxml")

    # Remove unwanted tags
    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Convert tables to readable text before extracting
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if any(cols):
                rows.append(" | ".join(cols))
        table.replace_with("\n".join(rows))

    text = soup.get_text(separator="\n")

    # Normalize whitespace
    lines = [line.strip() for line in text.splitlines()]
    # Remove duplicate consecutive lines
    deduped = []
    prev = None
    for line in lines:
        if line and line != prev:
            deduped.append(line)
            prev = line

    return "\n".join(deduped)
```

- [ ] **Step 4: Implement sufficiency checker**

```python
# src/cleaner/sufficiency_checker.py
import re

_MIN_LENGTH = 30

_KEYWORDS = [
    "protocolo",
    "status",
    "situação",
    "andamento",
    "movimentação",
    "pendente",
    "aprovado",
    "indeferido",
    "em análise",
    "aguardando",
    "documentação",
    "não encontrado",
    "não localizado",
    "cnpj",
]


def is_sufficient(clean_text: str) -> bool:
    if not clean_text or len(clean_text.strip()) < _MIN_LENGTH:
        return False
    text_lower = clean_text.lower()
    return any(kw in text_lower for kw in _KEYWORDS)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_html_cleaner.py tests/test_sufficiency_checker.py -v
```

Expected:
```
tests/test_html_cleaner.py::test_removes_script_tags PASSED
tests/test_html_cleaner.py::test_removes_style_tags PASSED
tests/test_html_cleaner.py::test_removes_nav_and_footer PASSED
tests/test_html_cleaner.py::test_preserves_protocol_number PASSED
tests/test_html_cleaner.py::test_preserves_status PASSED
tests/test_html_cleaner.py::test_preserves_table_content PASSED
tests/test_html_cleaner.py::test_removes_html_comments PASSED
tests/test_html_cleaner.py::test_returns_string PASSED
tests/test_html_cleaner.py::test_empty_html_returns_empty_string PASSED
tests/test_sufficiency_checker.py::test_sufficient_text_with_protocol_and_status PASSED
tests/test_sufficiency_checker.py::test_empty_text_is_not_sufficient PASSED
tests/test_sufficiency_checker.py::test_very_short_text_is_not_sufficient PASSED
tests/test_sufficiency_checker.py::test_text_without_keywords_is_not_sufficient PASSED
tests/test_sufficiency_checker.py::test_text_with_not_found_message_is_sufficient PASSED
14 passed in 0.xx s
```

- [ ] **Step 6: Commit**

```bash
git add src/cleaner/ tests/test_html_cleaner.py tests/test_sufficiency_checker.py
git commit -m "feat: add HTML cleaner and sufficiency checker for clean text validation"
```

---

## Task 6: AI Extraction Schema + JSON Validator

**Files:**
- Create: `src/ai/schemas.py`
- Create: `src/ai/json_validator.py`
- Create: `tests/test_ai_schemas.py`
- Create: `tests/test_json_validator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai_schemas.py
import pytest
from pydantic import ValidationError
from src.ai.schemas import ExtractionResult


def test_valid_extraction_result():
    result = ExtractionResult(
        found=True,
        protocol_number="12345",
        external_status="Em análise",
        confidence=0.92,
    )
    assert result.found is True
    assert result.confidence == 0.92


def test_confidence_must_be_between_0_and_1():
    with pytest.raises(ValidationError):
        ExtractionResult(found=True, confidence=1.5)


def test_confidence_negative_raises():
    with pytest.raises(ValidationError):
        ExtractionResult(found=True, confidence=-0.1)


def test_all_optional_fields_default_to_none():
    result = ExtractionResult(found=False, confidence=0.8)
    assert result.protocol_number is None
    assert result.external_status is None
    assert result.last_movement_date is None
    assert result.observation is None
    assert result.agency is None
    assert result.oficio is None
    assert result.error is None


def test_not_found_result():
    result = ExtractionResult(
        found=False,
        protocol_number="99999",
        observation="Protocolo não encontrado na origem",
        confidence=0.85,
    )
    assert result.found is False
    assert result.observation == "Protocolo não encontrado na origem"
```

```python
# tests/test_json_validator.py
import pytest
from src.ai.json_validator import extract_json_from_text, validate_extraction_result
from src.ai.schemas import ExtractionResult


def test_parse_clean_json():
    raw = '{"found": true, "confidence": 0.9, "external_status": "Em análise"}'
    result = extract_json_from_text(raw)
    assert result["found"] is True
    assert result["confidence"] == 0.9


def test_parse_json_with_markdown_fences():
    raw = '```json\n{"found": true, "confidence": 0.8}\n```'
    result = extract_json_from_text(raw)
    assert result["found"] is True


def test_parse_json_with_surrounding_text():
    raw = 'Aqui está o resultado: {"found": false, "confidence": 0.5} fim.'
    result = extract_json_from_text(raw)
    assert result["found"] is False


def test_raises_when_no_json_found():
    with pytest.raises(ValueError, match="No valid JSON"):
        extract_json_from_text("Não consigo extrair nada")


def test_validate_extraction_result_returns_model():
    data = {"found": True, "confidence": 0.91, "external_status": "Aprovado"}
    result = validate_extraction_result(data)
    assert isinstance(result, ExtractionResult)
    assert result.external_status == "Aprovado"


def test_validate_raises_on_invalid_confidence():
    data = {"found": True, "confidence": 5.0}
    with pytest.raises(Exception):
        validate_extraction_result(data)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_ai_schemas.py tests/test_json_validator.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src.ai.schemas'`

- [ ] **Step 3: Implement AI schemas**

```python
# src/ai/__init__.py
# (empty)
```

```python
# src/ai/schemas.py
from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    found: bool
    protocol_number: str | None = None
    cnpj: str | None = None
    external_status: str | None = None
    external_situation: str | None = None
    last_movement_date: str | None = None
    observation: str | None = None
    agency: str | None = None
    oficio: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    error: dict | None = None
```

- [ ] **Step 4: Implement JSON validator**

```python
# src/ai/json_validator.py
import json
import re
from src.ai.schemas import ExtractionResult


def extract_json_from_text(text: str) -> dict:
    """Try to extract a JSON object from raw LLM output."""
    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in AI response: {text[:200]!r}")


def validate_extraction_result(data: dict) -> ExtractionResult:
    return ExtractionResult.model_validate(data)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_ai_schemas.py tests/test_json_validator.py -v
```

Expected:
```
tests/test_ai_schemas.py::test_valid_extraction_result PASSED
tests/test_ai_schemas.py::test_confidence_must_be_between_0_and_1 PASSED
tests/test_ai_schemas.py::test_confidence_negative_raises PASSED
tests/test_ai_schemas.py::test_all_optional_fields_default_to_none PASSED
tests/test_ai_schemas.py::test_not_found_result PASSED
tests/test_json_validator.py::test_parse_clean_json PASSED
tests/test_json_validator.py::test_parse_json_with_markdown_fences PASSED
tests/test_json_validator.py::test_parse_json_with_surrounding_text PASSED
tests/test_json_validator.py::test_raises_when_no_json_found PASSED
tests/test_json_validator.py::test_validate_extraction_result_returns_model PASSED
tests/test_json_validator.py::test_validate_raises_on_invalid_confidence PASSED
11 passed in 0.xx s
```

- [ ] **Step 6: Commit**

```bash
git add src/ai/schemas.py src/ai/json_validator.py tests/test_ai_schemas.py tests/test_json_validator.py
git commit -m "feat: add AI extraction Pydantic schema and JSON parser with retry logic"
```

---

## Task 7: Ollama Client + Extraction Prompt

**Files:**
- Create: `src/ai/prompts.py`
- Create: `src/ai/ollama_client.py`
- Create: `tests/test_ollama_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ollama_client.py
import pytest
from unittest.mock import patch, MagicMock
from src.ai.ollama_client import call_ollama, build_extraction_prompt


def test_build_extraction_prompt_contains_clean_text():
    prompt = build_extraction_prompt(
        clean_text="Protocolo 12345 Status Em análise",
        protocol_number="12345",
        cnpj="12.345.678/0001-99",
        stakeholder_name="Prefeitura",
    )
    assert "12345" in prompt
    assert "Em análise" in prompt
    assert "12.345.678/0001-99" in prompt
    assert "Prefeitura" in prompt


def test_build_extraction_prompt_contains_schema():
    prompt = build_extraction_prompt(
        clean_text="texto",
        protocol_number="1",
        cnpj=None,
        stakeholder_name="Copel",
    )
    assert "found" in prompt
    assert "external_status" in prompt
    assert "confidence" in prompt


def test_call_ollama_returns_response_text():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": '{"found": true, "confidence": 0.9}'}
    }

    with patch("httpx.post", return_value=mock_response):
        result = call_ollama("Test prompt")

    assert result == '{"found": true, "confidence": 0.9}'


def test_call_ollama_raises_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = Exception("HTTP 500")

    with patch("httpx.post", return_value=mock_response):
        with pytest.raises(Exception, match="HTTP 500"):
            call_ollama("Test prompt")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_ollama_client.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src.ai.ollama_client'`

- [ ] **Step 3: Implement extraction prompt**

```python
# src/ai/prompts.py

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
```

- [ ] **Step 4: Implement Ollama client**

```python
# src/ai/ollama_client.py
import httpx
from src.config.settings import settings
from src.shared.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT = 60.0


def call_ollama(prompt: str) -> str:
    """Send prompt to Ollama and return raw text response."""
    url = f"{settings.ollama_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1},
    }
    response = httpx.post(url, json=payload, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()["message"]["content"]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_ollama_client.py -v
```

Expected:
```
tests/test_ollama_client.py::test_build_extraction_prompt_contains_clean_text PASSED
tests/test_ollama_client.py::test_build_extraction_prompt_contains_schema PASSED
tests/test_ollama_client.py::test_call_ollama_returns_response_text PASSED
tests/test_ollama_client.py::test_call_ollama_raises_on_http_error PASSED
4 passed in 0.xx s
```

- [ ] **Step 6: Commit**

```bash
git add src/ai/prompts.py src/ai/ollama_client.py tests/test_ollama_client.py
git commit -m "feat: add Ollama client and extraction prompt template"
```

---

## Task 8: Scraping Fetcher (Protocol + Stakeholder Data)

**Files:**
- Create: `src/scraping/fetcher.py`
- Create: `src/scraping/adapters/base.py`
- Create: `src/scraping/adapters/default_http.py`
- Create: `src/scraping/adapters/registry.py`
- Create: `tests/test_scraping_fetcher.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scraping_fetcher.py
import pytest
from unittest.mock import MagicMock, patch
from src.scraping.fetcher import fetch_scraping_target, ScrapingTarget
from src.scraping.adapters.default_http import DefaultHttpAdapter


def _make_mock_db(protocol: dict, stakeholder: dict):
    mock_db = MagicMock()
    mock_db["protocols"].find_one.return_value = protocol
    mock_db["stakeholders"].find_one.return_value = stakeholder
    return mock_db


def test_fetch_scraping_target_returns_target():
    mock_db = _make_mock_db(
        protocol={
            "_id": "prot_1",
            "protocol_number": "12345",
            "cnpj": "12.345.678/0001-99",
            "monitoring_enabled": True,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        },
        stakeholder={
            "_id": "stake_1",
            "name": "Prefeitura",
            "query_url_template": "https://prefeitura.gov.br/consulta?prot={protocol_number}",
            "requires_javascript": False,
            "has_captcha": False,
            "type": "prefeitura",
            "active": True,
        },
    )

    target = fetch_scraping_target(mock_db, "prot_1", "stake_1")

    assert target.protocol_number == "12345"
    assert target.cnpj == "12.345.678/0001-99"
    assert "12345" in target.resolved_url


def test_fetch_raises_if_protocol_not_monitorable():
    mock_db = _make_mock_db(
        protocol={
            "_id": "prot_1",
            "protocol_number": "12345",
            "monitoring_enabled": False,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        },
        stakeholder={"_id": "stake_1", "active": True},
    )

    with pytest.raises(ValueError, match="not monitorable"):
        fetch_scraping_target(mock_db, "prot_1", "stake_1")


def test_fetch_raises_if_stakeholder_inactive():
    mock_db = _make_mock_db(
        protocol={
            "_id": "prot_1",
            "protocol_number": "12345",
            "monitoring_enabled": True,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        },
        stakeholder={"_id": "stake_1", "active": False},
    )

    with pytest.raises(ValueError, match="inactive stakeholder"):
        fetch_scraping_target(mock_db, "prot_1", "stake_1")


def test_default_http_adapter_resolves_url():
    adapter = DefaultHttpAdapter()
    url = adapter.resolve_url(
        template="https://example.com?prot={protocol_number}&cnpj={cnpj}",
        protocol_number="12345",
        cnpj="12.345.678/0001-99",
        registry_office_number=None,
    )
    assert "12345" in url
    assert "12.345.678" in url
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_scraping_fetcher.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src.scraping.fetcher'`

- [ ] **Step 3: Implement adapters**

```python
# src/scraping/adapters/__init__.py
# (empty)
```

```python
# src/scraping/adapters/base.py
from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    @abstractmethod
    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None,
        registry_office_number: str | None,
    ) -> str: ...
```

```python
# src/scraping/adapters/default_http.py
from urllib.parse import quote
from src.scraping.adapters.base import BaseAdapter


class DefaultHttpAdapter(BaseAdapter):
    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None,
        registry_office_number: str | None,
    ) -> str:
        url = template
        url = url.replace("{protocol_number}", quote(protocol_number, safe=""))
        url = url.replace("{cnpj}", quote(cnpj or "", safe=""))
        url = url.replace(
            "{registry_office_number}",
            quote(registry_office_number or "", safe=""),
        )
        return url
```

```python
# src/scraping/adapters/registry.py
from src.scraping.adapters.base import BaseAdapter
from src.scraping.adapters.default_http import DefaultHttpAdapter

_registry: dict[str, BaseAdapter] = {}
_default = DefaultHttpAdapter()


def register_adapter(stakeholder_type: str, adapter: BaseAdapter) -> None:
    _registry[stakeholder_type.lower()] = adapter


def get_adapter(stakeholder_type: str) -> BaseAdapter:
    return _registry.get(stakeholder_type.lower(), _default)
```

- [ ] **Step 4: Implement scraping fetcher**

```python
# src/scraping/fetcher.py
from dataclasses import dataclass
from pymongo.database import Database
from src.scraping.adapters.registry import get_adapter


@dataclass
class ScrapingTarget:
    job_id: str
    protocol_id: str
    stakeholder_id: str
    protocol_number: str
    cnpj: str | None
    stakeholder_name: str
    stakeholder_type: str
    requires_javascript: bool
    has_captcha: bool
    resolved_url: str
    registry_office_number: str | None = None


def fetch_scraping_target(
    db: Database,
    protocol_id: str,
    stakeholder_id: str,
    job_id: str = "",
) -> ScrapingTarget:
    protocol = db["protocols"].find_one({"_id": protocol_id})
    if not protocol:
        raise ValueError(f"Protocol {protocol_id} not found")

    if (
        not protocol.get("monitoring_enabled", True)
        or protocol.get("closed_manually", False)
        or not protocol.get("active", True)
    ):
        raise ValueError(f"Protocol {protocol_id} is not monitorable")

    stakeholder = db["stakeholders"].find_one({"_id": stakeholder_id})
    if not stakeholder:
        raise ValueError(f"Stakeholder {stakeholder_id} not found")

    if not stakeholder.get("active", True):
        raise ValueError(f"Cannot scrape: inactive stakeholder {stakeholder_id}")

    template = stakeholder.get("query_url_template", "")
    if not template:
        raise ValueError(f"Stakeholder {stakeholder_id} has no query_url_template")

    adapter = get_adapter(stakeholder.get("type", "default"))
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
        requires_javascript=stakeholder.get("requires_javascript", False),
        has_captcha=stakeholder.get("has_captcha", False),
        resolved_url=resolved_url,
        registry_office_number=protocol.get("registry_office_number"),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_scraping_fetcher.py -v
```

Expected:
```
tests/test_scraping_fetcher.py::test_fetch_scraping_target_returns_target PASSED
tests/test_scraping_fetcher.py::test_fetch_raises_if_protocol_not_monitorable PASSED
tests/test_scraping_fetcher.py::test_fetch_raises_if_stakeholder_inactive PASSED
tests/test_scraping_fetcher.py::test_default_http_adapter_resolves_url PASSED
4 passed in 0.xx s
```

- [ ] **Step 6: Commit**

```bash
git add src/scraping/ tests/test_scraping_fetcher.py
git commit -m "feat: add scraping target fetcher with protocol/stakeholder validation and adapter registry"
```

---

## Task 9: HTTP Scraper (Make Real Requests)

**Files:**
- Create: `src/scraping/http_scraper.py`
- Create: `tests/test_http_scraper.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_http_scraper.py
import pytest
from unittest.mock import patch, MagicMock
from src.scraping.http_scraper import scrape_url, ScrapeResult


def _mock_response(status: int, html: str):
    r = MagicMock()
    r.status_code = status
    r.text = html
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return r


def test_scrape_success_returns_html():
    mock_resp = _mock_response(200, "<html><body>Protocolo 12345</body></html>")
    with patch("httpx.get", return_value=mock_resp):
        result = scrape_url("https://example.com")

    assert result.success is True
    assert "Protocolo 12345" in result.raw_html
    assert result.http_status == 200
    assert result.error_type is None


def test_scrape_empty_response_returns_error():
    mock_resp = _mock_response(200, "")
    with patch("httpx.get", return_value=mock_resp):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type == "HTML_EMPTY"


def test_scrape_404_returns_site_unavailable():
    mock_resp = _mock_response(404, "")
    with patch("httpx.get", return_value=mock_resp):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type in ("SITE_UNAVAILABLE", "HTML_EMPTY")


def test_scrape_timeout_returns_timeout_error():
    import httpx
    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type == "SCRAPING_TIMEOUT"


def test_scrape_connection_error_returns_site_unavailable():
    import httpx
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type == "SITE_UNAVAILABLE"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_http_scraper.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'src.scraping.http_scraper'`

- [ ] **Step 3: Implement HTTP scraper**

```python
# src/scraping/http_scraper.py
from dataclasses import dataclass, field
import httpx
from src.shared.logger import get_logger

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 30.0


@dataclass
class ScrapeResult:
    success: bool
    raw_html: str = ""
    http_status: int = 0
    error_type: str | None = None
    error_message: str | None = None


def scrape_url(url: str) -> ScrapeResult:
    try:
        response = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True)
        response.raise_for_status()

        html = response.text
        if not html or not html.strip():
            return ScrapeResult(
                success=False,
                http_status=response.status_code,
                error_type="HTML_EMPTY",
                error_message="Site returned empty body",
            )

        return ScrapeResult(
            success=True,
            raw_html=html,
            http_status=response.status_code,
        )

    except httpx.TimeoutException as e:
        return ScrapeResult(
            success=False,
            error_type="SCRAPING_TIMEOUT",
            error_message=str(e),
        )
    except httpx.ConnectError as e:
        return ScrapeResult(
            success=False,
            error_type="SITE_UNAVAILABLE",
            error_message=str(e),
        )
    except httpx.HTTPStatusError as e:
        return ScrapeResult(
            success=False,
            http_status=e.response.status_code,
            error_type="SITE_UNAVAILABLE",
            error_message=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected scraping error for {url}")
        return ScrapeResult(
            success=False,
            error_type="UNKNOWN_ERROR",
            error_message=str(e),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_http_scraper.py -v
```

Expected:
```
tests/test_http_scraper.py::test_scrape_success_returns_html PASSED
tests/test_http_scraper.py::test_scrape_empty_response_returns_error PASSED
tests/test_http_scraper.py::test_scrape_404_returns_site_unavailable PASSED
tests/test_http_scraper.py::test_scrape_timeout_returns_timeout_error PASSED
tests/test_http_scraper.py::test_scrape_connection_error_returns_site_unavailable PASSED
5 passed in 0.xx s
```

- [ ] **Step 5: Commit**

```bash
git add src/scraping/http_scraper.py tests/test_http_scraper.py
git commit -m "feat: add HTTP scraper with timeout, connection error and empty response handling"
```

---

## Task 10: Scraping Worker (Full Pipeline)

**Files:**
- Create: `src/scraping/worker.py`
- No new test file — integration test in next task

- [ ] **Step 1: Implement scraping worker**

This worker ties together: fetcher → http_scraper → save to MongoDB → publish to ai.extraction.jobs.

```python
# src/scraping/worker.py
from src.config.settings import settings
from src.database.client import get_db
from src.database.repositories.scraped_contents import ScrapedContentsRepository
from src.database.repositories.consultation_jobs import ConsultationJobsRepository
from src.queues.consumer import consume
from src.queues.publisher import publish_message
from src.scraping.fetcher import fetch_scraping_target
from src.scraping.http_scraper import scrape_url
from src.shared.errors import publish_failure
from src.shared.logger import get_logger

logger = get_logger(__name__)


def handle_scraping_job(payload: dict, method) -> None:
    from src.queues.connection import get_channel

    job_id = payload.get("job_id", "")
    protocol_id = payload.get("protocol_id", "")
    stakeholder_id = payload.get("stakeholder_id", "")

    if not all([job_id, protocol_id, stakeholder_id]):
        logger.error(f"Invalid scraping job payload: {payload}")
        publish_failure(
            job_id=job_id,
            protocol_id=protocol_id,
            stage="scraping",
            error_type="VALIDATION_FAILED",
            error_message=f"Missing required fields in payload: {payload}",
        )
        get_channel().basic_ack(delivery_tag=method.delivery_tag)
        return

    db = get_db()
    jobs_repo = ConsultationJobsRepository(db["consultation_jobs"])
    contents_repo = ScrapedContentsRepository(db["scraped_contents"])

    try:
        jobs_repo.update_status(job_id, "scraping_running")

        target = fetch_scraping_target(db, protocol_id, stakeholder_id, job_id)
        logger.info(f"Scraping {target.resolved_url} for job {job_id}")

        result = scrape_url(target.resolved_url)

        if not result.success:
            jobs_repo.update_status(job_id, "failed")
            publish_failure(
                job_id=job_id,
                protocol_id=protocol_id,
                stage="scraping",
                error_type=result.error_type or "UNKNOWN_ERROR",
                error_message=result.error_message or "Scraping failed",
            )
            get_channel().basic_ack(delivery_tag=method.delivery_tag)
            return

        content_id = contents_repo.save_raw_content(
            job_id=job_id,
            protocol_id=protocol_id,
            stakeholder_id=stakeholder_id,
            raw_html=result.raw_html,
            http_status=result.http_status,
            request_url=target.resolved_url,
        )

        jobs_repo.update_status(job_id, "scraping_completed")
        logger.info(f"HTML saved as content {content_id} for job {job_id}")

        publish_message(
            "ai.extraction.jobs",
            {
                "job_id": job_id,
                "protocol_id": protocol_id,
                "stakeholder_id": stakeholder_id,
                "content_id": content_id,
            },
        )
        jobs_repo.update_status(job_id, "ai_pending")

    except ValueError as e:
        logger.warning(f"Business rule violation for job {job_id}: {e}")
        jobs_repo.update_status(job_id, "ignored")
        publish_failure(
            job_id=job_id,
            protocol_id=protocol_id,
            stage="scraping",
            error_type="VALIDATION_FAILED",
            error_message=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error in scraping job {job_id}")
        jobs_repo.update_status(job_id, "failed")
        publish_failure(
            job_id=job_id,
            protocol_id=protocol_id,
            stage="scraping",
            error_type="UNKNOWN_ERROR",
            error_message=str(e),
        )
    finally:
        get_channel().basic_ack(delivery_tag=method.delivery_tag)


def run():
    logger.info("Starting scraping worker")
    consume("scraping.jobs", handle_scraping_job)
```

- [ ] **Step 2: Verify the file is syntactically correct**

```bash
python -c "from src.scraping.worker import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/scraping/worker.py
git commit -m "feat: add scraping worker — consume scraping.jobs, save raw HTML, publish to ai.extraction.jobs"
```

---

## Task 11: AI Extraction Worker (Full Pipeline)

**Files:**
- Create: `src/ai/worker.py`

- [ ] **Step 1: Implement the AI worker**

This worker: fetch content from MongoDB → clean HTML if needed → call Ollama → validate JSON → publish result + call API.

```python
# src/ai/worker.py
import httpx
from src.config.settings import settings
from src.database.client import get_db
from src.database.repositories.scraped_contents import ScrapedContentsRepository
from src.database.repositories.consultation_jobs import ConsultationJobsRepository
from src.queues.consumer import consume
from src.queues.publisher import publish_message
from src.cleaner.html_cleaner import clean_html
from src.cleaner.sufficiency_checker import is_sufficient
from src.ai.ollama_client import call_ollama
from src.ai.prompts import build_extraction_prompt, build_correction_prompt
from src.ai.json_validator import extract_json_from_text, validate_extraction_result
from src.shared.errors import publish_failure
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _deliver_to_api(result_payload: dict) -> None:
    if not settings.api_base_url or not settings.api_integration_token:
        logger.warning("API delivery skipped: no API_BASE_URL or API_INTEGRATION_TOKEN")
        return
    url = f"{settings.api_base_url}/integrations/extraction-results"
    headers = {"Authorization": f"Bearer {settings.api_integration_token}"}
    response = httpx.post(url, json=result_payload, headers=headers, timeout=15.0)
    response.raise_for_status()
    logger.info(f"Result delivered to API for job {result_payload.get('job_id')}")


def handle_ai_extraction_job(payload: dict, method) -> None:
    from src.queues.connection import get_channel

    job_id = payload.get("job_id", "")
    protocol_id = payload.get("protocol_id", "")
    stakeholder_id = payload.get("stakeholder_id", "")
    content_id = payload.get("content_id", "")

    if not all([job_id, protocol_id, stakeholder_id, content_id]):
        publish_failure(
            job_id=job_id, protocol_id=protocol_id,
            stage="ai_extraction", error_type="VALIDATION_FAILED",
            error_message=f"Missing fields: {payload}",
        )
        get_channel().basic_ack(delivery_tag=method.delivery_tag)
        return

    db = get_db()
    jobs_repo = ConsultationJobsRepository(db["consultation_jobs"])
    contents_repo = ScrapedContentsRepository(db["scraped_contents"])

    try:
        jobs_repo.update_status(job_id, "ai_running")

        content = contents_repo.get_by_id(content_id)
        if not content:
            raise ValueError(f"Content {content_id} not found")

        clean_text = content.get("clean_text")
        if not clean_text:
            clean_text = clean_html(content.get("raw_html", ""))
            if clean_text:
                contents_repo.update_clean_text(content_id, clean_text, "generic_html_text_extractor")

        if not is_sufficient(clean_text):
            raise ValueError("Clean text is insufficient for extraction")

        protocol = db["protocols"].find_one({"_id": protocol_id}) or {}
        stakeholder = db["stakeholders"].find_one({"_id": stakeholder_id}) or {}

        prompt = build_extraction_prompt(
            clean_text=clean_text,
            protocol_number=protocol.get("protocol_number", ""),
            cnpj=protocol.get("cnpj"),
            stakeholder_name=stakeholder.get("name", ""),
        )

        raw_response = call_ollama(prompt)

        # Try to parse, with one correction retry
        try:
            data = extract_json_from_text(raw_response)
        except ValueError:
            logger.warning(f"First parse failed for job {job_id}, retrying with correction prompt")
            correction_prompt = build_correction_prompt(raw_response)
            raw_response = call_ollama(correction_prompt)
            data = extract_json_from_text(raw_response)  # Raises if still fails

        result = validate_extraction_result(data)
        jobs_repo.update_status(job_id, "ai_completed")

        result_payload = {
            "job_id": job_id,
            "protocol_id": protocol_id,
            "stakeholder_id": stakeholder_id,
            **result.model_dump(),
        }

        publish_message("ai.extraction.results", result_payload)

        try:
            _deliver_to_api(result_payload)
        except Exception as e:
            logger.error(f"API delivery failed for job {job_id}: {e}")
            publish_failure(
                job_id=job_id, protocol_id=protocol_id,
                stage="api_delivery", error_type="API_DELIVERY_FAILED",
                error_message=str(e),
            )

        jobs_repo.update_status(job_id, "completed")

    except Exception as e:
        logger.exception(f"AI extraction failed for job {job_id}: {e}")
        jobs_repo.update_status(job_id, "failed")
        publish_failure(
            job_id=job_id, protocol_id=protocol_id,
            stage="ai_extraction", error_type="AI_EXTRACTION_FAILED",
            error_message=str(e),
        )
    finally:
        get_channel().basic_ack(delivery_tag=method.delivery_tag)


def run():
    logger.info("Starting AI extraction worker")
    consume("ai.extraction.jobs", handle_ai_extraction_job)
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "from src.ai.worker import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ai/worker.py
git commit -m "feat: add AI extraction worker — clean HTML, call Ollama, validate JSON, publish result"
```

---

## Task 12: Scheduler

**Files:**
- Create: `src/scheduler/scheduler.py`

- [ ] **Step 1: Implement scheduler**

```python
# src/scheduler/__init__.py
# (empty)
```

```python
# src/scheduler/scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from src.config.settings import settings
from src.database.client import get_db
from src.queues.publisher import publish_message
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _create_scraping_jobs() -> None:
    db = get_db()
    protocols = list(
        db["protocols"].find(
            {
                "monitoring_enabled": True,
                "active": True,
                "closed_manually": {"$ne": True},
            },
            {"_id": 1, "stakeholder_id": 1},
        )
    )

    if not protocols:
        logger.info("No monitorable protocols found")
        return

    published = 0
    for protocol in protocols:
        stakeholder_id = protocol.get("stakeholder_id")
        if not stakeholder_id:
            continue

        stakeholder = db["stakeholders"].find_one(
            {"_id": stakeholder_id, "active": True}, {"_id": 1}
        )
        if not stakeholder:
            continue

        from datetime import datetime, timezone
        job_id = f"auto_{protocol['_id']}_{int(datetime.now(timezone.utc).timestamp())}"

        publish_message(
            "scraping.jobs",
            {
                "job_id": job_id,
                "protocol_id": str(protocol["_id"]),
                "stakeholder_id": str(stakeholder_id),
            },
        )
        published += 1

    logger.info(f"Scheduler published {published} scraping jobs")


def run():
    logger.info(f"Starting scheduler with cron: {settings.scraping_cron}")
    scheduler = BlockingScheduler()
    # Parse "*/30 * * * *" → minute="*/30", hour="*", ...
    parts = settings.scraping_cron.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
    else:
        minute, hour, day, month, day_of_week = "*/30", "*", "*", "*", "*"

    scheduler.add_job(
        _create_scraping_jobs,
        "cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "from src.scheduler.scheduler import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/scheduler/
git commit -m "feat: add APScheduler-based job scheduler that publishes scraping.jobs on cron"
```

---

## Task 13: Main Entry Points

**Files:**
- Create: `src/main.py`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create main.py with worker selection**

```python
# src/main.py
import sys
from src.shared.logger import get_logger

logger = get_logger("main")

WORKERS = {
    "scraping": "src.scraping.worker",
    "ai": "src.ai.worker",
    "scheduler": "src.scheduler.scheduler",
}


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python -m src.main <worker>")
        print(f"Available workers: {', '.join(WORKERS.keys())}")
        sys.exit(1)

    worker_name = sys.argv[1]
    if worker_name not in WORKERS:
        print(f"Unknown worker: {worker_name}. Available: {', '.join(WORKERS.keys())}")
        sys.exit(1)

    import importlib
    module = importlib.import_module(WORKERS[worker_name])
    logger.info(f"Starting worker: {worker_name}")
    module.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify main entry points**

```bash
python -m src.main --help 2>&1 | head -5
```

Expected: `Usage: python -m src.main <worker>`

- [ ] **Step 3: Create docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"

services:
  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: caminhoes_bpk

  rabbitmq:
    image: rabbitmq:3.13-management
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma

volumes:
  mongo_data:
  chroma_data:
```

- [ ] **Step 4: Commit**

```bash
git add src/main.py docker-compose.yml
git commit -m "feat: add main entry point for worker selection and docker-compose for infra"
```

---

## Task 14: End-to-End Tests with Fake HTML

**Files:**
- Create: `tests/test_error_scenarios.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/conftest.py
import pytest

PROTOCOL_NOT_FOUND_HTML = """
<html><head><title>Consulta</title></head>
<body>
  <main>
    <p>Protocolo não encontrado no sistema.</p>
    <p>Por favor, verifique o número informado.</p>
  </main>
</body>
</html>
"""

STATUS_EM_ANALISE_HTML = """
<html><head></head>
<body>
  <main>
    <h2>Resultado da Consulta</h2>
    <p>Protocolo: 12345</p>
    <p>CNPJ: 12.345.678/0001-99</p>
    <p>Status: Em análise</p>
    <table>
      <tr><th>Data</th><th>Andamento</th></tr>
      <tr><td>20/05/2026</td><td>Aguardando documentação complementar</td></tr>
    </table>
  </main>
</body>
</html>
"""

EMPTY_HTML = ""

NOISY_HTML = """
<html>
<head><script>var x=1;</script><style>.a{color:red}</style></head>
<body>
  <nav>Home Projetos Sair</nav>
  <div class="cookie-banner">Usamos cookies. Aceitar</div>
  <main>
    <p>Protocolo: 99999</p>
    <p>Situação: Aprovado</p>
    <p>Última movimentação: 10/01/2026</p>
  </main>
  <footer>© 2026 Prefeitura. Termos de uso.</footer>
</body>
</html>
"""
```

```python
# tests/test_error_scenarios.py
import pytest
from tests.conftest import (
    PROTOCOL_NOT_FOUND_HTML,
    STATUS_EM_ANALISE_HTML,
    EMPTY_HTML,
    NOISY_HTML,
)
from src.cleaner.html_cleaner import clean_html
from src.cleaner.sufficiency_checker import is_sufficient


def test_not_found_html_cleans_to_sufficient_text():
    clean = clean_html(PROTOCOL_NOT_FOUND_HTML)
    assert "não encontrado" in clean.lower()
    assert is_sufficient(clean)


def test_status_em_analise_html_preserves_status():
    clean = clean_html(STATUS_EM_ANALISE_HTML)
    assert "Em análise" in clean
    assert "12345" in clean
    assert "20/05/2026" in clean
    assert is_sufficient(clean)


def test_empty_html_is_not_sufficient():
    clean = clean_html(EMPTY_HTML)
    assert not is_sufficient(clean)


def test_noisy_html_removes_noise_and_preserves_content():
    clean = clean_html(NOISY_HTML)
    assert "var x=1" not in clean
    assert "color:red" not in clean
    assert "cookie" not in clean.lower()
    assert "© 2026" not in clean
    assert "Aprovado" in clean
    assert "99999" in clean
    assert is_sufficient(clean)


def test_noisy_html_removes_nav():
    clean = clean_html(NOISY_HTML)
    assert "Home Projetos Sair" not in clean
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_error_scenarios.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or some test failures.

- [ ] **Step 3: Run all tests to see full status**

```bash
python -m pytest tests/ -v
```

Expected: All previously passing tests still pass + new tests pass.

- [ ] **Step 4: Fix any failures**

If `test_not_found_html_cleans_to_sufficient_text` fails because the cleaned text is too short, check `_MIN_LENGTH` in `sufficiency_checker.py` — the not-found HTML may produce text shorter than 30 chars. Lower `_MIN_LENGTH` to 20 if needed, but only if the keyword check also passes.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected:
```
tests/test_settings.py::test_settings_default_values PASSED
tests/test_settings.py::test_settings_integration_token_defaults_empty PASSED
tests/test_db_repositories.py::test_save_raw_content_returns_inserted_id PASSED
tests/test_db_repositories.py::test_get_by_id_returns_document PASSED
tests/test_db_repositories.py::test_update_clean_text PASSED
tests/test_db_repositories.py::test_update_job_status PASSED
tests/test_queues.py::test_scraping_job_message_schema PASSED
tests/test_queues.py::test_ai_extraction_job_message_schema PASSED
tests/test_queues.py::test_failed_job_message_has_required_fields PASSED
tests/test_queues.py::test_publish_message_calls_basic_publish PASSED
tests/test_queues.py::test_publish_failure_sends_to_failed_jobs PASSED
tests/test_html_cleaner.py::* PASSED (9 tests)
tests/test_sufficiency_checker.py::* PASSED (5 tests)
tests/test_ai_schemas.py::* PASSED (5 tests)
tests/test_json_validator.py::* PASSED (6 tests)
tests/test_ollama_client.py::* PASSED (4 tests)
tests/test_scraping_fetcher.py::* PASSED (4 tests)
tests/test_http_scraper.py::* PASSED (5 tests)
tests/test_error_scenarios.py::* PASSED (5 tests)
XX passed in X.xx s
```

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py tests/test_error_scenarios.py
git commit -m "test: add end-to-end HTML scenario tests for cleaner and sufficiency checker"
```

---

## Task 15: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup, workers and queue structure"
```

---

## Self-Review

### Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| SCRAP-001 Estrutura do serviço | Task 1 |
| SCRAP-002 MongoDB | Task 2 |
| SCRAP-003 RabbitMQ | Task 3 |
| SCRAP-004 Worker scraping.jobs | Task 10 |
| SCRAP-005 Buscar dados protocolo/stakeholder | Task 8 |
| SCRAP-006 HTTP scraping | Task 9 |
| SCRAP-007 Publicar ai.extraction.jobs | Task 10 |
| SCRAP-008 Cleaner/parser | Task 5 |
| SCRAP-009 Worker ai.extraction.jobs | Task 11 |
| SCRAP-010 Prompt extração | Task 7 |
| SCRAP-011 Ollama integration | Task 7 |
| SCRAP-012 Validar schema JSON | Task 6 |
| SCRAP-013 IA avalia suficiência | Task 5 (sufficiency_checker) |
| SCRAP-014 Publicar ai.extraction.results | Task 11 |
| SCRAP-015 Enviar para API | Task 11 (_deliver_to_api) |
| SCRAP-016 Protocolo não encontrado | Tasks 5 + 14 |
| SCRAP-017 Tratamento de falhas | Task 4 (errors.py) + Tasks 10/11 |
| SCRAP-018 Scheduler | Task 12 |
| SCRAP-019 Adapters por stakeholder | Task 8 (registry) |
| SCRAP-020 Testes com HTML fake | Task 14 |
| SCRAP-021 README | Task 15 |

No gaps found.

### Placeholder Scan

No TBD, TODO, or placeholder patterns found. All code blocks are complete.

### Type Consistency Check

- `ScrapingTarget.resolved_url` → used in `worker.py` as `target.resolved_url` ✓
- `ScrapeResult.raw_html` → used in `worker.py` as `result.raw_html` ✓
- `contents_repo.save_raw_content(...)` returns `str` → used as `content_id` in publisher ✓
- `ExtractionResult.model_dump()` → used in result_payload spread ✓
- `ScrapedContentsRepository(collection)` takes `Collection` → tests mock with `MagicMock()` ✓
