# PRD-000 — Data Model, Import Normalization, Dedupe (v1)

## Goal
Support local-first expense tracking from CSV exports (BoursoBank-like) with:
- append-only raw imports
- canonical transactions with dedupe across overlapping imports
- split allocations per transaction
- payees (people + merchants)
- moments overlay (tag splits)
- deterministic rules engine scaffolding

## Non-goals (v1)
- bank auto-sync
- multi-currency FX conversion
- complex reconciliation between multiple accounts (we still model accounts, but may import only 1)

## Input CSV (observed)
Columns:
- dateOp, dateVal, label, category, categoryParent, supplierFound, amount, comment, accountNum, accountLabel, accountbalance

Observed label patterns:
- "CARTE dd/mm/yy <MERCHANT> CB*####" (card)
- "PRLV SEPA <ENTITY>" (direct debit)
- "VIR SEPA <ENTITY>" (transfer)
- "VIR INST <ENTITY>" (instant transfer)
- "TDF EMIS VIA CB ... Revolut" (transfer-like)
- "AVOIR ..." (refund, positive amount)

Amounts:
- French format with spaces and comma decimals: "-1 300,00", "2 848,02"

## Canonical concepts
- Account: bank account (at least 1)
- Import: one file upload
- ImportRow: raw row stored forever
- Transaction: canonical, deduped row representing a real movement
- Split: allocation lines that must sum exactly to transaction.amount
- Payee: normalized party (person or merchant) inferred from supplierFound/label
- Category: your taxonomy (independent from bank’s raw categories)
- Moment: overlay event/time window; can tag splits (preferred) or whole transaction (fallback)
- Rule: deterministic matcher + action; can create splits/categories/moment tags

## Postgres schema (v1)
accounts
- id (pk)
- account_num (text, unique)
- label (text)
- institution (text, nullable)
- currency (text, default 'EUR')
- created_at

imports
- id (pk)
- account_id (fk accounts.id)
- file_name (text)
- file_hash (text)  # sha256 of file bytes
- imported_at (timestamptz)
- notes (text, nullable)

import_rows
- id (pk)
- import_id (fk imports.id)
- row_hash (text)   # hash of raw row normalized to detect duplicates inside an import
- raw_json (jsonb)
- date_op (date)
- date_val (date)
- label_raw (text)
- supplier_raw (text, nullable)
- amount (numeric(12,2))
- currency (text, default 'EUR')
- category_raw (text, nullable)
- category_parent_raw (text, nullable)
- comment_raw (text, nullable)
- balance_after (numeric(14,2), nullable)
- created_at

payees
- id (pk)
- name (text)                 # display
- kind (text)                 # 'person' | 'merchant' | 'unknown'
- canonical_name (text, nullable)
- created_at

transactions
- id (pk)
- account_id (fk accounts.id)
- posted_at (date)            # from dateVal
- operation_at (date)         # from dateOp
- amount (numeric(12,2))
- currency (text)
- label_raw (text)
- label_norm (text)
- supplier_raw (text, nullable)
- payee_id (fk payees.id, nullable)
- type (text)                 # 'expense'|'income'|'transfer'|'refund'|'adjustment'
- fingerprint (text, unique)  # cross-import dedupe key
- created_at

import_row_links
- id (pk)
- import_row_id (fk import_rows.id)
- transaction_id (fk transactions.id)
- linked_at

categories
- id (pk)
- name (text)
- parent_id (fk categories.id, nullable)
- created_at

moments
- id (pk)
- name (text)
- start_date (date)
- end_date (date)
- description (text, nullable)
- created_at

splits
- id (pk)
- transaction_id (fk transactions.id)
- amount (numeric(12,2))
- category_id (fk categories.id)
- moment_id (fk moments.id, nullable)
- note (text, nullable)
- created_at

rules
- id (pk)
- name (text)
- priority (int)              # lower runs first
- enabled (bool)
- matcher_json (jsonb)
- action_json (jsonb)
- created_at

rule_runs
- id (pk)
- transaction_id (fk transactions.id)
- rule_id (fk rules.id)
- applied_at (timestamptz)
- result_json (jsonb)

## Normalization rules (v1)
- posted_at := dateVal
- operation_at := dateOp
- amount parsing:
  - remove spaces
  - replace comma with dot
  - cast numeric(12,2)
- label_norm:
  - lowercase
  - trim spaces
  - collapse whitespace
  - optional cleanup:
    - remove trailing "cb*####"
    - remove leading "carte dd/mm/yy" date token
  Keep raw label always.

- payee inference:
  - prefer supplierFound if present
  - else parse label patterns (e.g., after "PRLV SEPA", after "VIR SEPA", etc.)
  - store in payees with kind heuristic:
    - if looks like a person name (two tokens / common patterns) -> 'person'
    - else -> 'merchant' or 'unknown'

## Transaction type classification (heuristic v1)
Based on label_norm prefixes:
- startswith "carte " -> expense (unless amount > 0 => refund)
- startswith "prlv sepa" -> expense
- startswith "vir sepa" or "vir inst" or contains "virement" -> transfer or income/expense depending on amount sign:
  - amount > 0 => income unless matches internal savings keywords -> transfer
  - amount < 0 => expense unless matches internal savings keywords -> transfer
- startswith "avoir" and amount > 0 -> refund

Internal transfer keywords (seed list):
- "livret a", "epargne", "revolut" (can be transfer)
Note: user may import only one account; still classify transfers so analytics can exclude them by default.

## Dedupe (fingerprint) strategy (v1)
fingerprint := sha256(
  account_num + "|" +
  posted_at + "|" +
  amount_normalized + "|" +
  label_norm_core
)

label_norm_core:
- label_norm after cleanup removing cb* suffix and card date prefix (optional but recommended)
Rationale: overlapping imports should not create duplicate canonical transactions.

## Split invariant (critical)
- If a transaction has 0 splits, it is “uncategorized”.
- If it has >=1 splits, sum(splits.amount) must equal transaction.amount exactly.
- For negative expenses: split amounts are negative too.
- Backend enforces invariant on create/update of splits.

## Minimal API surfaces (v1)
- POST /imports (upload CSV) -> import_id + stats (created/linked/duplicates)
- GET /imports, GET /imports/{id}, GET /imports/{id}/rows
- GET /transactions?filters...
- GET /transactions/{id}
- POST/PUT/DELETE /transactions/{id}/splits
- GET/POST/PUT/DELETE /categories
- GET/POST/PUT/DELETE /payees
- GET/POST/PUT/DELETE /moments
- GET/POST/PUT/DELETE /rules
- POST /rules/run?scope=import|date_range|all

## Acceptance criteria
- Importing the same CSV twice does not create duplicate transactions.
- Overlapping CSV date ranges do not create duplicates (fingerprint works).
- You can manually split an expense and it stays consistent.
- Transfers are excluded from analytics by default.

