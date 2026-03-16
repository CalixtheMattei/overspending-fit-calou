from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models import Category, Rule


def bootstrap_finary_rules(
    db: Session,
    *,
    rules_path: str | Path,
    categories_path: str | Path,
) -> dict[str, int]:
    rules_payload = json.loads(Path(rules_path).read_text(encoding="utf-8-sig"))
    categories_payload = json.loads(Path(categories_path).read_text(encoding="utf-8-sig"))

    categories_result = categories_payload.get("result") or {}
    categories_rows = categories_result.get("categories") or []
    rules_rows = rules_payload.get("result") or []

    source_id_to_category: dict[int, Category] = {}
    created_categories = 0
    updated_categories = 0

    parent_rows = [row for row in categories_rows if isinstance(row, dict)]
    for parent in sorted(parent_rows, key=lambda row: int(row.get("id", 0))):
        category, created = _upsert_finary_category(db, parent, parent_id=None)
        source_id_to_category[int(parent["id"])] = category
        if created:
            created_categories += 1
        else:
            updated_categories += 1

    for parent in sorted(parent_rows, key=lambda row: int(row.get("id", 0))):
        parent_db = source_id_to_category.get(int(parent["id"]))
        if parent_db is None:
            continue
        for child in sorted(parent.get("subcategories") or [], key=lambda row: int(row.get("id", 0))):
            if not isinstance(child, dict):
                continue
            category, created = _upsert_finary_category(db, child, parent_id=parent_db.id)
            source_id_to_category[int(child["id"])] = category
            if created:
                created_categories += 1
            else:
                updated_categories += 1

    if not _find_category_by_normalized_name(db, "Empreintes bancaires"):
        category = Category(
            name="Empreintes bancaires",
            color="#9CA3AF",
            icon="tag",
            is_custom=True,
            source="finary_category_name",
            source_ref="empreintes_bancaires",
        )
        db.add(category)
        db.flush()
        created_categories += 1

    categories_by_normalized_name = {}
    for category in db.query(Category).all():
        categories_by_normalized_name.setdefault(_normalize_name(category.name), category)

    created_rules = 0
    updated_rules = 0
    disabled_rules = 0

    for idx, row in enumerate(rules_rows):
        if not isinstance(row, dict):
            continue
        source_ref = str(row.get("id"))
        if not source_ref:
            continue

        transaction_category = row.get("transaction_category") or {}
        category_id = _map_rule_category_id(
            db,
            source_id_to_category=source_id_to_category,
            categories_by_normalized_name=categories_by_normalized_name,
            transaction_category=transaction_category,
        )

        matcher_json = _matcher_from_pattern(row.get("pattern") or [])
        action_json = {"set_category": category_id}
        usage_count = int(row.get("transactions_count") or 0)
        enabled = usage_count > 0
        if not enabled:
            disabled_rules += 1

        name_category = _repair_text(str(transaction_category.get("name") or "Unmapped category"))
        default_name = f"Finary {source_ref} -> {name_category}"

        existing = db.query(Rule).filter(Rule.source == "finary", Rule.source_ref == source_ref).one_or_none()
        if existing:
            existing.name = default_name
            existing.priority = idx + 1
            existing.enabled = enabled
            existing.matcher_json = matcher_json
            existing.action_json = action_json
            updated_rules += 1
        else:
            db.add(
                Rule(
                    name=default_name,
                    priority=idx + 1,
                    enabled=enabled,
                    source="finary",
                    source_ref=source_ref,
                    matcher_json=matcher_json,
                    action_json=action_json,
                )
            )
            created_rules += 1

    db.flush()

    return {
        "categories_created": created_categories,
        "categories_updated": updated_categories,
        "rules_created": created_rules,
        "rules_updated": updated_rules,
        "rules_disabled": disabled_rules,
    }


