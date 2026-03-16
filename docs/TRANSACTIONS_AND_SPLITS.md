# Transactions and Splits: How It Actually Works

## Why this doc exists
Use this as the canonical quick reference for how money data is modeled and processed in this repo.

## Core Concepts
1. `Transaction` is the canonical imported bank event.
2. `Split` is the analytic allocation unit for one transaction.
3. Transactions come from CSV import and dedupe logic.
4. Splits are edited manually from Ledger today.

## Data Ownership
### Transaction owns
1. bank/account context
2. amount, date, raw label, normalized label
3. type (`expense`, `income`, `transfer`, `refund`, `adjustment`)
4. payee assignment (optional)

### Split owns
1. allocated amount
2. category
3. optional moment tag
4. optional internal account
5. position/order and optional note

## Lifecycle
### Step 1: Import creates transactions
Import pipeline creates transactions and import links, but no splits.
Main path: `backend/app/services/import_service.py`.

### Step 2: Ledger user assigns splits
Ledger drawer loads transaction + existing splits.
Save calls `PUT /transactions/{id}/splits` with full replacement payload.
Main paths:
1. `frontend/src/pages/ledger/dashboard-page.tsx`
2. `backend/app/routers/transactions.py`

### Step 3: Backend replaces splits atomically per transaction
For one save request:
1. Validate split payload.
2. Delete existing splits for the transaction.
3. Insert new splits in provided order.
4. Commit.

## Invariants (Important)
These rules define correctness:
1. `splits=[]` is valid and means uncategorized transaction.
2. If splits exist, each split requires `category_id`.
3. Split amount precision is max 2 decimals.
4. Each split sign must match transaction sign.
5. Sum of split amounts must equal transaction amount exactly.

Enforcement layers:
1. API validation in `backend/app/services/ledger_validation.py`.
2. DB trigger enforcement in `backend/alembic/versions/0001_initial_schema.py`.

## Derived Transaction Status
Computed in transaction responses:
1. `splits_sum`
2. `splits_count`
3. `is_balanced`
4. `is_categorized`
5. `remaining_amount`

Source: `backend/app/routers/transactions.py`.

## Payees and Internal Accounts
1. Payee is attached to `Transaction`, not `Split`.
2. Internal account is attached to `Split`.
3. Today UI lists mostly count metrics:
   - payee `transaction_count`
   - internal account `split_count`

## Analytics Implications
If you are building analytics:
1. Use splits as fact table for spending allocations.
2. Join transactions to get date, type, and payee context.
3. Keep semantics consistent: do not mix split links with transaction totals in same chart context.
4. Exclude transfers by default for spending views.

## Counterparty Sign Convention
When a "counterparty view" is needed:
1. Do not duplicate stored splits.
2. Compute at query time:
   - `user_amount = split.amount`
   - `counterparty_amount = -split.amount`

## Known Gotcha
Check `splits.category_id` nullability consistency across:
1. migrations
2. ORM model
3. category delete behavior

Before adding analytics features, verify this is aligned in your actual DB.

## Fast File Map
1. Transaction model: `backend/app/models/transaction.py`
2. Split model: `backend/app/models/split.py`
3. Import pipeline: `backend/app/services/import_service.py`
4. Split validation: `backend/app/services/ledger_validation.py`
5. Transactions API: `backend/app/routers/transactions.py`
6. Analytics flow API: `backend/app/routers/analytics.py`
7. Ledger split editor UI: `frontend/src/pages/ledger/dashboard-page.tsx`
8. Transaction client types: `frontend/src/services/transactions.ts`

