# C1 - Splits End-to-End Audit

Status: Complete (2026-02-28)
Owner: C1
Baseline commit: `773fd310aa724159902383f9bdc2f5e33b038777`

## Goal
Audit split editor plus split API end-to-end, enforce invariants, and produce must-pass scenarios.

## Scope and evidence reviewed
- Frontend draft/state logic: `frontend/src/components/ledger/splits/use-split-draft.ts`
- Frontend split UI: `frontend/src/components/ledger/splits/split-editor.tsx`
- Frontend split modal orchestration: `frontend/src/components/ledger/splits/split-editor-modal.tsx`
- Ledger page integration and quick-categorize path: `frontend/src/pages/ledger/dashboard-page.tsx`
- Frontend API contract and error mapping: `frontend/src/services/transactions.ts`, `frontend/src/services/api.ts`
- Backend split endpoint and helpers: `backend/app/routers/transactions.py`
- Backend validation helpers: `backend/app/services/ledger_validation.py`
- Relevant tests: `backend/tests/test_ledger_v2.py`, `backend/tests/test_moments.py`, `backend/tests/test_split_invariant.py`, `backend/tests/test_categories.py`
- DB-level invariant setup: `backend/alembic/versions/0001_initial_schema.py`

## Current E2E flow snapshot
1. `/ledger` drawer quick-categorize supports `splits_count` of `0` or `1`; `>1` routes user to split editor.
2. Split modal drafts are initialized from server split rows, preserving split `id` for replace-all updates.
3. Frontend blocks save on invalid amount, missing category, sign mismatch, or non-zero remaining total.
4. `PUT /transactions/{id}/splits` validates again server-side: category required, sign, exact sum, decimal precision (`<=2`).
5. Backend canonicalizes deprecated category IDs, validates category/moment/internal-account IDs, and enforces moment reassignment handshake (`MOMENT_REASSIGN_CONFIRM_REQUIRED` with `409`) unless `confirm_reassign=true`.
6. Replace-all writes are idempotent on unchanged payloads (no manual event written when payload is semantically equal).

## Invariant validation map
- Split records are first-class in DB and API: confirmed.
- Sum invariant (`sum(split.amount) == transaction.amount`) enforced in API and DB trigger: confirmed.
- Split sign must match transaction sign: confirmed in frontend+backend.
- Moment tagging is split-level only: confirmed in payload and model.
- Transfer exclusion from analytics is separate concern and does not block split editing: confirmed by architecture.

## Must-pass scenario matrix (C1)
| # | Scenario | Expected outcome | Current status |
|---|---|---|---|
| 1 | Quick categorize on `0` splits | Creates one split with full transaction amount | Covered in UI path, needs dedicated API+UI test |
| 2 | Quick categorize on `1` split | Rewrites single split category in-place | Covered in UI path, needs dedicated test |
| 3 | Quick categorize on `>1` splits | Blocked with explicit "Edit split" redirect | Covered in UI |
| 4 | Save empty `splits: []` | Allowed; transaction remains uncategorized | Covered (`test_ledger_v2`) |
| 5 | Sum mismatch | `422` + `SPLIT_SUM_MISMATCH` | Covered (`test_ledger_v2`, `test_split_invariant`) |
| 6 | Sign mismatch on expense | `422` + `SPLIT_SIGN_MISMATCH` | Covered (`test_ledger_v2`) |
| 7 | Sign mismatch on positive tx (income/refund) | `422` + `SPLIT_SIGN_MISMATCH` | Gap (no direct test) |
| 8 | Decimal precision > 2 places | `422` + "amount must have at most 2 decimal places" | Gap (no test; frontend does not pre-validate) |
| 9 | Missing `category_id` in split row | `422` + `SPLIT_CATEGORY_REQUIRED` | Gap (no direct API test) |
| 10 | Duplicate split IDs in payload | `422` + `detail.code=SPLIT_ID_DUPLICATE` | Gap (no test) |
| 11 | Split ID not belonging to transaction | `422` + `detail.code=SPLIT_ID_NOT_FOUND` | Gap (no test) |
| 12 | Unknown `moment_id` | `404` + `detail.code=MOMENT_NOT_FOUND` | Covered (`test_moments`) |
| 13 | Reassign split from moment A to B without confirm | `409` + `MOMENT_REASSIGN_CONFIRM_REQUIRED` | Covered (`test_moments`) |
| 14 | Reassign with `confirm_reassign=true` | `200`, reassignment applied | Covered (`test_moments`) |
| 15 | Deprecated category ID in payload | Canonicalized to active category | Covered (`test_categories`) |

## Findings and risks
1. Drawer offers `Uncategorized` for single-split rows, but backend rejects `category_id=null` (`SPLIT_CATEGORY_REQUIRED`), creating a predictable UX dead-end.
2. Frontend error mapping does not include `SPLIT_ID_DUPLICATE`, `SPLIT_ID_NOT_FOUND`, or decimal precision message normalization, so some failures surface as raw backend text.
3. High-value API edge cases (duplicate IDs, invalid IDs, >2 decimals, positive-sign mismatch) are not test-covered yet.
4. Test harness file `backend/tests/test_moments_harness.py` still references stale code `MOMENT_REASSIGN_CONFIRMATION_REQUIRED` (extra "ATION"), which can mislead future agents despite active tests using the correct code.
5. Local test execution in this environment is blocked without `TEST_DATABASE_URL`; assertions below are based on code review plus existing test corpus.

## API contract recommendations
1. Standardize split endpoint errors to object shape for all 4xx responses: `{ code, message, ...context }` (some paths still return plain strings).
2. Add explicit codes for missing category/internal account (`CATEGORY_NOT_FOUND`, `INTERNAL_ACCOUNT_NOT_FOUND`) to align with other structured errors.
3. Add split row index/path metadata in validation errors to improve UX for multi-row correction.

## UX recommendations
1. Remove `Uncategorized` from drawer single-split selector unless backend is changed to allow nullable category rows.
2. Add client-side `<=2` decimal validation before submit to reduce round-trip failures.
3. Add human-friendly messages for `SPLIT_ID_DUPLICATE` and `SPLIT_ID_NOT_FOUND`.
4. In reassignment confirm modal, include split count plus source/target moment names (currently count-only summary).

## Delegation-ready tickets (next coding session)
1. `C1-T1 Drawer/category consistency`: Align drawer options with backend category-required rule (or relax backend rule intentionally). Include regression tests for single-split "uncategorize" behavior.
2. `C1-T2 Split API test expansion`: Add parameterized tests for scenarios #7-#11 above in `backend/tests/test_ledger_v2.py`.
3. `C1-T3 Error contract hardening`: Convert remaining plain-string split errors to `{code,message}` objects and update frontend error mapping.
4. `C1-T4 Frontend precision guard`: Enforce 2-decimal input validation in `use-split-draft` and block submit with clear inline message.

## Deliverable checklist
- [x] 10-15 must-pass scenarios.
- [x] API contract improvement proposals (error code/message shape).
- [x] UX improvements for clarity and failure prevention.
