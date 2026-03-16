from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any


_SPLIT_DECIMAL = Decimal("0.01")


class SplitValidationError(Exception):
    """Structured validation error for split operations."""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra

    def to_detail(self) -> dict[str, Any]:
        detail: dict[str, Any] = {"code": self.code, "message": self.message}
        detail.update(self.extra)
        return detail


def normalize_payee_display_name(name: str) -> str:
    value = re.sub(r"\s+", " ", (name or "").strip())
    if not value:
        return ""
    return " ".join(part[:1].upper() + part[1:].lower() for part in value.split(" "))


def canonicalize_payee_name(name: str) -> str:
    value = (name or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def parse_decimal_2(amount: str | int | float | Decimal) -> Decimal:
    if isinstance(amount, Decimal):
        value = amount
    else:
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("amount must be a valid decimal") from exc

    try:
        quantized = value.quantize(_SPLIT_DECIMAL)
    except InvalidOperation as exc:
        raise ValueError("amount must be a valid decimal") from exc

    if quantized != value:
        raise ValueError("amount must have at most 2 decimal places")

    return quantized


def validate_splits(transaction_amount: Decimal, splits: list[dict]) -> list[dict]:
    if not splits:
        return []

    normalized: list[dict] = []
    split_sum = Decimal("0.00")

    for index, split in enumerate(splits):
        try:
            amount = parse_decimal_2(split.get("amount"))
        except ValueError as exc:
            raise SplitValidationError(
                code="SPLIT_AMOUNT_INVALID",
                message=str(exc),
                split_index=index,
                path=f"splits[{index}].amount",
            ) from exc
        if transaction_amount < 0 and amount > 0:
            raise SplitValidationError(
                code="SPLIT_SIGN_MISMATCH",
                message="Split amounts must match transaction sign",
                split_index=index,
                path=f"splits[{index}].amount",
            )
        if transaction_amount > 0 and amount < 0:
            raise SplitValidationError(
                code="SPLIT_SIGN_MISMATCH",
                message="Split amounts must match transaction sign",
                split_index=index,
                path=f"splits[{index}].amount",
            )

        split_sum += amount
        normalized.append({**split, "amount": amount})

    if split_sum != transaction_amount:
        raise SplitValidationError(
            code="SPLIT_SUM_MISMATCH",
            message="Split total must equal transaction amount",
        )

    return normalized
