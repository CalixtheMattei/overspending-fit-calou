from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models import Account, Category, Moment, MomentCandidate, Split, Transaction, TransactionType
from app.services import moment_candidates as moment_candidate_service


def _create_split(
    db_session,
    *,
    fingerprint: str,
    amount: Decimal,
    operation_at: date,
    moment_id: int | None = None,
) -> Split:
    account = Account(account_num=f"ACC-{fingerprint}", label=f"Account {fingerprint}")
    category = Category(name=f"Category {fingerprint}")
    db_session.add_all([account, category])
    db_session.flush()

    tx_type = TransactionType.income if amount > 0 else TransactionType.expense
    transaction = Transaction(
        account_id=account.id,
        posted_at=operation_at,
        operation_at=operation_at,
        amount=amount,
        currency="EUR",
        label_raw=f"Label {fingerprint}",
        label_norm=f"label {fingerprint}",
        supplier_raw=f"Supplier {fingerprint}",
        payee_id=None,
        type=tx_type,
        fingerprint=fingerprint,
    )
    db_session.add(transaction)
    db_session.flush()

    split = Split(
        transaction_id=transaction.id,
        amount=amount,
        category_id=category.id,
        moment_id=moment_id,
        note=f"note {fingerprint}",
        position=0,
    )
    db_session.add(split)
    db_session.flush()
    return split


def test_refresh_is_idempotent_and_preserves_rejected_decision(db_session):
    moment = Moment(name="September", start_date=date(2024, 9, 1), end_date=date(2024, 9, 30))
    db_session.add(moment)
    db_session.flush()

    split = _create_split(
        db_session,
        fingerprint="refresh-idempotent",
        amount=Decimal("-32.10"),
        operation_at=date(2024, 9, 12),
    )

    first_refresh = moment_candidate_service.refresh_candidates_for_moment(
        db_session,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
    )
    assert first_refresh["inserted_count"] == 1
    assert first_refresh["status_counts"]["pending"] == 1

    moment_candidate_service.decide_candidates(
        db_session,
        moment_id=moment.id,
        split_ids=[split.id],
        decision=moment_candidate_service.CANDIDATE_STATUS_REJECTED,
        confirm_reassign=False,
    )
    db_session.flush()

    candidate = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == moment.id, MomentCandidate.split_id == split.id)
        .one()
    )
    previous_decided_at = candidate.decided_at
    previous_last_seen_at = candidate.last_seen_at

    second_refresh = moment_candidate_service.refresh_candidates_for_moment(
        db_session,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
    )
    db_session.flush()

    candidate = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == moment.id, MomentCandidate.split_id == split.id)
        .one()
    )
    assert candidate.status == moment_candidate_service.CANDIDATE_STATUS_REJECTED
    assert candidate.decided_at == previous_decided_at
    assert candidate.last_seen_at >= previous_last_seen_at
    assert second_refresh["inserted_count"] == 0
    assert second_refresh["status_counts"]["rejected"] == 1


def test_accept_reassign_rewrites_source_candidate_state(db_session):
    source = Moment(name="Source", start_date=date(2024, 10, 1), end_date=date(2024, 10, 31))
    target = Moment(name="Target", start_date=date(2024, 10, 1), end_date=date(2024, 10, 31))
    db_session.add_all([source, target])
    db_session.flush()

    split = _create_split(
        db_session,
        fingerprint="reassign-accept",
        amount=Decimal("-44.00"),
        operation_at=date(2024, 10, 15),
        moment_id=source.id,
    )
    moment_candidate_service.upsert_candidate_status(
        db_session,
        moment_id=source.id,
        split_ids=[split.id],
        status=moment_candidate_service.CANDIDATE_STATUS_ACCEPTED,
    )
    moment_candidate_service.upsert_candidate_status(
        db_session,
        moment_id=target.id,
        split_ids=[split.id],
        status=moment_candidate_service.CANDIDATE_STATUS_PENDING,
    )

    result = moment_candidate_service.decide_candidates(
        db_session,
        moment_id=target.id,
        split_ids=[split.id],
        decision=moment_candidate_service.CANDIDATE_STATUS_ACCEPTED,
        confirm_reassign=True,
    )
    db_session.flush()

    db_session.refresh(split)
    assert split.moment_id == target.id
    assert result["updated_count"] == 1
    assert result["reassigned_count"] == 1

    source_row = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == source.id, MomentCandidate.split_id == split.id)
        .one()
    )
    target_row = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == target.id, MomentCandidate.split_id == split.id)
        .one()
    )
    assert source_row.status == moment_candidate_service.CANDIDATE_STATUS_REJECTED
    assert target_row.status == moment_candidate_service.CANDIDATE_STATUS_ACCEPTED


