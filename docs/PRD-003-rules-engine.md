# PRD-003 — Rules Engine (v1 deterministic)

## Goal
Deterministic rules that auto-assign:
- payee
- category (single split)
- split templates
- moment tags (optional)
- transfer classification override

Rules must be inspectable and testable (no black box).

## Rule model
rules:
- priority (int): lower runs first
- matcher_json:
  - any/all conditions
  - supported predicates (v1):
    - label_contains, label_regex
    - supplier_contains
    - amount_between
    - amount_equals
    - type_is
    - posted_at_between
    - day_of_month_is (subscriptions)
  - normalization: apply on label_norm + supplier_raw

- action_json (v1):
  - set_payee(name or id)
  - set_type(expense|income|transfer|refund)
  - set_category(category_id)  -> creates single split for full amount
  - set_split_template([{amount_fixed|percent, category_id, note?}])
  - set_moment(moment_id)      -> tags splits (if created) else store pending moment tag

## Execution semantics
- Rules run in priority order on a transaction.
- A rule can be:
  - non-destructive (only fills missing values)
  - destructive (overwrites) — disabled in v1 unless user enables "allow overwrite"
Default v1: only fill missing fields.

- Split behavior:
  - If transaction has no splits, a rule may create them.
  - If it already has splits, v1 rules do NOT modify splits unless user opts-in.

## UI (v1)
- Rules list:
  - enable/disable toggle
  - priority reorder (simple up/down)
- Rule editor:
  - form-based builder for common matchers
  - JSON view advanced mode (optional)
- “Create rule from transaction”:
  - prefill with label_contains (merchant token) and action set_category
- Test runner:
  - pick a transaction -> preview what would change

## API (v1)
- CRUD /rules
- POST /rules/run?scope=import:{id} OR date range
- GET /rule_runs?transaction_id=...

## Acceptance criteria
- Create a rule: label_contains "openai" -> category "Subscriptions/AI"
- Import new CSV and see it auto-categorized.
- Rule-run logs show which rules applied.
