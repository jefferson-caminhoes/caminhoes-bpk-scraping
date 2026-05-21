# src/scraping/adapters/dynamic.py
import re
import json
import httpx
from bs4 import BeautifulSoup

from src.scraping.adapters.base import BaseAdapter
from src.scraping.probe_schema import SiteProbe, ProbeStep
from src.scraping.http_scraper import ScrapeResult, _HEADERS, _TIMEOUT
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _interpolate(template: str, context: dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        return context.get(key, match.group(0))
    return re.sub(r"\{(\w+)\}", replace, template)


def _interpolate_dict(d: dict, context: dict[str, str]) -> dict:
    return {k: _interpolate(v, context) for k, v in d.items()}


def _execute_step(
    client: httpx.Client,
    step: ProbeStep,
    context: dict[str, str],
) -> tuple[str, dict[str, str]]:
    url = _interpolate(step.url, context)

    if step.type == "get":
        response = client.get(url, headers=step.headers)
    elif step.type == "post":
        form = _interpolate_dict(step.form_data, context)
        response = client.post(url, data=form, headers=step.headers)
    elif step.type == "post_json":
        body_str = json.dumps(step.json_body or {})
        body_str = _interpolate(body_str, context)
        body = json.loads(body_str)
        response = client.post(url, json=body, headers=step.headers)
    else:
        raise ValueError(f"DynamicAdapter: tipo de passo desconhecido: {step.type}")

    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    new_context = dict(context)
    for rule in step.extract:
        if rule.selector == "viewstate":
            el = soup.find("input", {"name": "javax.faces.ViewState"})
            value = el.get("value", "") if el else ""
        elif rule.selector.startswith("json_path:"):
            path = rule.selector[len("json_path:"):]
            try:
                data = response.json()
                key = path.lstrip("$.")
                value = str(data.get(key, ""))
            except Exception:
                value = ""
        else:
            el = soup.select_one(rule.selector)
            if el:
                value = (
                    el.get_text(strip=True)
                    if rule.attribute == "text"
                    else el.get(rule.attribute, el.get_text(strip=True))
                )
            else:
                value = ""
        new_context[f"var_{rule.name}"] = value
        logger.debug(f"Extracted var_{rule.name}={value[:50]!r}")

    result_text = ""
    if step.is_result_step:
        if step.result_selector:
            el = soup.select_one(step.result_selector)
            result_text = el.get_text(separator="\n", strip=True) if el else ""
        else:
            result_text = soup.get_text(separator="\n", strip=True)

    return result_text, new_context


class DynamicAdapter(BaseAdapter):
    def __init__(self, probe: SiteProbe) -> None:
        self._probe = probe

    def resolve_url(
        self,
        template: str,
        protocol_number: str,
        cnpj: str | None = None,
        registry_office_number: str | None = None,
    ) -> str:
        return self._probe.base_url

    def scrape(self, target) -> ScrapeResult:
        if self._probe.captcha_detected:
            return ScrapeResult(
                success=False,
                error_type="CAPTCHA_BLOCKED",
                error_message=(
                    f"Portal '{target.stakeholder_name}' tem CAPTCHA detectado. "
                    "Scraping automático não é possível."
                ),
            )

        context: dict[str, str] = {
            "base_url": self._probe.base_url,
            "protocol_number": target.protocol_number or "",
            "cnpj": target.cnpj or "",
            "registry_office_number": getattr(target, "registry_office_number", "") or "",
            "credential_username": "",
            "credential_password": "",
        }

        try:
            with httpx.Client(
                headers=_HEADERS,
                timeout=_TIMEOUT,
                follow_redirects=True,
            ) as client:
                result_text = ""
                for step in sorted(self._probe.steps, key=lambda s: s.step):
                    logger.info(
                        f"DynamicAdapter step {step.step}: "
                        f"{step.type.upper()} {_interpolate(step.url, context)[:80]}"
                    )
                    text, context = _execute_step(client, step, context)
                    if step.is_result_step:
                        result_text = text

                if not result_text or not result_text.strip():
                    return ScrapeResult(
                        success=False,
                        error_type="PROTOCOL_NOT_FOUND",
                        error_message=(
                            f"DynamicAdapter: nenhum conteúdo encontrado para "
                            f"protocolo '{target.protocol_number}'."
                        ),
                    )

                return ScrapeResult(success=True, raw_html=result_text, http_status=200)

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
            logger.exception(f"DynamicAdapter unexpected error: {e}")
            return ScrapeResult(
                success=False,
                error_type="UNKNOWN_ERROR",
                error_message=str(e),
            )
