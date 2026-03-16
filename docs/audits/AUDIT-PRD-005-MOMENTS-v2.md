# AUDIT-PRD-005: Moments v2 (Central Modal Overlay)

## Objective + Scope Summary
- Objective: plan and execute a repository-grounded audit for `PRD-005 Moments v2`, focused on introducing a **central Moment modal overlay** with `Tagged` + `Candidates` flows and consistent split-tagging behavior across Ledger and Analytics.
- Scope (audit-only in this phase): DB schema/migrations, backend API surface, candidate computation + accept/reject persistence, frontend Moments modal/tables, transaction detail moment selector behavior, analytics exclusion toggle, and unsplit category-assignment parity behavior.
- Out of scope (per PRD v2): rules-engine auto-tagging, multi-tagging (one split -> many moments), and Moments-local analytics toggle.

## Decisions Locked (from PRD + current baseline)
- `dateOp` is the candidate anchor (PRD term); in current backend model this maps to `transactions.operation_at`.
- Moments are defined by **selected/tagged splits**, not "all splits in date range."
- A split can be tagged to **0 or 1** moment (`splits.moment_id` single FK).
- Tagging may be out-of-range (manual assignment allowed even when split date is outside moment range).
- Candidate flow persists decisions (`pending | accepted | rejected`) and should not lose accept/reject states on refresh.
- Reassigning a split from one moment to another requires explicit confirmation.
- Deleting a moment must untag splits (`moment_id -> null`).
- Candidate accept behavior for unsplit/transaction-level rows is no-friction: auto-create a canonical single split equivalent to the transaction and tag it during accept (no `Split first` blocking UX).
- Analytics exclusion toggle for moment-tagged splits lives in Analytics (not Moments UI), defaults to showing tagged splits (`exclude_moment_tagged=false`), and persists for the current session only.
- No cross-screen consistency requirement for `exclude_moment_tagged` between Analytics and Ledger mini-flow (each screen may maintain independent defaults/state).

## Audit Questions Checklist
### DB / Schema
- [x] Do existing tables/indexes support PRD-005 (`moments`, `splits.moment_id`, `dateOp` anchor index, `moment_candidates`) without regressions?
- [x] What migration sequence is required (including constraints/invariants) and what rollback risks exist?
- [x] How should candidate lifecycle timestamps (`first_seen_at`, `last_seen_at`, `decided_at`) be stored and indexed?

### API / Backend
- [x] Which endpoints are needed for moments CRUD, candidate refresh/list/filter, accept/reject, bulk actions, and reassignment confirmation?
- [x] Where should candidate computation live (router vs service) and how will decisions persist safely?
- [x] Which invariants are enforced server-side (single moment per split, accepted <-> split.moment_id consistency)?

### UI / UX
- [x] How should the central modal overlay be structured (route/state ownership, tab model, table state, bulk actions)?
- [x] Where are existing modal/table patterns that should be reused to avoid UI drift?
- [x] How should split reassignment confirmation and "Split first" CTA be surfaced?

### Analytics
- [x] Where are analytics filters applied today and where should `exclude_moment_tagged` be threaded?
- [x] Are flow/payee/internal-account queries consistently split-based and compatible with exclusion logic?
- [x] Which tests must be added/updated to prevent filter regressions?

## Workstreams
### A) DB & Migrations
- Goal: define minimal, safe schema changes for moments candidates + indexes/invariants.
- Exact questions to answer:
  - Does current schema already include required moment fields and indexes?
  - What new tables/indexes/constraints are needed for `moment_candidates`?
  - Is `dateOp` index already present or required (`transactions.operation_at` and/or split-level support)?
- Files to inspect:
  - `backend/alembic/versions/0001_initial_schema.py`
  - `backend/alembic/versions/` (new migration placeholder for PRD-005)
  - `backend/app/models/moment.py`
  - `backend/app/models/split.py`
  - `backend/app/models/transaction.py`
  - `[placeholder] backend/app/models/moment_candidate.py` (if created)
- Outputs expected:
  - Proposed schema delta (DDL-level list)
  - Migration plan order + downgrade notes
  - Invariant checklist (DB + app-layer)
- Dependencies: none.
- Parallelization: can run in parallel with B, D, G after baseline mapping.
- Status: COMPLETE (Session 2 audit baseline complete; implementation not started)

### B) Backend API Endpoints
- Goal: map current moments/transactions API and define exact endpoint deltas for v2.
- Exact questions to answer:
  - What moments endpoints exist now and what is missing for central modal and candidate flow?
  - Which endpoint contracts should support tagged tab, candidates tab, bulk accept/reject/remove/move, and delete moment behavior?
  - How should errors/validation be normalized for frontend consumption?
- Files to inspect:
  - `backend/app/routers/moments.py`
  - `backend/app/routers/transactions.py`
  - `backend/app/main.py`
  - `backend/tests/test_ledger_v2.py`
  - `[placeholder] backend/tests/test_moments.py`
