from src.scraping.adapters.base import BaseAdapter
from src.scraping.adapters.default_http import DefaultHttpAdapter

_registry: dict[str, BaseAdapter] = {}
_default = DefaultHttpAdapter()


def register_adapter(stakeholder_type: str, adapter: BaseAdapter) -> None:
    _registry[stakeholder_type.lower()] = adapter


def get_adapter(stakeholder_type: str) -> BaseAdapter:
    return _registry.get(stakeholder_type.lower(), _default)
