from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from app.models import Account, Category, Moment, MomentCandidate, Split, Transaction, TransactionType


def _make_split_and_moment(db_session):
    account = Account(account_num="ACC-MOMENTS-SCHEMA", label="Moments schema")
    category = Category(name="Moments category")
    db_session.add_all([account, category])
    db_session.flush()

    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 3, 1),
        operation_at=date(2024, 3, 1),
        amount=Decimal("-10.00"),
        currency="EUR",
        label_raw="Moments candidate row",
        label_norm="moments candidate row",
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense,
        fingerprint="moments-schema-fingerprint",
    )
    db_session.add(transaction)
    db_session.flush()

    split = Split(
        transaction_id=transaction.id,
        amount=Decimal("-10.00"),
        category_id=category.id,
        position=0,
    )
    moment = Moment(
        name="March getaway",
        start_date=date(2024, 3, 1),
        end_date=date(2024, 3, 31),
    )
    db_session.add_all([split, moment])
    db_session.flush()
    return split, moment


def test_moments_table_has_updated_at_and_required_indexes(db_session):
    inspector = inspect(db_session.bind)

    moments_columns = {column["name"] for column in inspector.get_columns("moments")}
    assert "updated_at" in moments_columns

    split_indexes = {index["name"] for index in inspector.get_indexes("splits")}
    assert "ix_splits_moment_id" in split_indexes

    transaction_indexes = {index["name"] for index in inspector.get_indexes("transactions")}
    assert "ix_transactions_operation_at" in transaction_indexes


def test_moments_date_range_check_constraint_rejects_invalid_rows(db_session):
    invalid_moment = Moment(
        name="Invalid range",
        start_date=date(2024, 4, 10),
        end_date=date(2024, 4, 1),
    )
    db_session.add(invalid_moment)

    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_moment_candidates_schema_constraints_and_indexes(db_session):
    split, moment = _make_split_and_moment(db_session)

    inspector = inspect(db_session.bind)
    candidate_indexes = {index["name"] for index in inspector.get_indexes("moment_candidates")}
    assert "ix_moment_candidates_moment_status" in candidate_indexes
    assert "ix_moment_candidates_split_id" in candidate_indexes

    candidate_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints("moment_candidates")}
    assert "uq_moment_candidates_moment_id_split_id" in candidate_uniques

    candidate_checks = {constraint["name"] for constraint in inspector.get_check_constraints("moment_candidates")}
    assert "ck_moment_candidates_status" in candidate_checks

    db_session.add(
        MomentCandidate(
            moment_id=moment.id,
            split_id=split.id,
            status="pending",
        )
    )
    db_session.flush()

    db_session.add(
        MomentCandidate(
            moment_id=moment.id,
            split_id=split.id,
            status="accepted",
        )
    )
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_moment_candidates_status_check_rejects_invalid_status(db_session):
    split, moment = _make_split_and_moment(db_session)

    db_session.add(
        MomentCandidate(
            moment_id=moment.id,
            split_id=split.id,
            status="invalid_status",
        )
    )
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()
