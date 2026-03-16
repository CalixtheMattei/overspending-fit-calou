from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import Counterparty, CounterpartyKind, Rule
from .ledger_validation import canonicalize_payee_name, normalize_payee_display_name

AUTOMATIC_PAYEE_RULE_SOURCE = "automatic_payee_mapping"
AUTOMATIC_PAYEE_RULE_PRIORITY = 1_000_000


def build_automatic_payee_lookup(db: Session) -> dict[str, int]:
    payee_rows = (
        db.query(Counterparty.id, Counterparty.canonical_name)
        .filter(Counterparty.kind.in_(_payee_kinds()))
        .all()
    )
    payee_ids = {int(payee_id) for payee_id, _canonical_name in payee_rows}

    lookup: dict[str, int] = {}
    for payee_id, canonical_name in payee_rows:
        if canonical_name:
            lookup[str(canonical_name)] = int(payee_id)

    for source_ref, action_json in _mapping_rule_rows(db):
        seed_canonical_name = canonicalize_payee_name(source_ref or "")
        if not seed_canonical_name:
            continue
        payee_id = _extract_payee_id(action_json)
        if payee_id is None or payee_id not in payee_ids:
            continue
        lookup[seed_canonical_name] = payee_id

    return lookup


def upsert_automatic_payee_mapping_rule(
    db: Session,
    *,
    seed_canonical_name: str,
    seed_display_name: str,
    payee_id: int,
) -> None:
    normalized_seed = canonicalize_payee_name(seed_canonical_name)
    if not normalized_seed:
        return

    matcher_value = normalize_payee_display_name(seed_display_name) or seed_display_name.strip() or normalized_seed
    matcher_json: dict[str, Any] = {
        "any": [
            {"predicate": "supplier_contains", "value": matcher_value},
            {"predicate": "label_contains", "value": matcher_value},
        ]
    }
    action_json: dict[str, Any] = {"set_payee": {"id": int(payee_id)}}

    row = (
        db.query(Rule)
        .filter(
            Rule.source == AUTOMATIC_PAYEE_RULE_SOURCE,
            Rule.source_ref == normalized_seed,
        )
        .one_or_none()
    )
    if row:
        row.name = f"Automatic payee mapping: {matcher_value}"
        row.priority = AUTOMATIC_PAYEE_RULE_PRIORITY
        row.enabled = False
        row.matcher_json = matcher_json
        row.action_json = action_json
        row.source = AUTOMATIC_PAYEE_RULE_SOURCE
        row.source_ref = normalized_seed
        return

    db.add(
        Rule(
            name=f"Automatic payee mapping: {matcher_value}",
            priority=AUTOMATIC_PAYEE_RULE_PRIORITY,
            enabled=False,
            source=AUTOMATIC_PAYEE_RULE_SOURCE,
            source_ref=normalized_seed,
            matcher_json=matcher_json,
            action_json=action_json,
        )
    )


def delete_automatic_payee_mappings_for_payee(db: Session, *, payee_id: int) -> None:
    rows = db.query(Rule).filter(Rule.source == AUTOMATIC_PAYEE_RULE_SOURCE).all()
    for row in rows:
        mapped_payee_id = _extract_payee_id(row.action_json)
        if mapped_payee_id == payee_id:
            db.delete(row)


def _mapping_rule_rows(db: Session) -> list[tuple[str | None, dict[str, Any] | None]]:
    return (
        db.query(Rule.source_ref, Rule.action_json)
        .filter(Rule.source == AUTOMATIC_PAYEE_RULE_SOURCE)
        .all()
    )


def _extract_payee_id(action_json: Any) -> int | None:
    if not isinstance(action_json, dict):
        return None

    set_payee = action_json.get("set_payee")
    if isinstance(set_payee, int):
        return set_payee
    if isinstance(set_payee, dict):
        raw_id = set_payee.get("id")
        if isinstance(raw_id, int):
            return raw_id
    return None


def _payee_kinds() -> tuple[CounterpartyKind, ...]:
    return (
        CounterpartyKind.person,
        CounterpartyKind.merchant,
        CounterpartyKind.unknown,
    )
