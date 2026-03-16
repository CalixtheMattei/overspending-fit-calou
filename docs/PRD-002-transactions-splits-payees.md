PRD-002 v2 — Ledger (Transactions, Splits, Payees, Internal Accounts)
0) Scope

Goal: Provide a deterministic workflow to turn imported bank transactions into clean, queryable financial records.

In scope (v2):

Ledger tab: Transactions table + filters + search

Transaction detail drawer with split editor

Strict split balancing validation (balanced or empty only)

Payee: search + create + rename (no merge yet)

Internal Accounts: create + rename + reorder (lightweight “manage list”)

Transaction type: minimal support (expense|income|transfer|refund) with manual override

Out of scope (v2):

Payee merge/aliasing

Rules engine (PRD-003)

Analytics visualizations (PRD-004)

Double-entry accounting, automated transfer pairing

1) Definitions & invariants (non-negotiable)

Transaction = imported bank event (source-of-truth row).

Split = analytic unit (used for categories/moments/internal accounts).

Uncategorized = splits.length == 0

Categorized = splits.length >= 1 AND sum(split.amount) == transaction.amount exactly (to cent).

Strict saving rule (D1=1):

You can save either empty splits (uncategorized) or fully balanced splits.

You cannot save partial/unbalanced splits.

Amount/sign rules:

All amounts stored as Decimal(12,2).

Split amounts must have the same sign as the parent transaction amount.

sum(splits.amount) must equal transaction.amount exactly.

2) Entities
2.1 Transaction (existing)

Fields (min v2):

id

posted_at (dateOp or dateVal choice, but pick one consistently; recommend dateOp for “what happened”)

value_at (optional)

label_raw, label_norm

supplier_raw (optional)

amount (Decimal(12,2))

currency (default EUR)

source_bank_account_id

payee_id (nullable)

type enum: expense|income|transfer|refund (default inferred from amount sign: negative=expense, positive=income; user can override)

comment (optional)

Derived in API responses:

splits_sum

is_balanced

is_categorized

remaining_amount

2.2 Split (v2)

Fields:

id

transaction_id

amount (Decimal(12,2))

category_id (nullable if you want “uncategorized split”; but simplest: require category when splits exist)

moment_id (nullable)

internal_account_id (nullable) ✅ (D2=1)

note (optional)

position (int, ordering)

Rule: if transaction has splits, each split must have a category unless you intentionally support “split exists but still uncategorized”. For v2, keep it simple:

If splits exist: category_id is required.

2.3 Payee (v2)

Fields:

id

name (display)

canonical_name (lower/trim/collapse spaces)

kind enum: merchant|person|unknown (optional)

created_at, updated_at

Uniqueness (v2): enforce unique on canonical_name to prevent duplicates. (Merge later.)

2.4 Bank Account (source account)

Fields:

id

account_num (string)

label

institution (optional)

currency

is_active

2.5 Internal Account (NEW, v2)

Represents your financial buckets (Savings, Investments, etc.)

Fields:

id

name

type enum (optional): cash|savings|investments|debt|other (helps analytics later)

position (int for ordering)

is_archived (bool)

3) Ledger UX
3.1 Ledger tab layout

Top → bottom:

Summary strip (quick health metrics)

Uncategorized transactions count

Uncategorized total amount (absolute)

Categorized % last 30 days

Transactions table (primary working area)
Columns:

Date

Label

Payee

Amount

Type

Category (derived: if single split, show that category; if multiple, show “Split (n)”)

Internal Account (derived: single → show it; multiple → “Mixed”)

Status: Uncategorized/Categorized

Controls:

Search (label/payee)

Filters:

Status: uncategorized/categorized/all (default uncategorized)

Type: expense/income/transfer/refund

Payee

Category

Internal Account

Bank Account (future-proof; even if only one now)

Row click → opens Transaction detail drawer.

Manage lists (small, inside Ledger)
Sub-tabs or a right-side panel:

Payees: search, rename, create

Internal Accounts: create, rename, reorder, archive

Keep it lightweight. This is not “Settings”.

