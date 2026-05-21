from src.scraping.adapters.base import BaseAdapter
from src.scraping.adapters.default_http import DefaultHttpAdapter
from src.scraping.adapters.copel import CopelAdapter
from src.scraping.adapters.equiplano import EquiplanoAdapter
from src.scraping.adapters.cartorio import CartorioAdapter

_registry: dict[str, BaseAdapter] = {
    "copel": CopelAdapter(),
    "equiplano_toledo": EquiplanoAdapter(entity_hint="toledo"),
    "cartorio": CartorioAdapter(),
}
_default = DefaultHttpAdapter()


def register_adapter(stakeholder_type: str, adapter: BaseAdapter) -> None:
    _registry[stakeholder_type.lower()] = adapter


def get_adapter(stakeholder_type: str) -> BaseAdapter:
    return _registry.get(stakeholder_type.lower(), _default)
