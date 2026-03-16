from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import (
    Account,
    Category,
    Counterparty,
    CounterpartyKind,
    Moment,
    RuleRunEffect,
    Split,
    Transaction,
    TransactionManualEvent,
    TransactionType,
)
from ..services.category_canonicalization import (
    CategoryMetadata,
    build_category_metadata_index,
    canonicalize_category_ids,
    ensure_transaction_category_assignment_allowed,
)
from ..services.ledger_validation import SplitValidationError, validate_splits

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionPatch(BaseModel):
    payee_id: int | None = None
    type: str | None = None
    comment: str | None = None


class SplitPayload(BaseModel):
    id: int | None = None
    amount: str | float | int
    category_id: int | None = None
    moment_id: int | None = None
    internal_account_id: int | None = None
    note: str | None = None


class SplitsUpdate(BaseModel):
    splits: list[SplitPayload]
    confirm_reassign: bool = False


@router.get("")
def list_transactions(
    status_filter: str = Query("uncategorized", alias="status"),
    type_filter: str = Query("all", alias="type"),
    q: str | None = Query(None, alias="q"),
    payee_id: int | None = Query(None, alias="payee_id"),
    category_id: int | None = Query(None, alias="category_id"),
    internal_account_id: int | None = Query(None, alias="internal_account_id"),
    bank_account_id: int | None = Query(None, alias="bank_account_id"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    splits_agg = (
        db.query(
            Split.transaction_id.label("transaction_id"),
            func.coalesce(func.sum(Split.amount), 0).label("splits_sum"),
            func.count(Split.id).label("splits_count"),
            func.sum(case((Split.category_id.is_(None), 1), else_=0)).label("uncategorized_splits_count"),
            func.min(Split.category_id).label("min_category_id"),
            func.max(Split.category_id).label("max_category_id"),
            func.min(Split.internal_account_id).label("min_internal_account_id"),
            func.max(Split.internal_account_id).label("max_internal_account_id"),
        )
        .group_by(Split.transaction_id)
        .subquery()
    )

    query = (
        db.query(
            Transaction,
            splits_agg.c.splits_sum,
            splits_agg.c.splits_count,
            splits_agg.c.uncategorized_splits_count,
            splits_agg.c.min_category_id,
            splits_agg.c.max_category_id,
            splits_agg.c.min_internal_account_id,
            splits_agg.c.max_internal_account_id,
        )
        .outerjoin(splits_agg, Transaction.id == splits_agg.c.transaction_id)
        .options(joinedload(Transaction.payee), joinedload(Transaction.account))
    )

    splits_count_expr = func.coalesce(splits_agg.c.splits_count, 0)
    uncategorized_splits_expr = func.coalesce(splits_agg.c.uncategorized_splits_count, 0)

    if status_filter not in {"uncategorized", "categorized", "all"}:
        raise HTTPException(status_code=400, detail="Invalid status filter")
    if status_filter == "uncategorized":
        query = query.filter(or_(splits_count_expr == 0, uncategorized_splits_expr > 0))
    elif status_filter == "categorized":
        query = query.filter(splits_count_expr > 0, uncategorized_splits_expr == 0)

    if type_filter != "all":
        allowed_types = {t.value for t in TransactionType if t != TransactionType.adjustment}
        if type_filter not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid type filter")
        query = query.filter(Transaction.type == TransactionType(type_filter))

    if q and q.strip():
        search_value = f"%{q.strip()}%"
        query = query.outerjoin(Counterparty, Transaction.payee)
        query = query.filter(
            or_(
                Transaction.label_raw.ilike(search_value),
                Transaction.supplier_raw.ilike(search_value),
                Counterparty.name.ilike(search_value),
            )
        )

    if payee_id is not None:
        query = query.filter(Transaction.payee_id == payee_id)

    if category_id is not None:
        query = query.filter(Transaction.splits.any(Split.category_id == category_id))

    if internal_account_id is not None:
        query = query.filter(Transaction.splits.any(Split.internal_account_id == internal_account_id))

    if bank_account_id is not None:
        query = query.filter(Transaction.account_id == bank_account_id)

    total = query.count()

    rows = (
        query.order_by(Transaction.posted_at.desc(), Transaction.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    single_category_ids: set[int] = set()
    for row in rows:
        (
            _transaction,
            _splits_sum,
            splits_count,
            _uncategorized_splits_count,
            min_category_id,
            max_category_id,
            _min_internal_account_id,
            _max_internal_account_id,
        ) = row
        if splits_count == 1 and min_category_id is not None and min_category_id == max_category_id:
            single_category_ids.add(min_category_id)

    category_by_id: dict[int, Category] = {}
    metadata_index: dict[int, CategoryMetadata] | None = None
    if single_category_ids:
        category_by_id = {
            category.id: category
            for category in db.query(Category).filter(Category.id.in_(single_category_ids)).all()
        }
        metadata_index = build_category_metadata_index(db)

    payload_rows: list[dict[str, object]] = []
    for row in rows:
        (
            _transaction,
            _splits_sum,
            splits_count,
            _uncategorized_splits_count,
            min_category_id,
            max_category_id,
            _min_internal_account_id,
            _max_internal_account_id,
        ) = row

        single_category: Category | None = None
        if splits_count == 1 and min_category_id is not None and min_category_id == max_category_id:
            single_category = category_by_id.get(min_category_id)

        payload_rows.append(
            _transaction_summary(
                *row,
                single_category=single_category,
                metadata_index=metadata_index,
            )
        )

    return jsonable_encoder(
        {
            "rows": payload_rows,
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    )


@router.get("/summary")
def get_transactions_summary(db: Session = Depends(get_db)) -> dict[str, object]:
    splits_agg = (
        db.query(
            Split.transaction_id.label("transaction_id"),
            func.count(Split.id).label("splits_count"),
            func.sum(case((Split.category_id.is_(None), 1), else_=0)).label("uncategorized_splits_count"),
        )
        .group_by(Split.transaction_id)
        .subquery()
    )

    splits_count_expr = func.coalesce(splits_agg.c.splits_count, 0)
    uncategorized_splits_expr = func.coalesce(splits_agg.c.uncategorized_splits_count, 0)

    uncategorized_query = (
        db.query(Transaction)
        .outerjoin(splits_agg, Transaction.id == splits_agg.c.transaction_id)
        .filter(or_(splits_count_expr == 0, uncategorized_splits_expr > 0))
    )

    uncategorized_count = uncategorized_query.count()
    uncategorized_total_abs = (
        db.query(func.coalesce(func.sum(func.abs(Transaction.amount)), 0))
        .outerjoin(splits_agg, Transaction.id == splits_agg.c.transaction_id)
        .filter(or_(splits_count_expr == 0, uncategorized_splits_expr > 0))
        .scalar()
    )

    window_start = date.today() - timedelta(days=30)
    total_last_30 = db.query(Transaction).filter(Transaction.posted_at >= window_start).count()
    categorized_last_30 = (
        db.query(Transaction)
        .outerjoin(splits_agg, Transaction.id == splits_agg.c.transaction_id)
        .filter(Transaction.posted_at >= window_start, splits_count_expr > 0, uncategorized_splits_expr == 0)
        .count()
    )

    categorized_percent = 0
    if total_last_30:
        categorized_percent = round((categorized_last_30 / total_last_30) * 100, 1)

    return jsonable_encoder(
        {
            "uncategorized_count": uncategorized_count,
            "uncategorized_total_abs": uncategorized_total_abs,
            "categorized_percent_30d": categorized_percent,
        }
    )


@router.get("/{transaction_id}")
def get_transaction(transaction_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    transaction = (
        db.query(Transaction)
        .options(
            joinedload(Transaction.payee),
            joinedload(Transaction.account),
            joinedload(Transaction.splits).joinedload(Split.category),
            joinedload(Transaction.splits).joinedload(Split.moment),
            joinedload(Transaction.splits).joinedload(Split.internal_account),
        )
        .filter(Transaction.id == transaction_id)
        .one_or_none()
    )

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    splits = sorted(transaction.splits, key=lambda split: (split.position, split.id))
    splits_sum = sum((split.amount for split in splits), Decimal("0.00"))
    splits_count = len(splits)
    is_balanced = splits_count > 0 and splits_sum == transaction.amount
    category_provenance = _build_category_provenance(db, transaction.id, splits)

    payload = _transaction_detail(transaction, splits, splits_sum, splits_count, is_balanced, category_provenance)
    return jsonable_encoder(payload)


@router.patch("/{transaction_id}")
def update_transaction(
    transaction_id: int,
    payload: TransactionPatch,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    data = payload.model_dump(exclude_unset=True)

    if "payee_id" in data:
        payee_id = data["payee_id"]
        if payee_id is not None:
            payee = db.query(Counterparty).filter(Counterparty.id == payee_id).one_or_none()
            if not payee:
                raise HTTPException(status_code=400, detail="Payee not found")
            if payee.kind == CounterpartyKind.internal:
                raise HTTPException(status_code=400, detail="Payee id must reference a payee counterparty")
        transaction.payee_id = payee_id

    if "type" in data:
        allowed_types = {t.value for t in TransactionType if t != TransactionType.adjustment}
        tx_type = data["type"]
        if tx_type is not None and tx_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid transaction type")
        if tx_type is not None:
            transaction.type = TransactionType(tx_type)

    if "comment" in data:
        transaction.comment = data["comment"]

    db.commit()
    db.refresh(transaction)

    return get_transaction(transaction.id, db)


@router.put("/{transaction_id}/splits", status_code=status.HTTP_200_OK)
def replace_splits(
    transaction_id: int,
    payload: SplitsUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    existing_splits = (
        db.query(Split)
        .filter(Split.transaction_id == transaction.id)
        .order_by(Split.position.asc(), Split.id.asc())
        .all()
    )
    existing_normalized = _normalize_existing_splits(existing_splits)

    raw_splits = [split.model_dump() for split in payload.splits]

    try:
        normalized = validate_splits(transaction.amount, raw_splits)
    except SplitValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.to_detail()) from exc

    if normalized:
        duplicate_split_ids = _find_duplicate_split_ids(normalized)
        if duplicate_split_ids:
            _raise_api_error(
                status_code=422,
                code="SPLIT_ID_DUPLICATE",
                message="Split payload contains duplicate split ids",
                split_ids=duplicate_split_ids,
            )

        invalid_split_ids = _find_invalid_split_ids(normalized, existing_splits)
        if invalid_split_ids:
            _raise_api_error(
                status_code=422,
                code="SPLIT_ID_NOT_FOUND",
                message="One or more split ids do not belong to the transaction",
                split_ids=invalid_split_ids,
                transaction_id=transaction_id,
            )

        original_category_ids = {
            split["category_id"]
            for split in normalized
            if split.get("category_id") is not None
        }
        if original_category_ids:
            canonical_map = canonicalize_category_ids(
                db,
                original_category_ids,
                context=f"transactions.replace_splits tx={transaction_id}",
            )
            for split in normalized:
                category_id = split.get("category_id")
                if category_id is None:
                    continue
                split["category_id"] = canonical_map.get(category_id, category_id)

        category_ids = {split["category_id"] for split in normalized if split.get("category_id") is not None}
        if category_ids:
            found = {
                row[0]
                for row in db.query(Category.id).filter(Category.id.in_(category_ids)).all()
            }
            missing = category_ids - found
            if missing:
                _raise_api_error(
                    status_code=400,
                    code="CATEGORY_NOT_FOUND",
                    message="One or more categories not found",
                    category_ids=sorted(missing),
                )
            try:
                ensure_transaction_category_assignment_allowed(
                    db,
                    transaction_type=transaction.type,
                    category_ids=category_ids,
                )
            except ValueError as exc:
                _raise_api_error(
                    status_code=422,
                    code="CATEGORY_ASSIGNMENT_NOT_ALLOWED",
                    message=str(exc),
                )

        moment_ids = {split["moment_id"] for split in normalized if split.get("moment_id") is not None}
        if moment_ids:
            found = {
                row[0]
                for row in db.query(Moment.id).filter(Moment.id.in_(moment_ids)).all()
            }
            missing = moment_ids - found
            if missing:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "MOMENT_NOT_FOUND",
                        "message": "Moment not found",
                        "moment_ids": sorted(missing),
                    },
                )

        internal_ids = {
            split["internal_account_id"]
            for split in normalized
            if split.get("internal_account_id") is not None
        }
        if internal_ids:
            found = {
                row[0]
                for row in db.query(Counterparty.id)
                .filter(Counterparty.id.in_(internal_ids), Counterparty.kind == CounterpartyKind.internal)
                .all()
            }
            missing = internal_ids - found
            if missing:
                _raise_api_error(
                    status_code=400,
                    code="INTERNAL_ACCOUNT_NOT_FOUND",
                    message="One or more internal accounts not found",
                    internal_account_ids=sorted(missing),
                )

        reassignments = _collect_moment_reassignments(existing_splits, normalized)
        if reassignments and not payload.confirm_reassign:
            _raise_api_error(
                status_code=409,
                code="MOMENT_REASSIGN_CONFIRM_REQUIRED",
                message="One or more splits are already tagged to another moment",
                split_ids=[row["split_id"] for row in reassignments],
                source_moment_ids=sorted({row["from_moment_id"] for row in reassignments}),
                target_moment_ids=sorted({row["to_moment_id"] for row in reassignments}),
                reassignments=reassignments,
            )

    splits_changed = not _are_split_payloads_equal(existing_normalized, normalized)
    if splits_changed:
        db.query(Split).filter(Split.transaction_id == transaction.id).delete()

        for index, split in enumerate(normalized):
            db.add(
                Split(
                    transaction_id=transaction.id,
                    amount=split["amount"],
                    category_id=split["category_id"],
                    moment_id=split.get("moment_id"),
                    internal_account_id=split.get("internal_account_id"),
                    note=split.get("note"),
                    position=index,
                )
            )

        db.add(
            TransactionManualEvent(
                transaction_id=transaction.id,
                event_type="splits_replaced",
                payload_json={
                    "before": _serialize_split_payloads(existing_normalized),
                    "after": _serialize_split_payloads(normalized),
                },
            )
        )

        db.commit()

    return get_transaction(transaction.id, db)


def _transaction_summary(
    transaction: Transaction,
    splits_sum: Decimal | None,
    splits_count: int | None,
    uncategorized_splits_count: int | None,
    min_category_id: int | None,
    max_category_id: int | None,
    min_internal_account_id: int | None,
    max_internal_account_id: int | None,
    single_category: Category | None = None,
    metadata_index: dict[int, CategoryMetadata] | None = None,
) -> dict[str, object]:
    splits_sum_value = splits_sum or Decimal("0.00")
    splits_count_value = splits_count or 0
    uncategorized_count_value = uncategorized_splits_count or 0
    is_balanced = splits_count_value > 0 and splits_sum_value == transaction.amount
    remaining_amount = transaction.amount - splits_sum_value

    single_category_id = None
    single_internal_account_id = None
    if splits_count_value == 1 and min_category_id == max_category_id:
        single_category_id = min_category_id
    if splits_count_value == 1 and min_internal_account_id == max_internal_account_id:
        single_internal_account_id = min_internal_account_id

    return {
        "id": transaction.id,
        "posted_at": transaction.posted_at,
        "operation_at": transaction.operation_at,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "label_raw": transaction.label_raw,
        "supplier_raw": transaction.supplier_raw,
        "payee": _payee_summary(transaction.payee),
        "account": _account_summary(transaction.account),
        "type": transaction.type.value,
        "comment": transaction.comment,
        "splits_sum": splits_sum_value,
        "splits_count": splits_count_value,
        "is_balanced": is_balanced,
        "is_categorized": splits_count_value > 0 and is_balanced and uncategorized_count_value == 0,
        "remaining_amount": remaining_amount,
        "single_category_id": single_category_id,
        "single_category": _category_summary(single_category, metadata_index=metadata_index),
        "single_internal_account_id": single_internal_account_id,
    }


def _transaction_detail(
    transaction: Transaction,
    splits: list[Split],
    splits_sum: Decimal,
    splits_count: int,
    is_balanced: bool,
    category_provenance: dict[str, Any],
) -> dict[str, object]:
    has_uncategorized = any(split.category_id is None for split in splits)
    return {
        "transaction": {
            "id": transaction.id,
            "posted_at": transaction.posted_at,
            "operation_at": transaction.operation_at,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "label_raw": transaction.label_raw,
            "supplier_raw": transaction.supplier_raw,
            "type": transaction.type.value,
            "comment": transaction.comment,
            "payee": _payee_summary(transaction.payee),
            "account": _account_summary(transaction.account),
        },
        "splits": [
            {
                "id": split.id,
                "amount": split.amount,
                "category_id": split.category_id,
                "category": _category_summary(split.category),
                "moment_id": split.moment_id,
                "moment": _moment_summary(split.moment),
                "internal_account_id": split.internal_account_id,
                "internal_account": _internal_account_summary(split.internal_account),
                "note": split.note,
                "position": split.position,
            }
            for split in splits
        ],
        "splits_sum": splits_sum,
        "splits_count": splits_count,
        "is_balanced": is_balanced,
        "is_categorized": splits_count > 0 and is_balanced and not has_uncategorized,
        "remaining_amount": transaction.amount - splits_sum,
        "category_provenance": category_provenance,
    }


def _build_category_provenance(db: Session, transaction_id: int, splits: list[Split]) -> dict[str, Any]:
    latest_manual_event = (
        db.query(TransactionManualEvent)
        .filter(
            TransactionManualEvent.transaction_id == transaction_id,
            TransactionManualEvent.event_type == "splits_replaced",
        )
        .order_by(TransactionManualEvent.id.desc())
        .first()
    )
    latest_rule_effect = _latest_category_rule_effect(db, transaction_id=transaction_id)

    manual_at = latest_manual_event.created_at if latest_manual_event else None
    rule_at = latest_rule_effect.applied_at if latest_rule_effect else None

    source = "import_default"
    if len(splits) == 0:
        source = "uncategorized"
    elif len(splits) > 1:
        source = "mixed"
    elif manual_at and (rule_at is None or manual_at >= rule_at):
        source = "manual"
    elif rule_at:
        source = "rule"

    last_applied_at = None
    if manual_at and rule_at:
        last_applied_at = manual_at if manual_at >= rule_at else rule_at
    elif manual_at:
        last_applied_at = manual_at
    elif rule_at:
        last_applied_at = rule_at

    rule_payload = None
    if source == "rule" and latest_rule_effect and latest_rule_effect.rule:
        rule_payload = {
            "id": latest_rule_effect.rule.id,
            "name": latest_rule_effect.rule.name,
        }

    return {
        "source": source,
        "last_applied_at": last_applied_at,
        "rule": rule_payload,
    }


def _latest_category_rule_effect(db: Session, *, transaction_id: int) -> RuleRunEffect | None:
    effects = (
        db.query(RuleRunEffect)
        .options(joinedload(RuleRunEffect.rule))
        .filter(
            RuleRunEffect.transaction_id == transaction_id,
            RuleRunEffect.status == "applied",
        )
        .order_by(RuleRunEffect.id.desc())
        .all()
    )
    for effect in effects:
        split_operations = (effect.change_json or {}).get("split_operations")
        if isinstance(split_operations, list) and split_operations:
            return effect
    return None


def _normalize_existing_splits(splits: list[Split]) -> list[dict[str, Any]]:
    return [
        {
            "id": split.id,
            "amount": split.amount,
            "category_id": split.category_id,
            "moment_id": split.moment_id,
            "internal_account_id": split.internal_account_id,
            "note": split.note or None,
        }
        for split in splits
    ]


def _serialize_decimal(value: Decimal) -> str:
    return f"{value:.2f}"


def _are_split_payloads_equal(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    if len(left) != len(right):
        return False

    for idx, left_row in enumerate(left):
        right_row = right[idx]
        if _serialize_decimal(left_row["amount"]) != _serialize_decimal(right_row["amount"]):
            return False
        if left_row.get("category_id") != right_row.get("category_id"):
            return False
        if left_row.get("moment_id") != right_row.get("moment_id"):
            return False
        if left_row.get("internal_account_id") != right_row.get("internal_account_id"):
            return False
        if (left_row.get("note") or None) != (right_row.get("note") or None):
            return False
    return True


def _serialize_split_payloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "amount": _serialize_decimal(row["amount"]),
            "id": row.get("id"),
            "category_id": row.get("category_id"),
            "moment_id": row.get("moment_id"),
            "internal_account_id": row.get("internal_account_id"),
            "note": row.get("note") or None,
        }
        for row in rows
    ]


def _find_duplicate_split_ids(rows: list[dict[str, Any]]) -> list[int]:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for row in rows:
        split_id = row.get("id")
        if not isinstance(split_id, int):
            continue
        if split_id in seen:
            duplicates.add(split_id)
            continue
        seen.add(split_id)
    return sorted(duplicates)


def _find_invalid_split_ids(rows: list[dict[str, Any]], existing_splits: list[Split]) -> list[int]:
    existing_ids = {split.id for split in existing_splits}
    invalid: set[int] = set()
    for row in rows:
        split_id = row.get("id")
        if not isinstance(split_id, int):
            continue
        if split_id not in existing_ids:
            invalid.add(split_id)
    return sorted(invalid)


def _collect_moment_reassignments(
    existing_splits: list[Split],
    incoming_rows: list[dict[str, Any]],
) -> list[dict[str, int]]:
    if not existing_splits or not incoming_rows:
        return []

    incoming_has_ids = any(isinstance(row.get("id"), int) for row in incoming_rows)
    existing_by_id = {split.id: split for split in existing_splits}
    mapped_existing: list[Split | None] = [None] * len(incoming_rows)
    used_existing_ids: set[int] = set()

    if incoming_has_ids:
        for index, row in enumerate(incoming_rows):
            split_id = row.get("id")
            if not isinstance(split_id, int):
                continue
            split = existing_by_id.get(split_id)
            if split is None or split.id in used_existing_ids:
                continue
            mapped_existing[index] = split
            used_existing_ids.add(split.id)
    else:
        for index, split in enumerate(existing_splits):
            if index >= len(mapped_existing):
                break
            mapped_existing[index] = split
            used_existing_ids.add(split.id)

    reassignments: list[dict[str, int]] = []
    for index, existing_split in enumerate(mapped_existing):
        if existing_split is None:
            continue
        current_moment_id = existing_split.moment_id
        target_moment_id = incoming_rows[index].get("moment_id")
        if not isinstance(current_moment_id, int) or not isinstance(target_moment_id, int):
            continue
        if current_moment_id == target_moment_id:
            continue
        reassignments.append(
            {
                "split_id": existing_split.id,
                "from_moment_id": current_moment_id,
                "to_moment_id": target_moment_id,
            }
        )

    return reassignments


def _raise_api_error(status_code: int, code: str, message: str, **extra: object) -> None:
    detail: dict[str, object] = {"code": code, "message": message}
    for key, value in extra.items():
        detail[key] = value
    raise HTTPException(status_code=status_code, detail=detail)


def _payee_summary(payee: Counterparty | None) -> dict[str, object] | None:
    if not payee:
        return None
    return {
        "id": payee.id,
        "name": payee.name,
        "kind": payee.kind.value,
    }


def _account_summary(account: Account | None) -> dict[str, object] | None:
    if not account:
        return None
    return {
        "id": account.id,
        "account_num": account.account_num,
        "label": account.label,
    }


def _category_summary(
    category: Category | None,
    *,
    metadata_index: dict[int, CategoryMetadata] | None = None,
) -> dict[str, object] | None:
    if not category:
        return None
    metadata = metadata_index.get(category.id) if metadata_index else None
    return {
        "id": category.id,
        "name": category.name,
        "parent_id": category.parent_id,
        "color": category.color,
        "icon": category.icon,
        "is_custom": category.is_custom,
        "display_name": metadata.get("display_name") if metadata else None,
    }


def _moment_summary(moment: Moment | None) -> dict[str, object] | None:
    if not moment:
        return None
    return {
        "id": moment.id,
        "name": moment.name,
    }


def _internal_account_summary(account: Counterparty | None) -> dict[str, object] | None:
    if not account:
        return None
    return {
        "id": account.id,
        "name": account.name,
        "type": account.type,
        "position": account.position,
        "is_archived": account.is_archived,
    }
