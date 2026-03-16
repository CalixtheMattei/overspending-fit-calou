from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models import Account, Category, Rule, RuleRunBatch, RuleRunEffect, Split, Transaction, TransactionType
from app.services.import_service import import_csv_bytes
from app.services.category_catalog import seed_native_categories
from app.services.rules_engine import (
    RuleExecutionScope,
    confirm_rule_delete,
    preview_rule_impact,
    preview_rule_delete,
    run_rules_batch,
)


def _create_account(db_session, suffix: str) -> Account:
    account = Account(account_num=f"ACC-{suffix}", label=f"Account {suffix}")
    db_session.add(account)
    db_session.flush()
    return account


def _create_transaction(
    db_session,
    *,
    account: Account,
    amount: Decimal,
    label_raw: str,
    label_norm: str,
    fingerprint: str,
) -> Transaction:
    transaction = Transaction(
        account_id=account.id,
        posted_at=date(2024, 2, 2),
        operation_at=date(2024, 2, 1),
        amount=amount,
        currency="EUR",
        label_raw=label_raw,
        label_norm=label_norm,
        supplier_raw=None,
        payee_id=None,
        type=TransactionType.expense if amount < 0 else TransactionType.income,
        fingerprint=fingerprint,
    )
    db_session.add(transaction)
    db_session.flush()
    return transaction


def _create_category(db_session, name: str) -> Category:
    category = Category(name=name, color="#9CA3AF", icon="tag", is_custom=True)
    db_session.add(category)
    db_session.flush()
    return category


def _create_rule(db_session, *, name: str, token: str, category_id: int, priority: int = 1) -> Rule:
    rule = Rule(
        name=name,
        priority=priority,
        enabled=True,
        matcher_json={"all": [{"predicate": "label_contains", "value": token}]},
        action_json={"set_category": category_id},
    )
    db_session.add(rule)
    db_session.flush()
    return rule


def test_run_rules_apply_creates_single_split_and_lineage(db_session):
    account = _create_account(db_session, "rules-apply")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-24.00"),
        label_raw="NETFLIX FEB",
        label_norm="netflix feb",
        fingerprint="rules-apply-fp",
    )
    category = _create_category(db_session, "Subscriptions")
    _create_rule(db_session, name="Netflix", token="netflix", category_id=category.id)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    assert batch.summary_json is not None
    assert batch.summary_json["applied"] == 1

    splits = db_session.query(Split).filter(Split.transaction_id == transaction.id).all()
    assert len(splits) == 1
    assert splits[0].category_id == category.id
    assert splits[0].amount == Decimal("-24.00")

    effect = (
        db_session.query(RuleRunEffect)
        .filter(RuleRunEffect.batch_id == batch.id, RuleRunEffect.transaction_id == transaction.id)
        .one()
    )
    assert effect.status == "applied"
    assert effect.change_json is not None
    assert effect.change_json["split_operations"]


def test_fill_missing_blocks_split_overwrite_without_flag(db_session):
    account = _create_account(db_session, "rules-no-overwrite")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-50.00"),
        label_raw="COFFEE SHOP",
        label_norm="coffee shop",
        fingerprint="rules-no-overwrite-fp",
    )
    category_existing = _create_category(db_session, "Food")
    category_target = _create_category(db_session, "Transport")
    db_session.add(
        Split(
            transaction_id=transaction.id,
            amount=Decimal("-50.00"),
            category_id=category_existing.id,
            moment_id=None,
            internal_account_id=None,
            note=None,
            position=0,
        )
    )
    _create_rule(db_session, name="Coffee", token="coffee", category_id=category_target.id)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    effect = (
        db_session.query(RuleRunEffect)
        .filter(RuleRunEffect.batch_id == batch.id, RuleRunEffect.transaction_id == transaction.id)
        .one()
    )
    assert effect.status == "matched_noop"
    assert effect.reason_code == "SPLITS_ALREADY_EXIST"

    split = db_session.query(Split).filter(Split.transaction_id == transaction.id).one()
    assert split.category_id == category_existing.id


def test_destructive_mode_overwrites_existing_split_when_allowed(db_session):
    account = _create_account(db_session, "rules-overwrite")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-45.00"),
        label_raw="METRO PASS",
        label_norm="metro pass",
        fingerprint="rules-overwrite-fp",
    )
    category_existing = _create_category(db_session, "Commuting Old")
    category_target = _create_category(db_session, "Commuting New")
    db_session.add(
        Split(
            transaction_id=transaction.id,
            amount=Decimal("-45.00"),
            category_id=category_existing.id,
            moment_id=None,
            internal_account_id=None,
            note=None,
            position=0,
        )
    )
    _create_rule(db_session, name="Metro", token="metro", category_id=category_target.id)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=True,
        trigger_type="manual_scope",
    )
    db_session.flush()

    effect = (
        db_session.query(RuleRunEffect)
        .filter(RuleRunEffect.batch_id == batch.id, RuleRunEffect.transaction_id == transaction.id)
        .one()
    )
    assert effect.status == "applied"

    split = db_session.query(Split).filter(Split.transaction_id == transaction.id).one()
    assert split.category_id == category_target.id


def test_first_match_stops_subsequent_rules_for_transaction(db_session):
    account = _create_account(db_session, "rules-first-match")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-31.00"),
        label_raw="SAME LABEL",
        label_norm="same label",
        fingerprint="rules-first-match-fp",
    )
    category_one = _create_category(db_session, "First Category")
    category_two = _create_category(db_session, "Second Category")
    _create_rule(db_session, name="Rule 1", token="same", category_id=category_one.id, priority=1)
    _create_rule(db_session, name="Rule 2", token="same", category_id=category_two.id, priority=2)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    effects = (
        db_session.query(RuleRunEffect)
        .filter(RuleRunEffect.batch_id == batch.id, RuleRunEffect.transaction_id == transaction.id)
        .all()
    )
    assert len(effects) == 1
    assert effects[0].status == "applied"

    split = db_session.query(Split).filter(Split.transaction_id == transaction.id).one()
    assert split.category_id == category_one.id


def test_run_rules_batch_can_target_selected_rule_ids(db_session):
    account = _create_account(db_session, "rules-selective")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-18.00"),
        label_raw="SELECTIVE LABEL",
        label_norm="selective label",
        fingerprint="rules-selective-fp",
    )
    category_one = _create_category(db_session, "Selective One")
    category_two = _create_category(db_session, "Selective Two")
    rule_one = _create_rule(db_session, name="Rule One", token="selective", category_id=category_one.id, priority=1)
    rule_two = _create_rule(db_session, name="Rule Two", token="selective", category_id=category_two.id, priority=2)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
        rule_ids=[rule_two.id],
    )
    db_session.flush()

    effect = (
        db_session.query(RuleRunEffect)
        .filter(RuleRunEffect.batch_id == batch.id, RuleRunEffect.transaction_id == transaction.id)
        .one()
    )
    assert effect.rule_id == rule_two.id
    assert effect.rule_id != rule_one.id

    split = db_session.query(Split).filter(Split.transaction_id == transaction.id).one()
    assert split.category_id == category_two.id


def test_preview_rule_impact_is_deterministic_and_non_mutating(db_session):
    account = _create_account(db_session, "rules-preview")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-11.50"),
        label_raw="PREVIEW LABEL",
        label_norm="preview label",
        fingerprint="rules-preview-fp",
    )
    category = _create_category(db_session, "Preview Category")

    preview = preview_rule_impact(
        db_session,
        scope=RuleExecutionScope(type="all"),
        matcher_json={"all": [{"predicate": "label_contains", "value": "preview"}]},
        action_json={"set_category": category.id},
        allow_overwrite=False,
        limit=10,
        offset=0,
    )

    assert preview["transactions_scanned"] == 1
    assert preview["transactions_matched"] == 1
    assert preview["transactions_changed"] == 1
    assert preview["match_count"] == 1
    assert len(preview["rows"]) == 1
    assert preview["rows"][0]["transaction_id"] == transaction.id
    assert preview["rows"][0]["before"]["has_splits"] is False
    assert preview["rows"][0]["after"]["category_id"] == category.id

    assert db_session.query(Split).filter(Split.transaction_id == transaction.id).count() == 0
    assert db_session.query(RuleRunBatch).count() == 0


def test_dry_run_persists_effects_without_mutating_transaction(db_session):
    account = _create_account(db_session, "rules-dry")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-19.99"),
        label_raw="SPOTIFY",
        label_norm="spotify",
        fingerprint="rules-dry-fp",
    )
    category = _create_category(db_session, "Music")
    _create_rule(db_session, name="Spotify", token="spotify", category_id=category.id)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="dry_run",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    assert batch.mode == "dry_run"
    assert db_session.query(Split).filter(Split.transaction_id == transaction.id).count() == 0

    effect = (
        db_session.query(RuleRunEffect)
        .filter(RuleRunEffect.batch_id == batch.id, RuleRunEffect.transaction_id == transaction.id)
        .one()
    )
    assert effect.status == "applied"
    assert effect.before_json is not None
    assert effect.after_json is not None


def test_import_auto_run_applies_only_to_created_transactions(db_session):
    category = _create_category(db_session, "Auto Category")
    _create_rule(db_session, name="SNCF", token="sncf", category_id=category.id)

    csv_data = (
        "dateOp\tdateVal\tlabel\tcategory\tcategoryParent\tsupplierFound\tamount\tcomment\taccountNum\taccountLabel\taccountbalance\n"
        "01/01/2024\t02/01/2024\tSNCF-VOYAGEURS\tTravel\tTrain\tsncf\t-12,50\t\tACC-RULE-IMPORT\tMain\t1000,00\n"
    )

    first = import_csv_bytes(db_session, "rules-import.csv", csv_data.encode("utf-8"))
    assert first.stats.created_count == 1
    tx = db_session.query(Transaction).filter(Transaction.fingerprint.is_not(None)).order_by(Transaction.id.desc()).first()
    assert tx is not None
    assert db_session.query(Split).filter(Split.transaction_id == tx.id).count() == 1

    batches_after_first = db_session.query(RuleRunBatch).count()
    assert batches_after_first == 1

    second = import_csv_bytes(db_session, "rules-import.csv", csv_data.encode("utf-8"))
    assert second.stats.created_count == 0
    assert second.stats.linked_count == 1

    batches_after_second = db_session.query(RuleRunBatch).count()
    assert batches_after_second == 1


def test_delete_preview_and_confirm_safe_rollback(db_session):
    account = _create_account(db_session, "rules-delete")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-40.00"),
        label_raw="GYM MEMBERSHIP",
        label_norm="gym membership",
        fingerprint="rules-delete-fp",
    )
    category = _create_category(db_session, "Fitness")
    rule = _create_rule(db_session, name="Gym", token="gym", category_id=category.id)

    run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    preview = preview_rule_delete(db_session, rule=rule)
    assert preview.total_impacted == 1
    assert preview.reverted_to_uncategorized == 1

    summary = confirm_rule_delete(db_session, rule=rule, rollback=True)
    db_session.flush()
    assert summary["deleted"] is True
    assert summary["reverted_to_uncategorized"] == 1

    assert db_session.query(Rule).filter(Rule.id == rule.id).one_or_none() is None
    assert db_session.query(Split).filter(Split.transaction_id == transaction.id).count() == 0


def test_delete_preview_marks_conflict_after_manual_edit(db_session):
    account = _create_account(db_session, "rules-conflict")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-65.00"),
        label_raw="BOOK STORE",
        label_norm="book store",
        fingerprint="rules-conflict-fp",
    )
    category_one = _create_category(db_session, "Books")
    category_two = _create_category(db_session, "Other")
    rule = _create_rule(db_session, name="Books", token="book", category_id=category_one.id)

    run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    db_session.query(Split).filter(Split.transaction_id == transaction.id).delete()
    db_session.add(
        Split(
            transaction_id=transaction.id,
            amount=Decimal("-65.00"),
            category_id=category_two.id,
            moment_id=None,
            internal_account_id=None,
            note=None,
            position=0,
        )
    )
    db_session.flush()

    preview = preview_rule_delete(db_session, rule=rule)
    assert preview.total_impacted == 1
    assert preview.reverted_to_uncategorized == 0
    assert preview.skipped_conflict == 1


def test_rules_engine_canonicalizes_deprecated_category_on_apply(db_session):
    seed_native_categories(db_session)

    account = _create_account(db_session, "rules-canonicalize")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("-24.00"),
        label_raw="VIDEO SUBSCRIPTION",
        label_norm="video subscription",
        fingerprint="rules-canonicalize-fp",
    )

    deprecated = (
        db_session.query(Category)
        .filter(Category.source == "native_catalog", Category.source_ref == "31428")
        .one()
    )
    canonical = (
        db_session.query(Category)
        .filter(Category.source == "native_catalog", Category.source_ref == "31382")
        .one()
    )
    _create_rule(db_session, name="Subscriptions", token="subscription", category_id=deprecated.id)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    assert batch.summary_json is not None
    assert batch.summary_json["applied"] == 1
    split = db_session.query(Split).filter(Split.transaction_id == transaction.id).one()
    assert split.category_id == canonical.id


def test_rules_engine_blocks_business_branch_assignment_for_income_transactions(db_session):
    seed_native_categories(db_session)

    account = _create_account(db_session, "rules-income-business-guard")
    transaction = _create_transaction(
        db_session,
        account=account,
        amount=Decimal("120.00"),
        label_raw="BUSINESS INCOME",
        label_norm="business income",
        fingerprint="rules-income-business-guard-fp",
    )
    transaction.type = TransactionType.income
    db_session.flush()

    business_category = (
        db_session.query(Category)
        .filter(Category.source == "native_catalog", Category.source_ref == "31383")
        .one()
    )
    _create_rule(db_session, name="Business income", token="income", category_id=business_category.id)

    batch = run_rules_batch(
        db_session,
        scope=RuleExecutionScope(type="all"),
        mode="apply",
        allow_overwrite=False,
        trigger_type="manual_scope",
    )
    db_session.flush()

    effect = (
        db_session.query(RuleRunEffect)
        .filter(RuleRunEffect.batch_id == batch.id, RuleRunEffect.transaction_id == transaction.id)
        .one()
    )
    assert effect.status == "error"
    assert effect.reason_code == "VALIDATION_FAILED"
    assert db_session.query(Split).filter(Split.transaction_id == transaction.id).count() == 0
