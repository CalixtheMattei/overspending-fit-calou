from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Account, Import, ImportRow, ImportRowLink, ImportRowStatus, Transaction, TransactionType
from .automatic_payee_mapping import build_automatic_payee_lookup
from .import_normalization import (
    compute_fingerprint,
    compute_row_hash,
    infer_payee,
    infer_type,
    normalize_label,
    parse_amount_fr,
    parse_date,
)
from .ledger_validation import canonicalize_payee_name
from .rules_engine import run_rules_for_import_created_transactions


@dataclass(slots=True)
class ImportStats:
    row_count: int = 0
    created_count: int = 0
    linked_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0


@dataclass(slots=True)
class ImportResult:
    import_record: Import
    stats: ImportStats


EXPECTED_HEADERS = {
    "dateop": "dateOp",
    "dateval": "dateVal",
    "label": "label",
    "category": "category",
    "categoryparent": "categoryParent",
    "supplierfound": "supplierFound",
    "amount": "amount",
    "comment": "comment",
    "accountnum": "accountNum",
    "accountlabel": "accountLabel",
    "accountbalance": "accountbalance",
}


def import_csv_bytes(db: Session, file_name: str, file_bytes: bytes) -> ImportResult:
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    rows = _read_rows(file_bytes)

    if not rows:
        raise ValueError("CSV file is empty or missing headers")

    account_numbers = {row.get("accountNum") for row in rows if row.get("accountNum")}
    if not account_numbers:
        raise ValueError("CSV file does not contain accountNum values")

    primary_account_num = sorted(account_numbers)[0]
    account = _get_or_create_account(db, primary_account_num, rows)

    import_record = Import(account_id=account.id, file_name=file_name, file_hash=file_hash)
    db.add(import_record)
    db.flush()
    import_record.file_path = _store_import_file(file_bytes, file_name, import_record.id)

    stats = ImportStats()
    seen_row_hashes: set[str] = set()
    automatic_payee_lookup = build_automatic_payee_lookup(db)

    for row in rows:
        stats.row_count += 1
        raw_json = row.copy()
        row_hash = compute_row_hash(raw_json)

        if row_hash in seen_row_hashes:
            stats.duplicate_count += 1
            continue
        seen_row_hashes.add(row_hash)

        account_num = row.get("accountNum")
        if not account_num:
            _store_error_row(
                db,
                import_record.id,
                row_hash,
                raw_json,
                error_code="missing_account",
                error_message="accountNum is missing",
            )
            stats.error_count += 1
            continue

        if account_num != primary_account_num:
            _store_error_row(
                db,
                import_record.id,
                row_hash,
                raw_json,
                error_code="multiple_accounts",
                error_message=f"accountNum {account_num} does not match primary account",
            )
            stats.error_count += 1
            continue

        try:
            date_op = parse_date(row.get("dateOp", ""))
            date_val = parse_date(row.get("dateVal", ""))
            amount = parse_amount_fr(row.get("amount", ""))
        except ValueError as exc:
            _store_error_row(
                db,
                import_record.id,
                row_hash,
                raw_json,
                error_code="parse_error",
                error_message=str(exc),
                date_op=None,
                date_val=None,
                amount=None,
            )
            stats.error_count += 1
            continue

        label_raw = row.get("label", "")
        supplier_raw = row.get("supplierFound")
        label_norm = normalize_label(label_raw)
        tx_type = infer_type(label_norm, amount)
        inferred_payee = infer_payee(supplier_raw, label_raw)
        inferred_payee_canonical = canonicalize_payee_name(inferred_payee or "")
        mapped_payee_id = automatic_payee_lookup.get(inferred_payee_canonical) if inferred_payee_canonical else None

        fingerprint = compute_fingerprint(primary_account_num, date_val, amount, label_norm)

        transaction, created = _get_or_create_transaction(
            db,
            account.id,
            date_val,
            date_op,
            amount,
            label_raw,
            label_norm,
            supplier_raw,
            tx_type,
            fingerprint,
            mapped_payee_id,
        )

        import_row = ImportRow(
            import_id=import_record.id,
            row_hash=row_hash,
            raw_json=raw_json,
            date_op=date_op,
            date_val=date_val,
            label_raw=label_raw,
            supplier_raw=supplier_raw,
            amount=amount,
            currency="EUR",
            category_raw=row.get("category"),
            category_parent_raw=row.get("categoryParent"),
            comment_raw=row.get("comment"),
            balance_after=_parse_optional_amount(row.get("accountbalance")),
            status=ImportRowStatus.created if created else ImportRowStatus.linked,
        )
        db.add(import_row)

        link = ImportRowLink(import_row=import_row, transaction=transaction)
        db.add(link)

        if created:
            stats.created_count += 1
        else:
            stats.linked_count += 1

    import_record.row_count = stats.row_count
    import_record.created_count = stats.created_count
    import_record.linked_count = stats.linked_count
    import_record.duplicate_count = stats.duplicate_count
    import_record.error_count = stats.error_count

    if stats.created_count > 0:
        run_rules_for_import_created_transactions(db, import_record.id)

    db.commit()
    db.refresh(import_record)

    return ImportResult(import_record=import_record, stats=stats)


