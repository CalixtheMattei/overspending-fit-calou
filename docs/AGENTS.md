# AGENTS.md

This repo is a personal expense tracker monorepo. The frontend uses the Untitled UI Vite starter and the backend is FastAPI + Postgres. This file is for both humans and AI agents contributing to it.

## Mission
Build a local-first expense tracker for personal use (may go public later) that:
- imports bank CSV exports (BoursoBank-like)
- dedupes across overlapping imports
- supports split allocations (critical)
- supports deterministic rules to auto-categorize
- supports “Moments” overlay to isolate event-based spend vs baseline
- includes analytics dashboards (minimal v1)

## Product Principles (non-negotiable)
1. Splits are first-class. Without splits, reimbursements/shared purchases are impossible to model correctly.
2. Raw imports are append-only. Never discard raw rows; always store raw_json.
3. Canonical transactions are deduped via stable fingerprint so overlapping imports don’t duplicate data.
4. Transfers exist as a type and are excluded from spending by default.
5. Moment is an overlay, not a category. Prefer tagging splits, not whole transactions.

## Observed CSV format
Tab-separated, headers:
`dateOp, dateVal, label, category, categoryParent, supplierFound, amount, comment, accountNum, accountLabel, accountbalance`
- amount uses French formatting with spaces and comma decimals: "-1 300,00", "2 848,02"
- label patterns include: `CARTE`, `PRLV SEPA`, `VIR SEPA`, `VIR INST`, `AVOIR`
- `supplierFound` is a useful payee seed (e.g., "hamon ocyane", "sncf", "navigo")

## Architecture (v1)
- Frontend: Vite + React + Untitled UI
- Backend: FastAPI
- DB: Postgres (Docker Compose)
- Migrations: Alembic
- Local dev: `docker compose up` + backend `uvicorn` + frontend `vite`

## Repo structure
/
  docker-compose.yml
  /backend
    /app
      main.py
      db.py
      /models
      /routers
      /services
    alembic/
    pyproject.toml
  /frontend
    src/
    index.html
  /docs
    AGENTS.md
    PRD-000-data-model-and-dedupe.md
    PRD-001-import.md
    PRD-002-transactions-splits-payees.md
    PRD-003-rules-engine.md
    PRD-004-analytics.md
    PRD-005-moments.md

## Quickstart
Frontend (npm)
- `cd frontend`
- `npm install`
- `npm run dev`
- `npm run build` (runs `tsc -b` then `vite build`)
- `npm run preview`

Backend
- `cd backend`
- `python -m pip install -e .`
- `uvicorn app.main:app --reload`

Database
- `docker compose up -d`

## Frontend conventions
- Path alias: `@/` maps to `src/` (see `frontend/tsconfig.json` and `frontend/vite.config.ts`)
- Tailwind config is driven by `frontend/src/styles/globals.css` importing `theme.css` and `typography.css`
- Formatting uses Prettier (no lint or test scripts configured)

## Component library requirement
This repo uses Untitled UI React components. Every vibe-coding session must reference and use this component library when building or modifying UI to keep design and behavior consistent.

## Core data model (summary)
- accounts
- imports, import_rows, import_row_links
- transactions (fingerprint unique)
- splits (sum invariant)
- categories
- payees (person/merchant)
- moments
- rules, rule_runs

## Invariants & validation
Split invariant
- If transaction has splits: sum(splits.amount) must equal transaction.amount exactly.
- Negative transactions have negative splits.
- Backend enforces invariant on every split update.

Dedupe
- `fingerprint = sha256(accountNum|dateVal|amount|label_norm_core)`
- upsert canonical transaction by fingerprint
- link every import_row to a transaction

Transfer exclusion
- transfers are not “spending”; analytics excludes them by default
- heuristic classification based on label prefixes + keywords (livret a, epargne, revolut)

## Milestone plan (execute tab-by-tab; end-to-end each time)
M0 Skeleton
- docker compose + alembic + health endpoint + sidebar routes with empty states

M1 Import (end-to-end)
- upload CSV -> store imports/import_rows -> upsert transactions -> link rows -> import stats UI

M2 Inbox + Splits + Payees
- list uncategorized (no splits) -> transaction detail -> split editor -> category assignment
- payee selection (seed from supplierFound)

M3 Rules engine
- rules CRUD + create from transaction + apply to import/date range + rule_runs logs

M4 Analytics
- month/year filters + spend by category (splits) + cashflow line
- exclude transfers toggle

M5 Moments
- CRUD moments + tag splits + moment detail + analytics overlay toggles

## API contracts (v1)
- POST `/imports` (multipart file upload) -> `{import_id, stats}`
- GET `/imports`, GET `/imports/{id}`, GET `/imports/{id}/rows`
- GET `/transactions?status=uncategorized&exclude_transfers=true&date_range=...`
- GET `/transactions/{id}`
- PATCH `/transactions/{id}` (payee_id, type override)
- PUT `/transactions/{id}/splits` (replace-all) + validation
- CRUD `/categories`, `/payees`, `/moments`, `/rules`
- POST `/rules/run?scope=import:{id}|date_range|all`
- GET `/rule_runs?transaction_id=...`

## Agent workflow (Codex-friendly)
When implementing a milestone:
1. Read relevant PRD(s) in `docs/`
2. Implement backend endpoints + migrations first
3. Add minimal frontend to exercise endpoints
4. Add 3-5 integration tests for critical invariants (import dedupe, split sum)
5. Manual QA checklist (below)
6. Commit with milestone label

## Manual QA checklist
Import
- importing same file twice yields 0 new transactions
- overlapping date range import doesn’t duplicate
- parsing handles French decimals and negatives

Splits
- can create 1 split for full amount
- can create multi-split; sum matches; errors shown if not

Transfers
- transfer rows not counted in spend

Rules
- rule “openai” => category applies on import

Moments
- tag split to moment; exclude moments affects analytics

## Known future enhancements (not v1)
- embeddings/LLM auto-categorization
- subscription detection (recurrence clustering)
- payee merge + alias table
- multi-account transfer pairing (when importing savings accounts too)
- Sankey chart
