from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..models import (
    Category,
    Counterparty,
    CounterpartyKind,
    ImportRow,
    ImportRowLink,
    ImportRowStatus,
    Moment,
    Rule,
    RuleRunBatch,
    RuleRunEffect,
    Split,
    SplitLineage,
    Transaction,
    TransactionType,
)
from .category_canonicalization import canonicalize_category_id, ensure_transaction_category_assignment_allowed
from .ledger_validation import SplitValidationError, canonicalize_payee_name, normalize_payee_display_name, parse_decimal_2, validate_splits

ALLOWED_MATCH_PREDICATES = {
    "label_contains",
    "label_regex",
    "supplier_contains",
    "amount_between",
    "amount_equals",
    "type_is",
    "posted_at_between",
    "day_of_month_is",
    "account_id_is",
}

ALLOWED_ACTION_KEYS = {
    "set_payee",
    "set_type",
    "set_category",
    "set_split_template",
    "set_moment",
}

RULE_REASON_DISABLED = "RULE_DISABLED"
RULE_REASON_NO_MATCH = "NO_MATCH"
RULE_REASON_FIELD_ALREADY_SET = "FIELD_ALREADY_SET"
RULE_REASON_SPLITS_ALREADY_EXIST = "SPLITS_ALREADY_EXIST"
RULE_REASON_OVERWRITE_NOT_ALLOWED = "OVERWRITE_NOT_ALLOWED"
RULE_REASON_VALIDATION_FAILED = "VALIDATION_FAILED"
RULE_REASON_DEPENDENCY_NOT_FOUND = "DEPENDENCY_NOT_FOUND"
RULE_REASON_CONFLICT_LATER_EDIT = "CONFLICT_LATER_EDIT"

RULE_STATUS_MATCHED_NOOP = "matched_noop"
RULE_STATUS_APPLIED = "applied"
RULE_STATUS_SKIPPED = "skipped"
RULE_STATUS_ERROR = "error"


@dataclass(slots=True)
class RuleExecutionScope:
    type: str
    import_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    transaction_ids: list[int] | None = None
    created_only: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "import_id": self.import_id,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "transaction_ids": list(self.transaction_ids or []),
            "created_only": self.created_only,
        }


@dataclass(slots=True)
class RuleExecutionResult:
    status: str
    reason_code: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    change_json: dict[str, Any] | None
    split_operations: list[dict[str, Any]]
    matcher_hit: bool


@dataclass(slots=True)
class RuleEvaluationRecord:
    transaction: Transaction
    rule: Rule
    result: RuleExecutionResult


@dataclass(slots=True)
class RuleDeletePreview:
    total_impacted: int
    reverted_to_uncategorized: int
    skipped_conflict: int
    skipped_not_latest: int
    impacted: list[dict[str, Any]]


def validate_matcher_json(matcher_json: Any) -> list[str]:
    if not isinstance(matcher_json, dict):
        return ["matcher_json must be an object"]

    if "all" not in matcher_json and "any" not in matcher_json:
        return ["matcher_json requires at least one of: all, any"]

    errors: list[str] = []
    for group in ("all", "any"):
        raw_conditions = matcher_json.get(group, [])
        if raw_conditions is None:
            continue
        if not isinstance(raw_conditions, list):
            errors.append(f"matcher_json.{group} must be an array")
            continue
        for idx, condition in enumerate(raw_conditions):
            if not isinstance(condition, dict):
                errors.append(f"matcher_json.{group}[{idx}] must be an object")
                continue
            predicate = condition.get("predicate")
            if predicate not in ALLOWED_MATCH_PREDICATES:
                errors.append(f"matcher_json.{group}[{idx}] has unsupported predicate")
                continue
            if predicate in {"label_contains", "supplier_contains", "label_regex", "amount_equals", "type_is"}:
                if "value" not in condition:
                    errors.append(f"matcher_json.{group}[{idx}].value is required")
            if predicate == "amount_between" and ("min" not in condition and "max" not in condition):
                errors.append(f"matcher_json.{group}[{idx}] requires min and/or max")
            if predicate == "posted_at_between" and ("from" not in condition and "to" not in condition):
                errors.append(f"matcher_json.{group}[{idx}] requires from and/or to")
            if predicate == "day_of_month_is" and "value" not in condition:
                errors.append(f"matcher_json.{group}[{idx}].value is required")
            if predicate == "label_regex" and "value" in condition:
                try:
                    re.compile(str(condition["value"]))
                except re.error:
                    errors.append(f"matcher_json.{group}[{idx}] has invalid regex")
    return errors


