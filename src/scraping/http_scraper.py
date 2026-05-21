from dataclasses import dataclass
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
