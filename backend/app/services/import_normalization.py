from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..models import TransactionType


_TRANSFER_KEYWORDS = ("livret a", "epargne", "revolut")
_REFUND_KEYWORDS = (
    "refund",
    "refunded",
    "annulation",
    "annule",
    "retour",
    "avoir",
    "chargeback",
    "reversal",
    "storno",
)


def parse_amount_fr(raw: str) -> Decimal:
    if raw is None:
        raise ValueError("amount is required")
    value = raw.strip()
    if not value:
        raise ValueError("amount is empty")
    normalized = re.sub(r"\s+", "", value).replace(",", ".")
    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount: {raw}") from exc


def parse_date(raw: str) -> date:
    if raw is None:
        raise ValueError("date is required")
    value = raw.strip()
    if not value:
        raise ValueError("date is empty")
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date: {raw}")


def normalize_label(raw: str) -> str:
    if raw is None:
        return ""
    value = raw.strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"^carte\s+\d{2}/\d{2}/\d{2}\s+", "", value)
    value = re.sub(r"\s+cb\*\d{4}$", "", value)
    return value.strip()


def infer_type(label_norm: str, amount: Decimal) -> TransactionType:
    label = (label_norm or "").strip().lower()

    if amount > 0 and any(keyword in label for keyword in _REFUND_KEYWORDS):
        return TransactionType.refund

    if label.startswith("carte"):
        return TransactionType.refund if amount > 0 else TransactionType.expense

    if label.startswith("prlv sepa"):
        return TransactionType.income if amount > 0 else TransactionType.expense

    if label.startswith("vir sepa") or label.startswith("vir inst") or "virement" in label:
        if any(keyword in label for keyword in _TRANSFER_KEYWORDS):
            return TransactionType.transfer
        return TransactionType.income if amount > 0 else TransactionType.expense

    if any(keyword in label for keyword in _TRANSFER_KEYWORDS):
        return TransactionType.transfer

    return TransactionType.income if amount > 0 else TransactionType.expense


def infer_payee(supplier_found: str | None, label_raw: str | None) -> str | None:
    if supplier_found:
        cleaned = supplier_found.strip()
        return cleaned or None

    if not label_raw:
        return None

    value = label_raw.strip()
    lower = value.lower()

    patterns = [
        r"^prlv sepa\s+",
        r"^vir sepa\s+",
        r"^vir inst\s+",
        r"^virement\s+",
        r"^carte\s+\d{2}/\d{2}/\d{2}\s+",
        r"^avoir\s+",
    ]
    for pattern in patterns:
        if re.match(pattern, lower):
            return re.sub(pattern, "", value, flags=re.IGNORECASE).strip() or None

    return value or None


def compute_row_hash(row: dict) -> str:
    normalized = {key: _normalize_value(value) for key, value in row.items()}
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_fingerprint(account_num: str, posted_at: date, amount: Decimal, label_norm_core: str) -> str:
    normalized_amount = amount.quantize(Decimal("0.01"))
    payload = f"{account_num}|{posted_at.isoformat()}|{normalized_amount}|{label_norm_core}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return value