- Outputs expected:
  - Endpoint inventory (existing vs required)
  - Request/response contract draft
  - API dependency map for frontend workstreams
- Dependencies: A for final schema fields.
- Parallelization: parallel with D/G; coordinate with C for candidate semantics.
- Status: COMPLETE (Session 2 audit baseline complete; implementation not started)

### C) Candidate Computation + Accept/Reject State
- Goal: specify canonical candidate selection/refresh/decision state machine.
- Exact questions to answer:
  - What is the exact eligibility query and how is rejected-state persistence handled?
  - What updates are required on accept/reject/move/delete to keep `splits.moment_id` and candidate status consistent?
  - How to handle drift (candidate becomes ineligible after external changes)?
- Files to inspect:
  - `backend/app/routers/moments.py`
  - `backend/app/models/moment.py`
  - `backend/app/models/split.py`
  - `backend/app/routers/transactions.py`
  - `[placeholder] backend/app/services/moment_candidates.py`
  - `[placeholder] backend/tests/test_moment_candidates.py`
- Outputs expected:
  - Candidate state machine (events + transitions)
  - Query/refresh algorithm sketch
  - Consistency rules list (accept/reject/reassign/delete)
- Dependencies: A (schema), B (API contracts), G (unsplit parity behavior).
- Parallelization: mostly parallel after A/B interfaces are known.
- Status: COMPLETE (Session 3 Part C audit baseline complete; implementation not started)

### D) UI Moments Tab + Central Modal + Tables
- Goal: map frontend architecture for central modal overlay and reusable table patterns.
- Exact questions to answer:
  - Where should modal state live (`moments-page` local state vs route-driven)?
  - Which existing modal/table components can be reused directly?
  - What UI states are needed for tagged/candidates filters, selection, and bulk actions?
- Files to inspect:
  - `frontend/src/pages/moments-page.tsx`
  - `frontend/src/main.tsx`
  - `frontend/src/components/application/modals/modal.tsx`
  - `frontend/src/components/application/table/table.tsx`
  - `frontend/src/services/moments.ts`
  - `[placeholder] frontend/src/components/moments/*`
- Outputs expected:
  - UI component map + ownership boundaries
  - Modal interaction/state model
  - Table interaction spec (selection/actions/pagination)
- Dependencies: B for endpoint contracts, C for candidate-state semantics.
- Parallelization: parallel with A/B reconnaissance; integration after C stabilizes.
- Status: COMPLETE (Session 4 audit baseline complete; implementation not started)

### E) Transaction Detail Moment Selector
- Goal: verify and plan split-row moment selector behavior, including reassignment confirmations.
- Exact questions to answer:
  - How is moment currently selected per split and where is confirmation UX missing?
  - How does split save payload carry `moment_id` today?
  - How should out-of-range manual tagging be represented in UI copy/validation?
- Files to inspect:
  - `frontend/src/components/ledger/splits/split-editor-modal.tsx`
  - `frontend/src/components/ledger/splits/split-editor.tsx`
  - `frontend/src/components/ledger/splits/use-split-draft.ts`
  - `frontend/src/pages/ledger/dashboard-page.tsx`
  - `frontend/src/services/transactions.ts`
  - `frontend/src/services/moments.ts`
- Outputs expected:
  - Transaction-detail interaction map
  - Confirmation decision table (set/change/clear moment)
  - Payload compatibility checklist
- Dependencies: B for endpoint behavior, C for reassignment rules.
- Parallelization: parallel with D once candidate semantics are known.
- Status: COMPLETE (Session 4 audit baseline complete; implementation not started)

### F) Analytics Toggle: Exclude Moment-Tagged Splits
- Goal: locate and define end-to-end analytics filter threading for moment exclusion.
- Exact questions to answer:
  - Where are analytics query params built and consumed now?
  - How should `exclude_moment_tagged` apply across flow/payees/internal-accounts consistently?
  - How should date filters + exclude-transfer + moment exclusion combine?
- Files to inspect:
  - `backend/app/routers/analytics.py`
  - `frontend/src/services/analytics.ts`
  - `frontend/src/pages/analytics-page.tsx`
  - `backend/tests/test_analytics.py`
  - `[placeholder] frontend/src/components/analytics/*`
- Outputs expected:
  - Filter contract delta (`exclude_moment_tagged` propagation)
  - Query-path matrix by endpoint
  - Test matrix for filter combinations
- Dependencies: A (schema field availability), B (API signature).
- Parallelization: parallel with D/E.
- Status: COMPLETE (Session 5 audit baseline complete; implementation not started)

### G) Existing Unsplit Category Assignment Behavior (Parity Requirement)
- Goal: document exact current behavior when a transaction has no splits, and reuse it for Moments candidate acceptance.
- Exact questions to answer:
  - Does current UI auto-create one split when category is assigned at transaction-level?
  - Where does backend enforce/rely on that behavior?
  - Are there edge paths where app blocks and requires split editor first?
