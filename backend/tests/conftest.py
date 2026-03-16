import os
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_ROOT))

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL is not set; skipping DB tests.", allow_module_level=True)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.db import get_db
from app.main import app
from app.models import Account, Category, Counterparty, CounterpartyKind, Moment, Split, Transaction, TransactionType


def _alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    command.upgrade(_alembic_config(), "head")


engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture()
def client(db_session):
    db_session.begin_nested()

    @event.listens_for(db_session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    event.remove(db_session, "after_transaction_end", restart_savepoint)


@dataclass(frozen=True)
class WsGFixture:
    account_id: int
    primary_moment_id: int
    primary_moment_name: str
    secondary_moment_id: int
    secondary_moment_name: str
    tagged_transaction_id: int
    tagged_split_id: int
    tagged_split_amount: str
    tagged_split_category_id: int
    tagged_split_internal_account_id: int | None
    untagged_candidate_transaction_id: int
    untagged_candidate_split_id: int
    unsplit_candidate_transaction_id: int
    analytics_tagged_expense_total: float


@pytest.fixture()
def ws_g_fixture(db_session) -> WsGFixture:
    account = Account(account_num="ACC-WSG-QA", label="Wave1 QA")
    category_travel = Category(name="Travel")
    category_groceries = Category(name="Groceries")
    category_salary = Category(name="Salary")
    payee_airline = Counterparty(
        name="BlueSky Air",
        canonical_name="bluesky air",
        kind=CounterpartyKind.merchant,
        type=None,
        position=0,
        is_archived=False,
    )
    payee_market = Counterparty(
        name="Fresh Market",
        canonical_name="fresh market",
        kind=CounterpartyKind.merchant,
        type=None,
        position=1,
        is_archived=False,
    )
    payee_employer = Counterparty(
        name="Northwind Payroll",
        canonical_name="northwind payroll",
        kind=CounterpartyKind.merchant,
        type=None,
        position=2,
        is_archived=False,
    )
    internal_cash = Counterparty(
        name="Cash",
        canonical_name="cash",
        kind=CounterpartyKind.internal,
        type="wallet",
        position=0,
        is_archived=False,
    )
    internal_savings = Counterparty(
        name="Savings",
        canonical_name="savings",
        kind=CounterpartyKind.internal,
        type="savings",
        position=1,
        is_archived=False,
    )
    primary_moment = Moment(
        name="Summer Trip 2024",
        start_date=date(2024, 7, 1),
        end_date=date(2024, 7, 31),
        description="WS-G fixture: primary moment",
    )
    secondary_moment = Moment(
        name="Move Home 2024",
        start_date=date(2024, 8, 1),
        end_date=date(2024, 8, 31),
        description="WS-G fixture: secondary moment",
    )
    db_session.add_all(
        [
            account,
            category_travel,
            category_groceries,
            category_salary,
            payee_airline,
            payee_market,
            payee_employer,
            internal_cash,
            internal_savings,
            primary_moment,
            secondary_moment,
        ]
    )
    db_session.flush()

    tx_tagged = Transaction(
        account_id=account.id,
        posted_at=date(2024, 7, 10),
        operation_at=date(2024, 7, 9),
        amount=Decimal("-120.00"),
        currency="EUR",
        label_raw="Flight booking",
        label_norm="flight booking",
        supplier_raw=None,
        payee_id=payee_airline.id,
        type=TransactionType.expense,
        fingerprint="ws-g-tagged-expense",
    )
    tx_untagged_candidate = Transaction(
        account_id=account.id,
        posted_at=date(2024, 7, 12),
        operation_at=date(2024, 7, 12),
        amount=Decimal("-80.00"),
        currency="EUR",
        label_raw="Groceries weekly",
        label_norm="groceries weekly",
        supplier_raw=None,
        payee_id=payee_market.id,
        type=TransactionType.expense,
        fingerprint="ws-g-untagged-candidate",
    )
    tx_secondary_tagged = Transaction(
        account_id=account.id,
        posted_at=date(2024, 7, 20),
        operation_at=date(2024, 7, 20),
        amount=Decimal("-55.00"),
        currency="EUR",
        label_raw="Storage rental",
        label_norm="storage rental",
        supplier_raw=None,
        payee_id=payee_market.id,
        type=TransactionType.expense,
        fingerprint="ws-g-secondary-tagged",
    )
    tx_unsplit_candidate = Transaction(
        account_id=account.id,
        posted_at=date(2024, 7, 14),
        operation_at=date(2024, 7, 14),
        amount=Decimal("-25.00"),
        currency="EUR",
        label_raw="Taxi local",
        label_norm="taxi local",
        supplier_raw=None,
        payee_id=payee_market.id,
        type=TransactionType.expense,
        fingerprint="ws-g-unsplit-candidate",
    )
    tx_income = Transaction(
        account_id=account.id,
        posted_at=date(2024, 7, 3),
        operation_at=date(2024, 7, 3),
        amount=Decimal("500.00"),
        currency="EUR",
        label_raw="Payroll",
        label_norm="payroll",
        supplier_raw=None,
        payee_id=payee_employer.id,
        type=TransactionType.income,
        fingerprint="ws-g-income",
    )
    tx_transfer = Transaction(
        account_id=account.id,
        posted_at=date(2024, 7, 16),
        operation_at=date(2024, 7, 16),
        amount=Decimal("-40.00"),
        currency="EUR",
        label_raw="Transfer to wallet",
        label_norm="transfer to wallet",
        supplier_raw=None,
        payee_id=payee_market.id,
        type=TransactionType.transfer,
        fingerprint="ws-g-transfer",
    )
    db_session.add_all(
        [
            tx_tagged,
            tx_untagged_candidate,
            tx_secondary_tagged,
            tx_unsplit_candidate,
            tx_income,
            tx_transfer,
        ]
    )
    db_session.flush()

    tagged_split = Split(
        transaction_id=tx_tagged.id,
        amount=Decimal("-120.00"),
        category_id=category_travel.id,
        moment_id=primary_moment.id,
        internal_account_id=internal_cash.id,
        position=0,
    )
    untagged_candidate_split = Split(
        transaction_id=tx_untagged_candidate.id,
        amount=Decimal("-80.00"),
        category_id=category_groceries.id,
        moment_id=None,
        internal_account_id=None,
        position=0,
    )
    db_session.add(
        Split(
            transaction_id=tx_secondary_tagged.id,
            amount=Decimal("-55.00"),
            category_id=category_groceries.id,
            moment_id=secondary_moment.id,
            internal_account_id=internal_cash.id,
            position=0,
        )
    )
    db_session.add(
        Split(
            transaction_id=tx_income.id,
            amount=Decimal("500.00"),
            category_id=category_salary.id,
            moment_id=None,
            internal_account_id=internal_savings.id,
            position=0,
        )
    )
    db_session.add(
        Split(
            transaction_id=tx_transfer.id,
            amount=Decimal("-40.00"),
            category_id=category_travel.id,
            moment_id=None,
            internal_account_id=internal_cash.id,
            position=0,
        )
    )
    db_session.add_all([tagged_split, untagged_candidate_split])
    db_session.flush()

    return WsGFixture(
        account_id=account.id,
        primary_moment_id=primary_moment.id,
        primary_moment_name=primary_moment.name,
        secondary_moment_id=secondary_moment.id,
        secondary_moment_name=secondary_moment.name,
        tagged_transaction_id=tx_tagged.id,
        tagged_split_id=tagged_split.id,
        tagged_split_amount="-120.00",
        tagged_split_category_id=category_travel.id,
        tagged_split_internal_account_id=internal_cash.id,
        untagged_candidate_transaction_id=tx_untagged_candidate.id,
        untagged_candidate_split_id=untagged_candidate_split.id,
        unsplit_candidate_transaction_id=tx_unsplit_candidate.id,
        analytics_tagged_expense_total=175.0,
    )
