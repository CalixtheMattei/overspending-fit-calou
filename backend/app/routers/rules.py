from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Rule, RuleRunEffect
from ..services.automatic_payee_mapping import AUTOMATIC_PAYEE_RULE_SOURCE
from ..services.category_canonicalization import canonicalize_category_ids
from ..services.rules_engine import (
    RuleExecutionScope,
    confirm_rule_delete,
    list_rule_impacts,
    list_transaction_rule_history,
    preview_rule_delete,
    preview_rule_impact,
    run_rules_batch,
    validate_action_json,
    validate_matcher_json,
)

router = APIRouter(tags=["rules"])


class RuleCreate(BaseModel):
    name: str
    priority: int | None = None
    enabled: bool = True
    matcher_json: dict[str, Any]
    action_json: dict[str, Any]
    source: str | None = None
    source_ref: str | None = None


class RuleUpdate(BaseModel):
    name: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    matcher_json: dict[str, Any] | None = None
    action_json: dict[str, Any] | None = None
    source: str | None = None
    source_ref: str | None = None


class RuleRunPayload(BaseModel):
    scope: Literal["import", "date_range", "all"]
    mode: Literal["dry_run", "apply"] = "apply"
    allow_overwrite: bool = False
    rule_ids: list[int] | None = None
    import_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


class RulePreviewScopePayload(BaseModel):
    type: Literal["import", "date_range", "all"]
    import_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None