- Files to inspect:
  - `frontend/src/pages/ledger/dashboard-page.tsx`
  - `frontend/src/components/ledger/transactions/transactions-table.tsx`
  - `frontend/src/services/transactions.ts`
  - `backend/app/routers/transactions.py`
  - `backend/app/services/rules_engine.py`
  - `backend/tests/test_ledger_v2.py`
- Outputs expected:
  - Parity decision memo (auto-create vs split-first)
  - Reusable UX copy/actions for candidate accept flow
  - Risk list for behavior divergence
- Dependencies: none (feeds C and E).
- Parallelization: can be executed immediately in parallel with A/B/D.
- Status: COMPLETE (Session 5 parity closure complete; implementation not started)

## Sessions
### Session 1 (current, short) - Audit bootstrap + minimal reconnaissance
- Create and initialize tracking document.
- Lock PRD decisions for v2 scope (dateOp, selected splits, accept/reject persistence).
- Map top-level repo structure and identify backend/frontend frameworks.
- Identify primary schema/model/router/page files for moments, splits, analytics.
- Define workstreams, dependencies, and session-splittable execution plan.

### Session 2 - DB + Backend contract baseline (A + B in parallel)
- Audit current `moments` and `splits` schema vs PRD-required fields/indexes.
- Draft `moment_candidates` schema and migration sequence.
- Inventory existing moments/transactions endpoints and identify missing routes/actions.
- Produce endpoint contract draft for tagged/candidates/bulk actions.
- Capture open API decisions requiring user sign-off.

### Session 3 - Candidate engine + unsplit parity (C + G in parallel)
- Formalize candidate eligibility query + refresh semantics.
- Define state transitions for pending/accepted/rejected and drift handling.
- Audit unsplit category-assignment behavior end-to-end and lock parity rule for Moments accept.
- Map split reassignment and delete-moment side effects.
- Produce consistency/invariant checklist tied to API actions.

### Session 4 - Frontend modal architecture + transaction detail integration (D + E in parallel)
- Map Moments page ownership and central modal state strategy.
- Define tagged/candidates table interaction model (filters, selection, bulk actions).
- Audit current split editor moment selector and required confirmation points.
- Produce component map and UI flow diagram notes for implementation.
- List frontend service contract changes and data-shape needs.

### Session 5 - Analytics integration + audit synthesis (F + cross-stream closure)
- Trace analytics filter threading and define `exclude_moment_tagged` behavior.
- Build test matrix covering analytics + moments interactions.
- Resolve remaining cross-stream dependencies and decision gaps.
- Produce final implementation-ready audit summary with prioritized execution order.
- Mark workstream statuses and open risks.

## Session 2 Outputs (Workstreams A + B)
### A) DB & Migrations
- Existing coverage: `moments` table and nullable `splits.moment_id` FK exist, but no `moment_candidates` table exists and no migration currently introduces it.
- Existing index gap: migrations only create `ix_import_row_links_transaction_id` and lineage/manual-event indexes; no index exists for `splits(moment_id)` or `transactions(operation_at)` even though PRD-005 candidate selection anchors on operation date.
- Existing invariant gap: no DB check ensures `moments.start_date <= moments.end_date`, and no DB/app invariant currently links accepted candidate state to `splits.moment_id`.
- Proposed schema delta (DDL-level):
- Add `moment_candidates` table with `id`, `moment_id`, `split_id`, `status`, `first_seen_at`, `last_seen_at`, `decided_at`, `decided_by` (nullable), `note` (nullable).
- Add unique constraint `uq_moment_candidates_moment_id_split_id` on (`moment_id`, `split_id`).
- Add FK constraints from `moment_candidates.moment_id -> moments.id` and `moment_candidates.split_id -> splits.id` with `ON DELETE CASCADE`.
- Add indexes `ix_moment_candidates_moment_status` on (`moment_id`, `status`) and `ix_moment_candidates_split_id` on (`split_id`).
- Add index `ix_splits_moment_id` on `splits(moment_id)`.
- Add index `ix_transactions_operation_at` on `transactions(operation_at)`.
- Add check constraint `ck_moments_valid_date_range` enforcing `start_date <= end_date`.
- Add `moments.updated_at` timestamp (non-null) for CRUD parity with PRD.
- Migration sequence recommendation:
- Migration 1: add `moments.updated_at` nullable, backfill `now()`, then set `NOT NULL`.
- Migration 2: add date-range check constraint on `moments`.
- Migration 3: create `moment_candidates` table + constraints + indexes.
- Migration 4: add `ix_splits_moment_id` and `ix_transactions_operation_at`.
- Rollback risks:
- Downgrading after creating candidate history loses accept/reject decisions.
- If API starts depending on `updated_at`, rollback must also remove or guard response fields.
- Large ledgers may see lock contention when adding new indexes; schedule during low-traffic window.
- Timestamp/index guidance for candidate lifecycle:
- Store lifecycle times as timezone-aware `DateTime` aligned with existing `created_at` conventions.
- Keep `first_seen_at` immutable after insert; update `last_seen_at` on refresh.
- Set `decided_at` when status transitions to `accepted` or `rejected`, clear only if explicitly reset back to `pending`.

