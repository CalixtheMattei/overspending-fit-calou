"""
Deterministic demo data seed script for the personal expense tracker.

Usage:
    DATABASE_URL=postgresql+psycopg://... python -m scripts.seed_demo

Requires DATABASE_URL env var (set by docker-compose).
Optionally set DEMO_APP_PASSWORD to create a read-only PostgreSQL role.
Optionally set DEMO_AVATAR_PATH to a JPEG/PNG file to use as the profile avatar
  (defaults to a grey placeholder PNG).  In Docker the seed service bind-mounts
  the real avatar into the container and passes the in-container path via this var.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import shutil
import struct
import sys
import zlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Ensure backend package is importable when run as `python -m scripts.seed_demo`
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import UserProfile
from app.models import (
    Account,
    Category,
    Counterparty,
    CounterpartyKind,
    Import,
    ImportRow,
    ImportRowLink,
    ImportRowStatus,
    Moment,
    MomentCandidate,
    Rule,
    Split,
    Transaction,
    TransactionType,
)
from app.services.category_catalog import seed_native_categories

# ---------------------------------------------------------------------------
# Deterministic RNG
# ---------------------------------------------------------------------------
RNG = random.Random(42)

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
DATE_START = date(2025, 9, 1)
DATE_END = date(2026, 2, 28)


def _iter_dates(start: date, end: date):
    """Yield every date from *start* to *end* inclusive."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _fingerprint(account_num: str, posted_at: date, amount: Decimal, label_norm: str) -> str:
    raw = f"{account_num}|{posted_at.isoformat()}|{amount}|{label_norm}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _label_norm(label_raw: str) -> str:
    return label_raw.strip().lower()


# ---------------------------------------------------------------------------
# Counterparty definitions
# ---------------------------------------------------------------------------
MERCHANT_DEFS: list[dict] = [
    {"name": "Monoprix", "canonical_name": "monoprix"},
    {"name": "Carrefour City", "canonical_name": "carrefour city"},
    {"name": "SNCF", "canonical_name": "sncf"},
    {"name": "EDF", "canonical_name": "edf"},
    {"name": "Orange", "canonical_name": "orange"},
    {"name": "Netflix", "canonical_name": "netflix"},
    {"name": "Spotify", "canonical_name": "spotify"},
    {"name": "Boulangerie Martin", "canonical_name": "boulangerie martin"},
    {"name": "Pharmacie Centrale", "canonical_name": "pharmacie centrale"},
    {"name": "Decathlon", "canonical_name": "decathlon"},
    {"name": "Amazon", "canonical_name": "amazon"},
    {"name": "Fnac", "canonical_name": "fnac"},
    {"name": "Velib", "canonical_name": "velib"},
    {"name": "Uber Eats", "canonical_name": "uber eats"},
    {"name": "Deliveroo", "canonical_name": "deliveroo"},
]

INTERNAL_DEFS: list[dict] = [
    {"name": "Livret A Epargne", "canonical_name": "livret a epargne", "type": "savings"},
    {"name": "Revolut", "canonical_name": "revolut", "type": "wallet"},
]

