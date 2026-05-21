"""
Adapter para o portal JSF da Copel (Acompanhamento de Solicitações).

Fluxo:
  1. GET /slwweb/publico/acompanhamento/inicio.jsf  → obtém ViewState e jsessionid
  2. POST com o número do protocolo → obtém lista de ordens (sem status)
  3. Para cada ordem: AJAX rowSelect → obtém status individual da ordem
  4. Retorna HTML consolidado com protocolo + lista de ordens + status de cada uma
"""
import xml.etree.ElementTree as ET
import warnings
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from src.scraping.adapters.base import BaseAdapter
from src.scraping.http_scraper import ScrapeResult, _HEADERS, _TIMEOUT

_BASE = "https://www.copel.com"
_JSF_URL = f"{_BASE}/slwweb/publico/acompanhamento/inicio.jsf"
_AJAX_HEADERS = {**_HEADERS, "Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest"}

_NOISE_LINES = {
    "Acompanhamento de serviço comercial",
    "Número do serviço",
    "Pesquisar",
    "A sua solicitação é composta por Ordens que são geradas conforme o andamento do serviço.",
    "Clique sobre a ordem desejada para visualizar o seu respectivo acompanhamento.",
    "Sequência",
    "Descrição",
    "Ok",
    "Aguarde...",
    "Inatividade",
    "Tela inativa por muito tempo!",
    "É importante não confundir o número do serviço com o número do protocolo de atendimento.",
    "Ajuda - Número do serviço",
}

_NOISE_PREFIXES = ("V 3.", "V3.", "© Copel", "Versão")



def _extract_viewstate(soup: BeautifulSoup) -> str | None:
    inp = soup.find("input", {"name": "javax.faces.ViewState"})
    return inp["value"] if inp else None