### B) Backend API Endpoints
- Existing endpoint inventory:
- `GET /moments` is the only moments endpoint.
- Transactions endpoints currently available: `GET /transactions`, `GET /transactions/summary`, `GET /transactions/{id}`, `PATCH /transactions/{id}`, `PUT /transactions/{id}/splits`.
- Existing behavior relevant to moments:
- `PUT /transactions/{id}/splits` accepts `moment_id`, validates existence, and writes directly to `splits.moment_id`; there is no reassignment confirmation contract and no candidate-state persistence.
- Required endpoint delta for PRD-005 v2:
- Add moments CRUD: `POST /moments`, `GET /moments/{id}`, `PATCH /moments/{id}`, `DELETE /moments/{id}`.
- Add tagged tab endpoints: `GET /moments/{id}/tagged`, bulk remove tagged splits, bulk move tagged splits with explicit reassignment confirmation contract.
- Add candidates endpoints: `POST /moments/{id}/candidates/refresh`, `GET /moments/{id}/candidates?status=pending|accepted|rejected`, and bulk decision endpoint for accept/reject.
- Add delete behavior contract that untags splits (`moment_id = null`) before deleting the moment.
- Contract normalization recommendations:
- Use stable machine-readable error codes in `detail.code` (for example `MOMENT_NOT_FOUND`, `MOMENT_REASSIGN_CONFIRM_REQUIRED`, `SPLIT_NOT_ELIGIBLE`, `SPLIT_REQUIRES_SPLIT_FIRST`).
- Normalize missing-resource semantics to `404` across moments/splits rather than mixed `400` responses.
- Use `409` for confirmation-required conflicts and `422` for validation errors.
- Candidate computation placement recommendation:
- Implement candidate eligibility/refresh/decision logic in a dedicated service module (for example `backend/app/services/moment_candidates.py`) and keep routers thin to avoid duplication between refresh/list/decision/bulk actions.
- API dependency map for frontend workstreams:
- `frontend/src/services/moments.ts` currently depends only on `GET /moments`.
- `frontend/src/services/transactions.ts` already carries `moment_id` through split payloads (`PUT /transactions/{id}/splits`), so reassignment/error-code changes affect ledger split editor flows.
- `frontend/src/pages/moments-page.tsx` is still an empty-state page; central modal/tagged/candidates UI has no backend-backed integration yet.

## Session 2 Discovered File Paths
- `backend/alembic/versions/0001_initial_schema.py`
- `backend/alembic/versions/0004_ledger_v2.py`
- `backend/alembic/versions/0010_counterparty_merge_phase_d.py`
- `backend/app/models/moment.py`
- `backend/app/models/split.py`
- `backend/app/models/transaction.py`
- `backend/app/routers/moments.py`
- `backend/app/routers/transactions.py`
- `backend/app/main.py`
- `backend/tests/test_ledger_v2.py`
- `backend/tests/test_split_invariant.py`
- `frontend/src/services/moments.ts`
- `frontend/src/services/transactions.ts`
- `frontend/src/pages/moments-page.tsx`

## Session 3 Outputs (Workstream C)
### C) Candidate Computation + Accept/Reject State
- Existing implementation baseline:
- No candidate persistence model/service exists yet (`backend/app/services/moment_candidates.py` and `backend/tests/test_moment_candidates.py` are both absent).
- Current moments API remains read-only (`GET /moments`) and does not expose candidate refresh/list/decision routes.
- Canonical candidate query shape (service-level target):
- Anchor on `transactions.operation_at` (PRD `dateOp`) by joining `splits -> transactions`.
- Candidate-eligible rows are splits where `splits.moment_id IS NULL` and `transactions.operation_at` is in `[moments.start_date, moments.end_date]`.
- Left-join `moment_candidates` on (`moment_id`, `split_id`) so accepted/rejected history can be preserved and filtered without losing state on refresh.
- Candidate lifecycle state machine (recommended):
- `refresh`: upsert missing rows as `pending`; update `last_seen_at` on every currently eligible row; keep existing `accepted`/`rejected` statuses unchanged.
- `accept`: atomically set `splits.moment_id = <moment_id>` and set candidate status to `accepted` with `decided_at`.
- `reject`: set candidate status to `rejected` with `decided_at` and do not modify `splits.moment_id`.
- `reassign`: move `splits.moment_id` from source to target only via explicit confirmation; rewrite candidate rows for both moments in the same DB transaction.
- `delete moment`: untag linked splits first, then delete moment; candidate rows should cascade-delete with the moment to avoid orphans.
- Drift + consistency risks discovered:
- Split identity churn risk: both `PUT /transactions/{id}/splits` and rules-engine split replacement delete/recreate split rows, so candidate history keyed by `split_id` can be dropped or detached unless remap/lineage handling is designed.
- Invariant gap: no current server-side guard enforces `moment_candidates.status='accepted'` <-> `splits.moment_id=<moment_id>` consistency.
- Unsplit acceptance dependency: split validation currently requires `category_id` for each split payload, so candidate acceptance for unsplit transactions depends on Workstream G parity decision.
- Concurrency risk: refresh and accept/reject can race without transactional upsert + row-locking around (`moment_id`, `split_id`) decisions.

