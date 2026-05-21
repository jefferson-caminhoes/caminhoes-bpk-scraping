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