class RulePreviewPayload(BaseModel):
    scope: RulePreviewScopePayload
    matcher_json: dict[str, Any]
    action_json: dict[str, Any]
    mode: Literal["non_destructive", "destructive"] = "non_destructive"
    limit: int = Field(default=10, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = (
        db.query(Rule)
        .filter(or_(Rule.source.is_(None), Rule.source != AUTOMATIC_PAYEE_RULE_SOURCE))
        .order_by(Rule.priority.asc(), Rule.id.asc())
        .all()
    )
    return jsonable_encoder([_rule_summary(row) for row in rows])


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Rule name is required")

    action_json = _canonicalize_action_categories(db, payload.action_json)
    _validate_rule_payload(payload.matcher_json, action_json)

    if payload.source and payload.source_ref:
        existing = db.query(Rule).filter(Rule.source == payload.source, Rule.source_ref == payload.source_ref).one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Rule source mapping already exists")

    row = Rule(
        name=name,
        priority=payload.priority if payload.priority is not None else _next_top_priority(db),
        enabled=payload.enabled,
        matcher_json=payload.matcher_json,
        action_json=action_json,
        source=payload.source.strip() if payload.source else None,
        source_ref=payload.source_ref.strip() if payload.source_ref else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return jsonable_encoder(_rule_summary(row))


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(Rule).filter(Rule.id == rule_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Rule name is required")
        row.name = name
    if "priority" in data and data["priority"] is not None:
        row.priority = data["priority"]
    if "enabled" in data and data["enabled"] is not None:
        row.enabled = data["enabled"]
    if "source" in data:
        row.source = data["source"].strip() if data["source"] else None
    if "source_ref" in data:
        row.source_ref = data["source_ref"].strip() if data["source_ref"] else None
    if "matcher_json" in data and data["matcher_json"] is not None:
        _validate_rule_payload(data["matcher_json"], row.action_json)
        row.matcher_json = data["matcher_json"]
    if "action_json" in data and data["action_json"] is not None:
        canonical_action_json = _canonicalize_action_categories(db, data["action_json"])
        _validate_rule_payload(row.matcher_json, canonical_action_json)
        row.action_json = canonical_action_json

    if row.source and row.source_ref:
        duplicate = (
            db.query(Rule)
            .filter(Rule.source == row.source, Rule.source_ref == row.source_ref, Rule.id != row.id)
            .one_or_none()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Rule source mapping already exists")

    db.commit()
    db.refresh(row)
    return jsonable_encoder(_rule_summary(row))


@router.post("/rules/run")
def run_rules(payload: RuleRunPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    scope = _scope_from_payload(payload)
    batch = run_rules_batch(
        db,
        scope=scope,
        mode=payload.mode,
        allow_overwrite=payload.allow_overwrite,
        trigger_type="manual_scope",
        rule_ids=payload.rule_ids,
    )
    db.commit()
    db.refresh(batch)
    return jsonable_encoder(_batch_summary(batch))


@router.post("/rules/preview")
def preview_rule(payload: RulePreviewPayload, db: Session = Depends(get_db)) -> dict[str, Any]:
    action_json = _canonicalize_action_categories(db, payload.action_json)
    _validate_rule_payload(payload.matcher_json, action_json)
    scope = _scope_from_preview_payload(payload.scope)
    preview = preview_rule_impact(
        db,
        scope=scope,
        matcher_json=payload.matcher_json,
        action_json=action_json,
        allow_overwrite=payload.mode == "destructive",
        limit=payload.limit,
        offset=payload.offset,
    )
    return jsonable_encoder(preview)


@router.get("/rules/{rule_id}/impacts")
def get_rule_impacts(
    rule_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(Rule).filter(Rule.id == rule_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    impacts, total = list_rule_impacts(db, rule_id=rule_id, limit=limit, offset=offset)
    return jsonable_encoder(
        {
            "rule": _rule_summary(row),
            "rows": [_effect_summary(effect, include_rule=False) for effect in impacts],
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    )


@router.get("/transactions/{transaction_id}/rule-history")
def get_transaction_rule_history(
    transaction_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    impacts, total = list_transaction_rule_history(db, transaction_id=transaction_id, limit=limit, offset=offset)
    return jsonable_encoder(
        {
            "rows": [_effect_summary(effect, include_rule=True) for effect in impacts],
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    )


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    mode: Literal["preview", "confirm"] = Query("preview"),
    rollback: bool = Query(True),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.query(Rule).filter(Rule.id == rule_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    if mode == "preview":
        preview = preview_rule_delete(db, rule=row)
        return {
            "total_impacted": preview.total_impacted,
            "reverted_to_uncategorized": preview.reverted_to_uncategorized,
            "skipped_conflict": preview.skipped_conflict,
            "skipped_not_latest": preview.skipped_not_latest,
            "deleted": False,
            "impacted": preview.impacted,
        }

    summary = confirm_rule_delete(db, rule=row, rollback=rollback)
    db.commit()
    return summary


def _scope_from_payload(payload: RuleRunPayload) -> RuleExecutionScope:
    return _scope_from_values(
        scope_type=payload.scope,
        import_id=payload.import_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )


def _scope_from_preview_payload(payload: RulePreviewScopePayload) -> RuleExecutionScope:
    return _scope_from_values(
        scope_type=payload.type,
        import_id=payload.import_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )


def _scope_from_values(
    *,
    scope_type: Literal["import", "date_range", "all"],
    import_id: int | None,
    date_from: date | None,
    date_to: date | None,
) -> RuleExecutionScope:
    if scope_type == "import":
        if import_id is None:
            raise HTTPException(status_code=400, detail="import_id is required for import scope")
        return RuleExecutionScope(type="import", import_id=import_id)
    if scope_type == "date_range":
        if date_from is None and date_to is None:
            raise HTTPException(status_code=400, detail="date_from or date_to is required for date_range scope")
        return RuleExecutionScope(type="date_range", date_from=date_from, date_to=date_to)
    return RuleExecutionScope(type="all")


def _validate_rule_payload(matcher_json: dict[str, Any], action_json: dict[str, Any]) -> None:
    matcher_errors = validate_matcher_json(matcher_json)
    if matcher_errors:
        raise HTTPException(status_code=400, detail=matcher_errors[0])
    action_errors = validate_action_json(action_json)
    if action_errors:
        raise HTTPException(status_code=400, detail=action_errors[0])


def _next_top_priority(db: Session) -> int:
    min_priority = db.query(func.min(Rule.priority)).scalar()
    if min_priority is None:
        return 100
    return int(min_priority) - 1


def _canonicalize_action_categories(db: Session, action_json: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action_json, dict):
        return action_json

    category_ids: set[int] = set()
    set_category = action_json.get("set_category")
    if isinstance(set_category, int):
        category_ids.add(set_category)

    template = action_json.get("set_split_template")
    if isinstance(template, list):
        for row in template:
            if not isinstance(row, dict):
                continue
            category_id = row.get("category_id")
            if isinstance(category_id, int):
                category_ids.add(category_id)

    if not category_ids:
        return action_json

    canonical_map = canonicalize_category_ids(db, category_ids, context="rules.write_action_json")
    result = dict(action_json)

    if isinstance(set_category, int):
        result["set_category"] = canonical_map.get(set_category, set_category)

    if isinstance(template, list):
        next_template: list[Any] = []
        for row in template:
            if not isinstance(row, dict):
                next_template.append(row)
                continue
            next_row = dict(row)
            category_id = row.get("category_id")
            if isinstance(category_id, int):
                next_row["category_id"] = canonical_map.get(category_id, category_id)
            next_template.append(next_row)
        result["set_split_template"] = next_template

    return result


def _rule_summary(row: Rule) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "priority": row.priority,
        "enabled": row.enabled,
        "source": row.source,
        "source_ref": row.source_ref,
        "matcher_json": row.matcher_json,
        "action_json": row.action_json,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _batch_summary(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "trigger_type": row.trigger_type,
        "scope_json": row.scope_json,
        "mode": row.mode,
        "allow_overwrite": row.allow_overwrite,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "created_by": row.created_by,
        "summary_json": row.summary_json,
    }


def _effect_summary(effect: RuleRunEffect, *, include_rule: bool) -> dict[str, Any]:
    payload = {
        "id": effect.id,
        "batch_id": effect.batch_id,
        "rule_id": effect.rule_id,
        "transaction_id": effect.transaction_id,
        "status": effect.status,
        "reason_code": effect.reason_code,
        "before_json": effect.before_json,
        "after_json": effect.after_json,
        "change_json": effect.change_json,
        "applied_at": effect.applied_at,
        "batch": _batch_summary(effect.batch) if effect.batch else None,
        "split_lineage": [
            {
                "id": row.id,
                "transaction_id": row.transaction_id,
                "split_id": row.split_id,
                "effect_id": row.effect_id,
                "operation": row.operation,
                "before_json": row.before_json,
                "after_json": row.after_json,
                "recorded_at": row.recorded_at,
            }
            for row in effect.split_lineage
        ],
    }
    if include_rule and effect.rule:
        payload["rule"] = {
            "id": effect.rule.id,
            "name": effect.rule.name,
            "priority": effect.rule.priority,
            "enabled": effect.rule.enabled,
        }
    return payload