## Session 3 Discovered File Paths (Part C)
- `docs/PRD-005-moments.md`
- `backend/app/routers/moments.py`
- `backend/app/routers/transactions.py`
- `backend/app/models/moment.py`
- `backend/app/models/split.py`
- `backend/app/models/transaction.py`
- `backend/app/models/rule.py`
- `backend/app/services/ledger_validation.py`
- `backend/app/services/rules_engine.py`
- `backend/tests/test_ledger_v2.py`
- `backend/tests/test_split_invariant.py`
- `[missing] backend/app/services/moment_candidates.py`
- `[missing] backend/tests/test_moment_candidates.py`

## Session 4 Outputs (Workstreams D + E)
### D) UI Moments Tab + Central Modal + Tables
- Existing frontend baseline:
- `frontend/src/pages/moments-page.tsx` is currently a static empty state; there is no Moments modal orchestration, no tabs, no table rows, and no bulk-action state yet.
- Route topology in `frontend/src/main.tsx` exposes only `/moments` (no nested route like `/moments/:id`); no URL-search-param modal pattern is used elsewhere, so modal state is currently page-local by convention.
- Reusable UI patterns confirmed:
- Modal primitives: `frontend/src/components/application/modals/modal.tsx` (overlay/backdrop/animation/focus handling) with consistent usage in split and rules modals.
- Table primitives: `frontend/src/components/application/table/table.tsx` already supports row selection (`selectionBehavior === "toggle"`, checkboxes, sortable heads) even though current ledger table usage is single-row action oriented.
- Tab primitives: `frontend/src/components/application/tabs/tabs.tsx` supports badge counts and manual keyboard activation, suitable for `Tagged` / `Candidates`.
- Existing table card + empty state + pagination composition reference: `frontend/src/components/ledger/transactions/transactions-table.tsx`.
- UI ownership boundary recommendation (implementation target):
- Keep top-level state in `frontend/src/pages/moments-page.tsx` for: selected moment, overlay open/close, active tab, per-tab filters, per-tab pagination, per-tab row selection, and pending bulk action.
- Introduce `frontend/src/components/moments/*` to isolate presentation and row rendering (`moments-list`, `moment-overlay`, `tagged-table`, `candidates-table`, `bulk-action-bar`) and keep page file orchestration-only.
- Keep data fetching/contract mapping in `frontend/src/services/moments.ts`; do not couple modal components directly to `apiFetch`.
- Table interaction spec (for implementation phase):
- Use shared `Table` with `selectionMode="multiple"` for both Tagged and Candidates, with stable row ids (`split_id` or candidate-row id) and a single bulk-action toolbar above each table.
- Clear selection when moment, tab, filter, or page changes to avoid cross-context bulk mutations.
- Preserve transaction drill-down action per row (open transaction detail/split editor) in addition to bulk operations.
- Risks discovered:
- Without route-driven state, opening a specific moment overlay is not deep-linkable and browser back-button semantics are limited.
- `frontend/src/components/moments/` does not exist yet, so implementation starts from zero and risks logic crowding in `moments-page.tsx` unless component boundaries are enforced.
- Current `frontend/src/services/moments.ts` only supports `GET /moments`; all tagged/candidates/bulk contracts from Session 2 are still missing.

### E) Transaction Detail Moment Selector
- Current interaction map:
- Split editor modal is owned by `frontend/src/pages/ledger/dashboard-page.tsx` (`splitModalOpen`, `splitModalTransactionId`, `splitModalData`) and opened from both transactions table and transaction-detail drawer CTA.
- `frontend/src/components/ledger/splits/split-editor.tsx` exposes per-split `Moment` select with options `No moment` + fetched moments; changes update local draft only until Save.
- Save flow (`handleSaveSplits`) sends full split replacement through `replaceTransactionSplits` in `frontend/src/services/transactions.ts`, including `moment_id` on every split row.
- Confirmation UX baseline:
- Existing confirmations cover only discard edits and "replace with single split" in `split-editor-modal.tsx`.
- There is no moment-specific reassignment confirmation (change moment A -> B) and no "Split first" CTA in the moment selector flow.
- Out-of-range manual tagging baseline:
- UI allows selecting any moment name regardless of split/transaction date and provides no copy or indicator for out-of-range assignment (implicit support, low explainability).
- Payload compatibility checklist:
- Compatible now: split payload already carries nullable `moment_id` and backend validates moment existence.
- Contract gap: no `confirm_reassign` flag or conflict/error-code branch is exposed, so frontend cannot implement explicit reassignment confirmation without API extension.
- Error-mapping gap: `mapSplitErrorMessage` only maps split sum/sign/category errors; moment-specific conflict codes would currently surface as raw strings.
- Persistence caveat: backend `PUT /transactions/{id}/splits` deletes and recreates all split rows, so split-id-based candidate history can drift unless remapped.
- Decision table for implementation phase:
- `null -> moment_id`: allow without confirmation.
- `moment_id A -> moment_id B`: require explicit confirmation dialog before submit.
- `moment_id -> null`: allow direct clear (or soft-confirm only if product wants extra guardrail).
- Unsplit transaction from candidate accept path: follow Session 3/G parity baseline (auto-create single split behavior), otherwise route to split editor with explicit "Split first" CTA.
- Risks discovered:
- Reassignment confirmation required by PRD is currently absent end-to-end.
- Full split replacement semantics increase risk of candidate-link drift and race conditions once candidate persistence is added.

