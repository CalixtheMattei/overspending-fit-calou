# AUDIT INDEX

Last updated: 2026-02-28
Mode: Lightweight repo audit for delegation only.

## North star (categories UX target)
- Categories page should feel like a Finary-style accordion list.
- Parent categories render as colored rows/tiles.
- Expanding a parent reveals child categories.
- Each row supports a per-row modifier action.
- Create subcategory action is available inside parent context.

## Shared invariants (verify in every agent report)
1. Splits are first-class records (not derived UI-only state).
2. For any transaction with splits, `sum(split.amount) == transaction.amount` exactly (2-decimal precision).
3. Split amount sign must match transaction sign.
4. Moment tagging lives on splits, not transactions.
5. Transfers are excluded from spending analytics by default.

## Scope matrix

### 1) Categories
- Owner agents: A1 (UX), A2 (data/API), A3 (create/edit/picker)
- Primary files touched:
  - `frontend/src/pages/ledger/categories-page.tsx`
  - `frontend/src/components/ledger/categories/category-visuals.tsx`
  - `frontend/src/services/categories.ts`
  - `frontend/src/pages/ledger/dashboard-page.tsx` (drawer + split modal category interactions)
  - `backend/app/routers/categories.py`
  - `backend/app/models/category.py`
  - `backend/app/services/category_catalog.py`
  - `backend/app/services/category_canonicalization.py`
  - `backend/alembic/versions/0006_category_metadata_and_native_seed.py`
  - `backend/tests/test_categories.py`
- Endpoints:
  - `GET /categories`
  - `GET /categories/presets`
  - `POST /categories`
  - `PATCH /categories/{category_id}`
  - `DELETE /categories/{category_id}`
- UI routes:
  - `/ledger/categories`
  - `/ledger` (transaction drawer quick category + split editor category picker)
  - `/rules` (category usage in rule actions)
- Main risks:
  - Current categories page is card/list based, not explicit Finary-style colored accordion rows.
  - No explicit ordering field in category schema; ordering is name-based.
  - Delete behavior nulls split `category_id` and detaches children (no merge/reassign flow).
  - Tree is constrained to 2 levels; UX must keep that constraint clear.
- Done checklist:
  - [ ] A1 defines target UX parity and acceptance criteria.
  - [ ] A2 validates category API/model constraints and proposes schema deltas.
  - [ ] A3 specifies create/edit/delete/picker modal states and interactions.
  - [ ] Delegated coding tickets are written and scoped.

### 2) Transactions and Splits
- Owner agents: B1 (transaction category flow), C1 (splits e2e)
- Primary files touched:
  - `frontend/src/pages/ledger/dashboard-page.tsx`
  - `frontend/src/components/ledger/transactions/transactions-table.tsx`
  - `frontend/src/components/ledger/splits/use-split-draft.ts`
  - `frontend/src/components/ledger/splits/split-editor.tsx`
  - `frontend/src/components/ledger/splits/split-editor-modal.tsx`
  - `frontend/src/services/transactions.ts`
  - `backend/app/routers/transactions.py`
  - `backend/app/services/ledger_validation.py`
  - `backend/app/models/transaction.py`
  - `backend/app/models/split.py`
  - `backend/tests/test_split_invariant.py`
- Endpoints:
  - `GET /transactions`
  - `GET /transactions/summary`
  - `GET /transactions/{transaction_id}`
  - `PATCH /transactions/{transaction_id}`
  - `PUT /transactions/{transaction_id}/splits`
- UI routes:
  - `/ledger` (table, right drawer, split editor modal)
- Main risks:
  - Quick categorize in drawer only supports 0/1 split; multi-split requires modal path.
  - Drawer currently exposes `Uncategorized` for single-split rows, but backend rejects split payloads with `category_id: null` (`SPLIT_CATEGORY_REQUIRED`).
  - Replace-all splits API is strict; UX errors must stay synchronized with backend codes.
  - Conflict flow (`MOMENT_REASSIGN_CONFIRM_REQUIRED`) must stay consistent between modal and quick actions.
  - Shared refresh trigger (`refreshKey`) refetches both transactions and Sankey flow after split/category changes, which slows high-volume categorization loops.
  - Rounding/sign edge cases need explicit must-pass coverage.
