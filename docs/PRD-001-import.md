# PRD-001 - Import Tab (v1)

## Goal
Allow user to import a CSV export, store raw rows, upsert canonical transactions with dedupe, and inspect imports.

## Import Tab IA (v1)
Route: `/imports`

Layout:
- Section A - Import file (always visible at top)
- Section B - Tabs

Section A - Import file:
- Upload zone + "Import CSV"
- After import: show stats (created/linked/duplicates/errors) + primary CTA "View import results"

Section B - Tabs:
- Imports (history): table exactly as described below (imported_at, file_name, account, stats)
- Imports (history): clicking a row selects that import and updates the Import results tab
- Import results (recommended: last/selected import results): shows transactions/rows created or linked by the most recent or selected import
- Import results: avoids duplicating PRD-002's global transactions experience
- If "All imported transactions" is used instead of Import results: must be read-only
- If "All imported transactions" is used instead of Import results: must include Import filter (required)
- If "All imported transactions" is used instead of Import results: must not include categorization actions (belongs to Inbox in PRD-002)

## User stories
- As a user, I upload a CSV and see "X new transactions created, Y linked to existing, Z duplicates ignored".
- As a user, I can browse previous imports and drill into which rows were in each import.
- As a user, I can click a row and see which canonical transaction it linked to (or why it failed).

## UI (v1)
Sidebar tab: Import

Single route: `/imports` (ImportsPage container)
- Uploader section at top (sticky or first section)
- Tabs below: Imports | Import results

Imports tab:
- table: imported_at, file_name, account, stats (new/linked/dupes/errors)
- action: uses uploader section above (Upload zone + "Import CSV")
- empty state: explain supported columns + sample file expectations
- row click: selects import and updates Import results tab (and switches to it)

Import results tab:
- header: import metadata (date, file_hash, account)
- summary cards: created / linked / duplicates / errors
- table of import rows: dateVal, label, supplierFound, amount, raw category, linked transaction id
- filter: all / unlinked / errors
- row click opens drawer

Row detail drawer:
- raw_json viewer
- normalization preview (parsed dates, amount, label_norm, inferred type, inferred payee)
- linked canonical transaction preview

Optional deep inspection:
- Keep `/imports/:id` detail page only if needed for deep inspection (row drawer, raw_json, etc.)

## Backend behavior
- Upload endpoint parses CSV with robust delimiter handling (tabs or commas) and header mapping
- Store Import + ImportRows
- For each row: compute row_hash (to detect dupes within same import)
- For each row: normalize fields
- For each row: compute transaction fingerprint
- For each row: upsert transaction by fingerprint
- For each row: link row to transaction in import_row_links
- Return stats (counts + top errors)

## Parsing specifics (from observed data)
- delimiter appears to be tab-separated in provided sample
- decimal format: comma decimals, spaces thousands
- negative expenses, positive income/refunds
- accountbalance is balance after transaction (optional usage)

## Acceptance criteria
- Can import December sample successfully.
- Rows with duplicate identical "VIR Virement depuis LIVRET A 150,00" that appear twice in file do not create 2 transactions (dedupe works).
- Import history persists across refresh.
- On `/imports`, the Import file section is always visible at the top.
- Tabs exist and persist state: Imports shows history.
- Tabs exist and persist state: Import results shows transactions/rows tied to an import.
- Clicking an import in history updates the Import results tab (selected import model).
- No categorization actions appear in Import results (belongs to Inbox in PRD-002).

## Plan vs PRD audit (PRD-001-import-plan.md)
Status: aligned with PRD-001-import-plan.md.
- No open gaps between plan and PRD as of this revision.