# ---------------------------------------------------------------------------
# Transaction templates
# ---------------------------------------------------------------------------
# Each template: (payee_canonical, label_format, amount_range, tx_type, frequency_per_month, category_keyword)
# label_format uses {dd}/{mm}/{yy} placeholders for the posted date.
EXPENSE_TEMPLATES: list[dict] = [
    # Groceries
    {"payee": "monoprix", "label": "CARTE {dd}/{mm}/{yy} MONOPRIX", "amount": (-85, -25), "type": "expense", "freq": (4, 6), "cat_kw": "courses"},
    {"payee": "carrefour city", "label": "CARTE {dd}/{mm}/{yy} CARREFOUR CITY", "amount": (-60, -15), "type": "expense", "freq": (3, 5), "cat_kw": "courses"},
    # Bakery
    {"payee": "boulangerie martin", "label": "CARTE {dd}/{mm}/{yy} BOULANGERIE MARTIN", "amount": (-12, -3), "type": "expense", "freq": (6, 10), "cat_kw": "alimentation"},
    # Transport
    {"payee": "sncf", "label": "CARTE {dd}/{mm}/{yy} SNCF", "amount": (-150, -20), "type": "expense", "freq": (1, 2), "cat_kw": "transports"},
    {"payee": "velib", "label": "CARTE {dd}/{mm}/{yy} VELIB METROPOLE", "amount": (-4, -1), "type": "expense", "freq": (3, 6), "cat_kw": "transports"},
    # Subscriptions (SEPA)
    {"payee": "netflix", "label": "PRLV SEPA NETFLIX", "amount": (-18, -14), "type": "expense", "freq": (1, 1), "cat_kw": "loisirs"},
    {"payee": "spotify", "label": "PRLV SEPA SPOTIFY", "amount": (-11, -10), "type": "expense", "freq": (1, 1), "cat_kw": "loisirs"},
    {"payee": "orange", "label": "PRLV SEPA ORANGE SA", "amount": (-40, -30), "type": "expense", "freq": (1, 1), "cat_kw": "communication"},
    # Utilities
    {"payee": "edf", "label": "PRLV SEPA EDF", "amount": (-120, -60), "type": "expense", "freq": (1, 1), "cat_kw": "logement"},
    # Pharmacy
    {"payee": "pharmacie centrale", "label": "CARTE {dd}/{mm}/{yy} PHARMACIE CENTRALE", "amount": (-45, -8), "type": "expense", "freq": (1, 2), "cat_kw": "sante"},
    # Sport
    {"payee": "decathlon", "label": "CARTE {dd}/{mm}/{yy} DECATHLON", "amount": (-90, -20), "type": "expense", "freq": (0, 1), "cat_kw": "loisirs"},
    # Online shopping
    {"payee": "amazon", "label": "CARTE {dd}/{mm}/{yy} AMAZON EU SARL", "amount": (-120, -10), "type": "expense", "freq": (1, 3), "cat_kw": "achats"},
    {"payee": "fnac", "label": "CARTE {dd}/{mm}/{yy} FNAC", "amount": (-80, -15), "type": "expense", "freq": (0, 1), "cat_kw": "achats"},
    # Dining / delivery
    {"payee": "uber eats", "label": "CARTE {dd}/{mm}/{yy} UBER EATS", "amount": (-35, -12), "type": "expense", "freq": (2, 4), "cat_kw": "alimentation"},
    {"payee": "deliveroo", "label": "CARTE {dd}/{mm}/{yy} DELIVEROO", "amount": (-30, -10), "type": "expense", "freq": (1, 3), "cat_kw": "alimentation"},
]

