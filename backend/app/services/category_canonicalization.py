from __future__ import annotations

import logging
from typing import Iterable, TypedDict

from sqlalchemy.orm import Session

from ..models import Category, TransactionType
from .category_catalog import native_specs_by_source_id

logger = logging.getLogger(__name__)


class CategoryMetadata(TypedDict):
    display_name: str | None
    is_deprecated: bool
    canonical_id: int | None
    group: str | None


def build_category_metadata_index(db: Session) -> dict[int, CategoryMetadata]:
    categories = db.query(Category).all()
    source_specs = native_specs_by_source_id()

    source_id_to_db_id: dict[int, int] = {}
    for category in categories:
        source_id = _parse_native_source_ref(category)
        if source_id is None:
            continue
        source_id_to_db_id[source_id] = category.id

    metadata_index: dict[int, CategoryMetadata] = {}
    for category in categories:
        source_id = _parse_native_source_ref(category)
        spec = source_specs.get(source_id) if source_id is not None else None

        canonical_id: int | None = None
        if spec is not None and spec["canonical_source_id"] is not None:
            canonical_id = source_id_to_db_id.get(spec["canonical_source_id"])

        metadata_index[category.id] = {
            "display_name": spec["display_name"] if spec is not None else None,
            "is_deprecated": bool(spec["is_deprecated"]) if spec is not None else False,
            "canonical_id": canonical_id,
            "group": spec["group"] if spec is not None else None,
        }

    return metadata_index


def canonicalize_category_id(db: Session, category_id: int, *, context: str | None = None) -> int:
    rewritten = canonicalize_category_ids(db, [category_id], context=context)
    return rewritten.get(category_id, category_id)


def canonicalize_category_ids(
    db: Session,
    category_ids: Iterable[int],
    *,
    context: str | None = None,
) -> dict[int, int]:
    metadata_index = build_category_metadata_index(db)
    rewritten: dict[int, int] = {}
    for category_id in set(category_ids):
        metadata = metadata_index.get(category_id)
        replacement = category_id
        if metadata and metadata["is_deprecated"] and metadata["canonical_id"] is not None:
            replacement = metadata["canonical_id"]
            if context:
                logger.info("Canonicalized category id %s -> %s (%s)", category_id, replacement, context)
            else:
                logger.info("Canonicalized category id %s -> %s", category_id, replacement)
        rewritten[category_id] = replacement
    return rewritten


def ensure_transaction_category_assignment_allowed(
    db: Session,
    *,
    transaction_type: TransactionType | str,
    category_ids: Iterable[int],
) -> None:
    tx_type_value = transaction_type.value if isinstance(transaction_type, TransactionType) else str(transaction_type)
    if tx_type_value != TransactionType.income.value:
        return

    business_branch_ids = _business_branch_category_ids(db)
    assigned_ids = set(category_ids)
    if assigned_ids.intersection(business_branch_ids):
        raise ValueError("BUSINESS_CATEGORY_INCOME_NOT_ALLOWED")


def _business_branch_category_ids(db: Session) -> set[int]:
    categories = db.query(Category).all()
    children_by_parent: dict[int | None, list[Category]] = {}
    for category in categories:
        children_by_parent.setdefault(category.parent_id, []).append(category)

    business_root_ids: set[int] = set()
    for category in categories:
        source_id = _parse_native_source_ref(category)
        if source_id == 16:
            business_root_ids.add(category.id)
            continue
        if category.parent_id is None and category.name == "business_and_work":
            business_root_ids.add(category.id)

    branch_ids: set[int] = set()
    stack = list(business_root_ids)
    while stack:
        current_id = stack.pop()
        if current_id in branch_ids:
            continue
        branch_ids.add(current_id)
        for child in children_by_parent.get(current_id, []):
            stack.append(child.id)
    return branch_ids


def _parse_native_source_ref(category: Category) -> int | None:
    if category.source != "native_catalog":
        return None
    if not category.source_ref:
        return None
    try:
        return int(category.source_ref)
    except ValueError:
        return None
