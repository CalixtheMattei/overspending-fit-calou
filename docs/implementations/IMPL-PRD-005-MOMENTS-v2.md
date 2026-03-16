# IMPL-PRD-005-MOMENTS-v2

## Summary
Implement PRD-005 Moments v2 using a **central modal overlay** on `/moments` with `Tagged` + `Candidates` tabs, split-level single-tag model (`splits.moment_id`), persistent candidate decisions (`pending|accepted|rejected`), reassignment confirmation, and analytics exclusion toggle.

Key product decisions:
- Central modal overlay (not drawer)
- Candidate anchor is `transactions.operation_at` (`dateOp`)
- Split can belong to 0..1 moment
- Out-of-range manual tagging is allowed
- Deleting a moment untags linked splits
- Candidate accept for unsplit rows auto-creates canonical single split + tags it
- `exclude_moment_tagged` lives in Analytics, defaults `false`, session-only persistence

## Derived From Audit
Source: `docs/audits/AUDIT-PRD-005-MOMENTS-v2.md`

Audit findings driving implementation:
- `moment_candidates` table is missing.
- Missing indexes: `splits(moment_id)`, `transactions(operation_at)`.
- Missing invariant: `moments.start_date <= moments.end_date`.
- Moments API is currently list-only (`GET /moments`).
- Candidate logic should be implemented in a dedicated service (thin routers).
- Moments UI is empty-state; modal/table/tabs primitives already exist.
- Split editor carries `moment_id` today but lacks reassignment confirmation contract.
- Analytics lacks `exclude_moment_tagged` threading.
- Unsplit parity locked: accept should not block on "Split first".

## Implementation Phases + Exit Criteria

### Phase 1 - Schema + Contracts Foundation
Exit criteria:
- Migration plan locked (`moment_candidates`, indexes, `moments.updated_at`, check constraint).
- API endpoint list and DTO/error contract frozen.
- Cross-stream contract doc published (backend/frontend).

### Phase 2 - Backend Semantics (Candidates + Invariants)
Exit criteria:
- Candidate refresh/list/accept/reject/reassign semantics implemented at service boundary.
- Transactional consistency rules defined for split tag + candidate status.
- Unsplit candidate accept path contract finalized.

### Phase 3 - Moments UI (Central Modal)
Exit criteria:
- `/moments` has modal overlay with `Tagged` and `Candidates` tabs.
- Table selection/filter/pagination/bulk states defined and wired.
- `frontend/src/services/moments.ts` expanded to full API usage.

### Phase 4 - Ledger Split Editor Integration
Exit criteria:
- Reassignment confirmation flow (`A -> B`) implemented via API conflict contract.
- Moment-specific error mapping added in split editor flows.
- Decision table behavior locked (`null->id`, `idA->idB`, `id->null`).

### Phase 5 - Analytics Toggle Integration
Exit criteria:
- `exclude_moment_tagged` added end-to-end (frontend + backend) for flow/payees/internal-accounts.
- `/analytics/flow` preserves unsplit fallback behavior.
- Filter combination test matrix covered.

### Phase 6 - QA Hardening + Release Readiness
Exit criteria:
- Regression suites added for candidate lifecycle, reassignment conflicts, analytics combinations.
- High-risk drift/concurrency scenarios covered by tests or explicit follow-up items.
- DoD checklist fully complete.

## Workstreams (Parallelizable)

### A) DB Migrations + Schema + Indexes
- Goal: Add schema/invariants for Moments v2.
- Dependencies: none.
- Files/modules to touch:
- `backend/alembic/versions/*new_prd005*.py`
- `backend/app/models/moment.py`
- `backend/app/models/split.py`
- `backend/app/models/transaction.py`
- `backend/app/models/moment_candidate.py` (new)
- Concrete tasks:
- Add `moment_candidates` table + constraints + indexes.
- Add `moments.updated_at` with backfill then non-null.
- Add `ck_moments_valid_date_range`.
- Add `ix_splits_moment_id`, `ix_transactions_operation_at`.
- Test plan items:
- Migration up/down smoke.
- Constraint behavior checks.
- Index presence checks.
- Status: TODO.