def validate_action_json(action_json: Any) -> list[str]:
    if not isinstance(action_json, dict):
        return ["action_json must be an object"]
    if not action_json:
        return ["action_json must not be empty"]

    errors: list[str] = []
    unknown_keys = set(action_json.keys()) - ALLOWED_ACTION_KEYS
    if unknown_keys:
        errors.append(f"action_json contains unsupported keys: {', '.join(sorted(unknown_keys))}")

    if "set_payee" in action_json:
        value = action_json["set_payee"]
        if not isinstance(value, (int, str, dict)):
            errors.append("action_json.set_payee must be an integer id, string name, or object")

    if "set_type" in action_json:
        value = action_json["set_type"]
        allowed = {t.value for t in TransactionType if t != TransactionType.adjustment}
        if not isinstance(value, str) or value not in allowed:
            errors.append("action_json.set_type must be one of: expense, income, transfer, refund")

    if "set_category" in action_json:
        value = action_json["set_category"]
        if not isinstance(value, int):
            errors.append("action_json.set_category must be an integer category id")

    if "set_split_template" in action_json:
        template = action_json["set_split_template"]
        if not isinstance(template, list) or not template:
            errors.append("action_json.set_split_template must be a non-empty array")
        else:
            for idx, row in enumerate(template):
                if not isinstance(row, dict):
                    errors.append(f"action_json.set_split_template[{idx}] must be an object")
                    continue
                if "category_id" not in row or not isinstance(row["category_id"], int):
                    errors.append(f"action_json.set_split_template[{idx}].category_id must be an integer")
                has_fixed = "amount_fixed" in row
                has_percent = "percent" in row
                if has_fixed == has_percent:
                    errors.append(
                        f"action_json.set_split_template[{idx}] must define exactly one of amount_fixed or percent"
                    )

    if "set_moment" in action_json and action_json["set_moment"] is not None:
        if not isinstance(action_json["set_moment"], int):
            errors.append("action_json.set_moment must be an integer moment id")

    if "set_category" in action_json and "set_split_template" in action_json:
        errors.append("action_json cannot contain both set_category and set_split_template")

    return errors


def run_rules_batch(
    db: Session,
    *,
    scope: RuleExecutionScope,
    mode: str,
    allow_overwrite: bool,
    trigger_type: str,
    rule_ids: list[int] | None = None,
    created_by: str | None = None,
) -> RuleRunBatch:
    if mode not in {"dry_run", "apply"}:
        raise ValueError("mode must be dry_run or apply")
    if trigger_type not in {"import_auto", "manual_scope"}:
        raise ValueError("trigger_type must be import_auto or manual_scope")

    batch = RuleRunBatch(
        trigger_type=trigger_type,
        scope_json=scope.as_dict(),
        mode=mode,
        allow_overwrite=allow_overwrite,
        created_by=created_by,
    )
    db.add(batch)
    db.flush()

    rules = _load_rules_for_run(db, rule_ids=rule_ids)
    transactions = _load_transactions_for_scope(db, scope)
    records, counters = _evaluate_rules(
        db,
        transactions=transactions,
        rules=rules,
        mode=mode,
        allow_overwrite=allow_overwrite,
    )

    for record in records:
        effect = RuleRunEffect(
            batch_id=batch.id,
            rule_id=record.rule.id,
            transaction_id=record.transaction.id,
            status=record.result.status,
            reason_code=record.result.reason_code,
            before_json=record.result.before_json,
            after_json=record.result.after_json,
            change_json=record.result.change_json,
        )
        db.add(effect)
        db.flush()

        for operation in record.result.split_operations:
            db.add(
                SplitLineage(
                    transaction_id=record.transaction.id,
                    split_id=operation.get("split_id"),
                    effect_id=effect.id,
                    operation=operation["operation"],
                    before_json=operation.get("before_json"),
                    after_json=operation.get("after_json"),
                )
            )

    batch.summary_json = counters
    batch.finished_at = _utc_now()
    db.flush()
    return batch


def run_rules_for_import_created_transactions(db: Session, import_id: int) -> RuleRunBatch | None:
    has_enabled_rules = db.query(func.count(Rule.id)).filter(Rule.enabled.is_(True)).scalar() or 0
    if not has_enabled_rules:
        return None
    scope = RuleExecutionScope(type="import", import_id=import_id, created_only=True)
    return run_rules_batch(
        db,
        scope=scope,
        mode="apply",
        allow_overwrite=False,
        trigger_type="import_auto",
    )