## Session 4 Discovered File Paths (D + E)
- `docs/PRD-005-moments.md`
- `frontend/src/main.tsx`
- `frontend/src/providers/router-provider.tsx`
- `frontend/src/pages/moments-page.tsx`
- `frontend/src/pages/ledger/dashboard-page.tsx`
- `frontend/src/components/application/modals/modal.tsx`
- `frontend/src/components/application/slideout-menus/slideout-menu.tsx`
- `frontend/src/components/application/table/table.tsx`
- `frontend/src/components/application/tabs/tabs.tsx`
- `frontend/src/components/ledger/transactions/transactions-table.tsx`
- `frontend/src/components/ledger/splits/split-editor-modal.tsx`
- `frontend/src/components/ledger/splits/split-editor.tsx`
- `frontend/src/components/ledger/splits/use-split-draft.ts`
- `frontend/src/services/moments.ts`
- `frontend/src/services/transactions.ts`
- `backend/app/routers/moments.py`
- `backend/app/routers/transactions.py`
- `[missing] frontend/src/components/moments/*`

## Session 5 Outputs (Workstreams F + G closure)
### F) Analytics Toggle: Exclude Moment-Tagged Splits
- Existing filter-threading baseline:
- `frontend/src/pages/analytics-page.tsx` owns filter state and currently threads only `start_date`, `end_date`, `granularity`, `mode`, and `exclude_transfers` into all three analytics calls.
- `frontend/src/services/analytics.ts` serializes only existing params above for `/analytics/flow`, `/analytics/payees`, and `/analytics/internal-accounts`.
- `backend/app/routers/analytics.py` consumes `exclude_transfers` in each endpoint via `_allowed_types`; there is no moment-aware filter in any query yet.
- Query-path matrix + exclusion compatibility:
- `/analytics/flow` has two query paths: split-backed rows (`join Split`) plus unsplit transaction fallback (`outerjoin Split ... Split.id IS NULL`).
- Moment exclusion should apply only to split-backed rows (`Split.moment_id IS NULL` when `exclude_moment_tagged=true`); unsplit rows must stay included because they cannot be moment-tagged.
- `/analytics/payees` and `/analytics/internal-accounts` are split-joined only, so the same `Split.moment_id IS NULL` condition can be applied directly without extra fallback paths.
- Proposed contract delta (implementation target):
- Add `exclude_moment_tagged` query param to all three analytics endpoints and all frontend analytics service methods.
- Thread the new toggle from `frontend/src/pages/analytics-page.tsx` and keep it aligned with existing filters (`start_date`, `end_date`, `exclude_transfers`, `granularity`, `mode`).
- Extend ledger mini-flow fetch (`frontend/src/pages/ledger/dashboard-page.tsx`) to pass the same flag (or explicitly choose a fixed default) so analytics semantics do not diverge by screen.
- Test matrix required to prevent regressions:
- `flow`: verify `exclude_moment_tagged=true` removes tagged split totals/links but still keeps unsplit transaction contribution.
- `flow`: verify `exclude_moment_tagged=false` preserves current totals.
- `payees` + `internal-accounts`: verify tagged split exclusion updates grouped rows and totals consistently.
- Combination coverage: `exclude_transfers` on/off + `exclude_moment_tagged` on/off + date window filters.
- API compatibility: verify default behavior when param omitted.
- Risks discovered:
- Analytics windows are currently `Transaction.posted_at`-based while candidate discovery is `Transaction.operation_at`-based; users may perceive date-range mismatch after exclusions.
- Existing analytics tests cover transfer/mode behavior only; there is no moment-tagged coverage yet.