def preview_import_csv_bytes(db: Session, file_name: str, file_bytes: bytes) -> ImportStats:
    _ = file_name
    rows = _read_rows(file_bytes)

    if not rows:
        raise ValueError("CSV file is empty or missing headers")

    account_numbers = {row.get("accountNum") for row in rows if row.get("accountNum")}
    if not account_numbers:
        raise ValueError("CSV file does not contain accountNum values")

    primary_account_num = sorted(account_numbers)[0]

    stats = ImportStats()
    seen_row_hashes: set[str] = set()
    fingerprints: list[str] = []

    for row in rows:
        stats.row_count += 1
        raw_json = row.copy()
        row_hash = compute_row_hash(raw_json)

        if row_hash in seen_row_hashes:
            stats.duplicate_count += 1
            continue
        seen_row_hashes.add(row_hash)

        account_num = row.get("accountNum")
        if not account_num:
            stats.error_count += 1
            continue

        if account_num != primary_account_num:
            stats.error_count += 1
            continue

        try:
            parse_date(row.get("dateOp", ""))
            date_val = parse_date(row.get("dateVal", ""))
            amount = parse_amount_fr(row.get("amount", ""))
        except ValueError:
            stats.error_count += 1
            continue

        label_norm = normalize_label(row.get("label", ""))
        fingerprint = compute_fingerprint(primary_account_num, date_val, amount, label_norm)
        fingerprints.append(fingerprint)

    existing_fingerprints: set[str]
    if fingerprints:
        unique_fingerprints = set(fingerprints)
        existing_rows = (
            db.query(Transaction.fingerprint)
            .filter(Transaction.fingerprint.in_(unique_fingerprints))
            .all()
        )
        existing_fingerprints = {row[0] for row in existing_rows}
    else:
        existing_fingerprints = set()

    seen_new_fingerprints: set[str] = set()
    for fingerprint in fingerprints:
        if fingerprint in existing_fingerprints or fingerprint in seen_new_fingerprints:
            stats.linked_count += 1
        else:
            stats.created_count += 1
            seen_new_fingerprints.add(fingerprint)

    return stats


def _store_import_file(file_bytes: bytes, file_name: str, import_id: int) -> str:
    storage_dir = Path(settings.imports_storage_dir or "data/imports")
    storage_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file_name)
    stored_name = f"{import_id:06d}_{safe_name}"
    file_path = storage_dir / stored_name

    try:
        file_path.write_bytes(file_bytes)
    except OSError as exc:
        raise ValueError("Failed to store import file") from exc

    return stored_name


def _safe_filename(file_name: str) -> str:
    base = Path(file_name or "import.csv").name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not sanitized:
        sanitized = "import.csv"
    return sanitized[:120]


def _read_rows(file_bytes: bytes) -> list[dict[str, str]]:
    text = _decode_bytes(file_bytes)
    sample = text[:4096]
    delimiter = _detect_delimiter(sample)

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if reader.fieldnames is None:
        return []

    normalized_headers = {header: _normalize_header(header) for header in reader.fieldnames}
    mapping = {header: EXPECTED_HEADERS.get(normalized) for header, normalized in normalized_headers.items()}

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        canonical_row: dict[str, str] = {}
        for header, value in raw_row.items():
            key = mapping.get(header)
            if not key:
                continue
            canonical_row[key] = (value or "").strip()
        rows.append(canonical_row)
    return rows


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";"])
        return dialect.delimiter
    except csv.Error:
        if sample.count("\t") >= sample.count(","):
            return "\t"
        return ","


def _normalize_header(header: str) -> str:
    return "".join(char for char in header.lower() if char.isalnum())


def _decode_bytes(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("latin-1", errors="replace")


def _get_or_create_account(db: Session, account_num: str, rows: Iterable[dict[str, str]]) -> Account:
    account = db.query(Account).filter_by(account_num=account_num).one_or_none()
    if account:
        return account

    label = ""
    for row in rows:
        label = row.get("accountLabel") or ""
        if label:
            break
    if not label:
        label = f"Account {account_num}"

    account = Account(account_num=account_num, label=label)
    db.add(account)
    db.flush()
    return account


def _get_or_create_transaction(
    db: Session,
    account_id: int,
    posted_at,
    operation_at,
    amount: Decimal,
    label_raw: str,
    label_norm: str,
    supplier_raw: str | None,
    tx_type: TransactionType,
    fingerprint: str,
    payee_id: int | None = None,
) -> tuple[Transaction, bool]:
    existing = db.query(Transaction).filter_by(fingerprint=fingerprint).one_or_none()
    if existing:
        return existing, False

    transaction = Transaction(
        account_id=account_id,
        posted_at=posted_at,
        operation_at=operation_at,
        amount=amount,
        currency="EUR",
        label_raw=label_raw,
        label_norm=label_norm,
        supplier_raw=supplier_raw,
        payee_id=payee_id,
        type=tx_type,
        fingerprint=fingerprint,
    )
    db.add(transaction)
    db.flush()
    return transaction, True


def _store_error_row(
    db: Session,
    import_id: int,
    row_hash: str,
    raw_json: dict[str, str],
    error_code: str,
    error_message: str,
    date_op=None,
    date_val=None,
    amount=None,
) -> None:
    import_row = ImportRow(
        import_id=import_id,
        row_hash=row_hash,
        raw_json=raw_json,
        date_op=date_op,
        date_val=date_val,
        label_raw=raw_json.get("label", ""),
        supplier_raw=raw_json.get("supplierFound"),
        amount=amount,
        currency="EUR",
        category_raw=raw_json.get("category"),
        category_parent_raw=raw_json.get("categoryParent"),
        comment_raw=raw_json.get("comment"),
        balance_after=_parse_optional_amount(raw_json.get("accountbalance")),
        status=ImportRowStatus.error,
        error_code=error_code,
        error_message=error_message,
    )
    db.add(import_row)


def _parse_optional_amount(raw: str | None) -> Decimal | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return parse_amount_fr(raw)
    except ValueError:
        return None
