"""
Adapter para o portal e-Andamento dos Cartórios do Paraná (cartoriospr.com.br).

Fluxo:
  1. GET /eandamento/index.php?token= → extrai mapa serventia→CNS do <select id="serventia">
  2. Usa registry_office_number do protocolo para localizar o CNS
     (aceita nome da serventia OU código CNS de 6 dígitos diretamente)
  3. GET /eandamento/index.php?modulo=consultaPedidoClient&cns={cns}&tipo=1&numero={protocolo}
  4. Parseia <ul class="list-group"> → lista de movimentações
  5. Retorna texto consolidado com dados do protocolo + histórico + status atual

Configuração esperada no stakeholder:
    type: "cartorio"
    query_url_template: "https://www.cartoriospr.com.br/eandamento/index.php"

Configuração esperada no protocolo:
    protocol_number: número do protocolo (ex: "330571")
    registry_office_number: nome da serventia (ex: "Toledo 1 Oficio") ou CNS (6 dígitos)
"""
import httpx
from bs4 import BeautifulSoup

from src.scraping.adapters.base import BaseAdapter
from src.scraping.http_scraper import ScrapeResult, _HEADERS, _TIMEOUT

_DEFAULT_BASE = "https://www.cartoriospr.com.br/eandamento/index.php"
_TIPO = "1"  # 1 = Registro/Averbação


def _normalize_serventia(name: str) -> str:
    """Normaliza nome para comparação tolerante a acentos e símbolos."""
    import re
    import unicodedata
    # NFKD: decompõe acentos e mapeia ordinais (º→o, ª→a)
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    result = ascii_str.lower().replace("-", " ")
    # Remove sufixo ordinal 'o' ou 'a' colado em dígito (ex: "1o" → "1", "2a" → "2")
    result = re.sub(r"(\d)[oa](?=\s|$)", r"\1", result)
    return " ".join(result.split())


