from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from ..models import MomentCandidate, Split, Transaction

CANDIDATE_STATUS_PENDING = "pending"
CANDIDATE_STATUS_ACCEPTED = "accepted"
CANDIDATE_STATUS_REJECTED = "rejected"
ALLOWED_CANDIDATE_STATUSES = {
    CANDIDATE_STATUS_PENDING,
    CANDIDATE_STATUS_ACCEPTED,
    CANDIDATE_STATUS_REJECTED,
}
ALLOWED_CANDIDATE_DECISIONS = {
    CANDIDATE_STATUS_ACCEPTED,
    CANDIDATE_STATUS_REJECTED,
}

MOMENT_CANDIDATES = MomentCandidate.__table__


class CandidateConflictError(Exception):
    def __init__(self, split_ids: list[int], source_moment_ids: list[int]) -> None:
        self.split_ids = split_ids
        self.source_moment_ids = source_moment_ids
        super().__init__("candidate reassignment requires confirmation")


class CandidateEligibilityError(Exception):
    def __init__(self, split_ids: list[int]) -> None:
        self.split_ids = split_ids
        super().__init__("split is not an eligible candidate")


class TaggedSplitOwnershipError(Exception):
    def __init__(self, split_ids: list[int], moment_id: int) -> None:
        self.split_ids = split_ids
        self.moment_id = moment_id
        super().__init__("split is not tagged to source moment")


def refresh_candidates_for_moment(
    db: Session,
    *,
    moment_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, object]:
    now = _utcnow()
    _sync_candidate_invariants(db, moment_id=moment_id, now=now)

    eligible_split_ids = _eligible_split_ids(
        db,
        start_date=start_date,
        end_date=end_date,
    )

    inserted_count = 0
    touched_count = 0
    if eligible_split_ids:
        existing_before = int(
            db.execute(
                select(func.count())
                .select_from(MOMENT_CANDIDATES)
                .where(
                    MOMENT_CANDIDATES.c.moment_id == moment_id,
                    MOMENT_CANDIDATES.c.split_id.in_(eligible_split_ids),
                )
            ).scalar_one()
        )
        _insert_pending_candidates(
            db,
            moment_id=moment_id,
            split_ids=eligible_split_ids,
            now=now,
        )
        existing_after = int(
            db.execute(
                select(func.count())
                .select_from(MOMENT_CANDIDATES)
                .where(
                    MOMENT_CANDIDATES.c.moment_id == moment_id,
                    MOMENT_CANDIDATES.c.split_id.in_(eligible_split_ids),
                )
            ).scalar_one()
        )
        inserted_count = max(existing_after - existing_before, 0)
        db.execute(
            update(MOMENT_CANDIDATES)
            .where(
                MOMENT_CANDIDATES.c.moment_id == moment_id,
                MOMENT_CANDIDATES.c.split_id.in_(eligible_split_ids),
            )
            .values(last_seen_at=now)
        )
        touched_count = max(len(eligible_split_ids) - inserted_count, 0)

    status_counts = candidate_status_counts(
        db,
        moment_id=moment_id,
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "inserted_count": inserted_count,
        "touched_count": touched_count,
        "status_counts": status_counts,
    }


