from datetime import date
from decimal import Decimal

from app.models import TransactionType
from app.services.import_normalization import compute_fingerprint, infer_type, normalize_label, parse_amount_fr, parse_date


def test_parse_amount_fr_handles_spaces_and_commas():
    assert parse_amount_fr("2 848,02") == Decimal("2848.02")
    assert parse_amount_fr("-1 300,00") == Decimal("-1300.00")


def test_normalize_label_strips_card_prefix_and_cb_suffix():
    value = "CARTE 12/01/24 STARBUCKS CB*1234"
    assert normalize_label(value) == "starbucks"


def test_compute_fingerprint_is_stable():
    fingerprint = compute_fingerprint("ACC-1", date(2024, 1, 2), Decimal("-10.00"), "carte test")
    assert fingerprint == compute_fingerprint("ACC-1", date(2024, 1, 2), Decimal("-10.00"), "carte test")


def test_parse_date_handles_iso_format():
    assert parse_date("2025-12-30") == date(2025, 12, 30)


def test_infer_type_detects_refund_keywords_for_positive_amounts():
    assert infer_type("refund amazon", Decimal("12.00")) == TransactionType.refund
    assert infer_type("annulation billet train", Decimal("8.50")) == TransactionType.refund
    assert infer_type("retour marchand", Decimal("15.20")) == TransactionType.refund
    assert infer_type("avoir magasin", Decimal("4.00")) == TransactionType.refund


def test_infer_type_does_not_force_refund_when_amount_is_negative():
    assert infer_type("refund correction", Decimal("-9.00")) == TransactionType.expense
