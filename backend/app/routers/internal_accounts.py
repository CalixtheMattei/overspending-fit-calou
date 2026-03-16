from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Counterparty, CounterpartyKind, Split
from ..services.ledger_validation import canonicalize_payee_name

router = APIRouter(prefix="/internal-accounts", tags=["internal-accounts"])


class InternalAccountCreate(BaseModel):
    name: str
    type: str | None = None
    position: int | None = None


class InternalAccountUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    position: int | None = None
    is_archived: bool | None = None


@router.get("")
def list_internal_accounts(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    counts_subquery = (
        db.query(
            Split.internal_account_id.label("internal_account_id"),
            func.count(Split.id).label("split_count"),
        )
        .group_by(Split.internal_account_id)
        .subquery()
    )
    accounts = (
        db.query(Counterparty, func.coalesce(counts_subquery.c.split_count, 0))
        .outerjoin(counts_subquery, Counterparty.id == counts_subquery.c.internal_account_id)
        .filter(Counterparty.kind == CounterpartyKind.internal)
        .order_by(Counterparty.position.asc(), Counterparty.id.asc())
        .all()
    )
    return jsonable_encoder([_internal_account_summary(account, split_count=count) for account, count in accounts])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_internal_account(payload: InternalAccountCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    name = payload.name.strip() if payload.name else ""
    if not name:
        raise HTTPException(status_code=400, detail="Internal account name is required")
    canonical_name = _canonicalize_internal_name(name)

    existing = db.query(Counterparty).filter(Counterparty.canonical_name == canonical_name).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Internal account name already exists")

    accounts = (
        db.query(Counterparty)
        .filter(Counterparty.kind == CounterpartyKind.internal)
        .order_by(Counterparty.position.asc(), Counterparty.id.asc())
        .all()
    )
    position = _clamp_position(payload.position, len(accounts))

    account = Counterparty(
        name=name,
        canonical_name=canonical_name,
        kind=CounterpartyKind.internal,
        type=payload.type,
        position=position,
        is_archived=False,
    )
    db.add(account)
    db.flush()

    accounts.insert(position, account)
    _resequence_positions(accounts)

    db.commit()
    db.refresh(account)
    return jsonable_encoder(_internal_account_summary(account, split_count=0))


@router.patch("/{account_id}")
def update_internal_account(
    account_id: int,
    payload: InternalAccountUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    account = (
        db.query(Counterparty)
        .filter(Counterparty.id == account_id, Counterparty.kind == CounterpartyKind.internal)
        .one_or_none()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Internal account not found")

    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Internal account name is required")
        canonical_name = _canonicalize_internal_name(name)
        existing = (
            db.query(Counterparty)
            .filter(Counterparty.canonical_name == canonical_name, Counterparty.id != account.id)
            .one_or_none()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Internal account name already exists")
        account.name = name
        account.canonical_name = canonical_name

    if "type" in data:
        account.type = data["type"]

    if "is_archived" in data and data["is_archived"] is not None:
        account.is_archived = data["is_archived"]

    if "position" in data and data["position"] is not None:
        accounts = (
            db.query(Counterparty)
            .filter(Counterparty.kind == CounterpartyKind.internal)
            .order_by(Counterparty.position.asc(), Counterparty.id.asc())
            .all()
        )
        if account in accounts:
            accounts.remove(account)
        position = _clamp_position(data["position"], len(accounts))
        accounts.insert(position, account)
        _resequence_positions(accounts)

    db.commit()
    db.refresh(account)
    split_count = db.query(func.count(Split.id)).filter(Split.internal_account_id == account.id).scalar() or 0
    return jsonable_encoder(_internal_account_summary(account, split_count=split_count))


@router.delete("/{account_id}")
def delete_internal_account(account_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    account = (
        db.query(Counterparty)
        .filter(Counterparty.id == account_id, Counterparty.kind == CounterpartyKind.internal)
        .one_or_none()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Internal account not found")

    split_count = db.query(func.count(Split.id)).filter(Split.internal_account_id == account_id).scalar() or 0
    db.query(Split).filter(Split.internal_account_id == account_id).update(
        {Split.internal_account_id: None},
        synchronize_session=False,
    )
    db.delete(account)

    accounts = (
        db.query(Counterparty)
        .filter(Counterparty.kind == CounterpartyKind.internal)
        .order_by(Counterparty.position.asc(), Counterparty.id.asc())
        .all()
    )
    if account in accounts:
        accounts.remove(account)
    _resequence_positions(accounts)

    db.commit()
    return {"deleted": True, "split_count": split_count}


def _resequence_positions(accounts: list[Counterparty]) -> None:
    for index, account in enumerate(accounts):
        account.position = index


def _clamp_position(position: int | None, max_length: int) -> int:
    if position is None:
        return max_length
    return max(0, min(position, max_length))


def _internal_account_summary(account: Counterparty, split_count: int = 0) -> dict[str, object]:
    return {
        "id": account.id,
        "name": account.name,
        "type": account.type,
        "position": account.position,
        "is_archived": account.is_archived,
        "split_count": split_count,
    }


def _canonicalize_internal_name(name: str) -> str:
    return canonicalize_payee_name(name)
