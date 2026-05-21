from cryptography.fernet import Fernet, InvalidToken

from src.config.settings import settings


def decrypt_secret(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if not settings.stakeholder_secret_key:
        raise ValueError("STAKEHOLDER_SECRET_KEY is required to decrypt stakeholder secrets")
    try:
        return Fernet(settings.stakeholder_secret_key.encode("utf-8")).decrypt(
            value.encode("utf-8")
        ).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted secret") from exc
