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