def test_accept_conflict_requires_confirmation(db_session):
    source = Moment(name="Source C", start_date=date(2024, 11, 1), end_date=date(2024, 11, 30))
    target = Moment(name="Target C", start_date=date(2024, 11, 1), end_date=date(2024, 11, 30))
    db_session.add_all([source, target])
    db_session.flush()

    split = _create_split(
        db_session,
        fingerprint="reassign-conflict",
        amount=Decimal("-18.90"),
        operation_at=date(2024, 11, 9),
        moment_id=source.id,
    )
    moment_candidate_service.upsert_candidate_status(
        db_session,
        moment_id=target.id,
        split_ids=[split.id],
        status=moment_candidate_service.CANDIDATE_STATUS_PENDING,
    )

    with pytest.raises(moment_candidate_service.CandidateConflictError):
        moment_candidate_service.decide_candidates(
            db_session,
            moment_id=target.id,
            split_ids=[split.id],
            decision=moment_candidate_service.CANDIDATE_STATUS_ACCEPTED,
            confirm_reassign=False,
        )

    db_session.refresh(split)
    assert split.moment_id == source.id


def test_move_tagged_splits_keeps_candidate_states_consistent(db_session):
    source = Moment(name="Move Source", start_date=date(2024, 5, 1), end_date=date(2024, 5, 31))
    target = Moment(name="Move Target", start_date=date(2024, 5, 1), end_date=date(2024, 5, 31))
    db_session.add_all([source, target])
    db_session.flush()

    split = _create_split(
        db_session,
        fingerprint="move-tagged",
        amount=Decimal("-51.00"),
        operation_at=date(2024, 5, 9),
        moment_id=source.id,
    )
    moment_candidate_service.upsert_candidate_status(
        db_session,
        moment_id=source.id,
        split_ids=[split.id],
        status=moment_candidate_service.CANDIDATE_STATUS_ACCEPTED,
    )

    result = moment_candidate_service.move_tagged_splits(
        db_session,
        source_moment_id=source.id,
        target_moment_id=target.id,
        split_ids=[split.id],
    )
    db_session.flush()

    db_session.refresh(split)
    assert split.moment_id == target.id
    assert result["updated_count"] == 1

    source_row = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == source.id, MomentCandidate.split_id == split.id)
        .one()
    )
    target_row = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == target.id, MomentCandidate.split_id == split.id)
        .one()
    )
    assert source_row.status == moment_candidate_service.CANDIDATE_STATUS_REJECTED
    assert target_row.status == moment_candidate_service.CANDIDATE_STATUS_ACCEPTED


def test_pending_list_excludes_drifted_rows(db_session):
    moment = Moment(name="Drift Source", start_date=date(2024, 8, 1), end_date=date(2024, 8, 31))
    other = Moment(name="Drift Target", start_date=date(2024, 8, 1), end_date=date(2024, 8, 31))
    db_session.add_all([moment, other])
    db_session.flush()

    split = _create_split(
        db_session,
        fingerprint="drift-pending",
        amount=Decimal("-27.00"),
        operation_at=date(2024, 8, 12),
    )

    moment_candidate_service.refresh_candidates_for_moment(
        db_session,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
    )
    split.moment_id = other.id
    db_session.flush()

    rows, total = moment_candidate_service.list_candidates(
        db_session,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
        status=moment_candidate_service.CANDIDATE_STATUS_PENDING,
        limit=25,
        offset=0,
    )
    counts = moment_candidate_service.candidate_status_counts(
        db_session,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
    )

    assert total == 0
    assert rows == []
    assert counts["pending"] == 0


def test_refresh_repairs_accepted_invariant_for_tagged_split(db_session):
    moment = Moment(name="Invariant", start_date=date(2024, 7, 1), end_date=date(2024, 7, 31))
    db_session.add(moment)
    db_session.flush()

    split = _create_split(
        db_session,
        fingerprint="accepted-invariant",
        amount=Decimal("-99.99"),
        operation_at=date(2024, 7, 14),
        moment_id=moment.id,
    )

    result = moment_candidate_service.refresh_candidates_for_moment(
        db_session,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
    )
    db_session.flush()

    candidate = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == moment.id, MomentCandidate.split_id == split.id)
        .one()
    )
    assert candidate.status == moment_candidate_service.CANDIDATE_STATUS_ACCEPTED
    assert result["status_counts"]["accepted"] == 1


def test_refresh_rewrites_stale_accepted_to_rejected(db_session):
    moment = Moment(name="Stale", start_date=date(2024, 6, 1), end_date=date(2024, 6, 30))
    db_session.add(moment)
    db_session.flush()

    split = _create_split(
        db_session,
        fingerprint="stale-accepted",
        amount=Decimal("-11.00"),
        operation_at=date(2024, 6, 7),
        moment_id=None,
    )
    db_session.add(
        MomentCandidate(
            moment_id=moment.id,
            split_id=split.id,
            status=moment_candidate_service.CANDIDATE_STATUS_ACCEPTED,
        )
    )
    db_session.flush()

    result = moment_candidate_service.refresh_candidates_for_moment(
        db_session,
        moment_id=moment.id,
        start_date=moment.start_date,
        end_date=moment.end_date,
    )
    db_session.flush()

    candidate = (
        db_session.query(MomentCandidate)
        .filter(MomentCandidate.moment_id == moment.id, MomentCandidate.split_id == split.id)
        .one()
    )
    assert candidate.status == moment_candidate_service.CANDIDATE_STATUS_REJECTED
    assert result["status_counts"]["accepted"] == 0
    assert result["status_counts"]["rejected"] == 1
