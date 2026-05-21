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