### B) Backend Endpoints (Moments CRUD + Tagged/Candidates + Bulk)
- Goal: Deliver required API surface and normalized errors.
- Dependencies: A.
- Files/modules to touch:
- `backend/app/routers/moments.py`
- `backend/app/routers/transactions.py`
- `backend/app/main.py`
- `backend/tests/test_moments.py` (new)
- Concrete tasks:
- Add moments CRUD endpoints.
- Add tagged list + bulk remove/move endpoints.
- Add candidates refresh/list/bulk decision endpoints.
- Implement delete-moment untag contract.
- Normalize `detail.code` + 404/409/422 behavior.
- Test plan items:
- Endpoint contract tests.
- Error semantics tests.
- Delete-untag behavior tests.
- Status: TODO.

### C) Candidate Computation + Consistency Rules
- Goal: Implement canonical candidate state machine and invariants.
- Dependencies: A, B, G parity.
- Files/modules to touch:
- `backend/app/services/moment_candidates.py` (new)
- `backend/app/routers/moments.py`
- `backend/tests/test_moment_candidates.py` (new)
- Concrete tasks:
- Eligibility query anchored on `transactions.operation_at`.
- Refresh upsert preserving accepted/rejected.
- Accept/reject transitions with timestamps.
- Reassign handling in single transaction.
- Drift/concurrency protections.
- Test plan items:
- Refresh idempotency.
- Status persistence on refresh.
- Reassign and conflict flows.
- Drift/race regression coverage.
- Status: TODO.

### D) UI Moments Tab + Central Modal + Tables
- Goal: Build Moments v2 UI in central modal overlay.
- Dependencies: B, C.
- Files/modules to touch:
- `frontend/src/pages/moments-page.tsx`
- `frontend/src/components/moments/*` (new)
- `frontend/src/services/moments.ts`
- `frontend/src/components/application/modals/modal.tsx`
- `frontend/src/components/application/table/table.tsx`
- `frontend/src/components/application/tabs/tabs.tsx`
- Concrete tasks:
- Implement overlay open/close + tab model.
- Add Tagged and Candidates tables with multi-select.
- Add bulk action toolbar and row drill-down.
- Wire loading/empty/error states.
- Test plan items:
- State transitions clear selection on context changes.
- Bulk action success/failure UX.
- Modal keyboard/close behavior.
- Status: TODO.

### E) Transaction Detail Moment Selector + Confirmations
- Goal: Align split-editor moment assignment with PRD reassignment confirmation.
- Dependencies: B, C.
- Files/modules to touch:
- `frontend/src/components/ledger/splits/split-editor-modal.tsx`
- `frontend/src/components/ledger/splits/split-editor.tsx`
- `frontend/src/components/ledger/splits/use-split-draft.ts`
- `frontend/src/pages/ledger/dashboard-page.tsx`
- `frontend/src/services/transactions.ts`
- Concrete tasks:
- Add confirmation on `moment A -> moment B`.
- Map 409 conflict/error code to confirmation UI.
- Preserve direct `null->id` and `id->null` flows.
- Test plan items:
- Decision table scenario coverage.
- Error mapping coverage.
- Status: TODO.

### F) Analytics Toggle: Exclude Moment-Tagged Splits
- Goal: Add analytics filtering option for moment-tagged splits.
- Dependencies: B.
- Files/modules to touch:
- `backend/app/routers/analytics.py`
- `backend/tests/test_analytics.py`
- `frontend/src/services/analytics.ts`
- `frontend/src/pages/analytics-page.tsx`
- `frontend/src/pages/ledger/dashboard-page.tsx`
- Concrete tasks:
- Add `exclude_moment_tagged` param across 3 analytics endpoints/services.
- Apply `Split.moment_id IS NULL` filter in split-backed queries.
- Preserve unsplit fallback behavior in flow query.
- Test plan items:
- `exclude_transfers` x `exclude_moment_tagged` combinations.
- Omitted-param default behavior.
- Flow unsplit fallback assertions.
- Status: TODO.