def list_candidates(
    db: Session,
    *,
    moment_id: int,
    start_date: date,
    end_date: date,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    conditions = [
        MOMENT_CANDIDATES.c.moment_id == moment_id,
        _candidate_visibility_clause(
            moment_id=moment_id,
            start_date=start_date,
            end_date=end_date,
            status=status,
        ),
    ]

    base_query = (
        select(
            MOMENT_CANDIDATES.c.id.label("candidate_id"),
            MOMENT_CANDIDATES.c.moment_id.label("candidate_moment_id"),
            MOMENT_CANDIDATES.c.split_id.label("candidate_split_id"),
            MOMENT_CANDIDATES.c.status.label("candidate_status"),
            MOMENT_CANDIDATES.c.first_seen_at.label("candidate_first_seen_at"),
            MOMENT_CANDIDATES.c.last_seen_at.label("candidate_last_seen_at"),
            MOMENT_CANDIDATES.c.decided_at.label("candidate_decided_at"),
            Split.id.label("split_id"),
            Split.transaction_id.label("split_transaction_id"),
            Split.amount.label("split_amount"),
            Split.category_id.label("split_category_id"),
            Split.moment_id.label("split_moment_id"),
            Split.internal_account_id.label("split_internal_account_id"),
            Split.note.label("split_note"),
            Split.position.label("split_position"),
            Transaction.operation_at.label("tx_operation_at"),
            Transaction.posted_at.label("tx_posted_at"),
            Transaction.label_raw.label("tx_label_raw"),
            Transaction.supplier_raw.label("tx_supplier_raw"),
            Transaction.currency.label("tx_currency"),
        )
        .select_from(MOMENT_CANDIDATES)
        .join(Split, Split.id == MOMENT_CANDIDATES.c.split_id)
        .join(Transaction, Transaction.id == Split.transaction_id)
        .where(and_(*conditions))
    )

    total = int(
        db.execute(
            select(func.count())
            .select_from(MOMENT_CANDIDATES)
            .join(Split, Split.id == MOMENT_CANDIDATES.c.split_id)
            .join(Transaction, Transaction.id == Split.transaction_id)
            .where(and_(*conditions))
        ).scalar_one()
    )

    rows = (
        db.execute(
            base_query.order_by(Transaction.operation_at.desc(), MOMENT_CANDIDATES.c.id.desc())
            .offset(offset)
            .limit(limit)
        ).mappings()
    )
    return [dict(row) for row in rows], total


def decide_candidates(
    db: Session,
    *,
    moment_id: int,
    split_ids: list[int],
    decision: str,
    confirm_reassign: bool,
) -> dict[str, object]:
    unique_split_ids = _dedupe_ids(split_ids)
    if not unique_split_ids:
        return {"updated_count": 0, "reassigned_count": 0}

    now = _utcnow()
    _sync_candidate_invariants(db, moment_id=moment_id, now=now)

    rows = list(
        db.execute(
            select(
                MOMENT_CANDIDATES.c.id.label("candidate_id"),
                MOMENT_CANDIDATES.c.split_id.label("split_id"),
                Split.moment_id.label("split_moment_id"),
            )
            .select_from(Split)
            .join(
                MOMENT_CANDIDATES,
                and_(
                    MOMENT_CANDIDATES.c.split_id == Split.id,
                    MOMENT_CANDIDATES.c.moment_id == moment_id,
                ),
            )
            .where(
                Split.id.in_(unique_split_ids),
            )
            .with_for_update()
        ).mappings()
    )
    rows_by_split_id = {int(row["split_id"]): row for row in rows}
    missing = [split_id for split_id in unique_split_ids if split_id not in rows_by_split_id]
    if missing:
        raise CandidateEligibilityError(split_ids=missing)

    if decision == CANDIDATE_STATUS_ACCEPTED:
        conflicts: list[tuple[int, int]] = []
        for split_id in unique_split_ids:
            row = rows_by_split_id[split_id]
            current_moment_id = row["split_moment_id"]
            if current_moment_id is not None and current_moment_id != moment_id:
                conflicts.append((split_id, int(current_moment_id)))

        if conflicts and not confirm_reassign:
            conflict_split_ids = [row[0] for row in conflicts]
            source_moment_ids = sorted({row[1] for row in conflicts})
            raise CandidateConflictError(split_ids=conflict_split_ids, source_moment_ids=source_moment_ids)

        db.execute(
            update(Split)
            .where(Split.id.in_(unique_split_ids))
            .values(moment_id=moment_id)
        )
        _upsert_candidate_status_values(
            db,
            moment_id=moment_id,
            split_ids=unique_split_ids,
            status=CANDIDATE_STATUS_ACCEPTED,
            now=now,
        )
        _rewrite_accepted_rows_not_tagged_to_moment(
            db,
            split_ids=unique_split_ids,
            target_moment_id=moment_id,
            now=now,
        )

        return {
            "updated_count": len(unique_split_ids),
            "reassigned_count": len(conflicts),
        }

    rows_for_untag = [split_id for split_id in unique_split_ids if rows_by_split_id[split_id]["split_moment_id"] == moment_id]
    if rows_for_untag:
        db.execute(
            update(Split)
            .where(Split.id.in_(rows_for_untag))
            .values(moment_id=None)
        )

    _upsert_candidate_status_values(
        db,
        moment_id=moment_id,
        split_ids=unique_split_ids,
        status=CANDIDATE_STATUS_REJECTED,
        now=now,
    )
    if rows_for_untag:
        _rewrite_accepted_rows_not_tagged_to_moment(
            db,
            split_ids=rows_for_untag,
            target_moment_id=None,
            now=now,
        )

    return {
        "updated_count": len(unique_split_ids),
        "reassigned_count": 0,
    }


def upsert_candidate_status(
    db: Session,
    *,
    moment_id: int,
    split_ids: Iterable[int],
    status: str,
) -> int:
    normalized_ids = _dedupe_ids(list(split_ids))
    if not normalized_ids:
        return 0

    now = _utcnow()
    _upsert_candidate_status_values(
        db,
        moment_id=moment_id,
        split_ids=normalized_ids,
        status=status,
        now=now,
    )
    return len(normalized_ids)


def remove_tagged_splits(db: Session, *, moment_id: int, split_ids: list[int]) -> dict[str, int]:
    normalized_ids = _dedupe_ids(split_ids)
    if not normalized_ids:
        return {"updated_count": 0}

    rows = list(
        db.execute(
            select(Split.id, Split.moment_id)
            .where(Split.id.in_(normalized_ids))
            .with_for_update()
        )
    )
    current_moment_by_split_id = {int(row[0]): row[1] for row in rows}
    missing = [split_id for split_id in normalized_ids if current_moment_by_split_id.get(split_id) != moment_id]
    if missing:
        raise TaggedSplitOwnershipError(split_ids=missing, moment_id=moment_id)

    now = _utcnow()
    db.execute(
        update(Split)
        .where(Split.id.in_(normalized_ids))
        .values(moment_id=None)
    )
    _upsert_candidate_status_values(
        db,
        moment_id=moment_id,
        split_ids=normalized_ids,
        status=CANDIDATE_STATUS_REJECTED,
        now=now,
    )
    _rewrite_accepted_rows_not_tagged_to_moment(
        db,
        split_ids=normalized_ids,
        target_moment_id=None,
        now=now,
    )
    return {"updated_count": len(normalized_ids)}


def move_tagged_splits(
    db: Session,
    *,
    source_moment_id: int,
    target_moment_id: int,
    split_ids: list[int],
) -> dict[str, int]:
    normalized_ids = _dedupe_ids(split_ids)
    if not normalized_ids:
        return {"updated_count": 0}

    rows = list(
        db.execute(
            select(Split.id, Split.moment_id)
            .where(Split.id.in_(normalized_ids))
            .with_for_update()
        )
    )
    current_moment_by_split_id = {int(row[0]): row[1] for row in rows}
    missing = [split_id for split_id in normalized_ids if current_moment_by_split_id.get(split_id) != source_moment_id]
    if missing:
        raise TaggedSplitOwnershipError(split_ids=missing, moment_id=source_moment_id)

    now = _utcnow()
    db.execute(
        update(Split)
        .where(Split.id.in_(normalized_ids))
        .values(moment_id=target_moment_id)
    )
    _upsert_candidate_status_values(
        db,
        moment_id=source_moment_id,
        split_ids=normalized_ids,
        status=CANDIDATE_STATUS_REJECTED,
        now=now,
    )
    _upsert_candidate_status_values(
        db,
        moment_id=target_moment_id,
        split_ids=normalized_ids,
        status=CANDIDATE_STATUS_ACCEPTED,
        now=now,
    )
    _rewrite_accepted_rows_not_tagged_to_moment(
        db,
        split_ids=normalized_ids,
        target_moment_id=target_moment_id,
        now=now,
    )
    return {"updated_count": len(normalized_ids)}


def candidate_status_counts(
    db: Session,
    *,
    moment_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, int]:
    if start_date is None or end_date is None:
        rows = (
            db.execute(
                select(MOMENT_CANDIDATES.c.status, func.count())
                .where(MOMENT_CANDIDATES.c.moment_id == moment_id)
                .group_by(MOMENT_CANDIDATES.c.status)
            )
            .all()
        )
        counts = {
            CANDIDATE_STATUS_PENDING: 0,
            CANDIDATE_STATUS_ACCEPTED: 0,
            CANDIDATE_STATUS_REJECTED: 0,
        }
        for status, count in rows:
            counts[str(status)] = int(count)
        return counts

    return {
        CANDIDATE_STATUS_PENDING: _candidate_count(
            db,
            moment_id=moment_id,
            start_date=start_date,
            end_date=end_date,
            status=CANDIDATE_STATUS_PENDING,
        ),
        CANDIDATE_STATUS_ACCEPTED: _candidate_count(
            db,
            moment_id=moment_id,
            start_date=start_date,
            end_date=end_date,
            status=CANDIDATE_STATUS_ACCEPTED,
        ),
        CANDIDATE_STATUS_REJECTED: _candidate_count(
            db,
            moment_id=moment_id,
            start_date=start_date,
            end_date=end_date,
            status=CANDIDATE_STATUS_REJECTED,
        ),
    }


def _eligible_split_ids(
    db: Session,
    *,
    start_date: date,
    end_date: date,
) -> list[int]:
    rows = (
        db.query(Split.id)
        .join(Transaction, Transaction.id == Split.transaction_id)
        .filter(
            Split.moment_id.is_(None),
            Transaction.operation_at >= start_date,
            Transaction.operation_at <= end_date,
        )
        .all()
    )
    return [int(row[0]) for row in rows]


def _candidate_count(
    db: Session,
    *,
    moment_id: int,
    start_date: date,
    end_date: date,
    status: str,
) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(MOMENT_CANDIDATES)
            .join(Split, Split.id == MOMENT_CANDIDATES.c.split_id)
            .join(Transaction, Transaction.id == Split.transaction_id)
            .where(
                MOMENT_CANDIDATES.c.moment_id == moment_id,
                _candidate_visibility_clause(
                    moment_id=moment_id,
                    start_date=start_date,
                    end_date=end_date,
                    status=status,
                ),
            )
        ).scalar_one()
    )


