# PRD-001 Import Tab - Implementation Plan (v1)

This document is a decision-complete plan to implement PRD-001, aligned to the single-route `/imports` IA.

## Context Snapshot (for a fresh Codex session)
- Repo: personal expense tracker monorepo
- Frontend: Vite + React + Untitled UI components
- Backend: FastAPI + SQLAlchemy + Alembic + Postgres
- Relevant docs:
  - `docs/AGENTS.md` (product principles, API contracts, milestones)
  - `docs/PRD-000-data-model-and-dedupe.md` (schema, normalization, dedupe)
  - `docs/PRD-001-import.md` (import UI + behaviors)
- Current state:
  - Alembic initial schema exists (`backend/alembic/versions/0001_initial_schema.py`) with tables for accounts, imports, import_rows, import_row_links, transactions, etc.
  - No import endpoints or services exist yet.
  - Frontend `/imports` route exists with an empty state placeholder.

## Goal
Ship the Import tab end-to-end:
- Upload CSV
- Store raw rows
- Normalize + dedupe into canonical transactions
- Link rows to transactions
- Single `/imports` page with uploader + tabs (Imports history + Import results)
- Optional deep inspection via `/imports/:id` if needed

## Decision Summary (locked)
1. Accounts:
   - Auto-create account if `accountNum` from CSV does not exist.
2. Error storage:
   - Persist row errors with explicit columns on `import_rows` (status, error_code, error_message).
3. Paging:
   - `/imports/{id}/rows` uses server-side pagination + filters.
4. UX/IA:
   - `/imports` is the single container page.
   - Import results is last/selected import only; no global "all imported transactions" view.
   - No categorization actions in Import results (belongs to Inbox in PRD-002).

## Public API Additions
1. `POST /imports` (multipart upload)
   - Response: `{ import_id, stats }`
2. `GET /imports`
3. `GET /imports/{id}`
4. `GET /imports/{id}/rows?status=...&limit=...&offset=...`
5. `GET /imports/{id}/rows/{row_id}`

## Schema Changes (Post-PRD-000)
### `imports`
Add:
- `row_count` INT DEFAULT 0
- `created_count` INT DEFAULT 0
- `linked_count` INT DEFAULT 0
- `duplicate_count` INT DEFAULT 0
- `error_count` INT DEFAULT 0

### `import_rows`
Add:
- `status` TEXT (`created` | `linked` | `error`)
- `error_code` TEXT NULL
- `error_message` TEXT NULL

Relax nullability:
- `date_op`, `date_val`, `amount` nullable to allow storing parse errors.

## Backend Implementation Plan

### 1) Alembic migration
- Add columns above to `imports` and `import_rows`
- Alter `import_rows.date_op`, `date_val`, `amount` to nullable

### 2) SQLAlchemy model updates
- `Import` and `ImportRow` models to include new columns
- Add `ImportRowStatus` enum
- Adjust nullability on `date_op`, `date_val`, `amount`

### 3) Normalization utilities (`backend/app/services/import_normalization.py`)
Implement:
- `parse_amount_fr(raw: str) -> Decimal`
  - remove spaces, replace comma with dot
- `parse_date(raw: str) -> date`
  - support `%d/%m/%Y` and `%d/%m/%y`
- `normalize_label(raw: str) -> str`
  - lowercase, trim, collapse whitespace
  - remove leading `carte dd/mm/yy`
  - remove trailing `cb*####`
- `infer_type(label_norm: str, amount: Decimal) -> TransactionType`
  - per PRD-000 heuristic
- `infer_payee(supplier_found: str | None, label_raw: str) -> str | None`
- `compute_row_hash(row: dict) -> str`
  - sha256 of normalized raw row for intra-file dupes
- `compute_fingerprint(account_num, posted_at, amount, label_norm_core) -> str`

### 4) Import service (`backend/app/services/import_service.py`)
Flow:
1. Read CSV bytes, detect delimiter (tab/comma)
2. Map headers (use observed columns in PRD-000/001)
3. Resolve account by `accountNum` (create if missing)
4. Validate file has single account number
5. Iterate rows:
   - compute row_hash; skip if duplicate in file (count duplicates)
   - normalize fields
   - on parse error: store row with `status=error`, `error_code`, `error_message`, `raw_json`
   - else:
     - store ImportRow
     - compute fingerprint
     - upsert Transaction by fingerprint
     - create ImportRowLink
     - mark row status `created` or `linked`
6. Write stats to `imports` row and return in response

### 5) API router (`backend/app/routers/imports.py`)
Endpoints:
- `POST /imports`
  - Returns `import_id` + stats
- `GET /imports`
  - list with stats + account
- `GET /imports/{id}`
- `GET /imports/{id}/rows`
  - query: `status`, `limit`, `offset`
- `GET /imports/{id}/rows/{row_id}`

### 6) Include router in `backend/app/main.py`

## Frontend Implementation Plan

### 1) API client
- Add `frontend/src/services/api.ts` with `VITE_API_BASE_URL`
- Add `frontend/src/services/imports.ts` for all import endpoints

### 2) Imports page container (single route)
Replace `frontend/src/pages/imports-page.tsx` with a container that includes:
- Uploader section at top (always visible)
- Upload dropzone + "Import CSV" button
- After import: stats summary + primary CTA "View import results"
- Tabs below: Imports | Import results
- Tab state persisted (URL param or local state)

### 3) Tab 1 - Imports (history)
- Table with imported_at, file_name, account, stats
- Empty state for no imports
- Row click selects import and updates Import results tab (and switches to it)

### 4) Tab 2 - Import results (last/selected)
- Default selected import = most recent
- Header with import metadata (date, file_hash, account)
- Summary cards (created, linked, duplicates, errors)
- Table of rows (dateVal, label, supplierFound, amount, raw category, linked transaction id)
- Filters: all / unlinked / errors
- Row click opens drawer

### 5) Row detail drawer
Use `SlideoutMenu` component:
- Raw JSON viewer
- Normalization preview
- Linked transaction preview

### 6) Optional deep inspection route
- Keep `/imports/:importId` only if needed for deep inspection (row drawer, raw_json, etc.)
- If kept, route can simply set selected import and render the same Import results tab content

### 7) Routing
Update `frontend/src/main.tsx`:
- `/imports` -> ImportsPage
- `/imports/:importId` -> optional (only if deep inspection is kept)

## Tests

### Unit Tests (pytest)
- `parse_amount_fr` handles "2 848,02" and "-1 300,00"
- label normalization strips card date prefix + `cb*####`
- fingerprint dedupe across overlapping imports

### Integration Tests
- `POST /imports` with same file twice:
  - 1st: created_count > 0
  - 2nd: created_count == 0, linked_count == total rows
- duplicate rows in same file -> duplicate_count increments
- error rows persist and return in `GET /imports/{id}/rows?status=error`

### Manual QA
- Import December sample file
- Re-import same file -> 0 new transactions
- Duplicate `VIR Virement` row in file -> only one transaction
- On `/imports`, uploader is always visible at top
- Clicking an import updates Import results tab
- No categorization actions appear in Import results

## Assumptions and Defaults
- Single account per file; if multiple accounts appear, mark rows as error.
- All errors are stored on `import_rows`.
- Stats stored on `imports` for list/detail performance.
- API base URL defaults to `http://localhost:8000`.
- Import results tab is last/selected import only.

## Out of Scope
- Rules engine / auto-categorization
- Splits editor
- Analytics
