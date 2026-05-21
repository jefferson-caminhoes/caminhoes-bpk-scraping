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
