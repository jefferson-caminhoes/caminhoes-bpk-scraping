from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.scraping.fetcher import ScrapingTarget
    from src.scraping.http_scraper import ScrapeResult


class BaseAdapter(ABC):
    @abstractmethod
    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None,
        registry_office_number: str | None,
    ) -> str: ...

    def scrape(self, target: "ScrapingTarget") -> "Optional[ScrapeResult]":
        """Override to implement custom scraping (e.g., POST-based flows).
        Return None to fall back to the default GET via scrape_url(resolve_url(...))."""
        return None