### G) Existing Unsplit Category Assignment Behavior (Parity Requirement)
- Parity baseline confirmed:
- Transaction detail category assignment auto-creates a single split when `splits_count === 0` (`frontend/src/pages/ledger/dashboard-page.tsx`), with full transaction amount and null moment/internal-account fields.
- Table UX already reinforces this pattern: unsplit rows show "Uncategorized" + "Create split" CTA (`frontend/src/components/ledger/transactions/transactions-table.tsx`).
- Backend enforces split shape via `validate_splits` (`backend/app/services/ledger_validation.py`): every provided split requires `category_id`, while empty split arrays remain allowed.
- Rules engine mirrors the same auto-create behavior for `set_category` by creating one full-amount split (`backend/app/services/rules_engine.py`).
- Parity decision memo for Moments accept:
- Current app behavior for transaction-level category assignment is **auto-create single split**.
- For Moments candidate accept, parity is blocked if no category is available: `replace_splits` validation will reject category-less rows with `SPLIT_CATEGORY_REQUIRED`.
- Locked implementation direction (2026-02-21): use API-assisted single-split creation + tagging in one flow; do not block with `Split first` UX.
- Implementation invariant: backend accept path must supply/derive a valid `category_id` for the created split to satisfy `validate_splits`.
- Cross-stream risk closure:
- Candidate acceptance implementation must not assume category-less split creation; this is a hard backend validation boundary.
- Split replacement still recreates split ids, so candidate history keyed by split id remains drift-prone unless lineage/remap logic is added during implementation.

### Session 5 Synthesis (Implementation-Ready Order)
- Prioritized execution order:
- 1) Implement backend Moments CRUD + candidate service + `moment_candidates` persistence/invariants (Workstreams A/B/C).
- 2) Implement reassignment-confirmation/error-code contract and align split-editor handling (Workstreams B/E).
- 3) Build Moments central modal/tagged/candidates UI and wire bulk actions (Workstream D).
- 4) Add analytics `exclude_moment_tagged` contract + UI toggle + endpoint filters (Workstream F).
- 5) Add regression tests for candidate lifecycle, split-id drift edge cases, and analytics filter combinations (Workstreams C/F/G).
- Decisions locked on 2026-02-21 (ready for implementation):
- `exclude_moment_tagged` defaults to `false` (show tagged splits), persists only for the active session, and does not require cross-screen consistency with Ledger mini-flow.
- Candidate accept for unsplit/transaction-level rows uses API-assisted single-split creation + tagging in one flow (no `Split first` blocking step).

## Session 5 Discovered File Paths (F + G closure)
- `docs/PRD-005-moments.md`
- `backend/app/routers/analytics.py`
- `backend/tests/test_analytics.py`
- `frontend/src/services/analytics.ts`
- `frontend/src/pages/analytics-page.tsx`
- `frontend/src/pages/ledger/dashboard-page.tsx`
- `frontend/src/components/ledger/transactions/transactions-table.tsx`
- `frontend/src/services/transactions.ts`
- `backend/app/routers/transactions.py`
- `backend/app/services/rules_engine.py`
- `backend/app/services/ledger_validation.py`