- Done checklist:
  - [x] B1 produces flow map and breakpoints (sync/cache/optimistic behavior).
  - [ ] C1 produces 10-15 must-pass split scenarios + API/UX recommendations.
  - [x] Coding tickets for quick categorize, validation, and optimistic/refetch policy are drafted.
- B1 completion note (2026-02-28):
  - Report: `docs/audit/B1-transaction-category-flow.md`
  - Confirmed two-path categorization model: drawer quick path (0/1 split) and split modal for multi-split/advanced edits.
  - Confirmed highest-priority flow bug: single-split `Uncategorized` selection currently produces backend validation failure instead of intentional uncategorization.
  - Confirmed mutation strategy is pessimistic with global refresh coupling; no row-level optimistic updates yet.
- Next coding session queue (Transactions/Splits from B1):
  - 1) `B1-T1` Fix quick uncategorize semantics for single-split transactions: selecting `Uncategorized` should send `splits: []` (or hide the option), with frontend + backend regression coverage.
  - 2) `B1-T2` Add consistent drawer error UX for split mutation failures using code-aware mapping (`mapSplitErrorMessage`) and remove dead-end actions.
  - 3) `B1-T3` Implement transaction-row optimistic patching and split refresh policy so split/category edits do not always refetch Sankey immediately.
  - 4) `B1-T4` Optional throughput pass: add table-level quick category affordance for uncategorized and single-split rows.

### 3) Analytics and Sankey
- Owner agents: D1 (filters), D2 (Sankey semantics), E1 (drilldown)
- Primary files touched:
  - `frontend/src/pages/analytics-page.tsx`
  - `frontend/src/pages/ledger/dashboard-page.tsx`
  - `frontend/src/components/ledger/charts/sankey-utils.ts`
  - `frontend/src/components/ledger/charts/sankey-chart.tsx`
  - `frontend/src/services/analytics.ts`
  - `backend/app/routers/analytics.py`
  - `backend/tests/test_analytics.py`
- Endpoints:
  - `GET /analytics/flow`
  - `GET /analytics/payees`
  - `GET /analytics/internal-accounts`
- UI routes:
  - `/analytics`
  - `/ledger` (current Sankey placement)
  - target new route: `/analytics/category/:id` (pending E1)
- Main risks:
  - Filter state is duplicated across pages (analytics page vs ledger dashboard flow controls).
  - `/ledger` flow request hardcodes exclusions (`exclude_transfers=true`, `exclude_moment_tagged=false`) instead of sharing analytics-page filter state.
  - Sankey currently models `transaction_type -> category`; drilldown semantics are not formalized.
  - No dedicated backend endpoint for category-branch drilldown yet.
  - Potential inconsistency for uncategorized and transfer handling across widgets.
- Done checklist:
  - [x] D1 defines single source of truth for analytics filters.
  - [ ] D2 defines canonical node/edge semantics + endpoint proposal.
  - [ ] E1 defines drilldown UX/spec and gaps to current code.
  - [ ] Coding tickets for shared filters, Sankey endpoint/UI, and drilldown route are drafted.
- D1 completion note (2026-02-28):
  - Report: `docs/audit/D1-analytics-filters.md`
  - Mapped current state ownership and defaults across `/analytics` and `/ledger`, including storage behavior and endpoint threading.
  - Confirmed backend/services already support shared filter params; current divergence is mainly frontend state ownership and ledger hardcoded flags.
  - Validation note: local `pytest backend/tests/test_analytics.py` execution is skipped when `TEST_DATABASE_URL` is not set in this environment.