### G) QA + Fixtures + Regression Harness
- Goal: Ensure release safety across all streams.
- Dependencies: A-F.
- Files/modules to touch:
- `backend/tests/test_moments.py` (new)
- `backend/tests/test_moment_candidates.py` (new)
- `backend/tests/test_ledger_v2.py`
- `backend/tests/test_split_invariant.py`
- `backend/tests/test_analytics.py`
- Concrete tasks:
- Build shared fixtures for tagged/untagged/unsplit cases.
- Add lifecycle + reassignment + delete-untag regressions.
- Add analytics filter matrix regressions.
- Test plan items:
- End-to-end candidate lifecycle.
- Split-id drift risk scenarios.
- Analytics totals/group consistency.
- Status: TODO.

## Parallelization Strategy
- Branch per stream:
- `feature/prd005-ws-a-schema`
- `feature/prd005-ws-b-api`
- `feature/prd005-ws-c-candidates`
- `feature/prd005-ws-d-moments-ui`
- `feature/prd005-ws-e-split-editor`
- `feature/prd005-ws-f-analytics`
- `feature/prd005-ws-g-qa`
- Integration branch: `feature/prd005-moments-v2-integration`

Minimal inter-stream contracts:
- A -> all backend streams: final schema names/indexes/status enum
- B -> D/E/F: endpoint shapes + error code matrix
- C -> D/E: candidate DTO + state transitions + conflict semantics
- F -> analytics UI/tests: parameter default and filter behavior
- G consumes frozen contracts from A-F for stable assertions

## Session Plan (Small Sessions, 3-7 Tasks)

### Session 1 (parallelizable: A + B + G prep)
- Freeze migration checklist and DB invariants.
- Freeze endpoint/DTO/error-code matrix.
- Publish contract checkpoint CP1.
- Prepare core fixtures for moments/candidates/analytics.
- Validate dependency map and merge order.

### Session 2 (parallelizable: C + E)
- Finalize candidate state machine and transaction boundaries.
- Finalize reassignment confirmation API handshake.
- Lock unsplit accept category strategy.
- Define invariant checks (`accepted <-> split.moment_id`).
- Publish CP2 semantics checkpoint.

### Session 3 (parallelizable: D + F)
- Finalize modal state ownership and tab/table model.
- Freeze bulk action UX and loading/error states.
- Freeze analytics toggle threading and defaults.
- Publish CP3 (UI) and CP4 (analytics) checkpoints.

## Risk Register
- Split-id churn can detach candidate history.
- Mitigation: remap/lineage strategy + regression tests.
- Refresh vs accept/reject race conditions.
- Mitigation: transactional upsert and locking by (`moment_id`, `split_id`).
- API error inconsistency can break confirmation UX.
- Mitigation: strict code/status normalization tests.
- Index creation lock contention on large ledgers.
- Mitigation: rollout in low-traffic window + migration notes.
- Date-anchor mismatch (`posted_at` analytics vs `operation_at` candidate anchor) may confuse users.
- Mitigation: QA coverage and release notes.

## Definition of Done Checklist
- [ ] Functional: Moments CRUD, tagged/candidates flows, bulk actions, reassignment confirmation, delete-untag behavior.
- [ ] UI: central modal overlay on `/moments` with `Tagged` + `Candidates`.
- [ ] Migrations: `moment_candidates`, required indexes, date-range check, `moments.updated_at`.
- [ ] Analytics: `exclude_moment_tagged` implemented and tested across all analytics endpoints.
- [ ] Consistency: candidate status and split tagging invariants enforced.
- [ ] QA: regression suite passes for lifecycle, conflict, and filter matrix scenarios.