4) Transaction detail + split editor flow
4.1 Transaction detail drawer sections

Header:

Date + Amount

Type dropdown (manual override)

Source bank account badge

Payee:

Search dropdown (typeahead)

“Create payee” inline

Rename payee available from Payees list (not here)

Split editor (core)

Split rows: amount | category | moment | internal account | note | delete

Footer:

Total (transaction)

Sum (splits)

Remaining

Buttons:

Add remaining (creates new row with remaining amount)

Fill remaining into selected row

Single-split shortcut: “Set category for full amount” (one row)

Save button:

Enabled only when:

splits are empty (uncategorized) OR

splits are balanced AND all required fields present

No draft/unbalanced saving.

5) Flows to create Internal Accounts (your request)
Flow A — Inline create from split row (fastest)

In the split row internal account dropdown:

“+ Create internal account…”

modal: Name (required), Type (optional), Save

after save: auto-select the new internal account on that split

This avoids a separate admin detour.

Flow B — Ledger ▸ Internal Accounts list (clean-up mode)

List with:

reorder (drag or up/down)

rename inline

archive toggle

Archiving:

archived accounts cannot be selected for new splits

existing splits keep reference (history preserved)

6) Endpoints (implementation contract)
6.1 Transactions listing

GET /transactions
Query params:

status=uncategorized|categorized|all (default uncategorized)

type=expense|income|transfer|refund|all (default all)

q=...

payee_id=...

category_id=...

internal_account_id=...

bank_account_id=...

pagination: limit, offset

sorting: posted_at_desc default

Response includes derived status fields.

6.2 Transaction detail

GET /transactions/{id}
Returns:

transaction fields

payee

splits[] ordered

derived sums

6.3 Update transaction (type/payee)

PATCH /transactions/{id}
Body:

payee_id?: string | null

type?: "expense"|"income"|"transfer"|"refund"

comment?: string

6.4 Replace-all splits (single source of truth)

PUT /transactions/{id}/splits
Body:

{
  "splits": [
    {
      "amount": "-10.00",
      "category_id": "cat_food",
      "moment_id": null,
      "internal_account_id": "ia_cash",
      "note": ""
    }
  ]
}


Validation:

If splits=[]: OK → transaction becomes uncategorized

Else:

each split amount same sign as transaction.amount

each split amount has max 2 decimals

each split has category_id (v2 decision)

sum == transaction.amount exactly

Errors (422):

SPLIT_SUM_MISMATCH (expected, actual, remaining)

SPLIT_SIGN_MISMATCH

SPLIT_CATEGORY_REQUIRED

6.5 Payees

GET /payees?q=...&limit=...

POST /payees {name, kind?} (idempotent via canonical_name uniqueness)

PATCH /payees/{id} {name, kind?} (rename)

6.6 Internal Accounts

GET /internal-accounts

POST /internal-accounts {name, type?, position?}

PATCH /internal-accounts/{id} {name?, type?, position?, is_archived?}

7) Transaction.type: keep it minimal now (your note)

You’re right that type becomes more meaningful with Analytics, but implementing it now is cheap and prevents future refactors.

v2 constraints:

Default inferred:

amount < 0 → expense

amount > 0 → income

User can override anytime.

Ledger filters use type.

Analytics later will decide what types to include/exclude by default.

No other magic.

8) Acceptance tests

Balanced single split

Given transaction amount -23.00

When user creates one split -23.00 with category

Then transaction becomes categorized and disappears from default uncategorized view

Unbalanced rejected

Given transaction -23.00

When splits sum to -22.99

Then PUT splits returns 422 SPLIT_SUM_MISMATCH

Uncategorize

Given categorized transaction

When user saves splits=[]

Then transaction returns to uncategorized

Internal account creation inline

When user creates new internal account “Investments”

Then it appears in list and can be selected on splits immediately

Type override

Given transaction inferred as income (amount > 0)

When user sets type=transfer

Then Ledger filter “exclude transfers” hides it (default behavior can be decided later; Ledger can keep showing them if you prefer)