def preview_rule_impact(
    db: Session,
    *,
    scope: RuleExecutionScope,
    matcher_json: dict[str, Any],
    action_json: dict[str, Any],
    allow_overwrite: bool,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    preview_rule = Rule(
        name="preview_rule_candidate",
        priority=0,
        enabled=True,
        matcher_json=matcher_json,
        action_json=action_json,
    )
    transactions = _load_transactions_for_scope(db, scope)

    nested_tx = db.begin_nested()
    try:
        records, summary = _evaluate_rules(
            db,
            transactions=transactions,
            rules=[preview_rule],
            mode="dry_run",
            allow_overwrite=allow_overwrite,
        )
        matched_rows = [
            _preview_effect_row(record.transaction, record.result)
            for record in records
            if record.result.status == RULE_STATUS_APPLIED
        ]
    finally:
        if nested_tx.is_active:
            nested_tx.rollback()

    total = len(matched_rows)
    rows = matched_rows[offset : offset + limit]
    return {
        "transactions_scanned": summary["transactions_scanned"],
        "transactions_matched": summary["transactions_matched"],
        "transactions_changed": summary["transactions_changed"],
        "match_count": summary["transactions_changed"],
        "rows": rows,
        "sample": rows,
        "limit": limit,
        "offset": offset,
        "total": total,
    }


def _load_rules_for_run(db: Session, *, rule_ids: list[int] | None) -> list[Rule]:
    query = db.query(Rule).filter(Rule.enabled.is_(True))
    if rule_ids:
        deduped_ids = sorted(set(int(rule_id) for rule_id in rule_ids))
        query = query.filter(Rule.id.in_(deduped_ids))
    return query.order_by(Rule.priority.asc(), Rule.id.asc()).all()


def _evaluate_rules(
    db: Session,
    *,
    transactions: list[Transaction],
    rules: list[Rule],
    mode: str,
    allow_overwrite: bool,
) -> tuple[list[RuleEvaluationRecord], dict[str, int]]:
    dependency_cache = _load_dependency_cache(db)
    payee_cache: dict[str, int] = {}
    records: list[RuleEvaluationRecord] = []
    counters = {
        "transactions_scoped": len(transactions),
        "transactions_scanned": len(transactions),
        "transactions_matched": 0,
        "transactions_changed": 0,
        "rule_runs_created": 0,
        "rules_evaluated": 0,
        "applied": 0,
        "matched_noop": 0,
        "skipped": 0,
        "error": 0,
    }

    for transaction in transactions:
        transaction_matched = False
        transaction_changed = False

        for rule in rules:
            counters["rules_evaluated"] += 1
            result = _execute_rule(
                db,
                transaction=transaction,
                rule=rule,
                mode=mode,
                allow_overwrite=allow_overwrite,
                dependency_cache=dependency_cache,
                payee_cache=payee_cache,
            )
            records.append(
                RuleEvaluationRecord(
                    transaction=transaction,
                    rule=rule,
                    result=result,
                )
            )

            if result.status == RULE_STATUS_APPLIED:
                counters["applied"] += 1
            elif result.status == RULE_STATUS_MATCHED_NOOP:
                counters["matched_noop"] += 1
            elif result.status == RULE_STATUS_SKIPPED:
                counters["skipped"] += 1
            elif result.status == RULE_STATUS_ERROR:
                counters["error"] += 1

            if result.matcher_hit:
                transaction_matched = True
                if result.status == RULE_STATUS_APPLIED:
                    transaction_changed = True
                break

        if transaction_matched:
            counters["transactions_matched"] += 1
        if transaction_changed:
            counters["transactions_changed"] += 1

    counters["rule_runs_created"] = len(records)
    return records, counters


def _preview_effect_row(transaction: Transaction, result: RuleExecutionResult) -> dict[str, Any]:
    before = _preview_snapshot_state(result.before_json)
    after = _preview_snapshot_state(result.after_json)
    changed_fields = sorted(
        {
            *list((result.change_json or {}).get("fields", {}).keys()),
            *(
                ["splits"]
                if (result.change_json or {}).get("split_operations")
                else []
            ),
        }
    )
    return {
        "transaction_id": transaction.id,
        "posted_at": transaction.posted_at.isoformat(),
        "label_raw": transaction.label_raw,
        "amount": _serialize_amount(transaction.amount),
        "currency": transaction.currency,
        "before": before,
        "after": after,
        "changed_fields": changed_fields,
    }


def _preview_snapshot_state(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {
            "payee_id": None,
            "type": None,
            "category_id": None,
            "has_splits": False,
        }

    splits = snapshot.get("splits", [])
    single_category_id = None
    if len(splits) == 1:
        single_category_id = splits[0].get("category_id")
    return {
        "payee_id": snapshot.get("payee_id"),
        "type": snapshot.get("type"),
        "category_id": single_category_id,
        "has_splits": bool(splits),
    }


def list_rule_impacts(db: Session, *, rule_id: int, limit: int, offset: int) -> tuple[list[RuleRunEffect], int]:
    query = (
        db.query(RuleRunEffect)
        .options(
            joinedload(RuleRunEffect.batch),
            joinedload(RuleRunEffect.split_lineage),
        )
        .filter(RuleRunEffect.rule_id == rule_id)
    )
    total = query.count()
    rows = query.order_by(RuleRunEffect.id.desc()).offset(offset).limit(limit).all()
    return rows, total


def list_transaction_rule_history(
    db: Session,
    *,
    transaction_id: int,
    limit: int,
    offset: int,
) -> tuple[list[RuleRunEffect], int]:
    query = (
        db.query(RuleRunEffect)
        .options(
            joinedload(RuleRunEffect.rule),
            joinedload(RuleRunEffect.batch),
            joinedload(RuleRunEffect.split_lineage),
        )
        .filter(RuleRunEffect.transaction_id == transaction_id)
    )
    total = query.count()
    rows = query.order_by(RuleRunEffect.id.desc()).offset(offset).limit(limit).all()
    return rows, total


def preview_rule_delete(db: Session, *, rule: Rule) -> RuleDeletePreview:
    latest_effects = _latest_rule_effects_by_transaction(db, rule_id=rule.id)
    impacted: list[dict[str, Any]] = []

    total_impacted = len(latest_effects)
    reverted = 0
    skipped_conflict = 0
    skipped_not_latest = 0

    for transaction_id, effect in latest_effects.items():
        latest_overall = (
            db.query(RuleRunEffect)
            .filter(
                RuleRunEffect.transaction_id == transaction_id,
                RuleRunEffect.status == RULE_STATUS_APPLIED,
            )
            .order_by(RuleRunEffect.id.desc())
            .first()
        )

        is_latest = latest_overall is not None and latest_overall.id == effect.id
        transaction = (
            db.query(Transaction)
            .options(joinedload(Transaction.splits))
            .filter(Transaction.id == transaction_id)
            .one_or_none()
        )

        reversible = bool(transaction and is_latest and _snapshot_matches_effect_after(transaction, effect))
        reason = None
        if reversible:
            reverted += 1
        elif not is_latest:
            skipped_not_latest += 1
            reason = "skipped_not_latest"
        else:
            skipped_conflict += 1
            reason = "skipped_conflict"

        impacted.append(
            {
                "transaction_id": transaction_id,
                "effect_id": effect.id,
                "reversible": reversible,
                "reason": reason,
            }
        )

    return RuleDeletePreview(
        total_impacted=total_impacted,
        reverted_to_uncategorized=reverted,
        skipped_conflict=skipped_conflict,
        skipped_not_latest=skipped_not_latest,
        impacted=impacted,
    )


def confirm_rule_delete(
    db: Session,
    *,
    rule: Rule,
    rollback: bool,
) -> dict[str, Any]:
    preview = preview_rule_delete(db, rule=rule)

    reverted_count = 0
    if rollback:
        reversible_tx_ids = [item["transaction_id"] for item in preview.impacted if item["reversible"]]
        if reversible_tx_ids:
            transactions = (
                db.query(Transaction)
                .options(joinedload(Transaction.splits))
                .filter(Transaction.id.in_(reversible_tx_ids))
                .all()
            )
            for transaction in transactions:
                _replace_transaction_splits(db, transaction, [])
                reverted_count += 1

    db.delete(rule)
    db.flush()

    return {
        "total_impacted": preview.total_impacted,
        "reverted_to_uncategorized": reverted_count if rollback else 0,
        "skipped_conflict": preview.skipped_conflict,
        "skipped_not_latest": preview.skipped_not_latest,
        "deleted": True,
    }


def _execute_rule(
    db: Session,
    *,
    transaction: Transaction,
    rule: Rule,
    mode: str,
    allow_overwrite: bool,
    dependency_cache: dict[str, set[int]],
    payee_cache: dict[str, int],
) -> RuleExecutionResult:
    matcher = rule.matcher_json or {}

    try:
        matches = _rule_matches_transaction(transaction, matcher)
    except Exception:
        return RuleExecutionResult(
            status=RULE_STATUS_ERROR,
            reason_code=RULE_REASON_VALIDATION_FAILED,
            before_json=None,
            after_json=None,
            change_json={"error": "matcher_evaluation_failed"},
            split_operations=[],
            matcher_hit=False,
        )

    if not matches:
        return RuleExecutionResult(
            status=RULE_STATUS_SKIPPED,
            reason_code=RULE_REASON_NO_MATCH,
            before_json=None,
            after_json=None,
            change_json=None,
            split_operations=[],
            matcher_hit=False,
        )

    before_snapshot = _transaction_snapshot(transaction)
    try:
        planned = _plan_rule_changes(
            db,
            transaction=transaction,
            action_json=rule.action_json,
            allow_overwrite=allow_overwrite,
            dependency_cache=dependency_cache,
            payee_cache=payee_cache,
        )
    except LookupError:
        return RuleExecutionResult(
            status=RULE_STATUS_ERROR,
            reason_code=RULE_REASON_DEPENDENCY_NOT_FOUND,
            before_json=before_snapshot,
            after_json=before_snapshot,
            change_json={"error": "dependency_not_found"},
            split_operations=[],
            matcher_hit=True,
        )
    except (ValueError, SplitValidationError):
        return RuleExecutionResult(
            status=RULE_STATUS_ERROR,
            reason_code=RULE_REASON_VALIDATION_FAILED,
            before_json=before_snapshot,
            after_json=before_snapshot,
            change_json={"error": "action_validation_failed"},
            split_operations=[],
            matcher_hit=True,
        )

    if not planned["changed"]:
        return RuleExecutionResult(
            status=RULE_STATUS_MATCHED_NOOP,
            reason_code=planned["reason_code"] or RULE_REASON_FIELD_ALREADY_SET,
            before_json=before_snapshot,
            after_json=before_snapshot,
            change_json={"fields": {}, "split_operations": []},
            split_operations=[],
            matcher_hit=True,
        )

    if mode == "apply":
        if planned["field_updates"].get("payee_id", _MISSING) is not _MISSING:
            transaction.payee_id = planned["field_updates"]["payee_id"]
        if planned["field_updates"].get("type", _MISSING) is not _MISSING:
            transaction.type = TransactionType(planned["field_updates"]["type"])
        if planned["split_payloads"] is not _MISSING:
            _replace_transaction_splits(db, transaction, planned["split_payloads"])
        db.flush()
        after_snapshot = _transaction_snapshot(transaction)
    else:
        after_snapshot = _simulated_after_snapshot(
            transaction,
            field_updates=planned["field_updates"],
            split_payloads=planned["split_payloads"],
        )

    split_operations = _compute_split_operations(
        before_snapshot["splits"],
        after_snapshot["splits"],
        mode=mode,
    )
    return RuleExecutionResult(
        status=RULE_STATUS_APPLIED,
        reason_code=None,
        before_json=before_snapshot,
        after_json=after_snapshot,
        change_json={
            "fields": planned["field_changes"],
            "split_operations": split_operations,
        },
        split_operations=split_operations,
        matcher_hit=True,
    )


_MISSING = object()


def _plan_rule_changes(
    db: Session,
    *,
    transaction: Transaction,
    action_json: dict[str, Any],
    allow_overwrite: bool,
    dependency_cache: dict[str, set[int]],
    payee_cache: dict[str, int],
) -> dict[str, Any]:
    errors = validate_action_json(action_json)
    if errors:
        raise ValueError(errors[0])

    field_updates: dict[str, Any] = {}
    field_changes: dict[str, dict[str, Any]] = {}
    split_payloads: Any = _MISSING
    reason_code: str | None = None

    current_splits = _normalize_split_payloads_from_transaction(transaction)

    set_payee = action_json.get("set_payee", _MISSING)
    if set_payee is not _MISSING:
        target_payee_id = _resolve_payee_id(db, set_payee, payee_cache)
        if transaction.payee_id != target_payee_id:
            if transaction.payee_id is not None and not allow_overwrite:
                reason_code = reason_code or RULE_REASON_FIELD_ALREADY_SET
            else:
                field_updates["payee_id"] = target_payee_id
                field_changes["payee_id"] = {"before": transaction.payee_id, "after": target_payee_id}

    set_type = action_json.get("set_type", _MISSING)
    if set_type is not _MISSING:
        target_type = str(set_type)
        if transaction.type.value != target_type:
            if not allow_overwrite:
                reason_code = reason_code or RULE_REASON_OVERWRITE_NOT_ALLOWED
            else:
                field_updates["type"] = target_type
                field_changes["type"] = {"before": transaction.type.value, "after": target_type}

    requested_splits: list[dict[str, Any]] | None = None
    set_category = action_json.get("set_category", _MISSING)
    set_template = action_json.get("set_split_template", _MISSING)
    set_moment = action_json.get("set_moment", _MISSING)

    if set_category is not _MISSING or set_template is not _MISSING:
        if current_splits and not allow_overwrite:
            reason_code = reason_code or RULE_REASON_SPLITS_ALREADY_EXIST
        else:
            requested_splits = _build_split_payloads(
                db=db,
                transaction=transaction,
                action_json=action_json,
                dependency_cache=dependency_cache,
            )
    elif set_moment is not _MISSING and set_moment is not None:
        if current_splits and allow_overwrite:
            moment_id = int(set_moment)
            if moment_id not in dependency_cache["moment_ids"]:
                raise LookupError("moment not found")
            requested_splits = []
            for row in current_splits:
                next_row = {**row, "moment_id": moment_id}
                requested_splits.append(next_row)
        elif current_splits and not allow_overwrite:
            reason_code = reason_code or RULE_REASON_OVERWRITE_NOT_ALLOWED

    if requested_splits is not None:
        same_splits = _compare_split_payloads(current_splits, requested_splits)
        if not same_splits:
            split_payloads = requested_splits
        elif reason_code is None:
            reason_code = RULE_REASON_FIELD_ALREADY_SET

    target_type = field_updates.get("type", transaction.type.value)
    candidate_splits = current_splits if split_payloads is _MISSING else split_payloads
    candidate_category_ids = {
        int(row["category_id"])
        for row in candidate_splits
        if row.get("category_id") is not None
    }
    if candidate_category_ids:
        ensure_transaction_category_assignment_allowed(
            db,
            transaction_type=target_type,
            category_ids=candidate_category_ids,
        )

    changed = bool(field_changes) or split_payloads is not _MISSING
    return {
        "changed": changed,
        "reason_code": reason_code,
        "field_updates": field_updates,
        "field_changes": field_changes,
        "split_payloads": split_payloads,
    }


def _build_split_payloads(
    db: Session,
    *,
    transaction: Transaction,
    action_json: dict[str, Any],
    dependency_cache: dict[str, set[int]],
) -> list[dict[str, Any]]:
    global_moment = action_json.get("set_moment")
    if global_moment is not None:
        moment_id = int(global_moment)
        if moment_id not in dependency_cache["moment_ids"]:
            raise LookupError("moment not found")
    else:
        moment_id = None

    if "set_category" in action_json:
        category_id = canonicalize_category_id(db, int(action_json["set_category"]), context="rules_engine.set_category")
        if category_id not in dependency_cache["category_ids"]:
            raise LookupError("category not found")
        raw_splits = [
            {
                "amount": transaction.amount,
                "category_id": category_id,
                "moment_id": moment_id,
                "internal_account_id": None,
                "note": None,
            }
        ]
        return validate_splits(transaction.amount, raw_splits)

    template = action_json.get("set_split_template")
    if not isinstance(template, list):
        raise ValueError("set_split_template must be a list")

    raw_splits: list[dict[str, Any]] = []
    for row in template:
        category_id = canonicalize_category_id(
            db,
            int(row["category_id"]),
            context="rules_engine.set_split_template",
        )
        if category_id not in dependency_cache["category_ids"]:
            raise LookupError("category not found")

        local_moment = row.get("moment_id")
        resolved_moment = moment_id
        if local_moment is not None:
            resolved_moment = int(local_moment)
            if resolved_moment not in dependency_cache["moment_ids"]:
                raise LookupError("moment not found")

        internal_account_id = row.get("internal_account_id")
        if internal_account_id is not None:
            internal_account_id = int(internal_account_id)
            if internal_account_id not in dependency_cache["internal_account_ids"]:
                raise LookupError("internal_account not found")

        if "amount_fixed" in row:
            amount_value = parse_decimal_2(row["amount_fixed"])
        else:
            percent = _parse_decimal(row.get("percent"))
            amount_value = parse_decimal_2((transaction.amount * percent) / Decimal("100"))

        raw_splits.append(
            {
                "amount": amount_value,
                "category_id": category_id,
                "moment_id": resolved_moment,
                "internal_account_id": internal_account_id,
                "note": row.get("note"),
            }
        )

    return validate_splits(transaction.amount, raw_splits)


def _parse_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid decimal value") from exc


def _resolve_payee_id(db: Session, value: Any, payee_cache: dict[str, int]) -> int:
    if isinstance(value, int):
        exists = (
            db.query(Counterparty.id)
            .filter(
                Counterparty.id == value,
                Counterparty.kind.in_([CounterpartyKind.person, CounterpartyKind.merchant, CounterpartyKind.unknown]),
            )
            .one_or_none()
        )
        if not exists:
            raise LookupError("payee id not found")
        return value

    if isinstance(value, dict):
        if "id" in value:
            return _resolve_payee_id(db, value["id"], payee_cache)
        if "name" in value:
            return _resolve_payee_id(db, value["name"], payee_cache)
        raise ValueError("invalid payee object")

    if not isinstance(value, str):
        raise ValueError("set_payee must be string or id")

    name = value.strip()
    if not name:
        raise ValueError("set_payee name must not be empty")
    display_name = normalize_payee_display_name(name)
    canonical_name = canonicalize_payee_name(display_name)
    cached = payee_cache.get(canonical_name)
    if cached:
        return cached

    existing = db.query(Counterparty).filter(Counterparty.canonical_name == canonical_name).one_or_none()
    if existing:
        if existing.kind == CounterpartyKind.internal:
            raise LookupError("payee id not found")
        payee_cache[canonical_name] = existing.id
        return existing.id

    payee = Counterparty(
        name=display_name,
        kind=CounterpartyKind.unknown,
        canonical_name=canonical_name,
        type=None,
        position=0,
        is_archived=False,
    )
    db.add(payee)
    db.flush()
    payee_cache[canonical_name] = payee.id
    return payee.id


def _rule_matches_transaction(transaction: Transaction, matcher: dict[str, Any]) -> bool:
    all_conditions = matcher.get("all") or []
    any_conditions = matcher.get("any") or []

    if all_conditions and not all(_evaluate_condition(transaction, condition) for condition in all_conditions):
        return False
    if any_conditions and not any(_evaluate_condition(transaction, condition) for condition in any_conditions):
        return False
    return bool(all_conditions or any_conditions)


def _evaluate_condition(transaction: Transaction, condition: dict[str, Any]) -> bool:
    predicate = condition.get("predicate")
    if predicate not in ALLOWED_MATCH_PREDICATES:
        raise ValueError("unsupported predicate")

    label_norm = (transaction.label_norm or "").lower()
    supplier_raw = (transaction.supplier_raw or "").lower()

    if predicate == "label_contains":
        token = _normalize_text(str(condition.get("value", "")))
        return token in _normalize_text(label_norm)

    if predicate == "label_regex":
        pattern = str(condition.get("value", ""))
        return re.search(pattern, label_norm, flags=re.IGNORECASE) is not None

    if predicate == "supplier_contains":
        token = _normalize_text(str(condition.get("value", "")))
        return token in _normalize_text(supplier_raw)

    if predicate == "amount_between":
        minimum = condition.get("min")
        maximum = condition.get("max")
        amount = transaction.amount
        if minimum is not None and amount < _parse_decimal(minimum):
            return False
        if maximum is not None and amount > _parse_decimal(maximum):
            return False
        return True

    if predicate == "amount_equals":
        return transaction.amount == _parse_decimal(condition.get("value"))

    if predicate == "type_is":
        return transaction.type.value == str(condition.get("value"))

    if predicate == "posted_at_between":
        from_raw = condition.get("from")
        to_raw = condition.get("to")
        if from_raw:
            from_date = date.fromisoformat(str(from_raw))
            if transaction.posted_at < from_date:
                return False
        if to_raw:
            to_date = date.fromisoformat(str(to_raw))
            if transaction.posted_at > to_date:
                return False
        return True

    if predicate == "day_of_month_is":
        return transaction.posted_at.day == int(condition.get("value"))

    if predicate == "account_id_is":
        return transaction.account_id == int(condition.get("value"))

    return False


def _replace_transaction_splits(db: Session, transaction: Transaction, split_payloads: list[dict[str, Any]]) -> None:
    for split in list(transaction.splits):
        db.delete(split)
    db.flush()
    transaction.splits = []

    for index, payload in enumerate(split_payloads):
        transaction.splits.append(
            Split(
                transaction_id=transaction.id,
                amount=payload["amount"],
                category_id=payload["category_id"],
                moment_id=payload.get("moment_id"),
                internal_account_id=payload.get("internal_account_id"),
                note=payload.get("note"),
                position=index,
            )
        )
    db.flush()


def _normalize_split_payloads_from_transaction(transaction: Transaction) -> list[dict[str, Any]]:
    rows = []
    for split in sorted(transaction.splits, key=lambda row: (row.position, row.id)):
        rows.append(
            {
                "amount": split.amount,
                "category_id": split.category_id,
                "moment_id": split.moment_id,
                "internal_account_id": split.internal_account_id,
                "note": split.note,
            }
        )
    return rows


def _simulated_after_snapshot(
    transaction: Transaction,
    *,
    field_updates: dict[str, Any],
    split_payloads: Any,
) -> dict[str, Any]:
    payee_id = field_updates.get("payee_id", transaction.payee_id)
    tx_type = field_updates.get("type", transaction.type.value)

    if split_payloads is _MISSING:
        split_rows = _transaction_snapshot(transaction)["splits"]
    else:
        split_rows = [_snapshot_split_dict(None, row, idx) for idx, row in enumerate(split_payloads)]

    return {
        "transaction_id": transaction.id,
        "payee_id": payee_id,
        "type": tx_type,
        "amount": _serialize_amount(transaction.amount),
        "splits": split_rows,
    }


def _transaction_snapshot(transaction: Transaction) -> dict[str, Any]:
    return {
        "transaction_id": transaction.id,
        "payee_id": transaction.payee_id,
        "type": transaction.type.value,
        "amount": _serialize_amount(transaction.amount),
        "splits": [
            _snapshot_split(split)
            for split in sorted(transaction.splits, key=lambda row: (row.position, row.id))
        ],
    }


def _snapshot_split(split: Split) -> dict[str, Any]:
    return {
        "id": split.id,
        "amount": _serialize_amount(split.amount),
        "category_id": split.category_id,
        "moment_id": split.moment_id,
        "internal_account_id": split.internal_account_id,
        "note": split.note,
        "position": split.position,
    }


def _snapshot_split_dict(split_id: int | None, payload: dict[str, Any], position: int | None = None) -> dict[str, Any]:
    return {
        "id": split_id,
        "amount": _serialize_amount(payload["amount"]),
        "category_id": payload.get("category_id"),
        "moment_id": payload.get("moment_id"),
        "internal_account_id": payload.get("internal_account_id"),
        "note": payload.get("note"),
        "position": 0 if position is None else position,
    }


def _serialize_amount(value: Decimal | str | int | float) -> str:
    decimal_value = parse_decimal_2(value)
    return f"{decimal_value:.2f}"


def _compute_split_operations(
    before_splits: list[dict[str, Any]],
    after_splits: list[dict[str, Any]],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    max_length = max(len(before_splits), len(after_splits))
    operations: list[dict[str, Any]] = []

    for idx in range(max_length):
        before = before_splits[idx] if idx < len(before_splits) else None
        after = after_splits[idx] if idx < len(after_splits) else None
        if before is not None and after is not None:
            if _comparable_split(before) == _comparable_split(after):
                continue
            operations.append(
                {
                    "operation": "replace",
                    "split_id": after.get("id") if mode == "apply" else None,
                    "before_json": before,
                    "after_json": after,
                }
            )
        elif before is not None:
            operations.append(
                {
                    "operation": "delete",
                    "split_id": before.get("id") if mode == "apply" else None,
                    "before_json": before,
                    "after_json": None,
                }
            )
        elif after is not None:
            operations.append(
                {
                    "operation": "create",
                    "split_id": after.get("id") if mode == "apply" else None,
                    "before_json": None,
                    "after_json": after,
                }
            )

    return operations


def _comparable_split(split: dict[str, Any]) -> dict[str, Any]:
    return {
        "amount": split.get("amount"),
        "category_id": split.get("category_id"),
        "moment_id": split.get("moment_id"),
        "internal_account_id": split.get("internal_account_id"),
        "note": split.get("note"),
        "position": split.get("position"),
    }


def _compare_split_payloads(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> bool:
    if len(left) != len(right):
        return False

    for idx, row in enumerate(left):
        other = right[idx]
        if _serialize_amount(row["amount"]) != _serialize_amount(other["amount"]):
            return False
        if row.get("category_id") != other.get("category_id"):
            return False
        if row.get("moment_id") != other.get("moment_id"):
            return False
        if row.get("internal_account_id") != other.get("internal_account_id"):
            return False
        if (row.get("note") or None) != (other.get("note") or None):
            return False
    return True


def _load_transactions_for_scope(db: Session, scope: RuleExecutionScope) -> list[Transaction]:
    query = db.query(Transaction).options(joinedload(Transaction.splits))

    if scope.type == "all":
        pass
    elif scope.type == "date_range":
        if scope.date_from:
            query = query.filter(Transaction.posted_at >= scope.date_from)
        if scope.date_to:
            query = query.filter(Transaction.posted_at <= scope.date_to)
    elif scope.type == "import":
        if not scope.import_id:
            raise ValueError("import_id is required for import scope")
        tx_ids_query = (
            db.query(ImportRowLink.transaction_id)
            .join(ImportRow, ImportRow.id == ImportRowLink.import_row_id)
            .filter(ImportRow.import_id == scope.import_id)
        )
        if scope.created_only:
            tx_ids_query = tx_ids_query.filter(ImportRow.status == ImportRowStatus.created)
        tx_ids = sorted({row[0] for row in tx_ids_query.all()})
        if not tx_ids:
            return []
        query = query.filter(Transaction.id.in_(tx_ids))
    elif scope.type == "transaction_ids":
        if not scope.transaction_ids:
            return []
        query = query.filter(Transaction.id.in_(scope.transaction_ids))
    else:
        raise ValueError("unsupported scope type")

    return query.order_by(Transaction.id.asc()).all()


def _load_dependency_cache(db: Session) -> dict[str, set[int]]:
    category_ids = {row[0] for row in db.query(Category.id).all()}
    moment_ids = {row[0] for row in db.query(Moment.id).all()}
    internal_account_ids = {
        row[0]
        for row in db.query(Counterparty.id).filter(Counterparty.kind == CounterpartyKind.internal).all()
    }
    return {
        "category_ids": category_ids,
        "moment_ids": moment_ids,
        "internal_account_ids": internal_account_ids,
    }


def _latest_rule_effects_by_transaction(db: Session, *, rule_id: int) -> dict[int, RuleRunEffect]:
    rows = (
        db.query(RuleRunEffect)
        .filter(RuleRunEffect.rule_id == rule_id, RuleRunEffect.status == RULE_STATUS_APPLIED)
        .order_by(RuleRunEffect.transaction_id.asc(), RuleRunEffect.id.desc())
        .all()
    )
    result: dict[int, RuleRunEffect] = {}
    for row in rows:
        if row.transaction_id not in result:
            result[row.transaction_id] = row
    return result


def _snapshot_matches_effect_after(transaction: Transaction, effect: RuleRunEffect) -> bool:
    if not effect.after_json:
        return False
    current = _transaction_snapshot(transaction)
    expected = effect.after_json
    return _comparable_snapshot(current) == _comparable_snapshot(expected)


def _comparable_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "transaction_id": snapshot.get("transaction_id"),
        "payee_id": snapshot.get("payee_id"),
        "type": snapshot.get("type"),
        "amount": snapshot.get("amount"),
        "splits": [_comparable_split(split) for split in snapshot.get("splits", [])],
    }


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    return re.sub(r"\s+", " ", normalized)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