class CartorioAdapter(BaseAdapter):
    """Adapter para portais de cartórios do Paraná via cartoriospr.com.br."""

    # Cache de classe: nome_normalizado → cns (compartilhado entre instâncias)
    _cns_cache: dict[str, str] = {}
    _cache_loaded: bool = False

    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None = None,
        registry_office_number: str | None = None,
    ) -> str:
        """Retorna a URL base — a query URL real é montada em scrape()."""
        base = template.split("?")[0] if template else _DEFAULT_BASE
        return base

    # ── CNS lookup ────────────────────────────────────────────────────────────

    def _load_cns_map(self, base_url: str) -> None:
        """Popula o cache serventia→CNS a partir do dropdown da página inicial."""
        if CartorioAdapter._cache_loaded:
            return
        try:
            r = httpx.get(
                f"{base_url}?token=",
                headers=_HEADERS,
                timeout=_TIMEOUT,
                follow_redirects=True,
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            select = soup.find("select", {"id": "serventia"})
            if select:
                for opt in select.find_all("option"):
                    cns = opt.get("data-cns", "").strip()
                    name = opt.get_text(strip=True)
                    if cns and name:
                        CartorioAdapter._cns_cache[_normalize_serventia(name)] = cns
                CartorioAdapter._cache_loaded = True
        except Exception:
            pass  # Falha silenciosa — tenta continuar sem cache

    def _get_cns(self, base_url: str, registry_office_number: str) -> str | None:
        """Retorna o CNS para a serventia. Aceita CNS direto (6 dígitos) ou nome."""
        ron = registry_office_number.strip()

        # CNS direto: sequência de 6 dígitos
        if ron.isdigit() and len(ron) == 6:
            return ron

        self._load_cns_map(base_url)

        ron_norm = _normalize_serventia(ron)

        # Busca exata
        if ron_norm in self._cns_cache:
            return self._cns_cache[ron_norm]

        # Busca parcial (tolerante a variações de escrita)
        for key, cns in self._cns_cache.items():
            if ron_norm in key or key in ron_norm:
                return cns

        return None

    # ── Scraping ──────────────────────────────────────────────────────────────

    def scrape(self, target) -> ScrapeResult:
        ron = (target.registry_office_number or "").strip()
        if not ron:
            return ScrapeResult(
                success=False,
                error_type="MISSING_REGISTRY_OFFICE",
                error_message=(
                    "CartorioAdapter requer 'registry_office_number' preenchido no protocolo. "
                    "Informe o nome da serventia (ex: 'Toledo 1 Oficio') ou o código CNS (6 dígitos)."
                ),
            )

        base_url = target.resolved_url.split("?")[0]

        cns = self._get_cns(base_url, ron)
        if not cns:
            return ScrapeResult(
                success=False,
                error_type="SERVENTIA_NOT_FOUND",
                error_message=(
                    f"CNS não encontrado para serventia '{ron}'. "
                    "Verifique o nome exato no portal ou informe o código CNS (6 dígitos)."
                ),
            )

        query_url = (
            f"{base_url}"
            f"?modulo=consultaPedidoClient"
            f"&cns={cns}"
            f"&tipo={_TIPO}"
            f"&numero={target.protocol_number}"
        )

        try:
            with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
                r = client.get(query_url)
                r.raise_for_status()
                html = r.text

            consolidated = _parse_result(html, target.protocol_number, ron)

            if not consolidated:
                return ScrapeResult(
                    success=False,
                    http_status=r.status_code,
                    error_type="PROTOCOL_NOT_FOUND",
                    error_message=(
                        f"Protocolo '{target.protocol_number}' não localizado "
                        f"na serventia '{ron}' (CNS {cns})."
                    ),
                )

            return ScrapeResult(
                success=True,
                raw_html=consolidated,
                http_status=r.status_code,
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
            return ScrapeResult(
                success=False,
                error_type="UNKNOWN_ERROR",
                error_message=str(e),
            )


# ── HTML parser ───────────────────────────────────────────────────────────────

def _parse_result(html: str, protocol_number: str, serventia: str) -> str:
    """
    Extrai dados do resultado do portal cartoriospr.com.br.

    Retorna texto estruturado para o AI extractor, ou string vazia se o
    protocolo não foi encontrado na página.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Movimentações — presença confirma que o protocolo foi encontrado
    items = soup.select("ul.list-group li.list-group-item")
    if not items:
        return ""

    # Cabeçalho do protocolo (nome apresentante, datas, observações)
    header_lines: list[str] = []
    header_block = soup.find("div", class_="form-login")
    if header_block:
        for line in header_block.get_text(separator="\n", strip=True).splitlines():
            stripped = line.strip()
            if stripped:
                header_lines.append(stripped)

    # Parseia cada item da lista de movimentações
    movements: list[dict[str, str]] = []
    for li in items:
        entry: dict[str, str] = {}
        for b_tag in li.find_all("b"):
            label = b_tag.get_text(strip=True).rstrip(":")
            sibling = b_tag.next_sibling
            value = (str(sibling) if sibling else "").replace("\xa0", " ").strip()
            if label and value:
                entry[label] = value
        if entry:
            movements.append(entry)

    if not movements:
        return ""

    last = movements[-1]
    current_status = last.get("Posição de serviço", "").strip()
    last_date = last.get("Data Movimentação", "").strip()

    # Monta texto consolidado
    lines: list[str] = [
        f"Protocolo: {protocol_number}",
        f"Serventia: {serventia}",
        f"Tipo: Registro/Averbação",
        "",
    ]

    if header_lines:
        lines.append("Dados do protocolo:")
        lines.extend(header_lines)
        lines.append("")

    lines.append("Andamento do serviço:")
    for m in movements:
        parts: list[str] = []
        if "Data Movimentação" in m:
            parts.append(f"Data: {m['Data Movimentação']}")
        if "Setor" in m:
            parts.append(f"Setor: {m['Setor']}")
        if "Posição de serviço" in m:
            parts.append(f"Status: {m['Posição de serviço']}")
        if parts:
            lines.append("  " + " | ".join(parts))

    lines += [
        "",
        f"Status atual (último andamento): {current_status}",
        f"Data do último andamento: {last_date}",
        f"Total de movimentações: {len(movements)}",
    ]

    return "\n".join(lines)
