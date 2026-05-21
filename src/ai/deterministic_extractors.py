from __future__ import annotations


def _is_copel(stakeholder: dict, clean_text: str) -> bool:
    haystack = " ".join(
        [
            str(stakeholder.get("name") or ""),
            str(stakeholder.get("adapter_type") or ""),
            str(stakeholder.get("type") or ""),
            clean_text,
        ]
    ).lower()
    return "copel" in haystack or "ordens do protocolo" in haystack


def _strip_value(line: str, prefix: str) -> str:
    return line.split(prefix, 1)[1].strip()


def _parse_copel_orders(clean_text: str) -> list[dict]:
    orders: list[dict] = []
    current: dict | None = None

    for raw_line in clean_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("Sequencia:"):
            if current:
                orders.append(current)
            sequence = _strip_value(line, "Sequencia:")
            current = {
                "sequence": int(sequence) if sequence.isdigit() else None,
                "description": None,
                "status": None,
                "observation": None,
            }
            continue

        if current is None:
            continue

        if line.startswith("Descricao:"):
            current["description"] = _strip_value(line, "Descricao:")
        elif line.startswith("Status:"):
            current["status"] = _strip_value(line, "Status:")
        elif line.startswith("Observacao:"):
            current["observation"] = _strip_value(line, "Observacao:")

    if current:
        orders.append(current)

    return [order for order in orders if order.get("description")]


def _copel_external_status(orders: list[dict]) -> str | None:
    statuses = [str(order.get("status") or "").strip() for order in orders]
    known_statuses = [status for status in statuses if status and status.lower() != "desconhecido"]
    if not known_statuses:
        return "desconhecido" if orders else None
    if all(status.lower().startswith("conclu") for status in known_statuses):
        return "Concluída"
    return known_statuses[0]


def _copel_observation(orders: list[dict]) -> str | None:
    if not orders:
        return None
    parts = []
    for order in orders:
        description = order.get("description")
        status = order.get("status")
        if description and status:
            parts.append(f"{description}: {status}")
    return "; ".join(parts) if parts else None


def try_extract_deterministic(
    stakeholder: dict,
    clean_text: str,
    protocol_number: str,
    cnpj: str | None,
) -> dict | None:
    if not clean_text or not _is_copel(stakeholder, clean_text):
        return None

    orders = _parse_copel_orders(clean_text)
    if not orders:
        return None

    return {
        "found": True,
        "protocol_number": protocol_number or None,
        "cnpj": cnpj,
        "external_status": _copel_external_status(orders),
        "external_situation": None,
        "last_movement_date": None,
        "observation": _copel_observation(orders),
        "agency": "Copel",
        "oficio": None,
        "orders": orders,
        "confidence": 0.95,
        "error": None,
    }