def _candidate_visibility_clause(
    *,
    moment_id: int,
    start_date: date,
    end_date: date,
    status: str | None,
):
    pending_clause = and_(
        MOMENT_CANDIDATES.c.status == CANDIDATE_STATUS_PENDING,
        Split.moment_id.is_(None),
        Transaction.operation_at >= start_date,
        Transaction.operation_at <= end_date,
    )
    accepted_clause = and_(
        MOMENT_CANDIDATES.c.status == CANDIDATE_STATUS_ACCEPTED,
        Split.moment_id == moment_id,
    )
    rejected_clause = MOMENT_CANDIDATES.c.status == CANDIDATE_STATUS_REJECTED

    if status == CANDIDATE_STATUS_PENDING:
        return pending_clause
    if status == CANDIDATE_STATUS_ACCEPTED:
        return accepted_clause
    if status == CANDIDATE_STATUS_REJECTED:
        return rejected_clause
    return or_(pending_clause, accepted_clause, rejected_clause)


def _sync_candidate_invariants(db: Session, *, moment_id: int, now: datetime) -> None:
    stale_accepted_row_ids = [
        int(row[0])
        for row in db.execute(
            select(MOMENT_CANDIDATES.c.id)
            .select_from(MOMENT_CANDIDATES)
            .join(Split, Split.id == MOMENT_CANDIDATES.c.split_id)
            .where(
                MOMENT_CANDIDATES.c.moment_id == moment_id,
                MOMENT_CANDIDATES.c.status == CANDIDATE_STATUS_ACCEPTED,
                Split.moment_id != moment_id,
            )
        )
    ]
    if stale_accepted_row_ids:
        db.execute(
            update(MOMENT_CANDIDATES)
            .where(MOMENT_CANDIDATES.c.id.in_(stale_accepted_row_ids))
            .values(
                status=CANDIDATE_STATUS_REJECTED,
                decided_at=now,
                last_seen_at=now,
            )
        )

    tagged_rows = list(
        db.execute(
            select(
                Split.id.label("split_id"),
                MOMENT_CANDIDATES.c.id.label("candidate_id"),
                MOMENT_CANDIDATES.c.status.label("candidate_status"),
            )
            .select_from(Split)
            .outerjoin(
                MOMENT_CANDIDATES,
                and_(
                    MOMENT_CANDIDATES.c.moment_id == moment_id,
                    MOMENT_CANDIDATES.c.split_id == Split.id,
                ),
            )
            .where(Split.moment_id == moment_id)
        ).mappings()
    )

    split_ids_missing_rows: list[int] = []
    row_ids_to_accept: list[int] = []
    for row in tagged_rows:
        candidate_id = row["candidate_id"]
        if candidate_id is None:
            split_ids_missing_rows.append(int(row["split_id"]))
            continue
        if row["candidate_status"] != CANDIDATE_STATUS_ACCEPTED:
            row_ids_to_accept.append(int(candidate_id))

    if split_ids_missing_rows:
        _upsert_candidate_status_values(
            db,
            moment_id=moment_id,
            split_ids=split_ids_missing_rows,
            status=CANDIDATE_STATUS_ACCEPTED,
            now=now,
        )

    if row_ids_to_accept:
        db.execute(
            update(MOMENT_CANDIDATES)
            .where(MOMENT_CANDIDATES.c.id.in_(row_ids_to_accept))
            .values(
                status=CANDIDATE_STATUS_ACCEPTED,
                decided_at=now,
                last_seen_at=now,
            )
        )