def _upsert_finary_category(db: Session, row: dict[str, Any], parent_id: int | None) -> tuple[Category, bool]:
    source_ref = str(row.get("id") or "").strip()
    if not source_ref:
        raise ValueError("category row missing id")

    name = _repair_text(str(row.get("name") or source_ref))
    color = _repair_text(str(row.get("color") or "#9CA3AF"))
    icon = _repair_text(str(row.get("icon") or "tag"))

    existing = db.query(Category).filter(Category.source == "finary_category", Category.source_ref == source_ref).one_or_none()
    if existing:
        existing.name = name.strip()
        existing.parent_id = parent_id
        existing.color = color if _is_hex_color(color) else "#9CA3AF"
        existing.icon = icon or "tag"
        existing.is_custom = False
        return existing, False

    by_name = _find_category_with_parent(db, name=name, parent_id=parent_id)
    if by_name:
        by_name.source = "finary_category"
        by_name.source_ref = source_ref
        by_name.color = color if _is_hex_color(color) else by_name.color
        by_name.icon = icon or by_name.icon
        by_name.is_custom = False
        return by_name, False

    category = Category(
        name=name.strip(),
        parent_id=parent_id,
        color=color if _is_hex_color(color) else "#9CA3AF",
        icon=icon or "tag",
        is_custom=False,
        source="finary_category",
        source_ref=source_ref,
    )
    db.add(category)
    db.flush()
    return category, True


def _map_rule_category_id(
    db: Session,
    *,
    source_id_to_category: dict[int, Category],
    categories_by_normalized_name: dict[str, Category],
    transaction_category: dict[str, Any],
) -> int:
    source_id = transaction_category.get("id")
    if isinstance(source_id, int) and source_id in source_id_to_category:
        return source_id_to_category[source_id].id

    category_name = _repair_text(str(transaction_category.get("name") or "")).strip()
    if category_name:
        mapped = categories_by_normalized_name.get(_normalize_name(category_name))
        if mapped:
            return mapped.id

    fallback_name = category_name or "Unmapped finary category"
    fallback_source_ref = _slugify(fallback_name)
    existing = (
        db.query(Category)
        .filter(Category.source == "finary_category_name", Category.source_ref == fallback_source_ref)
        .one_or_none()
    )
    if existing:
        return existing.id

    category = Category(
        name=fallback_name,
        color="#9CA3AF",
        icon="tag",
        is_custom=True,
        source="finary_category_name",
        source_ref=fallback_source_ref,
    )
    db.add(category)
    db.flush()
    categories_by_normalized_name[_normalize_name(category.name)] = category
    return category.id


def _matcher_from_pattern(patterns: list[Any]) -> dict[str, Any]:
    conditions = []
    for raw_pattern in patterns:
        if not isinstance(raw_pattern, str):
            continue
        token = _repair_text(raw_pattern).strip()
        if not token:
            continue
        conditions.append({"predicate": "label_contains", "value": token})

    if not conditions:
        conditions = [{"predicate": "label_contains", "value": "__never_match__"}]

    return {
        "all": conditions,
        "source_pattern": [_repair_text(str(item)) for item in patterns if isinstance(item, str)],
    }


def _find_category_by_normalized_name(db: Session, name: str) -> Category | None:
    target = _normalize_name(name)
    for category in db.query(Category).all():
        if _normalize_name(category.name) == target:
            return category
    return None


def _find_category_with_parent(db: Session, *, name: str, parent_id: int | None) -> Category | None:
    target = _normalize_name(name)
    rows = db.query(Category).filter(Category.parent_id == parent_id).all()
    for row in rows:
        if _normalize_name(row.name) == target:
            return row
    return None


def _repair_text(value: str) -> str:
    text = value or ""
    if "\u00c3" in text or "\u00c2" in text:
        try:
            decoded = text.encode("latin-1").decode("utf-8")
            if decoded:
                text = decoded
        except UnicodeError:
            pass
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_name(name: str) -> str:
    normalized = _repair_text(name).lower().replace("_", " ")
    normalized = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _slugify(name: str) -> str:
    base = _normalize_name(name)
    return re.sub(r"\s+", "_", base) or "unknown"


def _is_hex_color(color: str) -> bool:
    return bool(re.match(r"^#[0-9A-Fa-f]{6}$", color or ""))