def _get_order_status(client: httpx.Client, action: str, view_state: str, row_key: str) -> tuple[str, str]:
    """Faz AJAX rowSelect para uma ordem e retorna (status, observacao)."""
    r = client.post(action, data={
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": "formPrincipal:j_idt29",
        "javax.faces.partial.event": "rowSelect",
        "javax.faces.partial.execute": "formPrincipal:j_idt29",
        "javax.faces.partial.render": "formPrincipal",
        "javax.faces.behavior.event": "rowSelect",
        "formPrincipal": "formPrincipal",
        "formPrincipal:j_idt29_selection": row_key,
        "javax.faces.ViewState": view_state,
    }, headers=_AJAX_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()

    root = ET.fromstring(r.text)

    # Atualiza ViewState com o retornado no AJAX
    new_vs = view_state
    for upd in root.iter("update"):
        if "ViewState" in upd.get("id", ""):
            new_vs = upd.text or view_state

    status = ""
    observation = ""
    for upd in root.iter("update"):
        if upd.get("id") == "formPrincipal" and upd.text:
            soup_u = BeautifulSoup(upd.text, "html.parser")
            lines = [l.strip() for l in soup_u.get_text(separator="\n").splitlines() if l.strip()]
            # Filtra ruído para encontrar status e observação
            details = [l for l in lines if l not in _NOISE_LINES and len(l) > 2
                       and l not in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
                       and "APROVAÇÃO" not in l and "OBRAS" not in l
                       and "Sequência" not in l and "Descrição" not in l]
            # Procura padrões de status
            for i, line in enumerate(details):
                if line in {"Concluída", "Em andamento", "Aguardando", "Cancelada", "Pendente"}:
                    status = line
                elif "essa ordem" in line.lower() or "ordem de serviço" in line.lower():
                    observation = line
            if not status and details:
                status = details[0] if details else ""
            break

    return status, observation, new_vs


class CopelAdapter(BaseAdapter):

    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None = None,
        registry_office_number: str | None = None,
    ) -> str:
        return _JSF_URL

    def scrape(self, target) -> ScrapeResult:
        try:
            with httpx.Client(follow_redirects=True, timeout=_TIMEOUT, headers=_HEADERS) as client:
                # Step 1: GET para obter ViewState e cookie de sessão
                r1 = client.get(_JSF_URL)
                r1.raise_for_status()

                soup1 = BeautifulSoup(r1.text, "html.parser")
                form = soup1.find("form", id="formPrincipal")
                if not form:
                    return ScrapeResult(
                        success=False,
                        error_type="SITE_UNAVAILABLE",
                        error_message="Copel: formulário 'formPrincipal' não encontrado",
                    )

                action = form.get("action", "")
                if not action.startswith("http"):
                    action = _BASE + action

                view_state = _extract_viewstate(soup1)
                if not view_state:
                    return ScrapeResult(
                        success=False,
                        error_type="SITE_UNAVAILABLE",
                        error_message="Copel: ViewState não encontrado",
                    )

                text_input = form.find("input", {"type": "text"})
                if not text_input:
                    return ScrapeResult(
                        success=False,
                        error_type="SITE_UNAVAILABLE",
                        error_message="Copel: campo de protocolo não encontrado",
                    )
                input_name = text_input["name"]

                # Step 2: POST com número do protocolo
                r2 = client.post(action, data={
                    "formPrincipal": "formPrincipal",
                    input_name: target.protocol_number,
                    "formPrincipal:btnPesquisar": "",
                    "javax.faces.ViewState": view_state,
                })
                r2.raise_for_status()

                soup2 = BeautifulSoup(r2.text, "html.parser")
                view_state2 = _extract_viewstate(soup2) or view_state

                # Step 3: Extrai lista de ordens da tabela (seq, desc, data-rk)
                table = soup2.find("table", attrs={"role": "grid"})
                orders = []
                if table:
                    for row in table.find("tbody").find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            seq = cells[0].get_text(strip=True)
                            desc = cells[1].get_text(strip=True)
                            row_key = row.get("data-rk", "")
                            if desc:
                                orders.append({
                                    "sequence": seq,
                                    "description": desc,
                                    "row_key": row_key,
                                })

                # Step 4: Para cada ordem, faz AJAX rowSelect para obter status
                cur_vs = view_state2
                for order in orders:
                    if order["row_key"]:
                        status, obs, cur_vs = _get_order_status(
                            client, action, cur_vs, order["row_key"]
                        )
                        order["status"] = status
                        order["observation"] = obs

                # Step 5: Monta HTML consolidado legível para o cleaner/IA
                lines = [
                    f"Protocolo: {target.protocol_number}",
                    f"Stakeholder: Copel",
                    "",
                    "Ordens do protocolo:",
                ]
                for o in orders:
                    lines.append(f"  Sequencia: {o['sequence']}")
                    lines.append(f"  Descricao: {o['description']}")
                    lines.append(f"  Status: {o.get('status') or 'desconhecido'}")
                    if o.get("observation"):
                        lines.append(f"  Observacao: {o['observation']}")
                    lines.append("")

                # Adiciona texto geral da página (status global, mensagens)
                lines.append("")
                page_text = soup2.get_text(separator="\n", strip=True)
                order_descs = {o["description"] for o in orders}
                for line in page_text.splitlines():
                    line = line.strip()
                    if (line and line not in _NOISE_LINES and len(line) > 3
                            and not any(line.startswith(p) for p in _NOISE_PREFIXES)
                            and line not in order_descs):
                        lines.append(line)

                consolidated_html = "\n".join(lines)

                if not orders and not consolidated_html.strip():
                    return ScrapeResult(
                        success=False,
                        http_status=r2.status_code,
                        error_type="HTML_EMPTY",
                        error_message="Copel: nenhuma ordem encontrada na resposta",
                    )

                return ScrapeResult(
                    success=True,
                    raw_html=consolidated_html,
                    http_status=r2.status_code,
                )

        except httpx.TimeoutException as e:
            return ScrapeResult(success=False, error_type="SCRAPING_TIMEOUT", error_message=str(e))
        except httpx.ConnectError as e:
            return ScrapeResult(success=False, error_type="SITE_UNAVAILABLE", error_message=str(e))
        except httpx.HTTPStatusError as e:
            return ScrapeResult(
                success=False,
                http_status=e.response.status_code,
                error_type="SITE_UNAVAILABLE",
                error_message=str(e),
            )
        except Exception as e:
            return ScrapeResult(success=False, error_type="UNKNOWN_ERROR", error_message=str(e))
