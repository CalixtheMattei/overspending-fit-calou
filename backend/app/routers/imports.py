from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import asc, desc, nullslast, or_
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..db import get_db
from ..models import Account, Import, ImportRow, ImportRowLink, ImportRowStatus
from ..services.import_normalization import infer_payee, infer_type, normalize_label
from ..services.import_service import import_csv_bytes, preview_import_csv_bytes

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/preview")
async def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        stats = preview_import_csv_bytes(db, file.filename or "import.csv", contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return jsonable_encoder({"stats": _stats_dict_from_preview(stats)})


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_import(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        result = import_csv_bytes(db, file.filename or "import.csv", contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stats = _stats_dict(result.import_record)
    return jsonable_encoder({"import_id": result.import_record.id, "stats": stats})


@router.get("")
def list_imports(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    imports = (
        db.query(Import)
        .options(joinedload(Import.account))
        .order_by(Import.imported_at.desc())
        .all()
    )
    return jsonable_encoder([_import_summary(item) for item in imports])


@router.get("/rows")
def list_all_import_rows(
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, alias="q"),
    date_from: date | None = Query(None, alias="date_from"),
    date_to: date | None = Query(None, alias="date_to"),
    sort: str | None = Query(None, alias="sort"),
    direction: str = Query("desc", alias="direction"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = db.query(ImportRow).options(joinedload(ImportRow.link), joinedload(ImportRow.import_).joinedload(Import.account))
    query = _apply_status_filter(query, status_filter)

    if q and q.strip():
        search_value = f"%{q.strip()}%"
        query = query.filter(or_(ImportRow.label_raw.ilike(search_value), ImportRow.supplier_raw.ilike(search_value)))

    if date_from:
        query = query.filter(ImportRow.date_val >= date_from)
    if date_to:
        query = query.filter(ImportRow.date_val <= date_to)

    allowed_sorts = {"date_val", "amount"}
    if sort and sort not in allowed_sorts:
        raise HTTPException(status_code=400, detail="Invalid sort field")

    if direction not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Invalid sort direction")

    total = query.count()
    order_by_clauses = []
    if sort:
        sort_column = ImportRow.date_val if sort == "date_val" else ImportRow.amount
        sort_direction = desc if direction == "desc" else asc
        order_by_clauses.append(nullslast(sort_direction(sort_column)))
    order_by_clauses.append(ImportRow.created_at.desc())

    rows = query.order_by(*order_by_clauses).offset(offset).limit(limit).all()

    return jsonable_encoder(
        {
            "rows": [_import_row_summary_with_import(row) for row in rows],
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    )


@router.get("/{import_id}")
def get_import(import_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    import_record = (
        db.query(Import)
        .options(joinedload(Import.account))
        .filter(Import.id == import_id)
        .one_or_none()
    )
    if not import_record:
        raise HTTPException(status_code=404, detail="Import not found")
    return jsonable_encoder(_import_summary(import_record))


@router.get("/{import_id}/file")
def download_import_file(import_id: int, db: Session = Depends(get_db)) -> FileResponse:
    import_record = db.query(Import).filter(Import.id == import_id).one_or_none()
    if not import_record:
        raise HTTPException(status_code=404, detail="Import not found")
    if not import_record.file_path:
        raise HTTPException(status_code=404, detail="Import file not available")

    storage_dir = Path(settings.imports_storage_dir or "data/imports").resolve()
    file_path = (storage_dir / import_record.file_path).resolve()

    if storage_dir not in file_path.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Import file not found on disk")

    return FileResponse(file_path, media_type="text/csv", filename=import_record.file_name)


@router.get("/{import_id}/rows")
def list_import_rows(
    import_id: int,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    import_record = db.query(Import).filter(Import.id == import_id).one_or_none()
    if not import_record:
        raise HTTPException(status_code=404, detail="Import not found")

    query = db.query(ImportRow).filter(ImportRow.import_id == import_id)
    query = _apply_status_filter(query, status_filter)

    total = query.count()
    rows = (
        query.options(joinedload(ImportRow.link))
        .order_by(ImportRow.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return jsonable_encoder(
        {
            "rows": [_import_row_summary(row) for row in rows],
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    )


@router.get("/{import_id}/rows/{row_id}")
def get_import_row(import_id: int, row_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = (
        db.query(ImportRow)
        .options(joinedload(ImportRow.link).joinedload(ImportRowLink.transaction))
        .filter(ImportRow.import_id == import_id, ImportRow.id == row_id)
        .one_or_none()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Import row not found")

    normalization_preview = _normalization_preview(row)
    transaction_preview = None
    if row.link and row.link.transaction:
        transaction_preview = {
            "id": row.link.transaction.id,
            "posted_at": row.link.transaction.posted_at,
            "amount": row.link.transaction.amount,
            "label_raw": row.link.transaction.label_raw,
            "type": row.link.transaction.type.value,
        }

    payload = _import_row_summary(row)
    payload.update(
        {
            "raw_json": row.raw_json,
            "normalization_preview": normalization_preview,
            "transaction": transaction_preview,
        }
    )
    return jsonable_encoder(payload)


def _stats_dict(import_record: Import) -> dict[str, int]:
    return {
        "row_count": import_record.row_count,
        "created_count": import_record.created_count,
        "linked_count": import_record.linked_count,
        "duplicate_count": import_record.duplicate_count,
        "error_count": import_record.error_count,
    }


def _stats_dict_from_preview(stats) -> dict[str, int]:
    return {
        "row_count": stats.row_count,
        "created_count": stats.created_count,
        "linked_count": stats.linked_count,
        "duplicate_count": stats.duplicate_count,
        "error_count": stats.error_count,
    }


def _import_summary(import_record: Import) -> dict[str, Any]:
    return {
        "id": import_record.id,
        "file_name": import_record.file_name,
        "file_hash": import_record.file_hash,
        "imported_at": import_record.imported_at,
        "account": _account_summary(import_record.account),
        "stats": _stats_dict(import_record),
    }


def _account_summary(account: Account | None) -> dict[str, Any] | None:
    if not account:
        return None
    return {
        "id": account.id,
        "account_num": account.account_num,
        "label": account.label,
    }


def _import_row_summary(row: ImportRow) -> dict[str, Any]:
    transaction_id = row.link.transaction_id if row.link else None
    return {
        "id": row.id,
        "status": row.status.value,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "date_op": row.date_op,
        "date_val": row.date_val,
        "label_raw": row.label_raw,
        "supplier_raw": row.supplier_raw,
        "amount": row.amount,
        "currency": row.currency,
        "category_raw": row.category_raw,
        "category_parent_raw": row.category_parent_raw,
        "comment_raw": row.comment_raw,
        "balance_after": row.balance_after,
        "transaction_id": transaction_id,
    }


def _import_row_summary_with_import(row: ImportRow) -> dict[str, Any]:
    import_record = row.import_
    payload = _import_row_summary(row)
    payload.update(
        {
            "import_id": row.import_id,
            "imported_at": import_record.imported_at,
            "file_name": import_record.file_name,
            "account": _account_summary(import_record.account),
        }
    )
    return payload


def _apply_status_filter(query, status_filter: str | None):
    if not status_filter:
        return query
    if status_filter not in {ImportRowStatus.created.value, ImportRowStatus.linked.value, ImportRowStatus.error.value}:
        raise HTTPException(status_code=400, detail="Invalid status filter")
    return query.filter(ImportRow.status == ImportRowStatus(status_filter))


def _normalization_preview(row: ImportRow) -> dict[str, Any]:
    label_norm = normalize_label(row.label_raw)
    inferred_payee = infer_payee(row.supplier_raw, row.label_raw)
    inferred_type = None
    if row.amount is not None:
        inferred_type = infer_type(label_norm, row.amount).value

    return {
        "label_norm": label_norm,
        "inferred_type": inferred_type,
        "inferred_payee": inferred_payee,
    }