- Next coding session queue (Analytics filters from D1):
  - 1) `D1-T1` Introduce shared `AnalyticsFilterState` domain (defaults + preset helpers) and remove duplicated page-local filter initialization.
  - 2) `D1-T2` Add URL query-param synchronization for analytics filters on `/analytics` and `/ledger` with URL-first hydration.
  - 3) `D1-T3` Remove hardcoded ledger flow exclusions and wire `/ledger` requests to shared `exclude_transfers` and `exclude_moment_tagged`.
  - 4) `D1-T4` Add cross-surface regression tests proving `/analytics` and `/ledger` return matching flow totals under identical filters.

### 4) Moments
- Owner agent: F1
- Primary files touched:
  - `frontend/src/pages/moments-page.tsx`
  - `frontend/src/components/moments/*`
  - `frontend/src/services/moments.ts`
  - `frontend/src/components/ledger/splits/split-editor.tsx` (moment tag on splits)
  - `backend/app/routers/moments.py`
  - `backend/app/models/moment.py`
  - `backend/app/models/split.py`
  - `backend/tests/test_moments.py`
  - `backend/tests/test_moments_v2_schema_migration.py`
- Endpoints:
  - `GET /moments`
  - `POST /moments`
  - `GET /moments/{moment_id}`
  - `PATCH /moments/{moment_id}`
  - `DELETE /moments/{moment_id}`
  - `GET /moments/{moment_id}/tagged`
  - `POST /moments/{moment_id}/tagged/remove`
  - `POST /moments/{moment_id}/tagged/move`
  - `POST /moments/{moment_id}/candidates/refresh`
  - `GET /moments/{moment_id}/candidates`
  - `POST /moments/{moment_id}/candidates/decision`
- UI routes:
  - `/moments`
  - `/ledger` (split editor moment selector)
- Main risks:
  - No cover image field in moment schema (`cover_image_url` absent).
  - Need explicit parity check of empty/loading/error states vs PRD-005.
  - Cross-flow consistency risk between split editor tagging and moments overlay bulk actions.
- Done checklist:
  - [ ] F1 validates current completeness vs PRD-005 and missing states.
  - [ ] F1 confirms split-level tagging invariant in UI + API.
  - [ ] F1 proposes image strategy (schema + upload/storage approach).
  - [ ] Coding tickets for detail totals, split tagging UX, and optional cover image are drafted.

### 5) Profile
- Owner agent: Orchestrator (unassigned coding follow-up)
- Scope decision (2026-02-28): Out of scope for this delegation wave.
- Primary files touched:
  - `frontend/src/pages/profile-page.tsx`
  - `frontend/src/features/profile/profile-provider.tsx`
  - `frontend/src/features/profile/storage.ts`
  - `frontend/src/features/profile/defaults.ts`
- Endpoints:
  - None (local-only profile state in browser storage)
- UI routes:
  - `/profile`
- Main risks:
  - No backend persistence; profile data is local browser state only.
  - Limited validation/test coverage and no API contract.
  - Route back-link depends on session storage key behavior.
- Done checklist:
  - [x] Confirm local-only profile behavior is intentional for this phase.
  - [x] Define if profile should remain out-of-scope for current delegation wave.

## Agent reports (write location)
- `docs/audit/A1-categories-ux.md`
- `docs/audit/A2-categories-data-api.md`
- `docs/audit/A3-category-edit-flow.md`
- `docs/audit/B1-transaction-category-flow.md`
- `docs/audit/C1-splits-e2e.md`
- `docs/audit/D1-analytics-filters.md`
- `docs/audit/D2-sankey-data.md`
- `docs/audit/E1-sankey-drilldown.md`
- `docs/audit/F1-moments.md`

## Lightweight audit notes used for this index
- Frontend routes are declared in `frontend/src/main.tsx`.
- Split invariant is enforced in `backend/app/services/ledger_validation.py` and exercised by `backend/tests/test_split_invariant.py`.
- Categories and metadata contracts are centered in `backend/app/routers/categories.py` and `backend/app/services/category_catalog.py`.
- Sankey currently renders from `GET /analytics/flow` via `buildSankeyData` in ledger dashboard.
- Moments are split-centric, with bulk tagged/candidate operations in `backend/app/routers/moments.py`.
