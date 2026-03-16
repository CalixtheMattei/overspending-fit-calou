# F1 - Moments Feature Audit

Status: Completed (2026-02-28)
Owner: F1
Commit context: `773fd310aa724159902383f9bdc2f5e33b038777`

## Goal
Audit moments completeness vs PRD-005, verify split-level tagging behavior, and propose a practical cover image direction.

## Scope and evidence
- Frontend:
  - `frontend/src/pages/moments-page.tsx`
  - `frontend/src/components/moments/*`
  - `frontend/src/services/moments.ts`
  - `frontend/src/components/ledger/splits/split-editor.tsx`
  - `frontend/src/components/ledger/splits/split-editor-modal.tsx`
- Backend:
  - `backend/app/routers/moments.py`
  - `backend/app/services/moment_candidates.py`
  - `backend/app/models/moment.py`
  - `backend/app/models/moment_candidate.py`
  - `backend/app/models/split.py`
  - `backend/app/routers/transactions.py`
- Tests:
  - `backend/tests/test_moments.py`
  - `backend/tests/test_moment_candidates.py`
  - `backend/tests/test_moments_v2_schema_migration.py`
  - `backend/tests/test_analytics.py`

## PRD-005 parity snapshot
- Implemented:
  - Moment create/read/update/delete API is present.
  - Tagged and candidate tabs exist with bulk remove/move and accept/reject.
  - Candidate refresh is implemented with upsert behavior and decision persistence.
  - Reassignment handshake is enforced (`MOMENT_REASSIGN_CONFIRM_REQUIRED`) in moments and split replacement flows.
  - Analytics supports `exclude_moment_tagged` across flow, payees, and internal accounts endpoints.
- Partial:
  - Moments list and overlay exist, but list/detail financial summaries are incomplete.
  - UI exposes create/open moments, but edit/delete actions are not surfaced in moments UI.
- Missing:
  - No card-level `expenses_total`, `income_total`, top categories, or tagged split count display parity.
  - No tagged summary block (expenses/income/category breakdown) inside overlay.
  - No cover image support in schema/API/UI (`cover_image_url` absent).
  - No explicit unsplit acceptance policy/CTA in candidates flow.

## Split-tagging invariant validation
- Confirmed:
  - Moment ownership is split-level (`splits.moment_id`), not transaction-level.
  - Split editor can set/clear `moment_id` per split in ledger flow.
  - Reassigning one split from moment A to B requires explicit confirmation in both:
    - `/transactions/{id}/splits`
    - `/moments/{id}/candidates/decision` and `/moments/{id}/tagged/move`
  - Candidate service repairs invariants so `accepted` candidate rows align with `splits.moment_id`.
- Evidence:
  - API and service logic in `backend/app/routers/moments.py`, `backend/app/services/moment_candidates.py`, `backend/app/routers/transactions.py`.
  - Regression tests in `backend/tests/test_moments.py` and `backend/tests/test_moment_candidates.py`.

## Missing state inventory (UI)
- Moments list (`moments-list.tsx`):
  - Loading: present.
  - Error with retry: present.
  - Empty with CTA: present.
  - Missing: no quick sort/filter controls from PRD (`Most recent`, `Highest spend`, candidate/tagged shortcuts).
- Overlay tagged tab:
  - Loading/error/empty table states: present.
  - Missing: tagged totals summary and category breakdown header section.
  - Missing: empty-state CTA to switch to Candidates tab.
  - Gap: `Open tx` action is currently disabled because no handler is passed from page layer.
- Overlay candidates tab:
  - Loading/error/empty table states: present.
  - Status filter + refresh + row/bulk actions: present.
  - Missing: explicit UX for transactions with no splits ("split first" fallback) as required by PRD consistency note.

## Findings (priority ordered)

### P0 - Moment list/detail metrics are missing against PRD baseline
- Current list cards only show name/date/description/id.
- Overlay lacks expenses/income totals and category breakdown for tagged splits.

### P0 - Frontend does not expose edit/delete moment actions
- Backend supports `PATCH /moments/{id}` and `DELETE /moments/{id}`, but moments page has no edit/delete controls.
- This blocks complete CRUD parity in actual user flow.

### P1 - Tagged overlay action path is incomplete
- `Open tx` button is rendered but effectively disabled due missing callback wiring.
- This breaks the intended "open detail" bridge from moment detail to transaction editing.

### P1 - Candidate unsplit behavior is not defined in UI
- Candidate generation is split-based; no explicit UI path for "split first" handling when user expects transaction-level action.

### P2 - Cover image is not modeled
- No `cover_image_url` field in model/migration/router/client.

## Cover image recommendation (pragmatic)
- Add nullable `moments.cover_image_url` as a metadata field (URL or app-served path string).
- Keep binary storage out of Postgres; use filesystem/object storage and persist only a pointer.
- Add optional upload endpoint later (`POST /moments/{id}/cover`) that returns normalized `cover_image_url`.
- Keep creation/edit flows backwards compatible by making field optional and non-blocking.

## Delegation outputs (tickets)
- [x] `F1-T1` Add moment summary metrics contract and UI:
  - backend: include `expenses_total`, `income_total`, `tagged_splits_count`, `top_categories` in list/detail response
  - frontend: show metrics on cards and overlay tagged summary
- [x] `F1-T2` Add edit/delete moments UX in `/moments` (with confirm for delete and untag side-effect copy)
- [x] `F1-T3` Wire tagged row "Open tx" action to ledger transaction detail/split editor flow
- [x] `F1-T4` Define and implement unsplit candidate policy:
  - either auto-create single split on accept
  - or enforce "Split first" CTA with deep-link
- [x] `F1-T5` Add optional cover image support (`cover_image_url` + upload/storage strategy)

## Suggested implementation order
1. Implement `F1-T1` (API + UI metrics) to close the largest PRD parity gap first.
2. Implement `F1-T2` for complete CRUD from moments UI.
3. Implement `F1-T3` to restore cross-flow navigation from moments to transaction editing.
4. Implement `F1-T4` and lock unsplit acceptance semantics with tests.
5. Implement `F1-T5` as optional enhancement once core behavior parity is stable.