def _insert_pending_candidates(
    db: Session,
    *,
    moment_id: int,
    split_ids: list[int],
    now: datetime,
) -> None:
    if not split_ids:
        return

    rows = [
        {
            "moment_id": moment_id,
            "split_id": split_id,
            "status": CANDIDATE_STATUS_PENDING,
            "first_seen_at": now,
            "last_seen_at": now,
            "decided_at": None,
        }
        for split_id in split_ids
    ]
    dialect_name = db.bind.dialect.name if db.bind is not None else ""
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(MOMENT_CANDIDATES).values(rows).on_conflict_do_nothing(
            index_elements=["moment_id", "split_id"]
        )
        db.execute(stmt)
        return
    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(MOMENT_CANDIDATES).values(rows).on_conflict_do_nothing(
            index_elements=["moment_id", "split_id"]
        )
        db.execute(stmt)
        return

    existing_ids = {
        int(row[0])
        for row in db.execute(
            select(MOMENT_CANDIDATES.c.split_id).where(
                MOMENT_CANDIDATES.c.moment_id == moment_id,
                MOMENT_CANDIDATES.c.split_id.in_(split_ids),
            )
        )
    }
    insert_rows = [row for row in rows if row["split_id"] not in existing_ids]
    if insert_rows:
        db.execute(MOMENT_CANDIDATES.insert(), insert_rows)


