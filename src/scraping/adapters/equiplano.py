"""
Adapter para o portal Equiplano (e.g., Prefeitura de Toledo – PR).

O portal usa Angular SPA no frontend, mas o backend expõe uma REST API:
  GET /portalContribuinteRest/processos/entidades  → lista de entidades
  GET /portalContribuinteRest/processos            → consulta do processo

Fluxo:
  1. Monta a URL base a partir do query_url_template do stakeholder
  2. CNPJ: tira formatação (apenas dígitos)
  3. Exercício: extraído do protocol_number se contiver "/" (ex: "18047/2025"),
     ou deduzido do ano atual
  4. Faz GET /processos com captcha fake (backend só valida não-vazio)
  5. Retorna texto estruturado para o cleaner/IA
"""
import re
from datetime import datetime, timezone
import httpx

from src.scraping.adapters.base import BaseAdapter
from src.scraping.http_scraper import ScrapeResult, _HEADERS, _TIMEOUT

_FAKE_CAPTCHA = "03AGdBq25_equiplano_bypass"

# Mapeamento nome→id para entidades conhecidas (cache estático)
_KNOWN_ENTITIES: dict[str, str] = {
    "toledo": "136",
}


def _digits_only(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj or "")


def _parse_protocol(protocol_number: str) -> tuple[str, str]:
    """Retorna (numero, exercicio). Aceita '18047/2025' ou '18047'."""
    if "/" in protocol_number:
        parts = protocol_number.split("/", 1)
        return parts[0].strip(), parts[1].strip()
    current_year = str(datetime.now(timezone.utc).year)
    return protocol_number.strip(), current_year


def _get_entity_id(client: httpx.Client, base_url: str, hint: str = "") -> str:
    """Consulta /processos/entidades e retorna o id da entidade mais relevante."""
    try:
        r = client.get(f"{base_url}/processos/entidades", timeout=_TIMEOUT)
        r.raise_for_status()
        entities = r.json()
        if not entities:
            return _KNOWN_ENTITIES.get(hint.lower(), "136")
        # Prioridade: hint no texto da entidade
        if hint:
            for e in entities:
                if hint.lower() in e.get("texto", "").lower():
                    return str(e["valor"])
        # Primeiro da lista
        return str(entities[0]["valor"])
    except Exception:
        return _KNOWN_ENTITIES.get(hint.lower(), "136")


class EquiplanoAdapter(BaseAdapter):
    """Adapter genérico para portais Equiplano municipais."""

    def __init__(self, entity_hint: str = "toledo"):
        self._entity_hint = entity_hint

    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None = None,
        registry_office_number: str | None = None,
    ) -> str:
        # template é a URL base da REST API, ex:
        # https://equiplano.toledo.pr.gov.br:7443/portalContribuinteRest
        return template.rstrip("/")

    def scrape(self, target) -> ScrapeResult:
        try:
            base_url = target.resolved_url
            numero, exercicio = _parse_protocol(target.protocol_number)
            cnpj_digits = _digits_only(target.cnpj or "")

            if not cnpj_digits:
                return ScrapeResult(
                    success=False,
                    error_type="INVALID_INPUT",
                    error_message="Equiplano: CNPJ não informado",
                )

            with httpx.Client(
                follow_redirects=True,
                timeout=_TIMEOUT,
                headers=_HEADERS,
                verify=False,  # alguns portais municipais têm cert auto-assinado
            ) as client:
                entity_id = _get_entity_id(client, base_url, self._entity_hint)

                params = {
                    "nrCpfCnpj": cnpj_digits,
                    "nrProcesso": numero,
                    "nrExercicio": exercicio,
                    "captcha": _FAKE_CAPTCHA,
                    "idEntidade": entity_id,
                }
                r = client.get(f"{base_url}/processos", params=params)
                r.raise_for_status()

                data = r.json()

                # Monta texto estruturado para o cleaner/IA
                lines = [
                    f"Protocolo: {target.protocol_number}",
                    f"Stakeholder: {target.stakeholder_name}",
                    "",
                ]

                situacao = data.get("situacao") or data.get("situação") or ""
                assunto = data.get("assunto", "")
                requerente = data.get("requerente", "")
                numero_retorno = data.get("numero", "")
                exercicio_retorno = data.get("exercicio", exercicio)

                if situacao:
                    lines.append(f"Status: {situacao}")
                if assunto:
                    lines.append(f"Assunto: {assunto}")
                if requerente:
                    lines.append(f"Requerente: {requerente}")
                if numero_retorno:
                    lines.append(f"Numero: {numero_retorno}")
                if exercicio_retorno:
                    lines.append(f"Exercicio: {exercicio_retorno}")

                # Campos extras que o portal pode retornar
                for key in ("dataAbertura", "dataConclusao", "parecerFinal", "observacao"):
                    val = data.get(key)
                    if val:
                        lines.append(f"{key}: {val}")

                consolidated = "\n".join(lines)

                if not situacao and not assunto:
                    return ScrapeResult(
                        success=False,
                        http_status=r.status_code,
                        error_type="HTML_EMPTY",
                        error_message="Equiplano: resposta sem situacao ou assunto",
                    )

                return ScrapeResult(
                    success=True,
                    raw_html=consolidated,
                    http_status=r.status_code,
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
