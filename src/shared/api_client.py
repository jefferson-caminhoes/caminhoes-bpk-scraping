"""
Cliente HTTP para integração com a API interna.
Faz login automático e cacheia o JWT. Reenvia se o token expirar (401).
"""
import threading
import httpx
from src.config.settings import settings
from src.shared.logger import get_logger

logger = get_logger(__name__)

_token: str | None = None
_lock = threading.Lock()


def _login() -> str:
    url = f"{settings.api_base_url}/auth/login"
    response = httpx.post(
        url,
        json={"email": settings.api_admin_email, "password": settings.api_admin_password},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _get_token() -> str:
    global _token
    with _lock:
        if _token is None:
            _token = _login()
            logger.info("API JWT obtido com sucesso")
    return _token


def _invalidate_token() -> None:
    global _token
    with _lock:
        _token = None


def deliver_extraction_result(result_payload: dict) -> None:
    """Entrega resultado de extração para a API via HTTP POST com JWT."""
    if not settings.api_base_url:
        logger.warning("API delivery ignorado: API_BASE_URL não configurado")
        return
    if not settings.api_admin_email or not settings.api_admin_password:
        logger.warning("API delivery ignorado: API_ADMIN_EMAIL ou API_ADMIN_PASSWORD não configurado")
        return

    url = f"{settings.api_base_url}/integrations/extraction-results"

    def _post(token: str) -> httpx.Response:
        return httpx.post(
            url,
            json=result_payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )

    token = _get_token()
    resp = _post(token)

    if resp.status_code == 401:
        # Token expirado — tenta novo login
        _invalidate_token()
        token = _get_token()
        resp = _post(token)

    resp.raise_for_status()
    logger.info(f"Resultado entregue à API — job_id={result_payload.get('job_id')}")
