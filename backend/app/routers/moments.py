from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Category, Counterparty, Moment, Split, Transaction, TransactionType
from ..services import moment_candidates as moment_candidate_service

router = APIRouter(prefix="/moments", tags=["moments"])


class MomentCreatePayload(BaseModel):
    name: str
    start_date: date
    end_date: date
    description: str | None = None
    cover_image_url: str | None = None


class MomentUpdatePayload(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None
    cover_image_url: str | None = None


class TaggedBulkPayload(BaseModel):
    split_ids: list[int]


class TaggedMovePayload(TaggedBulkPayload):
    target_moment_id: int
    confirm_reassign: bool = False


class CandidateDecisionPayload(TaggedBulkPayload):
    decision: str
    confirm_reassign: bool = False


@router.get("")
def list_moments(
    q: str | None = Query(None, alias="q"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = db.query(Moment)
    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(Moment.name.ilike(search))
    moments = query.order_by(Moment.name.asc()).limit(limit).all()
    if not moments:
        return []

    moment_ids = [moment.id for moment in moments]
    metrics_map = _compute_metrics_batch(db, moment_ids)
    return jsonable_encoder(
        [_moment_summary(moment, metrics=metrics_map.get(moment.id)) for moment in moments]
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_moment(payload: MomentCreatePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    name = _normalize_name(payload.name)
    if not name:
        _raise_api_error(
            status_code=422,
            code="MOMENT_NAME_REQUIRED",
            message="Moment name is required",
        )

    if payload.start_date > payload.end_date:
        _raise_api_error(
            status_code=422,
            code="MOMENT_INVALID_DATE_RANGE",
            message="Moment start_date must be on or before end_date",
        )

    moment = Moment(
        name=name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
        cover_image_url=_normalize_cover_image_url(payload.cover_image_url),
    )
    db.add(moment)
    db.commit()
    db.refresh(moment)

    return jsonable_encoder(_moment_summary(moment))


@router.get("/{moment_id}")
def get_moment(moment_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    moment = _require_moment(db, moment_id=moment_id)
    metrics = _compute_metrics_for_moment(db, moment.id)
    return jsonable_encoder(_moment_summary(moment, metrics=metrics))


@router.patch("/{moment_id}")
def update_moment(
    moment_id: int,
    payload: MomentUpdatePayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    moment = _require_moment(db, moment_id=moment_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data:
        name = _normalize_name(data["name"])
        if not name:
            _raise_api_error(
                status_code=422,
                code="MOMENT_NAME_REQUIRED",
                message="Moment name is required",
            )
        moment.name = name

    candidate_start_date = data.get("start_date", moment.start_date)
    candidate_end_date = data.get("end_date", moment.end_date)
    if candidate_start_date > candidate_end_date:
        _raise_api_error(
            status_code=422,
            code="MOMENT_INVALID_DATE_RANGE",
            message="Moment start_date must be on or before end_date",
        )

    if "start_date" in data:
        moment.start_date = candidate_start_date
    if "end_date" in data:
        moment.end_date = candidate_end_date
    if "description" in data:
        moment.description = data["description"]
    if "cover_image_url" in data:
        moment.cover_image_url = _normalize_cover_image_url(data["cover_image_url"])

    db.commit()
    db.refresh(moment)

    metrics = _compute_metrics_for_moment(db, moment.id)
    return jsonable_encoder(_moment_summary(moment, metrics=metrics))


@router.delete("/{moment_id}")
def delete_moment(moment_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    moment = _require_moment(db, moment_id=moment_id)
    tagged_split_ids = [row[0] for row in db.query(Split.id).filter(Split.moment_id == moment.id).all()]

    if tagged_split_ids:
        db.query(Split).filter(Split.id.in_(tagged_split_ids)).update(
            {Split.moment_id: None},
            synchronize_session=False,
        )

    db.delete(moment)
    db.commit()

    return jsonable_encoder(
        {
            "id": moment_id,
            "deleted": True,
            "untagged_splits_count": len(tagged_split_ids),
        }
    )


@router.get("/{moment_id}/tagged")
def list_tagged_splits(
    moment_id: int,
    q: str | None = Query(None, alias="q"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_moment(db, moment_id=moment_id)

    query = (
        db.query(Split, Transaction, Category, Counterparty)
        .join(Transaction, Transaction.id == Split.transaction_id)
        .outerjoin(Category, Category.id == Split.category_id)
        .outerjoin(Counterparty, Counterparty.id == Split.internal_account_id)
        .filter(Split.moment_id == moment_id)
    )
    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Transaction.label_raw.ilike(search),
                Transaction.supplier_raw.ilike(search),
            )
        )

    total = query.count()
    rows = (
        query.order_by(Transaction.operation_at.desc(), Split.position.asc(), Split.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return jsonable_encoder(
        {
            "rows": [
                _tagged_split_row(split, transaction, category, internal_account)
                for split, transaction, category, internal_account in rows
            ],
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    )


@router.post("/{moment_id}/tagged/remove")
def bulk_remove_tagged_splits(
    moment_id: int,
    payload: TaggedBulkPayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_moment(db, moment_id=moment_id)
    split_ids = _normalize_split_ids(payload.split_ids)
    if not split_ids:
        _raise_api_error(
            status_code=422,
            code="SPLIT_IDS_REQUIRED",
            message="split_ids must contain at least one id",
        )
    try:
        result = moment_candidate_service.remove_tagged_splits(
            db,
            moment_id=moment_id,
            split_ids=split_ids,
        )
    except moment_candidate_service.TaggedSplitOwnershipError as exc:
        _raise_api_error(
            status_code=422,
            code="SPLIT_NOT_TAGGED_TO_MOMENT",
            message="One or more splits are not tagged to the source moment",
            split_ids=exc.split_ids,
            moment_id=moment_id,
        )
    db.commit()

    return jsonable_encoder(
        {
            "moment_id": moment_id,
            "action": "remove",
            "updated_count": result["updated_count"],
        }
    )


@router.post("/{moment_id}/tagged/move")
def bulk_move_tagged_splits(
    moment_id: int,
    payload: TaggedMovePayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_moment(db, moment_id=moment_id)
    split_ids = _normalize_split_ids(payload.split_ids)
    if not split_ids:
        _raise_api_error(
            status_code=422,
            code="SPLIT_IDS_REQUIRED",
            message="split_ids must contain at least one id",
        )
    if payload.target_moment_id == moment_id:
        _raise_api_error(
            status_code=422,
            code="MOMENT_MOVE_TARGET_INVALID",
            message="target_moment_id must be different from source moment",
        )
    _require_moment(
        db,
        moment_id=payload.target_moment_id,
        code="MOMENT_TARGET_NOT_FOUND",
        message="Target moment not found",
    )

    if not payload.confirm_reassign:
        _raise_api_error(
            status_code=409,
            code="MOMENT_REASSIGN_CONFIRM_REQUIRED",
            message="Moving tagged splits requires explicit confirmation",
            split_ids=split_ids,
            source_moment_id=moment_id,
            target_moment_id=payload.target_moment_id,
        )

    try:
        result = moment_candidate_service.move_tagged_splits(
            db,
            source_moment_id=moment_id,
            target_moment_id=payload.target_moment_id,
            split_ids=split_ids,
        )
    except moment_candidate_service.TaggedSplitOwnershipError as exc:
        _raise_api_error(
            status_code=422,
            code="SPLIT_NOT_TAGGED_TO_MOMENT",
            message="One or more splits are not tagged to the source moment",
            split_ids=exc.split_ids,
            moment_id=moment_id,
        )
    db.commit()

    return jsonable_encoder(
        {
            "action": "move",
            "from_moment_id": moment_id,
            "to_moment_id": payload.target_moment_id,
            "updated_count": result["updated_count"],
        }
    )


@router.post("/{moment_id}/candidates/refresh")
def refresh_candidates(moment_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    moment = _require_moment(db, moment_id=moment_id)
    result = moment_candidate_service.refresh_candidates_for_moment(
        db,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
    )
    db.commit()

    return jsonable_encoder(
        {
            "moment_id": moment.id,
            "inserted_count": result["inserted_count"],
            "touched_count": result["touched_count"],
            "status_counts": result["status_counts"],
        }
    )


@router.get("/{moment_id}/candidates")
def list_moment_candidates(
    moment_id: int,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    moment = _require_moment(db, moment_id=moment_id)
    if status_filter is not None and status_filter not in moment_candidate_service.ALLOWED_CANDIDATE_STATUSES:
        _raise_api_error(
            status_code=422,
            code="MOMENT_CANDIDATE_STATUS_INVALID",
            message="status must be one of: pending, accepted, rejected",
        )

    rows, total = moment_candidate_service.list_candidates(
        db,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return jsonable_encoder(
        {
            "rows": [
                _candidate_row_payload(row)
                for row in rows
            ],
            "limit": limit,
            "offset": offset,
            "total": total,
            "status_counts": moment_candidate_service.candidate_status_counts(
                db,
                moment_id=moment.id,
                start_date=moment.start_date,
                end_date=moment.end_date,
            ),
        }
    )


@router.post("/{moment_id}/candidates/decision")
def decide_moment_candidates(
    moment_id: int,
    payload: CandidateDecisionPayload,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    moment = _require_moment(db, moment_id=moment_id)
    split_ids = _normalize_split_ids(payload.split_ids)
    if not split_ids:
        _raise_api_error(
            status_code=422,
            code="SPLIT_IDS_REQUIRED",
            message="split_ids must contain at least one id",
        )
    if payload.decision not in moment_candidate_service.ALLOWED_CANDIDATE_DECISIONS:
        _raise_api_error(
            status_code=422,
            code="MOMENT_CANDIDATE_DECISION_INVALID",
            message="decision must be one of: accepted, rejected",
        )

    try:
        result = moment_candidate_service.decide_candidates(
            db,
            moment_id=moment.id,
            split_ids=split_ids,
            decision=payload.decision,
            confirm_reassign=payload.confirm_reassign,
        )
    except moment_candidate_service.CandidateConflictError as exc:
        _raise_api_error(
            status_code=409,
            code="MOMENT_REASSIGN_CONFIRM_REQUIRED",
            message="One or more splits are already tagged to another moment",
            split_ids=exc.split_ids,
            source_moment_ids=exc.source_moment_ids,
            target_moment_id=moment_id,
        )
    except moment_candidate_service.CandidateEligibilityError as exc:
        _raise_api_error(
            status_code=422,
            code="SPLIT_NOT_ELIGIBLE",
            message="One or more splits are not candidates for this moment",
            split_ids=exc.split_ids,
            moment_id=moment_id,
        )

    db.commit()

    return jsonable_encoder(
        {
            "moment_id": moment_id,
            "decision": payload.decision,
            "updated_count": result["updated_count"],
            "reassigned_count": result["reassigned_count"],
            "status_counts": moment_candidate_service.candidate_status_counts(
                db,
                moment_id=moment.id,
                start_date=moment.start_date,
                end_date=moment.end_date,
            ),
        }
    )


class _MomentMetrics:
    """Computed summary metrics for a moment's tagged splits."""

    __slots__ = ("tagged_splits_count", "expenses_total", "income_total", "top_categories")

    def __init__(
        self,
        *,
        tagged_splits_count: int = 0,
        expenses_total: Decimal = Decimal("0"),
        income_total: Decimal = Decimal("0"),
        top_categories: list[dict[str, object]] | None = None,
    ) -> None:
        self.tagged_splits_count = tagged_splits_count
        self.expenses_total = expenses_total
        self.income_total = income_total
        self.top_categories = top_categories or []

    def to_dict(self) -> dict[str, object]:
        return {
            "tagged_splits_count": self.tagged_splits_count,
            "expenses_total": float(self.expenses_total),
            "income_total": float(self.income_total),
            "top_categories": self.top_categories,
        }


def _compute_metrics_for_moment(db: Session, moment_id: int) -> _MomentMetrics:
    """Compute full summary metrics for a single moment (transfers excluded)."""
    row = (
        db.query(
            func.count(Split.id).label("cnt"),
            func.coalesce(
                func.sum(case((Split.amount < 0, -Split.amount), else_=Decimal("0"))),
                Decimal("0"),
            ).label("expenses"),
            func.coalesce(
                func.sum(case((Split.amount > 0, Split.amount), else_=Decimal("0"))),
                Decimal("0"),
            ).label("income"),
        )
        .join(Transaction, Transaction.id == Split.transaction_id)
        .filter(Split.moment_id == moment_id, Transaction.type != TransactionType.transfer)
        .one()
    )

    tagged_splits_count = int(row.cnt)
    expenses_total = Decimal(str(row.expenses))
    income_total = Decimal(str(row.income))

    top_categories = _compute_top_categories(db, moment_id, expenses_total)

    return _MomentMetrics(
        tagged_splits_count=tagged_splits_count,
        expenses_total=expenses_total,
        income_total=income_total,
        top_categories=top_categories,
    )


def _compute_metrics_batch(db: Session, moment_ids: list[int]) -> dict[int, _MomentMetrics]:
    """Compute summary metrics for multiple moments in batch."""
    if not moment_ids:
        return {}

    rows = (
        db.query(
            Split.moment_id,
            func.count(Split.id).label("cnt"),
            func.coalesce(
                func.sum(case((Split.amount < 0, -Split.amount), else_=Decimal("0"))),
                Decimal("0"),
            ).label("expenses"),
            func.coalesce(
                func.sum(case((Split.amount > 0, Split.amount), else_=Decimal("0"))),
                Decimal("0"),
            ).label("income"),
        )
        .join(Transaction, Transaction.id == Split.transaction_id)
        .filter(Split.moment_id.in_(moment_ids), Transaction.type != TransactionType.transfer)
        .group_by(Split.moment_id)
        .all()
    )

    # Category breakdown per moment (all categories, transfers excluded; top 5 + "other" built in Python)
    cat_rows = (
        db.query(
            Split.moment_id,
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            func.sum(-Split.amount).label("spend"),
        )
        .join(Transaction, Transaction.id == Split.transaction_id)
        .join(Category, Category.id == Split.category_id)
        .filter(Split.moment_id.in_(moment_ids), Split.amount < 0, Transaction.type != TransactionType.transfer)
        .group_by(Split.moment_id, Category.id, Category.name)
        .order_by(Split.moment_id, func.sum(-Split.amount).desc())
        .all()
    )

    # Build per-moment category lists (all rows; sliced to top 5 + "other" below)
    cat_by_moment: dict[int, list[tuple[int, str, Decimal]]] = {}
    for cat_row in cat_rows:
        mid = cat_row.moment_id
        if mid not in cat_by_moment:
            cat_by_moment[mid] = []
        cat_by_moment[mid].append((cat_row.category_id, cat_row.category_name, Decimal(str(cat_row.spend))))

    # Build expenses_total lookup for percentage calculation
    expenses_by_moment: dict[int, Decimal] = {}
    for row in rows:
        expenses_by_moment[row.moment_id] = Decimal(str(row.expenses))

    result: dict[int, _MomentMetrics] = {}
    for row in rows:
        mid = row.moment_id
        exp = Decimal(str(row.expenses))
        all_cats = cat_by_moment.get(mid, [])
        top5 = all_cats[:5]
        rest = all_cats[5:]
        top_categories: list[dict[str, object]] = [
            {
                "category_id": cid,
                "name": cname,
                "amount": float(camount),
                "percentage": round(float(camount / exp * 100), 1) if exp > 0 else 0.0,
            }
            for cid, cname, camount in top5
        ]
        if rest:
            rest_total = sum(camount for _, _, camount in rest)
            top_categories.append({
                "category_id": -1,
                "name": f"Other ({len(rest)} {'category' if len(rest) == 1 else 'categories'})",
                "amount": float(rest_total),
                "percentage": round(float(rest_total / exp * 100), 1) if exp > 0 else 0.0,
                "is_other": True,
            })
        result[mid] = _MomentMetrics(
            tagged_splits_count=int(row.cnt),
            expenses_total=exp,
            income_total=Decimal(str(row.income)),
            top_categories=top_categories,
        )

    return result


def _compute_top_categories(db: Session, moment_id: int, expenses_total: Decimal) -> list[dict[str, object]]:
    """Compute top categories by expense spend for a single moment (transfers excluded, top 5 + optional other)."""
    cat_rows = (
        db.query(
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            func.sum(-Split.amount).label("spend"),
        )
        .join(Transaction, Transaction.id == Split.transaction_id)
        .join(Category, Category.id == Split.category_id)
        .filter(Split.moment_id == moment_id, Split.amount < 0, Transaction.type != TransactionType.transfer)
        .group_by(Category.id, Category.name)
        .order_by(func.sum(-Split.amount).desc())
        .all()
    )
    top5 = cat_rows[:5]
    rest = cat_rows[5:]
    result: list[dict[str, object]] = [
        {
            "category_id": row.category_id,
            "name": row.category_name,
            "amount": float(row.spend),
            "percentage": round(float(row.spend / expenses_total * 100), 1) if expenses_total > 0 else 0.0,
        }
        for row in top5
    ]
    if rest:
        rest_total = sum(Decimal(str(row.spend)) for row in rest)
        result.append({
            "category_id": -1,
            "name": f"Other ({len(rest)} {'category' if len(rest) == 1 else 'categories'})",
            "amount": float(rest_total),
            "percentage": round(float(rest_total / expenses_total * 100), 1) if expenses_total > 0 else 0.0,
            "is_other": True,
        })
    return result


def _moment_summary(moment: Moment, *, metrics: _MomentMetrics | None = None, tagged_splits_count: int = 0) -> dict[str, object]:
    updated_at = getattr(moment, "updated_at", moment.created_at)
    if metrics is None:
        metrics = _MomentMetrics(tagged_splits_count=tagged_splits_count)
    base = {
        "id": moment.id,
        "name": moment.name,
        "start_date": moment.start_date,
        "end_date": moment.end_date,
        "description": moment.description,
        "cover_image_url": moment.cover_image_url,
        "created_at": moment.created_at,
        "updated_at": updated_at,
    }
    base.update(metrics.to_dict())
    return base


def _tagged_split_row(
    split: Split,
    transaction: Transaction,
    category: Category | None,
    internal_account: Counterparty | None,
) -> dict[str, object]:
    return {
        "split_id": split.id,
        "transaction_id": split.transaction_id,
        "operation_at": transaction.operation_at,
        "posted_at": transaction.posted_at,
        "amount": split.amount,
        "currency": transaction.currency,
        "label_raw": transaction.label_raw,
        "supplier_raw": transaction.supplier_raw,
        "category_id": split.category_id,
        "category_name": category.name if category else None,
        "internal_account_id": split.internal_account_id,
        "internal_account_name": internal_account.name if internal_account else None,
        "note": split.note,
        "position": split.position,
    }


def _candidate_row_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row["candidate_id"],
        "moment_id": row["candidate_moment_id"],
        "split_id": row["candidate_split_id"],
        "status": row["candidate_status"],
        "first_seen_at": row["candidate_first_seen_at"],
        "last_seen_at": row["candidate_last_seen_at"],
        "decided_at": row["candidate_decided_at"],
        "split": {
            "id": row["split_id"],
            "transaction_id": row["split_transaction_id"],
            "amount": row["split_amount"],
            "category_id": row["split_category_id"],
            "moment_id": row["split_moment_id"],
            "internal_account_id": row["split_internal_account_id"],
            "note": row["split_note"],
            "position": row["split_position"],
            "operation_at": row["tx_operation_at"],
            "posted_at": row["tx_posted_at"],
            "label_raw": row["tx_label_raw"],
            "supplier_raw": row["tx_supplier_raw"],
            "currency": row["tx_currency"],
        },
    }


def _require_moment(
    db: Session,
    *,
    moment_id: int,
    code: str = "MOMENT_NOT_FOUND",
    message: str = "Moment not found",
) -> Moment:
    moment = db.query(Moment).filter(Moment.id == moment_id).one_or_none()
    if not moment:
        _raise_api_error(
            status_code=404,
            code=code,
            message=message,
            moment_id=moment_id,
        )
    return moment


def _normalize_name(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def _normalize_cover_image_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_split_ids(values: list[int] | None) -> list[int]:
    if not values:
        return []
    deduped: list[int] = []
    seen: set[int] = set()
    for split_id in values:
        if split_id in seen:
            continue
        seen.add(split_id)
        deduped.append(split_id)
    return deduped


def _raise_api_error(status_code: int, code: str, message: str, **extra: object) -> None:
    detail: dict[str, object] = {"code": code, "message": message}
    for key, value in extra.items():
        detail[key] = value
    raise HTTPException(status_code=status_code, detail=detail)


__all__ = ["router"]
