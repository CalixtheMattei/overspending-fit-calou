from __future__ import annotations

from enum import Enum as PyEnum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Counterparty, CounterpartyKind, ImportRow, ImportRowLink, PayeeSuggestionIgnore, Transaction
from ..services.automatic_payee_mapping import (
    build_automatic_payee_lookup,
    delete_automatic_payee_mappings_for_payee,
    upsert_automatic_payee_mapping_rule,
)
from ..services.import_normalization import infer_payee
from ..services.ledger_validation import canonicalize_payee_name, normalize_payee_display_name

router = APIRouter(prefix="/payees", tags=["payees"])


class PayeeKindValue(str, PyEnum):
    person = "person"
    merchant = "merchant"
    unknown = "unknown"


class PayeeCreate(BaseModel):
    name: str
    kind: PayeeKindValue | None = None


class PayeeUpdate(BaseModel):
    name: str | None = None
    kind: PayeeKindValue | None = None


class AutomaticPayeeApplyPayload(BaseModel):
    seed_canonical_name: str
    payee_name: str
    kind: PayeeKindValue = PayeeKindValue.merchant
    overwrite_existing: bool = False


class AutomaticPayeeIgnorePayload(BaseModel):
    canonical_name: str


@router.get("")
def list_payees(
    q: str | None = Query(None, alias="q"),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    counts_subquery = (
        db.query(
            Transaction.payee_id.label("payee_id"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .group_by(Transaction.payee_id)
        .subquery()
    )

    query = db.query(Counterparty, func.coalesce(counts_subquery.c.transaction_count, 0)).outerjoin(
        counts_subquery, Counterparty.id == counts_subquery.c.payee_id
    )
    query = query.filter(Counterparty.kind.in_(_payee_kinds()))
    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(Counterparty.name.ilike(search))
    payees = query.order_by(Counterparty.name.asc()).limit(limit).all()
    return jsonable_encoder([_payee_summary(payee, transaction_count=count) for payee, count in payees])


@router.get("/automatic")
def list_automatic_payees(
    q: str | None = Query(None, alias="q"),
    limit: int = Query(20, ge=1, le=200),
    include_ignored: bool = Query(False, alias="include_ignored"),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    aggregated = _collect_automatic_seed_matches(db)
    ignored_canonical_names = _ignored_seed_names(db)
    hidden_canonical_names = set(build_automatic_payee_lookup(db).keys())

    query_value = canonicalize_payee_name(q or "")
    rows: list[dict[str, object]] = []
    for canonical_name, entry in aggregated.items():
        if canonical_name in hidden_canonical_names:
            continue

        is_ignored = canonical_name in ignored_canonical_names
        if not include_ignored and is_ignored:
            continue

        name = str(entry["name"])
        if query_value and query_value not in canonical_name and query_value not in name.lower():
            continue

        linked_transaction_ids = entry["linked_transaction_ids"]
        linked_transaction_count = len(linked_transaction_ids) if isinstance(linked_transaction_ids, set) else 0
        rows.append(
            {
                "name": name,
                "canonical_name": canonical_name,
                "linked_transaction_count": linked_transaction_count,
                "is_ignored": is_ignored,
            }
        )

    rows.sort(key=lambda item: (-int(item["linked_transaction_count"]), str(item["name"]).lower(), str(item["canonical_name"])))
    return jsonable_encoder(rows[:limit])


@router.post("/automatic/apply")
def apply_automatic_payee(
    payload: AutomaticPayeeApplyPayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    seed_canonical_name = canonicalize_payee_name(payload.seed_canonical_name)
    if not seed_canonical_name:
        raise HTTPException(status_code=400, detail="seed_canonical_name is required")

    aggregated = _collect_automatic_seed_matches(db)
    seed = aggregated.get(seed_canonical_name)
    if not seed:
        raise HTTPException(status_code=404, detail="Automatic payee seed not found")

    display_name = normalize_payee_display_name(payload.payee_name)
    if not display_name:
        raise HTTPException(status_code=400, detail="payee_name is required")
    canonical_name = canonicalize_payee_name(display_name)

    existing = db.query(Counterparty).filter(Counterparty.canonical_name == canonical_name).one_or_none()
    if existing and existing.kind == CounterpartyKind.internal:
        raise HTTPException(status_code=409, detail="Name conflicts with an internal account")

    if existing and existing.kind in _payee_kinds():
        payee = existing
    else:
        payee = Counterparty(
            name=display_name,
            canonical_name=canonical_name,
            kind=CounterpartyKind(payload.kind.value),
            type=None,
            position=0,
            is_archived=False,
        )
        db.add(payee)
        db.flush()

    linked_transaction_ids = seed["linked_transaction_ids"]
    if not isinstance(linked_transaction_ids, set) or not linked_transaction_ids:
        db.commit()
        return {
            "payee": _payee_summary_with_count(payee, db),
            "matched_transaction_count": 0,
            "updated_transaction_count": 0,
            "skipped_assigned_count": 0,
        }

    matched_transaction_count = len(linked_transaction_ids)
    if payload.overwrite_existing:
        updated_transaction_count = (
            db.query(Transaction)
            .filter(Transaction.id.in_(linked_transaction_ids))
            .update({Transaction.payee_id: payee.id}, synchronize_session=False)
        )
        skipped_assigned_count = 0
    else:
        updated_transaction_count = (
            db.query(Transaction)
            .filter(Transaction.id.in_(linked_transaction_ids), Transaction.payee_id.is_(None))
            .update({Transaction.payee_id: payee.id}, synchronize_session=False)
        )
        skipped_assigned_count = matched_transaction_count - int(updated_transaction_count)

    upsert_automatic_payee_mapping_rule(
        db,
        seed_canonical_name=seed_canonical_name,
        seed_display_name=str(seed["name"]),
        payee_id=payee.id,
    )
    db.query(PayeeSuggestionIgnore).filter(PayeeSuggestionIgnore.canonical_name == seed_canonical_name).delete(
        synchronize_session=False
    )
    db.commit()
    return {
        "payee": _payee_summary_with_count(payee, db),
        "matched_transaction_count": matched_transaction_count,
        "updated_transaction_count": int(updated_transaction_count),
        "skipped_assigned_count": skipped_assigned_count,
    }


@router.post("/automatic/ignore", status_code=status.HTTP_201_CREATED)
def ignore_automatic_payee(payload: AutomaticPayeeIgnorePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    canonical_name = canonicalize_payee_name(payload.canonical_name)
    if not canonical_name:
        raise HTTPException(status_code=400, detail="canonical_name is required")

    existing = (
        db.query(PayeeSuggestionIgnore)
        .filter(PayeeSuggestionIgnore.canonical_name == canonical_name)
        .one_or_none()
    )
    if existing:
        return {"canonical_name": canonical_name, "ignored": True}

    db.add(PayeeSuggestionIgnore(canonical_name=canonical_name))
    db.commit()
    return {"canonical_name": canonical_name, "ignored": True}


@router.delete("/automatic/ignore/{canonical_name}")
def restore_automatic_payee(canonical_name: str, db: Session = Depends(get_db)) -> dict[str, object]:
    normalized = canonicalize_payee_name(canonical_name)
    if not normalized:
        raise HTTPException(status_code=400, detail="canonical_name is required")

    db.query(PayeeSuggestionIgnore).filter(PayeeSuggestionIgnore.canonical_name == normalized).delete(
        synchronize_session=False
    )
    db.commit()
    return {"canonical_name": normalized, "ignored": False}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_payee(payload: PayeeCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    name = payload.name.strip() if payload.name else ""
    if not name:
        raise HTTPException(status_code=400, detail="Payee name is required")

    canonical_name = canonicalize_payee_name(name)
    existing = db.query(Counterparty).filter(Counterparty.canonical_name == canonical_name).one_or_none()
    if existing and existing.kind == CounterpartyKind.internal:
        raise HTTPException(status_code=409, detail="Name conflicts with an internal account")
    if existing and existing.kind in _payee_kinds():
        return jsonable_encoder(_payee_summary_with_count(existing, db))

    payee = Counterparty(
        name=name,
        kind=CounterpartyKind((payload.kind or PayeeKindValue.unknown).value),
        canonical_name=canonical_name,
        type=None,
        position=0,
        is_archived=False,
    )
    db.add(payee)
    db.commit()
    db.refresh(payee)
    return jsonable_encoder(_payee_summary_with_count(payee, db))


@router.patch("/{payee_id}")
def update_payee(payee_id: int, payload: PayeeUpdate, db: Session = Depends(get_db)) -> dict[str, object]:
    payee = (
        db.query(Counterparty)
        .filter(Counterparty.id == payee_id, Counterparty.kind.in_(_payee_kinds()))
        .one_or_none()
    )
    if not payee:
        raise HTTPException(status_code=404, detail="Payee not found")

    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Payee name is required")
        canonical_name = canonicalize_payee_name(name)
        existing = (
            db.query(Counterparty)
            .filter(Counterparty.canonical_name == canonical_name, Counterparty.id != payee_id)
            .one_or_none()
        )
        if existing and existing.kind in _payee_kinds():
            raise HTTPException(status_code=409, detail="Payee name already exists")
        if existing and existing.kind == CounterpartyKind.internal:
            raise HTTPException(status_code=409, detail="Name conflicts with an internal account")
        payee.name = name
        payee.canonical_name = canonical_name

    if "kind" in data and data["kind"] is not None:
        payee.kind = CounterpartyKind(data["kind"].value)

    db.commit()
    db.refresh(payee)
    return jsonable_encoder(_payee_summary_with_count(payee, db))


@router.delete("/{payee_id}")
def delete_payee(payee_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    payee = (
        db.query(Counterparty)
        .filter(Counterparty.id == payee_id, Counterparty.kind.in_(_payee_kinds()))
        .one_or_none()
    )
    if not payee:
        raise HTTPException(status_code=404, detail="Payee not found")

    transaction_count = db.query(func.count(Transaction.id)).filter(Transaction.payee_id == payee_id).scalar() or 0
    db.query(Transaction).filter(Transaction.payee_id == payee_id).update(
        {Transaction.payee_id: None},
        synchronize_session=False,
    )
    delete_automatic_payee_mappings_for_payee(db, payee_id=payee_id)
    db.delete(payee)
    db.commit()
    return {"deleted": True, "transaction_count": transaction_count}


def _payee_summary(payee: Counterparty, transaction_count: int = 0) -> dict[str, object]:
    return {
        "id": payee.id,
        "name": payee.name,
        "kind": payee.kind.value,
        "transaction_count": transaction_count,
    }


def _payee_summary_with_count(payee: Counterparty, db: Session) -> dict[str, object]:
    transaction_count = db.query(func.count(Transaction.id)).filter(Transaction.payee_id == payee.id).scalar() or 0
    return _payee_summary(payee, transaction_count=transaction_count)


def _collect_automatic_seed_matches(db: Session) -> dict[str, dict[str, object]]:
    linked_rows = (
        db.query(
            ImportRow.label_raw,
            ImportRow.supplier_raw,
            ImportRowLink.transaction_id,
        )
        .join(ImportRowLink, ImportRowLink.import_row_id == ImportRow.id)
        .all()
    )

    aggregated: dict[str, dict[str, object]] = {}
    for label_raw, supplier_raw, transaction_id in linked_rows:
        inferred = infer_payee(supplier_raw, label_raw)
        if not inferred:
            continue

        display_name = normalize_payee_display_name(inferred)
        canonical_name = canonicalize_payee_name(display_name)
        if not canonical_name:
            continue

        entry = aggregated.get(canonical_name)
        if entry is None:
            entry = {
                "name": display_name,
                "linked_transaction_ids": set(),
            }
            aggregated[canonical_name] = entry
        elif display_name.lower() < str(entry["name"]).lower():
            entry["name"] = display_name

        linked_transaction_ids = entry["linked_transaction_ids"]
        if isinstance(linked_transaction_ids, set):
            linked_transaction_ids.add(transaction_id)

    return aggregated


def _ignored_seed_names(db: Session) -> set[str]:
    return {
        str(row[0])
        for row in db.query(PayeeSuggestionIgnore.canonical_name).all()
    }


def _payee_kinds() -> tuple[CounterpartyKind, ...]:
    return (
        CounterpartyKind.person,
        CounterpartyKind.merchant,
        CounterpartyKind.unknown,
    )