def _upsert_candidate_status_values(
    db: Session,
    *,
    moment_id: int,
    split_ids: list[int],
    status: str,
    now: datetime,
) -> None:
    if not split_ids:
        return

    decided_at = now if status != CANDIDATE_STATUS_PENDING else None
    insert_rows = [
        {
            "moment_id": moment_id,
            "split_id": split_id,
            "status": status,
            "first_seen_at": now,
            "last_seen_at": now,
            "decided_at": decided_at,
        }
        for split_id in split_ids
    ]

    update_values = {
        "status": status,
        "last_seen_at": now,
        "decided_at": decided_at,
    }

    dialect_name = db.bind.dialect.name if db.bind is not None else ""
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(MOMENT_CANDIDATES).values(insert_rows).on_conflict_do_update(
            index_elements=["moment_id", "split_id"],
            set_=update_values,
        )
        db.execute(stmt)
        return
    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(MOMENT_CANDIDATES).values(insert_rows).on_conflict_do_update(
            index_elements=["moment_id", "split_id"],
            set_=update_values,
        )
        db.execute(stmt)
        return

    existing_rows = (
        db.execute(
            select(MOMENT_CANDIDATES.c.id, MOMENT_CANDIDATES.c.split_id)
            .where(
                MOMENT_CANDIDATES.c.moment_id == moment_id,
                MOMENT_CANDIDATES.c.split_id.in_(split_ids),
            )
        ).mappings()
    )
    existing_by_split_id = {int(row["split_id"]): row for row in existing_rows}
    rows_to_insert: list[dict[str, Any]] = []
    for split_id in split_ids:
        existing = existing_by_split_id.get(split_id)
        if existing is None:
            rows_to_insert.append(
                {
                    "moment_id": moment_id,
                    "split_id": split_id,
                    "status": status,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "decided_at": decided_at,
                }
            )
            continue
        db.execute(
            update(MOMENT_CANDIDATES)
            .where(MOMENT_CANDIDATES.c.id == existing["id"])
            .values(**update_values)
        )
    if rows_to_insert:
        db.execute(MOMENT_CANDIDATES.insert(), rows_to_insert)


def _rewrite_accepted_rows_not_tagged_to_moment(
    db: Session,
    *,
    split_ids: list[int],
    target_moment_id: int | None,
    now: datetime,
) -> None:
    if not split_ids:
        return
    conditions = [
        MOMENT_CANDIDATES.c.split_id.in_(split_ids),
        MOMENT_CANDIDATES.c.status == CANDIDATE_STATUS_ACCEPTED,
    ]
    if target_moment_id is not None:
        conditions.append(MOMENT_CANDIDATES.c.moment_id != target_moment_id)
    db.execute(
        update(MOMENT_CANDIDATES)
        .where(and_(*conditions))
        .values(
            status=CANDIDATE_STATUS_REJECTED,
            decided_at=now,
            last_seen_at=now,
        )
    )


def _dedupe_ids(values: list[int]) -> list[int]:
    seen: set[int] = set()
    deduped: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
