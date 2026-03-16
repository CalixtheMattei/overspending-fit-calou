# B1 - Transaction Categorization Flow Audit

Status: Completed (2026-02-28)
Owner: B1

## Goal
Audit transaction list to category assignment flow and define reliable next coding tickets for fast categorization without invariant regressions.

## Scope and evidence
- Frontend orchestration: `frontend/src/pages/ledger/dashboard-page.tsx`
- Table interactions: `frontend/src/components/ledger/transactions/transactions-table.tsx`
- Split modal/draft logic:
  - `frontend/src/components/ledger/splits/split-editor-modal.tsx`
  - `frontend/src/components/ledger/splits/split-editor.tsx`
  - `frontend/src/components/ledger/splits/use-split-draft.ts`
- API client and error mapping: `frontend/src/services/transactions.ts`
- Backend split contract:
  - `backend/app/routers/transactions.py`
  - `backend/app/services/ledger_validation.py`
- Existing backend coverage:
  - `backend/tests/test_ledger_v2.py`
  - `backend/tests/test_moments.py`
  - `backend/tests/test_categories.py`

## User flow map (current implementation)

### Entry points
- Transactions table row click opens detail drawer (`transactions-table.tsx:123`, `dashboard-page.tsx:914`).
- Table split action opens split modal directly (`transactions-table.tsx:168`, `dashboard-page.tsx:915`).

### Drawer quick categorize path (0 or 1 split)
1. User opens drawer.
2. If `splits_count > 1`, drawer blocks quick category change and routes to split modal (`dashboard-page.tsx:590`, `dashboard-page.tsx:993`).
3. If `splits_count === 0`, selecting a category creates one split for full tx amount (`dashboard-page.tsx:609-619`).
4. If `splits_count === 1`, selecting a category replaces that split category while preserving moment/internal account/note (`dashboard-page.tsx:620-628`).
5. Save uses `PUT /transactions/{id}/splits` via `replaceTransactionSplits` (`dashboard-page.tsx:631`, `transactions.ts:160`).
6. On success: update drawer state, sync split modal state if same tx, increment `refreshKey` to refetch table/flow (`dashboard-page.tsx:632-637`).

### Split modal path (multi-split and advanced edits)
1. Modal fetches full transaction detail when opened (`dashboard-page.tsx:388-416`).
2. Draft state + client validation handled by `useSplitDraft` (`use-split-draft.ts:75`).
3. Save disabled until local validation passes (`split-editor-modal.tsx:334-337`).
4. Save uses same replace-all endpoint with optional `confirm_reassign` for moment conflicts (`dashboard-page.tsx:487-525`, `transactions.py:390-400`).
5. On successful save: drawer sync (if same tx), global refresh key bump, close modal (`dashboard-page.tsx:507-513`).

## State sync and caching behavior
- Source of truth is local `useState`; no query cache layer.
- `refreshKey` invalidates both transaction list and Sankey flow together (`dashboard-page.tsx:210-247`, `dashboard-page.tsx:290-320`).
- Drawer detail and split modal detail are fetched independently, then manually synced on successful split mutation (`dashboard-page.tsx:508-510`, `dashboard-page.tsx:633-635`).
- Strategy is pessimistic update + refetch, not optimistic row patching.

## Breakpoints and risks

### P0
- Single-split "Uncategorized" action is exposed in drawer, but backend rejects null category in split payload (`dashboard-page.tsx:667-676`, `dashboard-page.tsx:620-631`, `ledger_validation.py:51-54`). Result: user-visible validation error instead of intentional uncategorize behavior.
- Every categorize/save currently triggers full table refetch and flow refetch via shared `refreshKey`; this adds latency and extra network pressure for rapid categorization (`dashboard-page.tsx:511`, `dashboard-page.tsx:210-247`, `dashboard-page.tsx:290-320`).

### P1
- Quick categorize is only in drawer, not in the transactions table row itself, increasing click depth for high-volume categorization (`transactions-table.tsx:123`, `dashboard-page.tsx:989-1021`).
- Deprecated category remediation exists in split editor, but not drawer quick category selector; legacy/deprecated assignments are not handled uniformly (`split-editor.tsx:171-210`, `dashboard-page.tsx:667-676`).

### P2
- No frontend automated coverage for drawer/modal categorization paths; behavior relies on manual QA.

## Recommended UX strategy
- Keep dual-path model:
  - Quick path: lightweight categorization for 0/1 split transactions.
  - Full path: split editor for multi-split and moment/internal account edits.
- Tighten quick path semantics:
  - `0 splits + category -> create single split` (existing, keep).
  - `1 split + category change -> replace category` (existing, keep).
  - `1 split + Uncategorized -> send empty splits []` to intentionally clear categorization and stay API-valid.
  - `>1 splits -> route to split editor` (existing, keep).
- Decouple list refresh from flow refresh after category edits, or patch list row optimistically and defer flow refresh.

## Delegation outputs (tickets)
- [x] Ticket B1-1: Normalize quick categorize semantics for `Uncategorized` (single-split clear should issue `splits: []`, not invalid `category_id: null`).
- [x] Ticket B1-2: Add consistent inline split mutation error surface in drawer (code-aware copy from `mapSplitErrorMessage`) and avoid dead-end errors on supported actions.
- [x] Ticket B1-3: Implement row-level optimistic patch + scoped refetch policy (transactions list immediate update; Sankey flow refresh deferred or isolated).

## Suggested implementation order for next coding session
1. Fix quick-categorize uncategorize behavior (`1 split -> []`) and add regression backend/frontend test coverage.
2. Add optimistic transaction-row patching for quick categorize and split save success paths.
3. Split invalidation keys so category edits do not always refetch flow chart immediately.
4. Optional UX pass: add table-level quick category affordance for uncategorized/single-split rows.
