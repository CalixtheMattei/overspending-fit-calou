from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import Date, case, func, literal, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Category, Counterparty, CounterpartyKind, Split, Transaction, TransactionType

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _allowed_types(exclude_transfers: bool) -> list[TransactionType]:
    base = [TransactionType.expense, TransactionType.income, TransactionType.refund, TransactionType.transfer]
    if exclude_transfers:
        return [tx_type for tx_type in base if tx_type != TransactionType.transfer]
    return base


def _to_float(value: Decimal | None) -> float:
    return float(value or Decimal("0.00"))


def _sum_components(values: list[Decimal]) -> tuple[float, float, float, float]:
    income = Decimal("0.00")
    expense = Decimal("0.00")
    net = Decimal("0.00")
    absolute_total = Decimal("0.00")
    for value in values:
        net += value
        absolute_total += abs(value)
        if value >= 0:
            income += value
        else:
            expense += abs(value)
    return _to_float(income), _to_float(expense), _to_float(net), _to_float(absolute_total)


def _bucket_expression(granularity: Literal["day", "week", "month"]):
    return func.date_trunc(granularity, Transaction.posted_at).cast(Date)


@router.get("/flow")
def get_flow(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    exclude_transfers: bool = Query(True),
    exclude_moment_tagged: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    allowed_types = _allowed_types(exclude_transfers)

    split_query = (
        db.query(
            Transaction.type.label("tx_type"),
            Split.category_id.label("category_id"),
            func.sum(func.abs(Split.amount)).label("total"),
        )
        .join(Split, Split.transaction_id == Transaction.id)
        .filter(Transaction.type.in_(allowed_types))
    )

    no_split_query = (
        db.query(
            Transaction.type.label("tx_type"),
            func.sum(func.abs(Transaction.amount)).label("total"),
        )
        .outerjoin(Split, Split.transaction_id == Transaction.id)
        .filter(Split.id.is_(None))
        .filter(Transaction.type.in_(allowed_types))
    )

    if exclude_moment_tagged:
        split_query = split_query.filter(Split.moment_id.is_(None))

    if start_date:
        split_query = split_query.filter(Transaction.posted_at >= start_date)
        no_split_query = no_split_query.filter(Transaction.posted_at >= start_date)
    if end_date:
        split_query = split_query.filter(Transaction.posted_at <= end_date)
        no_split_query = no_split_query.filter(Transaction.posted_at <= end_date)

    split_rows = split_query.group_by(Transaction.type, Split.category_id).all()
    no_split_rows = no_split_query.group_by(Transaction.type).all()

    totals_by_pair: dict[tuple[str, int | None], Decimal] = {}
    for row in split_rows:
        tx_type = row.tx_type.value if isinstance(row.tx_type, TransactionType) else str(row.tx_type)
        key = (tx_type, row.category_id)
        totals_by_pair[key] = totals_by_pair.get(key, Decimal("0.00")) + (row.total or Decimal("0.00"))
    for row in no_split_rows:
        tx_type = row.tx_type.value if isinstance(row.tx_type, TransactionType) else str(row.tx_type)
        key = (tx_type, None)
        totals_by_pair[key] = totals_by_pair.get(key, Decimal("0.00")) + (row.total or Decimal("0.00"))

    category_ids = {category_id for (_, category_id), _ in totals_by_pair.items() if category_id is not None}
    categories = (
        db.query(Category.id, Category.name)
        .filter(Category.id.in_(category_ids))
        .order_by(Category.name.asc())
        .all()
        if category_ids
        else []
    )
    category_map = {row.id: row.name for row in categories}

    type_labels = {
        TransactionType.expense.value: "Expenses",
        TransactionType.income.value: "Income",
        TransactionType.refund.value: "Refunds",
        TransactionType.transfer.value: "Transfers",
    }

    nodes: list[dict[str, object]] = []
    for tx_type in allowed_types:
        nodes.append(
            {
                "id": tx_type.value,
                "name": type_labels[tx_type.value],
                "label": type_labels[tx_type.value],
                "type": "source",
                "kind": "transaction_type",
                "transaction_type": tx_type.value,
            }
        )

    category_node_ids: set[str] = set()
    for _, category_id in totals_by_pair:
        if category_id is None:
            category_node_ids.add("uncategorized")
        else:
            category_node_ids.add(f"cat_{category_id}")

    for node_id in sorted(category_node_ids):
        if node_id == "uncategorized":
            name = "Uncategorized"
            node: dict[str, object] = {
                "id": node_id,
                "name": name,
                "label": name,
                "type": "expense",
                "kind": "category_bucket",
            }
        else:
            raw_id = int(node_id.replace("cat_", ""))
            name = category_map.get(raw_id, "Category")
            node = {
                "id": node_id,
                "name": name,
                "label": name,
                "type": "expense",
                "kind": "category_bucket",
                "category_id": raw_id,
            }
        nodes.append(node)

    links = []
    totals = {"income": 0.0, "expenses": 0.0, "refunds": 0.0, "transfers": 0.0}
    for (source, category_id), total in totals_by_pair.items():
        target = "uncategorized" if category_id is None else f"cat_{category_id}"
        value = _to_float(total)
        if value <= 0:
            continue
        links.append({"source": source, "target": target, "value": value})
        if source == TransactionType.income.value:
            totals["income"] += value
        elif source == TransactionType.expense.value:
            totals["expenses"] += value
        elif source == TransactionType.refund.value:
            totals["refunds"] += value
        elif source == TransactionType.transfer.value:
            totals["transfers"] += value

    return jsonable_encoder({"nodes": nodes, "links": links, "totals": totals})


@router.get("/payees")
def get_payee_analytics(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: Literal["day", "week", "month"] = Query("month"),
    exclude_transfers: bool = Query(True),
    exclude_moment_tagged: bool = Query(False),
    mode: Literal["user", "counterparty"] = Query("user"),
    limit: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    allowed_types = _allowed_types(exclude_transfers)
    bucket = _bucket_expression(granularity)

    query = (
        db.query(
            Transaction.payee_id.label("entity_id"),
            Counterparty.name.label("entity_name"),
            bucket.label("bucket"),
            func.sum(Split.amount).label("amount"),
        )
        .join(Split, Split.transaction_id == Transaction.id)
        .outerjoin(Counterparty, Counterparty.id == Transaction.payee_id)
        .filter(Transaction.type.in_(allowed_types))
        .filter(
            (Counterparty.id.is_(None))
            | (Counterparty.kind.in_([CounterpartyKind.person, CounterpartyKind.merchant, CounterpartyKind.unknown]))
        )
    )
    if exclude_moment_tagged:
        query = query.filter(Split.moment_id.is_(None))
    if start_date:
        query = query.filter(Transaction.posted_at >= start_date)
    if end_date:
        query = query.filter(Transaction.posted_at <= end_date)

    rows = query.group_by(Transaction.payee_id, Counterparty.name, bucket).all()
    multiplier = Decimal("-1.00") if mode == "counterparty" else Decimal("1.00")
    return _build_grouped_timeseries_response(rows, multiplier, limit, unassigned_label="Unassigned payee")


@router.get("/internal-accounts")
def get_internal_account_analytics(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    granularity: Literal["day", "week", "month"] = Query("month"),
    exclude_transfers: bool = Query(True),
    exclude_moment_tagged: bool = Query(False),
    mode: Literal["user", "counterparty"] = Query("user"),
    limit: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    allowed_types = _allowed_types(exclude_transfers)
    bucket = _bucket_expression(granularity)

    query = (
        db.query(
            Split.internal_account_id.label("entity_id"),
            Counterparty.name.label("entity_name"),
            bucket.label("bucket"),
            func.sum(Split.amount).label("amount"),
        )
        .join(Split, Split.transaction_id == Transaction.id)
        .outerjoin(Counterparty, Counterparty.id == Split.internal_account_id)
        .filter(Transaction.type.in_(allowed_types))
        .filter((Counterparty.id.is_(None)) | (Counterparty.kind == CounterpartyKind.internal))
    )
    if exclude_moment_tagged:
        query = query.filter(Split.moment_id.is_(None))
    if start_date:
        query = query.filter(Transaction.posted_at >= start_date)
    if end_date:
        query = query.filter(Transaction.posted_at <= end_date)

    rows = query.group_by(Split.internal_account_id, Counterparty.name, bucket).all()
    multiplier = Decimal("-1.00") if mode == "counterparty" else Decimal("1.00")
    return _build_grouped_timeseries_response(rows, multiplier, limit, unassigned_label="Unassigned")


def _build_grouped_timeseries_response(
    rows: list,
    multiplier: Decimal,
    limit: int,
    unassigned_label: str,
) -> dict[str, object]:
    entity_bucket_values: dict[tuple[int | None, str], dict[str, Decimal]] = {}
    overall_bucket_values: dict[str, Decimal] = {}

    for row in rows:
        entity_id = row.entity_id
        entity_name = row.entity_name or unassigned_label
        entity_key = (entity_id, entity_name)
        bucket_date = row.bucket
        bucket_key = bucket_date.isoformat() if isinstance(bucket_date, date) else str(bucket_date)

        value = (row.amount or Decimal("0.00")) * multiplier
        entity_bucket_values.setdefault(entity_key, {})
        entity_bucket_values[entity_key][bucket_key] = (
            entity_bucket_values[entity_key].get(bucket_key, Decimal("0.00")) + value
        )
        overall_bucket_values[bucket_key] = overall_bucket_values.get(bucket_key, Decimal("0.00")) + value

    entities = []
    for (entity_id, entity_name), bucket_values in entity_bucket_values.items():
        values = list(bucket_values.values())
        income, expense, net, absolute_total = _sum_components(values)
        series = []
        for bucket_key in sorted(bucket_values.keys()):
            bucket_net = bucket_values[bucket_key]
            series.append(
                {
                    "bucket": bucket_key,
                    "income": _to_float(bucket_net if bucket_net > 0 else Decimal("0.00")),
                    "expense": _to_float(abs(bucket_net) if bucket_net < 0 else Decimal("0.00")),
                    "net": _to_float(bucket_net),
                }
            )
        entities.append(
            {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "income": income,
                "expense": expense,
                "net": net,
                "absolute_total": absolute_total,
                "series": series,
            }
        )

    entities.sort(key=lambda entity: entity["absolute_total"], reverse=True)
    top_entities = entities[:limit]

    total_income, total_expense, total_net, _ = _sum_components(list(overall_bucket_values.values()))
    total_series = []
    for bucket_key in sorted(overall_bucket_values.keys()):
        bucket_net = overall_bucket_values[bucket_key]
        total_series.append(
            {
                "bucket": bucket_key,
                "income": _to_float(bucket_net if bucket_net > 0 else Decimal("0.00")),
                "expense": _to_float(abs(bucket_net) if bucket_net < 0 else Decimal("0.00")),
                "net": _to_float(bucket_net),
            }
        )

    return jsonable_encoder(
        {
            "rows": top_entities,
            "total_rows": len(entities),
            "totals": {
                "income": total_income,
                "expense": total_expense,
                "net": total_net,
            },
            "series_totals": total_series,
        }
    )


# ---------------------------------------------------------------------------
# Category drilldown helpers
# ---------------------------------------------------------------------------


def _resolve_category_scope(
    category_ref: str,
    include_children: bool,
    db: Session,
) -> tuple[dict, list[int | None]]:
    """Return (category_info_dict, list_of_category_ids_in_scope).

    category_ids list contains ``None`` when uncategorized splits are in scope.
    """
    if category_ref == "uncategorized":
        info = {"id": None, "name": "Uncategorized", "scope_type": "uncategorized"}
        return info, [None]

    try:
        cat_id = int(category_ref)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Category not found")

    category = db.query(Category).filter(Category.id == cat_id).first()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.parent_id is not None:
        # child category – ignore include_children
        info = {
            "id": category.id,
            "name": category.name,
            "parent_id": category.parent_id,
            "scope_type": "child",
        }
        return info, [category.id]

    # parent category
    scope_ids: list[int | None] = [category.id]
    if include_children:
        children = db.query(Category.id).filter(Category.parent_id == category.id).all()
        scope_ids.extend(row.id for row in children)

    info = {
        "id": category.id,
        "name": category.name,
        "parent_id": None,
        "scope_type": "parent",
    }
    return info, scope_ids


def _scope_filter(scope_ids: list[int | None]):
    """Build a SQLAlchemy filter expression for Split.category_id matching scope."""
    non_null_ids = [cid for cid in scope_ids if cid is not None]
    has_null = None in scope_ids

    if has_null and non_null_ids:
        return or_(Split.category_id.in_(non_null_ids), Split.category_id.is_(None))
    elif has_null:
        return Split.category_id.is_(None)
    else:
        return Split.category_id.in_(non_null_ids)


def _apply_common_filters(query, start_date, end_date, allowed_types, exclude_moment_tagged):
    """Apply date, type, and moment filters to a query that already joins Transaction."""
    query = query.filter(Transaction.type.in_(allowed_types))
    if exclude_moment_tagged:
        query = query.filter(Split.moment_id.is_(None))
    if start_date:
        query = query.filter(Transaction.posted_at >= start_date)
    if end_date:
        query = query.filter(Transaction.posted_at <= end_date)
    return query


# ---------------------------------------------------------------------------
# GET /analytics/category/{category_ref}  –  branch aggregate
# ---------------------------------------------------------------------------


@router.get("/category/{category_ref}")
def get_category_drilldown(
    category_ref: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    exclude_transfers: bool = Query(True),
    exclude_moment_tagged: bool = Query(False),
    include_children: bool = Query(True),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    category_info, scope_ids = _resolve_category_scope(category_ref, include_children, db)
    allowed_types = _allowed_types(exclude_transfers)
    is_uncategorized = category_ref == "uncategorized"

    # ---- aggregate from splits matching scope ----
    split_query = (
        db.query(
            Transaction.type.label("tx_type"),
            Split.category_id.label("category_id"),
            func.sum(Split.amount).label("total_signed"),
            func.sum(func.abs(Split.amount)).label("total_abs"),
            func.count(func.distinct(Transaction.id)).label("tx_count"),
        )
        .join(Split, Split.transaction_id == Transaction.id)
        .filter(_scope_filter(scope_ids))
    )
    split_query = _apply_common_filters(split_query, start_date, end_date, allowed_types, exclude_moment_tagged)
    split_rows = split_query.group_by(Transaction.type, Split.category_id).all()

    # ---- for uncategorized, also include zero-split transactions ----
    no_split_rows = []
    if is_uncategorized:
        no_split_query = (
            db.query(
                Transaction.type.label("tx_type"),
                func.sum(Transaction.amount).label("total_signed"),
                func.sum(func.abs(Transaction.amount)).label("total_abs"),
                func.count(Transaction.id).label("tx_count"),
            )
            .outerjoin(Split, Split.transaction_id == Transaction.id)
            .filter(Split.id.is_(None))
            .filter(Transaction.type.in_(allowed_types))
        )
        if start_date:
            no_split_query = no_split_query.filter(Transaction.posted_at >= start_date)
        if end_date:
            no_split_query = no_split_query.filter(Transaction.posted_at <= end_date)
        no_split_rows = no_split_query.group_by(Transaction.type).all()

    # ---- compute totals ----
    income_abs = Decimal("0.00")
    expense_abs = Decimal("0.00")
    refund_abs = Decimal("0.00")
    transfer_abs = Decimal("0.00")
    net = Decimal("0.00")
    transaction_ids: set[int] = set()

    # We need unique transaction count; the group_by query gives per-type counts
    # but a transaction could appear in multiple groups if it has splits in multiple
    # scope categories.  Use a separate count query.

    totals_by_pair: dict[tuple[str, int | None], Decimal] = {}

    for row in split_rows:
        tx_type = row.tx_type.value if isinstance(row.tx_type, TransactionType) else str(row.tx_type)
        signed = row.total_signed or Decimal("0.00")
        abs_val = row.total_abs or Decimal("0.00")
        net += signed

        if tx_type == "income":
            income_abs += abs_val
        elif tx_type == "expense":
            expense_abs += abs_val
        elif tx_type == "refund":
            refund_abs += abs_val
        elif tx_type == "transfer":
            transfer_abs += abs_val

        key = (tx_type, row.category_id)
        totals_by_pair[key] = totals_by_pair.get(key, Decimal("0.00")) + abs_val

    for row in no_split_rows:
        tx_type = row.tx_type.value if isinstance(row.tx_type, TransactionType) else str(row.tx_type)
        signed = row.total_signed or Decimal("0.00")
        abs_val = row.total_abs or Decimal("0.00")
        net += signed

        if tx_type == "income":
            income_abs += abs_val
        elif tx_type == "expense":
            expense_abs += abs_val
        elif tx_type == "refund":
            refund_abs += abs_val
        elif tx_type == "transfer":
            transfer_abs += abs_val

        key = (tx_type, None)
        totals_by_pair[key] = totals_by_pair.get(key, Decimal("0.00")) + abs_val

    absolute_total = income_abs + expense_abs + refund_abs + transfer_abs

    # ---- transaction count (distinct) ----
    count_query = (
        db.query(func.count(func.distinct(Transaction.id)))
        .join(Split, Split.transaction_id == Transaction.id)
        .filter(_scope_filter(scope_ids))
    )
    count_query = _apply_common_filters(count_query, start_date, end_date, allowed_types, exclude_moment_tagged)
    transaction_count = count_query.scalar() or 0

    if is_uncategorized:
        no_split_count_query = (
            db.query(func.count(Transaction.id))
            .outerjoin(Split, Split.transaction_id == Transaction.id)
            .filter(Split.id.is_(None))
            .filter(Transaction.type.in_(allowed_types))
        )
        if start_date:
            no_split_count_query = no_split_count_query.filter(Transaction.posted_at >= start_date)
        if end_date:
            no_split_count_query = no_split_count_query.filter(Transaction.posted_at <= end_date)
        transaction_count += no_split_count_query.scalar() or 0

    # ---- build branch nodes/links (sankey sub-graph) ----
    type_labels = {
        TransactionType.expense.value: "Expenses",
        TransactionType.income.value: "Income",
        TransactionType.refund.value: "Refunds",
        TransactionType.transfer.value: "Transfers",
    }

    nodes: list[dict[str, object]] = []
    links: list[dict[str, object]] = []

    # source nodes (transaction types that have data)
    active_types = {tx_type for (tx_type, _) in totals_by_pair}
    for tx_type in allowed_types:
        if tx_type.value in active_types:
            nodes.append(
                {
                    "id": tx_type.value,
                    "name": type_labels[tx_type.value],
                    "label": type_labels[tx_type.value],
                    "type": "source",
                    "kind": "transaction_type",
                    "transaction_type": tx_type.value,
                }
            )

    # target nodes (categories in scope)
    category_ids_in_data = {cat_id for (_, cat_id) in totals_by_pair}
    cat_map: dict[int, str] = {}
    non_null_cat_ids = [cid for cid in category_ids_in_data if cid is not None]
    if non_null_cat_ids:
        cats = db.query(Category.id, Category.name).filter(Category.id.in_(non_null_cat_ids)).all()
        cat_map = {c.id: c.name for c in cats}

    for cat_id in sorted(category_ids_in_data, key=lambda x: (x is None, x)):
        if cat_id is None:
            nodes.append(
                {
                    "id": "uncategorized",
                    "name": "Uncategorized",
                    "label": "Uncategorized",
                    "type": "expense",
                    "kind": "category_bucket",
                }
            )
        else:
            nodes.append(
                {
                    "id": f"cat_{cat_id}",
                    "name": cat_map.get(cat_id, "Category"),
                    "label": cat_map.get(cat_id, "Category"),
                    "type": "expense",
                    "kind": "category_bucket",
                    "category_id": cat_id,
                }
            )

    for (tx_type, cat_id), total in totals_by_pair.items():
        target = "uncategorized" if cat_id is None else f"cat_{cat_id}"
        value = _to_float(total)
        if value <= 0:
            continue
        links.append({"source": tx_type, "target": target, "value": value})

    return jsonable_encoder(
        {
            "category": category_info,
            "scope_category_ids": [cid for cid in scope_ids if cid is not None] if not is_uncategorized else [],
            "totals": {
                "income_abs": _to_float(income_abs),
                "expense_abs": _to_float(expense_abs),
                "refund_abs": _to_float(refund_abs),
                "transfer_abs": _to_float(transfer_abs),
                "net": _to_float(net),
                "absolute_total": _to_float(absolute_total),
            },
            "transaction_count": transaction_count,
            "branch_nodes": nodes,
            "branch_links": links,
        }
    )


# ---------------------------------------------------------------------------
# GET /analytics/category/{category_ref}/transactions
# ---------------------------------------------------------------------------


@router.get("/category/{category_ref}/transactions")
def get_category_drilldown_transactions(
    category_ref: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    exclude_transfers: bool = Query(True),
    exclude_moment_tagged: bool = Query(False),
    include_children: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    category_info, scope_ids = _resolve_category_scope(category_ref, include_children, db)
    allowed_types = _allowed_types(exclude_transfers)
    is_uncategorized = category_ref == "uncategorized"

    # ---- Build base query for transactions with matching splits ----
    split_base = (
        db.query(
            Transaction.id.label("transaction_id"),
            Transaction.posted_at.label("posted_at"),
            Transaction.label_raw.label("label_raw"),
            Transaction.type.label("type"),
            Counterparty.name.label("payee"),
            Account.label.label("account"),
            Transaction.amount.label("transaction_amount"),
            func.sum(func.abs(Split.amount)).label("branch_amount_abs"),
            func.count(Split.id).label("matched_split_count"),
        )
        .join(Split, Split.transaction_id == Transaction.id)
        .outerjoin(Counterparty, Counterparty.id == Transaction.payee_id)
        .join(Account, Account.id == Transaction.account_id)
        .filter(_scope_filter(scope_ids))
    )
    split_base = _apply_common_filters(split_base, start_date, end_date, allowed_types, exclude_moment_tagged)
    split_base = split_base.group_by(
        Transaction.id,
        Transaction.posted_at,
        Transaction.label_raw,
        Transaction.type,
        Counterparty.name,
        Account.label,
        Transaction.amount,
    )

    if is_uncategorized:
        # Also include zero-split transactions
        no_split_base = (
            db.query(
                Transaction.id.label("transaction_id"),
                Transaction.posted_at.label("posted_at"),
                Transaction.label_raw.label("label_raw"),
                Transaction.type.label("type"),
                Counterparty.name.label("payee"),
                Account.label.label("account"),
                Transaction.amount.label("transaction_amount"),
                func.abs(Transaction.amount).label("branch_amount_abs"),
                literal(0).label("matched_split_count"),
            )
            .outerjoin(Split, Split.transaction_id == Transaction.id)
            .outerjoin(Counterparty, Counterparty.id == Transaction.payee_id)
            .join(Account, Account.id == Transaction.account_id)
            .filter(Split.id.is_(None))
            .filter(Transaction.type.in_(allowed_types))
        )
        if start_date:
            no_split_base = no_split_base.filter(Transaction.posted_at >= start_date)
        if end_date:
            no_split_base = no_split_base.filter(Transaction.posted_at <= end_date)

        combined = split_base.union_all(no_split_base).subquery()
    else:
        combined = split_base.subquery()

    # ---- total count ----
    total = db.query(func.count()).select_from(combined).scalar() or 0

    # ---- paginated rows ----
    rows = (
        db.query(combined)
        .order_by(combined.c.posted_at.desc(), combined.c.transaction_id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    result_rows = []
    for row in rows:
        tx_type = row.type
        if isinstance(tx_type, TransactionType):
            tx_type = tx_type.value
        result_rows.append(
            {
                "transaction_id": row.transaction_id,
                "posted_at": row.posted_at.isoformat() if hasattr(row.posted_at, "isoformat") else str(row.posted_at),
                "label_raw": row.label_raw,
                "type": tx_type,
                "payee": row.payee,
                "account": row.account,
                "transaction_amount": _to_float(row.transaction_amount),
                "branch_amount_abs": _to_float(row.branch_amount_abs),
                "matched_split_count": row.matched_split_count,
            }
        )

    return jsonable_encoder(
        {
            "rows": result_rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )
