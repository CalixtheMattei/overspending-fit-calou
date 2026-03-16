# PRD-003 Rules Engine Implementation Plan (Deterministic v1)

## 1. Title + Purpose
This document defines the implementation plan for PRD-003 with deterministic, inspectable rule execution.

Scope:
1. Auto-map payees, categories, transaction type, moments, and split templates.
2. Reuse Finary-exported rules from `docs/transactions_rules.json`.
3. Bootstrap and map categories from `docs/configuration_categories.json`.
4. Guarantee full retraceability of which rules impacted which transactions and splits.
5. Support safe rollback-to-uncategorized behavior when deleting a rule.

## 2. Current System Context
Current behavior in the app:
1. Import creates/links canonical transactions and stores append-only raw rows.
2. Splits are edited through `PUT /transactions/{id}/splits` and validated strictly.
3. Rules exist at schema/model level (`rules`, `rule_runs`) but no runtime rules engine or rules API is implemented yet.
4. Rules UI is currently an empty-state placeholder.

Key invariants that must remain unchanged:
1. `splits=[]` means uncategorized.
2. If splits exist, split amounts must match transaction sign.
3. If splits exist, split amounts must sum exactly to transaction amount.
4. Split amount precision is max 2 decimals.

Reviewed references:
1. `docs/PRD-003-rules-engine.md`
2. `docs/PRD-002-transactions-splits-payees.md`
3. `docs/TRANSACTIONS_AND_SPLITS.md`
4. `docs/transactions-splits-system-audit-2026-02-06.md`
5. `backend/app/services/import_service.py`
6. `backend/app/routers/transactions.py`
7. `backend/app/services/ledger_validation.py`
8. `backend/app/models/rule.py`
9. `frontend/src/pages/rules-page.tsx`

## 3. Finary Reuse Context
Source files:
1. `docs/transactions_rules.json`
2. `docs/configuration_categories.json`

Observed importable signals:
1. 99 Finary rules total.
2. 49 distinct rule categories.
3. 74 rules with `transactions_count > 0`.
4. 25 rules with `transactions_count == 0` (candidates to import as disabled by default).
5. One category present in rules but missing from category config: `Empreintes bancaires`.

Normalization and data-quality caveats:
1. Some patterns include escaped separators (for example backslashes and slash-heavy merchant tokens).
2. Some category names have trailing spaces and must be trimmed before matching.
3. Encoding artifacts exist in exported labels/categories and must be normalized during bootstrap.
4. Pattern arrays should be interpreted as deterministic AND token matching in v1.

## 4. Locked Product Decisions
Locked for v1:
1. Auto-run scope: apply rules to newly created transactions only during an import.
2. Default execution mode: fill missing values only.
3. Category strategy: seed + stable mapping keys from imported taxonomy.
4. Rule deletion strategy: safe rollback (preview + conditional uncategorization only when still reversible).

## 5. Rule Impact Lineage (Non-negotiable)
The system must always answer:
1. Which rule changed which transaction fields.
2. Which rule created, replaced, or removed which splits.
3. When it happened, under which run, and in which mode (dry_run/apply/import/manual).

Required append-only provenance model:
1. `rule_run_batches`
2. `rule_run_effects`
3. `split_lineage`

### 5.1 `rule_run_batches`
Purpose: one row per rules execution batch.

Suggested fields:
1. `id`
2. `trigger_type` (`import_auto`, `manual_scope`)
3. `scope_json` (import id/date range/all)
4. `mode` (`dry_run`, `apply`)
5. `allow_overwrite`
6. `started_at`
7. `finished_at`
8. `created_by` (nullable actor id for future auth)
9. `summary_json` (counters)

### 5.2 `rule_run_effects`
Purpose: immutable per-rule-per-transaction effect log.

Suggested fields:
1. `id`
2. `batch_id`
3. `rule_id`
4. `transaction_id`
5. `status` (`matched_noop`, `applied`, `skipped`, `error`)
6. `reason_code` (skip/conflict/error code)
7. `before_json`
8. `after_json`
9. `change_json` (field-level diff and split operations)
10. `applied_at`

### 5.3 `split_lineage`
Purpose: direct split-level traceability across replace-all split writes.

Suggested fields:
1. `id`
2. `transaction_id`
3. `split_id` (nullable for deleted/replaced rows)
4. `effect_id`
5. `operation` (`create`, `replace`, `delete`, `noop`)
6. `before_json`
7. `after_json`
8. `recorded_at`

Mandatory lineage constraints:
1. Effect rows are immutable (no update/delete).
2. Before/after snapshots are stored for every applied split or field change.
3. Dry-run effects are also persisted with explicit dry-run mode markers.

Mandatory lineage APIs:
1. `GET /rule-runs`
2. `GET /rules/{id}/impacts`
3. `GET /transactions/{id}/rule-history`

## 6. Safe Delete Workflow
Rule deletion must support safe rollback and explicit user communication.

Endpoint contract:
1. `DELETE /rules/{id}?mode=preview|confirm&rollback=true|false`

Behavior:
1. `mode=preview` computes impacted records and reversibility only.
2. `mode=confirm` performs delete/disable and optional rollback.

Safe rollback policy:
1. Revert to uncategorized only when current transaction/split state still matches the rule's latest applied effect.
2. Skip rollback if record was changed later by another rule or manual edit.
3. Never force overwrite conflicting current state in safe mode.

Response summary must include:
1. `total_impacted`
2. `reverted_to_uncategorized`
3. `skipped_conflict`
4. `skipped_not_latest`
5. `deleted` or `disabled` status

UI requirements:
1. Show preview warning before confirm delete.
2. Show post-confirm summary notification with reverted/skipped counts.
3. Explain why some records were not reverted.

## 7. API Contracts
Rules and runs:
1. CRUD `/rules`
2. `POST /rules/run`
3. `GET /rule-runs`
4. `GET /rules/{id}/impacts`
5. `GET /transactions/{id}/rule-history`
6. `DELETE /rules/{id}?mode=preview|confirm&rollback=true|false`

Run payload contract (`POST /rules/run`):
1. `scope` (`import`, `date_range`, `all`)
2. `mode` (`dry_run`, `apply`)
3. `allow_overwrite` (default `false`)

## 8. Execution Semantics
Rule ordering and matching:
1. Enabled rules run by ascending priority.
2. Matchers evaluate against normalized transaction data (`label_norm`, `supplier_raw`, amount, type, dates, account).

Default fill-missing behavior:
1. `set_payee` only if payee is missing.
2. `set_category` and `set_split_template` only if transaction has no splits.
3. `set_type` and split rewrites require explicit overwrite mode.

Split protection defaults:
1. If transaction already has splits, rules do not modify splits unless overwrite is enabled.
2. Any split write must pass existing split validation invariants.

Dry-run/apply behavior:
1. Dry-run stores computed impacts without mutating data.
2. Apply writes mutations and persists full lineage snapshots.

Conflict/skip reason codes (minimum set):
1. `RULE_DISABLED`
2. `NO_MATCH`
3. `FIELD_ALREADY_SET`
4. `SPLITS_ALREADY_EXIST`
5. `OVERWRITE_NOT_ALLOWED`
6. `VALIDATION_FAILED`
7. `DEPENDENCY_NOT_FOUND`
8. `CONFLICT_LATER_EDIT`

## 9. Bootstrap Plan
Add a bootstrap script for deterministic import of Finary categories and rules.

Script responsibilities:
1. Load and normalize category taxonomy from `docs/configuration_categories.json`.
2. Seed categories with stable external mapping key metadata.
3. Load rules from `docs/transactions_rules.json`.
4. Map each Finary rule pattern list to deterministic matcher JSON.
5. Map each Finary category to local `category_id`.
6. Upsert rules idempotently by `(source, source_ref)`.
7. Disable rules with zero historical usage by default.

Special handling:
1. Create missing category `Empreintes bancaires` as custom mapped category if absent.
2. Trim and normalize category names before lookup.
3. Preserve source metadata for traceability.

## 10. Testing Plan
Unit tests:
1. Matcher predicate tests.
2. Action validation tests.
3. Fill-missing vs overwrite behavior tests.

Integration tests:
1. Import auto-run applies only to newly created transactions.
2. Linked pre-existing transactions are not modified by import auto-run.
3. Rule run persistence writes batch/effect/lineage entries.
4. Dry-run writes effect logs without data mutation.
5. Delete preview reports accurate reversible vs conflict counts.
6. Delete confirm safe rollback uncategorizes only reversible records.

UI tests:
1. Impact history display by rule and by transaction.
2. Delete preview modal and summary banner.
3. Clear skip reason display for non-reverted records.

## 11. Acceptance Criteria
Core:
1. Deterministic rules can auto-map categories/payees/splits using configured matchers.
2. Import auto-run applies rules only to newly created transactions.
3. Existing split invariants remain enforced.

Traceability:
1. Any changed transaction or split can be traced to exact rule run batch and effect record.
2. API can retrieve per-rule and per-transaction impact history.

Safe deletion:
1. Deleting a rule supports preview before confirm.
2. Confirmed safe rollback can revert eligible records to uncategorized.
3. User receives explicit summary of reverted vs skipped conflicts.

## Assumptions and Defaults
1. Keep deterministic v1 only (no ML categorization in scope).
2. Keep strict split invariants unchanged.
3. Rule impact lineage is append-only and queryable via API.
4. Rule deletion defaults to safe rollback preview before confirm.