# Category keyword -> normalized name fragments to search in seeded categories
CATEGORY_KEYWORD_MAP = {
    "courses": ["courses", "groceries", "supermarche"],
    "alimentation": ["alimentation", "food", "restauration"],
    "transports": ["transports", "transport", "mobilite"],
    "loisirs": ["loisirs", "leisure", "divertissement"],
    "communication": ["communication", "telecom", "telephone"],
    "logement": ["logement", "housing", "habitation"],
    "sante": ["sante", "health", "pharmacie"],
    "achats": ["achats", "shopping", "achats et shopping"],
    "revenus": ["revenus", "salaire", "income", "salary"],
    "epargne": ["epargne", "savings", "virement"],
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _find_category_by_keyword(categories: list[Category], keyword: str) -> Category | None:
    """Find a category whose normalized name contains one of the keyword fragments."""
    fragments = CATEGORY_KEYWORD_MAP.get(keyword, [keyword])
    # First try leaf categories (children), then parents
    for cat in categories:
        cat_norm = (cat.normalized_name or cat.name).lower()
        for frag in fragments:
            if frag in cat_norm:
                return cat
    return None


def _build_category_map(db: Session) -> dict[str, int]:
    """Build keyword -> category_id mapping from the DB."""
    all_cats = db.query(Category).all()
    # Prefer child categories over parents
    children = [c for c in all_cats if c.parent_id is not None]
    parents = [c for c in all_cats if c.parent_id is None]
    ordered = children + parents

    cat_map: dict[str, int] = {}
    for kw in CATEGORY_KEYWORD_MAP:
        found = _find_category_by_keyword(ordered, kw)
        if found:
            cat_map[kw] = found.id
    # Fallback: use the first category if a keyword isn't matched
    if all_cats:
        fallback_id = all_cats[0].id
        for kw in CATEGORY_KEYWORD_MAP:
            cat_map.setdefault(kw, fallback_id)
    return cat_map


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def _make_placeholder_png(size: int = 64) -> bytes:
    """Generate a minimal valid grayscale PNG of *size* x *size* pixels."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0))
    # Each row: filter byte (0 = None) + <size> gray-128 pixels
    raw = (b"\x00" + bytes([128] * size)) * size
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


def seed_user_profile(db: Session) -> None:
    existing = db.query(UserProfile).filter(UserProfile.id == 1).one_or_none()
    if existing:
        return

    avatars_dir = Path(os.environ.get("AVATARS_STORAGE_DIR", "data/avatars"))
    avatars_dir.mkdir(parents=True, exist_ok=True)

    # Use a real avatar if provided via env var (bind-mounted into the container);
    # otherwise fall back to a grey placeholder PNG.
    demo_avatar_src = os.environ.get("DEMO_AVATAR_PATH", "")
    if demo_avatar_src and Path(demo_avatar_src).is_file():
        ext = Path(demo_avatar_src).suffix.lower() or ".jpg"
        avatar_filename = f"calou_avatar{ext}"
        shutil.copy2(demo_avatar_src, avatars_dir / avatar_filename)
        print(f"[seed] Avatar copied from {demo_avatar_src}")
    else:
        if demo_avatar_src:
            print(f"[seed] WARNING: DEMO_AVATAR_PATH={demo_avatar_src!r} not found, using placeholder")
        avatar_filename = "calou_avatar.png"
        (avatars_dir / avatar_filename).write_bytes(_make_placeholder_png(64))

    profile = UserProfile(
        id=1,
        name="Virtual Calou",
        email="calou@example.com",
        avatar_path=avatar_filename,
    )
    db.add(profile)
    db.flush()


def seed_accounts(db: Session) -> dict[str, Account]:
    acc_checking = Account(account_num="FR7600000000001", label="Compte Courant", institution="BoursoBank")
    acc_savings = Account(account_num="FR7600000000002", label="Livret A", institution="BoursoBank")
    db.add_all([acc_checking, acc_savings])
    db.flush()
    return {"checking": acc_checking, "savings": acc_savings}


def seed_counterparties(db: Session) -> dict[str, Counterparty]:
    result: dict[str, Counterparty] = {}
    for idx, defn in enumerate(MERCHANT_DEFS):
        cp = Counterparty(
            name=defn["name"],
            canonical_name=defn["canonical_name"],
            kind=CounterpartyKind.merchant,
            type=None,
            position=idx,
            is_archived=False,
        )
        db.add(cp)
        result[defn["canonical_name"]] = cp

    for idx, defn in enumerate(INTERNAL_DEFS):
        cp = Counterparty(
            name=defn["name"],
            canonical_name=defn["canonical_name"],
            kind=CounterpartyKind.internal,
            type=defn["type"],
            position=idx,
            is_archived=False,
        )
        db.add(cp)
        result[defn["canonical_name"]] = cp

    db.flush()
    return result


def _load_demo_asset_as_data_uri(filename: str) -> str | None:
    """Return a base64 data URI for a file in demo_assets/, or None if missing."""
    asset_path = Path(__file__).parent / "demo_assets" / filename
    if not asset_path.is_file():
        return None
    ext = asset_path.suffix.lower().lstrip(".")
    mime = {
        "svg": "image/svg+xml",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")
    data = base64.b64encode(asset_path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def seed_moments(db: Session) -> dict[str, Moment]:
    m_summer = Moment(
        name="Vacances d'ete 2025",
        start_date=date(2025, 7, 14),
        end_date=date(2025, 7, 31),
        description="Summer holidays in the south of France",
        cover_image_url=_load_demo_asset_as_data_uri("moment_summer.svg"),
    )
    m_xmas = Moment(
        name="Noel 2025",
        start_date=date(2025, 12, 20),
        end_date=date(2025, 12, 28),
        description="Christmas holidays and gifts",
        cover_image_url=_load_demo_asset_as_data_uri("moment_xmas.svg"),
    )
    db.add_all([m_summer, m_xmas])
    db.flush()
    return {"summer": m_summer, "xmas": m_xmas}


def seed_rules(db: Session, cat_map: dict[str, int]) -> list[Rule]:
    rules: list[Rule] = []

    # Rule 1: Netflix -> loisirs
    rules.append(Rule(
        name="Netflix -> Loisirs",
        priority=1,
        enabled=True,
        source="demo_seed",
        source_ref="demo_1",
        matcher_json={"all": [{"predicate": "label_contains", "value": "NETFLIX"}]},
        action_json={"set_category": cat_map.get("loisirs")},
    ))

    # Rule 2: Spotify -> loisirs
    rules.append(Rule(
        name="Spotify -> Loisirs",
        priority=2,
        enabled=True,
        source="demo_seed",
        source_ref="demo_2",
        matcher_json={"all": [{"predicate": "label_contains", "value": "SPOTIFY"}]},
        action_json={"set_category": cat_map.get("loisirs")},
    ))

    # Rule 3: EDF -> logement
    rules.append(Rule(
        name="EDF -> Logement",
        priority=3,
        enabled=True,
        source="demo_seed",
        source_ref="demo_3",
        matcher_json={"all": [{"predicate": "label_contains", "value": "EDF"}]},
        action_json={"set_category": cat_map.get("logement")},
    ))

    # Rule 4: Orange -> communication
    rules.append(Rule(
        name="Orange -> Communication",
        priority=4,
        enabled=True,
        source="demo_seed",
        source_ref="demo_4",
        matcher_json={"all": [{"predicate": "label_contains", "value": "ORANGE SA"}]},
        action_json={"set_category": cat_map.get("communication")},
    ))

    # Rule 5: SNCF -> transports
    rules.append(Rule(
        name="SNCF -> Transports",
        priority=5,
        enabled=True,
        source="demo_seed",
        source_ref="demo_5",
        matcher_json={"all": [{"predicate": "label_contains", "value": "SNCF"}]},
        action_json={"set_category": cat_map.get("transports")},
    ))

    db.add_all(rules)
    db.flush()
    return rules


def seed_transactions(
    db: Session,
    accounts: dict[str, Account],
    counterparties: dict[str, Counterparty],
    moments: dict[str, Moment],
    cat_map: dict[str, int],
) -> list[Transaction]:
    """Generate ~500-600 transactions over 6 months on the checking account."""
    checking = accounts["checking"]
    all_transactions: list[Transaction] = []
    all_splits: list[Split] = []

    # Moment date ranges for tagging some splits
    moment_ranges: list[tuple[date, date, int]] = [
        (moments["summer"].start_date, moments["summer"].end_date, moments["summer"].id),
        (moments["xmas"].start_date, moments["xmas"].end_date, moments["xmas"].id),
    ]

    def _moment_id_for_date(d: date) -> int | None:
        for start, end, mid in moment_ranges:
            if start <= d <= end:
                return mid
        return None

    # Collect all months in the range
    months: list[tuple[int, int]] = []
    d = DATE_START
    while d <= DATE_END:
        ym = (d.year, d.month)
        if ym not in months:
            months.append(ym)
        d += timedelta(days=28)

    # --- Expense transactions from templates ---
    for year, month in months:
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year, 12, 31)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
        # Clamp to our overall range
        month_start = max(month_start, DATE_START)
        month_end = min(month_end, DATE_END)

        for tpl in EXPENSE_TEMPLATES:
            freq_lo, freq_hi = tpl["freq"]
            count = RNG.randint(freq_lo, freq_hi)
            for _ in range(count):
                day = RNG.randint(month_start.day, month_end.day)
                try:
                    posted = date(year, month, day)
                except ValueError:
                    posted = month_end
                operation = posted - timedelta(days=RNG.randint(0, 2))

                amount_lo, amount_hi = tpl["amount"]
                # Generate a random amount in the range (both negative)
                raw_cents = RNG.randint(int(amount_lo * 100), int(amount_hi * 100))
                amount = Decimal(raw_cents) / Decimal(100)

                dd = posted.strftime("%d")
                mm = posted.strftime("%m")
                yy = posted.strftime("%y")
                label_raw = tpl["label"].format(dd=dd, mm=mm, yy=yy)
                norm = _label_norm(label_raw)
                fp = _fingerprint(checking.account_num, posted, amount, norm)

                payee = counterparties.get(tpl["payee"])
                cat_kw = tpl["cat_kw"]
                category_id = cat_map.get(cat_kw)

                tx = Transaction(
                    account_id=checking.id,
                    posted_at=posted,
                    operation_at=operation,
                    amount=amount,
                    currency="EUR",
                    label_raw=label_raw,
                    label_norm=norm,
                    supplier_raw=payee.name if payee else None,
                    payee_id=payee.id if payee else None,
                    type=TransactionType.expense,
                    fingerprint=fp,
                )
                all_transactions.append(tx)

                moment_id = _moment_id_for_date(posted)
                split = _DeferredSplit(
                    tx_ref=tx,
                    amount=amount,
                    category_id=category_id,
                    moment_id=moment_id,
                )
                all_splits.append(split)

        # --- Monthly salary (income) ---
        salary_day = RNG.choice([25, 26, 27, 28])
        try:
            salary_date = date(year, month, salary_day)
        except ValueError:
            salary_date = month_end
        salary_date = max(min(salary_date, month_end), month_start)

        salary_amount = Decimal("3200.00") + Decimal(RNG.randint(-5000, 5000)) / Decimal(100)
        salary_label = f"VIR SEPA ACME CORP SALAIRE {month:02d}/{year}"
        salary_norm = _label_norm(salary_label)
        salary_fp = _fingerprint(checking.account_num, salary_date, salary_amount, salary_norm)

        tx_salary = Transaction(
            account_id=checking.id,
            posted_at=salary_date,
            operation_at=salary_date,
            amount=salary_amount,
            currency="EUR",
            label_raw=salary_label,
            label_norm=salary_norm,
            supplier_raw="ACME CORP",
            payee_id=None,
            type=TransactionType.income,
            fingerprint=salary_fp,
        )
        all_transactions.append(tx_salary)
        all_splits.append(_DeferredSplit(
            tx_ref=tx_salary,
            amount=salary_amount,
            category_id=cat_map.get("revenus"),
            moment_id=None,
        ))

        # --- Monthly transfer to Livret A ---
        transfer_day = RNG.choice([1, 2, 3])
        try:
            transfer_date = date(year, month, transfer_day)
        except ValueError:
            transfer_date = month_start
        transfer_date = max(min(transfer_date, month_end), month_start)

        transfer_amount = Decimal("-500.00")
        transfer_label = f"VIR SEPA LIVRET A EPARGNE"
        transfer_norm = _label_norm(transfer_label)
        transfer_fp = _fingerprint(checking.account_num, transfer_date, transfer_amount, transfer_norm + f"_{month:02d}{year}")

        livret_cp = counterparties.get("livret a epargne")
        tx_transfer = Transaction(
            account_id=checking.id,
            posted_at=transfer_date,
            operation_at=transfer_date,
            amount=transfer_amount,
            currency="EUR",
            label_raw=transfer_label,
            label_norm=transfer_norm,
            supplier_raw=None,
            payee_id=livret_cp.id if livret_cp else None,
            type=TransactionType.transfer,
            fingerprint=transfer_fp,
        )
        all_transactions.append(tx_transfer)
        all_splits.append(_DeferredSplit(
            tx_ref=tx_transfer,
            amount=transfer_amount,
            category_id=cat_map.get("epargne"),
            moment_id=None,
        ))

        # --- Occasional refund (every other month) ---
        if month % 2 == 0:
            refund_day = RNG.randint(5, 20)
            try:
                refund_date = date(year, month, refund_day)
            except ValueError:
                refund_date = month_end
            refund_date = max(min(refund_date, month_end), month_start)

            refund_amount = Decimal(RNG.randint(1000, 8000)) / Decimal(100)
            merchant = RNG.choice(["AMAZON EU SARL", "FNAC", "DECATHLON"])
            refund_label = f"VIR SEPA REMB {merchant}"
            refund_norm = _label_norm(refund_label)
            refund_fp = _fingerprint(checking.account_num, refund_date, refund_amount, refund_norm)

            tx_refund = Transaction(
                account_id=checking.id,
                posted_at=refund_date,
                operation_at=refund_date,
                amount=refund_amount,
                currency="EUR",
                label_raw=refund_label,
                label_norm=refund_norm,
                supplier_raw=merchant,
                payee_id=None,
                type=TransactionType.refund,
                fingerprint=refund_fp,
            )
            all_transactions.append(tx_refund)
            all_splits.append(_DeferredSplit(
                tx_ref=tx_refund,
                amount=refund_amount,
                category_id=cat_map.get("achats"),
                moment_id=None,
            ))

    # --- Summer holiday transactions (for moment candidates) ---
    summer_merchants = [
        ("monoprix", "CARTE {dd}/{mm}/{yy} MONOPRIX MARSEILLE", (-65, -20), "courses"),
        ("sncf", "CARTE {dd}/{mm}/{yy} SNCF VOYAGES", (-180, -40), "transports"),
        ("uber eats", "CARTE {dd}/{mm}/{yy} UBER EATS", (-30, -12), "alimentation"),
        ("decathlon", "CARTE {dd}/{mm}/{yy} DECATHLON PLAGE", (-70, -15), "loisirs"),
    ]
    summer_start = date(2025, 7, 14)
    summer_end = date(2025, 7, 31)
    for _ in range(20):
        payee_cn, label_tpl, (amt_lo, amt_hi), cat_kw = RNG.choice(summer_merchants)
        day = RNG.randint(summer_start.day, summer_end.day)
        posted = date(2025, 7, day)
        operation = posted - timedelta(days=RNG.randint(0, 1))
        raw_cents = RNG.randint(int(amt_lo * 100), int(amt_hi * 100))
        amount = Decimal(raw_cents) / Decimal(100)
        dd, mm, yy = posted.strftime("%d"), posted.strftime("%m"), posted.strftime("%y")
        label_raw = label_tpl.format(dd=dd, mm=mm, yy=yy)
        norm = _label_norm(label_raw)
        fp = _fingerprint(checking.account_num, posted, amount, norm)
        payee = counterparties.get(payee_cn)
        tx = Transaction(
            account_id=checking.id,
            posted_at=posted,
            operation_at=operation,
            amount=amount,
            currency="EUR",
            label_raw=label_raw,
            label_norm=norm,
            supplier_raw=payee.name if payee else None,
            payee_id=payee.id if payee else None,
            type=TransactionType.expense,
            fingerprint=fp,
        )
        all_transactions.append(tx)
        all_splits.append(_DeferredSplit(
            tx_ref=tx,
            amount=amount,
            category_id=cat_map.get(cat_kw),
            moment_id=moments["summer"].id,
        ))

    # Flush transactions to get IDs
    db.add_all(all_transactions)
    db.flush()

    # Now create real Split objects
    real_splits: list[Split] = []
    for ds in all_splits:
        s = Split(
            transaction_id=ds.tx_ref.id,
            amount=ds.amount,
            category_id=ds.category_id,
            moment_id=ds.moment_id,
            position=0,
        )
        real_splits.append(s)
    db.add_all(real_splits)
    db.flush()

    # Store the split references back for moment candidate creation
    for ds, s in zip(all_splits, real_splits):
        ds.split_obj = s

    return all_transactions


class _DeferredSplit:
    """Holds split info before the parent transaction has an ID."""
    __slots__ = ("tx_ref", "amount", "category_id", "moment_id", "split_obj")

    def __init__(self, tx_ref: Transaction, amount: Decimal, category_id: int | None, moment_id: int | None):
        self.tx_ref = tx_ref
        self.amount = amount
        self.category_id = category_id
        self.moment_id = moment_id
        self.split_obj: Split | None = None


def seed_import(
    db: Session,
    account: Account,
    transactions: list[Transaction],
) -> Import:
    """Create one Import record with ImportRows and ImportRowLinks for a subset of transactions."""
    # Take the first 50 transactions as the "imported" subset
    subset = transactions[:50]

    imp = Import(
        account_id=account.id,
        file_name="export_boursobank_2025.csv",
        file_hash=hashlib.sha256(b"demo_import_file_content").hexdigest(),
        file_path=None,
        notes="Demo seed import",
        row_count=len(subset),
        created_count=len(subset),
        linked_count=len(subset),
        duplicate_count=0,
        error_count=0,
    )
    db.add(imp)
    db.flush()

    for idx, tx in enumerate(subset):
        raw_json = {
            "dateOp": tx.posted_at.isoformat(),
            "dateVal": tx.operation_at.isoformat(),
            "label": tx.label_raw,
            "category": "",
            "categoryParent": "",
            "supplierFound": tx.supplier_raw or "",
            "amount": str(tx.amount),
            "comment": "",
            "accountNum": account.account_num,
            "accountLabel": account.label,
            "accountbalance": "0",
        }
        row_hash = hashlib.sha256(json.dumps(raw_json, sort_keys=True).encode()).hexdigest()

        import_row = ImportRow(
            import_id=imp.id,
            row_hash=row_hash,
            raw_json=raw_json,
            date_op=tx.posted_at,
            date_val=tx.operation_at,
            label_raw=tx.label_raw,
            supplier_raw=tx.supplier_raw,
            amount=tx.amount,
            currency="EUR",
            category_raw=None,
            category_parent_raw=None,
            comment_raw=None,
            balance_after=None,
            status=ImportRowStatus.linked,
        )
        db.add(import_row)
        db.flush()

        link = ImportRowLink(
            import_row_id=import_row.id,
            transaction_id=tx.id,
        )
        db.add(link)

    db.flush()
    return imp


def seed_moment_candidates(
    db: Session,
    moments: dict[str, Moment],
    deferred_splits: list[_DeferredSplit],
) -> list[MomentCandidate]:
    """Create MomentCandidate records for splits in moment date ranges."""
    candidates: list[MomentCandidate] = []
    now = datetime.now(timezone.utc)

    moment_list = [
        (moments["summer"].id, moments["summer"].start_date, moments["summer"].end_date),
        (moments["xmas"].id, moments["xmas"].start_date, moments["xmas"].end_date),
    ]

    statuses = ["pending", "accepted", "rejected"]

    for moment_id, m_start, m_end in moment_list:
        # Find splits whose transaction falls in the moment date range
        eligible: list[Split] = []
        for ds in deferred_splits:
            if ds.split_obj is None:
                continue
            tx_date = ds.tx_ref.posted_at
            if m_start <= tx_date <= m_end:
                eligible.append(ds.split_obj)

        # Pick 10-15 candidates (or all if fewer)
        count = min(RNG.randint(10, 15), len(eligible))
        selected = RNG.sample(eligible, count) if eligible else []

        seen_split_ids: set[int] = set()
        for split in selected:
            if split.id in seen_split_ids:
                continue
            seen_split_ids.add(split.id)

            status = RNG.choice(statuses)
            decided_at = now if status != "pending" else None
            decided_by = "demo_seed" if status != "pending" else None

            mc = MomentCandidate(
                moment_id=moment_id,
                split_id=split.id,
                status=status,
                decided_at=decided_at,
                decided_by=decided_by,
            )
            candidates.append(mc)

    db.add_all(candidates)
    db.flush()
    return candidates


# ---------------------------------------------------------------------------
# Read-only role setup
# ---------------------------------------------------------------------------

def _setup_demo_app_role():
    password = os.environ.get("DEMO_APP_PASSWORD")
    if not password:
        print("DEMO_APP_PASSWORD not set, skipping role setup.")
        return

    import psycopg
    from psycopg import sql

    dsn = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn, autocommit=True) as conn:
        # Check if role exists
        exists = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = 'demo_app'"
        ).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE ROLE demo_app WITH LOGIN PASSWORD {}").format(sql.Literal(password)))
        else:
            conn.execute(sql.SQL("ALTER ROLE demo_app WITH PASSWORD {}").format(sql.Literal(password)))
        conn.execute("GRANT CONNECT ON DATABASE personal_expense_demo TO demo_app")
        conn.execute("GRANT USAGE ON SCHEMA public TO demo_app")
        conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO demo_app")
        conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO demo_app")
        conn.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO demo_app")
    print("demo_app role configured (read-only).")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    db: Session = SessionLocal()
    try:
        # 1. Seed category catalog
        print("Seeding native categories...")
        seed_native_categories(db)

        # 2. Idempotency check
        existing = db.query(Account).first()
        if existing is not None:
            print("Demo data already seeded (accounts exist). Exiting.")
            db.close()
            return

        print("Seeding demo data...")

        # 3. User profile
        seed_user_profile(db)
        print("  User profile: Virtual Calou")

        # 4. Accounts
        accounts = seed_accounts(db)
        print(f"  Accounts: {len(accounts)}")

        # 5. Counterparties
        counterparties = seed_counterparties(db)
        print(f"  Counterparties: {len(counterparties)}")

        # 6. Moments
        moments = seed_moments(db)
        print(f"  Moments: {len(moments)}")

        # 7. Build category map from DB
        cat_map = _build_category_map(db)
        print(f"  Category mappings: {len(cat_map)}")

        # 8. Rules
        rules = seed_rules(db, cat_map)
        print(f"  Rules: {len(rules)}")

        # 9. Transactions + splits
        # We need to collect the deferred splits for moment candidates
        # Temporarily capture them via a wrapper
        transactions = seed_transactions(db, accounts, counterparties, moments, cat_map)
        print(f"  Transactions: {len(transactions)}")

        # Gather deferred splits from the module-level call (we need to refactor slightly)
        # Actually, seed_transactions stores _DeferredSplit internally. Let's re-collect splits from DB.
        all_splits_db = db.query(Split).all()
        print(f"  Splits: {len(all_splits_db)}")

        # 9. Import + import rows + links
        imp = seed_import(db, accounts["checking"], transactions)
        print(f"  Import rows: {imp.row_count}")

        # 10. Moment candidates
        # Build deferred-split-like objects from DB data for moment candidate generation
        # We need transaction dates, so query joins
        _deferred_for_candidates: list[_DeferredSplit] = []
        for s in all_splits_db:
            tx = s.transaction
            ds = _DeferredSplit(tx_ref=tx, amount=s.amount, category_id=s.category_id, moment_id=s.moment_id)
            ds.split_obj = s
            _deferred_for_candidates.append(ds)

        mc_list = seed_moment_candidates(db, moments, _deferred_for_candidates)
        print(f"  Moment candidates: {len(mc_list)}")

        # Commit everything
        db.commit()
        print("Demo data committed successfully.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # 11. Set up read-only role (outside ORM session)
    _setup_demo_app_role()

    print("Done.")


if __name__ == "__main__":
    main()