## Findings Log (append-only)
- 2026-02-21 12:04:49 +01:00 | Inspected top-level repository structure. | Found primary app partitions: `backend/`, `frontend/`, `docs/`, `scripts/`. | Files: `backend`, `frontend`, `docs`, `scripts`
- 2026-02-21 12:04:49 +01:00 | Inspected backend framework + migrations baseline. | Backend is FastAPI + SQLAlchemy with Alembic migrations in `backend/alembic/versions/`; moments model and split FK already exist. | Files: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/db.py`, `backend/alembic/versions/0001_initial_schema.py`, `backend/app/models/moment.py`, `backend/app/models/split.py`
- 2026-02-21 12:04:49 +01:00 | Inspected current moments, transactions, and UI routing surface. | `moments` backend router currently exposes list endpoint; frontend routes include `/moments`; split editor payload already carries `moment_id`. | Files: `backend/app/routers/moments.py`, `backend/app/routers/transactions.py`, `frontend/src/main.tsx`, `frontend/src/services/moments.ts`, `frontend/src/services/transactions.ts`, `frontend/src/pages/ledger/dashboard-page.tsx`
- 2026-02-21 12:04:49 +01:00 | Inspected modal/table component system and analytics filter flow. | UI uses `react-aria-components` wrappers for modal/table; analytics filters currently include dates + `exclude_transfers`, with backend filters in `analytics.py`. | Files: `frontend/src/components/application/modals/modal.tsx`, `frontend/src/components/application/table/table.tsx`, `frontend/src/services/analytics.ts`, `frontend/src/pages/analytics-page.tsx`, `backend/app/routers/analytics.py`
- 2026-02-21 12:04:49 +01:00 | Located unsplit category-assignment parity entrypoint. | Transaction detail currently auto-creates a single split when assigning category on unsplit transaction (candidate accept parity anchor). | Files: `frontend/src/pages/ledger/dashboard-page.tsx`, `backend/app/routers/transactions.py`, `frontend/src/services/transactions.ts`
- 2026-02-21 12:16:31 +01:00 | Completed Session 2 Workstream A schema/migration baseline audit. | Confirmed no `moment_candidates` model/table or candidate lifecycle persistence exists yet; identified missing indexes for `splits(moment_id)` and `transactions(operation_at)` and drafted migration sequence/rollback risks. | Files: `backend/alembic/versions/0001_initial_schema.py`, `backend/alembic/versions/0004_ledger_v2.py`, `backend/alembic/versions/0010_counterparty_merge_phase_d.py`, `backend/app/models/moment.py`, `backend/app/models/split.py`, `backend/app/models/transaction.py`
- 2026-02-21 12:16:31 +01:00 | Completed Session 2 Workstream B endpoint contract baseline audit. | Found moments API currently limited to `GET /moments`; identified required CRUD + tagged/candidates/bulk-action endpoints and normalized error-contract requirements for frontend central modal and split-editor integration. | Files: `backend/app/routers/moments.py`, `backend/app/routers/transactions.py`, `backend/app/main.py`, `backend/tests/test_ledger_v2.py`, `backend/tests/test_split_invariant.py`, `frontend/src/services/moments.ts`, `frontend/src/services/transactions.ts`, `frontend/src/pages/moments-page.tsx`
- 2026-02-21 12:25:31 +01:00 | Completed Session 3 Workstream C candidate state audit. | Defined candidate eligibility/refresh state machine and consistency rules, and confirmed candidate service/test placeholders are still missing. | Files: `docs/PRD-005-moments.md`, `backend/app/routers/moments.py`, `backend/app/models/moment.py`, `backend/app/models/split.py`, `backend/app/models/transaction.py`, `backend/app/routers/transactions.py`, `backend/app/services/ledger_validation.py`, `backend/app/services/rules_engine.py`
- 2026-02-21 12:25:31 +01:00 | Logged Part C drift and invariant risks. | Found split-id churn due full split replacement paths (ledger + rules engine), no accepted<->tag invariant enforcement, and unresolved unsplit acceptance dependency on parity behavior. | Files: `backend/app/routers/transactions.py`, `backend/app/services/rules_engine.py`, `backend/app/models/rule.py`, `backend/tests/test_ledger_v2.py`, `backend/tests/test_split_invariant.py`
- 2026-02-21 12:31:04 +01:00 | Completed Session 4 Workstream D modal/table architecture audit. | Confirmed Moments page is still empty-state only, cataloged reusable modal/table/tab primitives, and defined state ownership + table interaction model for central overlay implementation. | Files: `frontend/src/pages/moments-page.tsx`, `frontend/src/main.tsx`, `frontend/src/providers/router-provider.tsx`, `frontend/src/components/application/modals/modal.tsx`, `frontend/src/components/application/table/table.tsx`, `frontend/src/components/application/tabs/tabs.tsx`, `frontend/src/components/ledger/transactions/transactions-table.tsx`, `frontend/src/services/moments.ts`
- 2026-02-21 12:31:04 +01:00 | Completed Session 4 Workstream E transaction-detail selector audit. | Mapped split-editor moment selector/save flow, documented missing reassignment confirmation and "Split first" CTA behavior, and captured payload/error-contract compatibility gaps for PRD-005 integration. | Files: `frontend/src/components/ledger/splits/split-editor-modal.tsx`, `frontend/src/components/ledger/splits/split-editor.tsx`, `frontend/src/components/ledger/splits/use-split-draft.ts`, `frontend/src/pages/ledger/dashboard-page.tsx`, `frontend/src/services/transactions.ts`, `frontend/src/services/moments.ts`, `backend/app/routers/transactions.py`, `backend/app/routers/moments.py`
- 2026-02-21 12:37:48 +01:00 | Completed Session 5 Workstream F analytics threading audit. | Mapped frontend/backend analytics param flow, produced endpoint query-path matrix for `exclude_moment_tagged`, and defined regression test matrix for flow/payees/internal-accounts combinations. | Files: `backend/app/routers/analytics.py`, `backend/tests/test_analytics.py`, `frontend/src/services/analytics.ts`, `frontend/src/pages/analytics-page.tsx`, `frontend/src/pages/ledger/dashboard-page.tsx`
- 2026-02-21 12:37:48 +01:00 | Closed Session 5 cross-stream dependency on Workstream G parity behavior. | Confirmed unsplit category assignment auto-creates one split, identified `SPLIT_CATEGORY_REQUIRED` as acceptance boundary for category-less candidate paths, and documented "Split first" vs API-expansion decision point. | Files: `frontend/src/pages/ledger/dashboard-page.tsx`, `frontend/src/components/ledger/transactions/transactions-table.tsx`, `frontend/src/services/transactions.ts`, `backend/app/routers/transactions.py`, `backend/app/services/rules_engine.py`, `backend/app/services/ledger_validation.py`, `backend/tests/test_ledger_v2.py`
- 2026-02-21 12:37:48 +01:00 | Attempted targeted backend test execution for Session 5 areas. | `uv run pytest tests/test_analytics.py tests/test_ledger_v2.py -q` could not execute assertions because test harness skips DB tests when `TEST_DATABASE_URL` is unset in `backend/tests/conftest.py`. | Files: `backend/tests/conftest.py`, `backend/tests/test_analytics.py`, `backend/tests/test_ledger_v2.py`


