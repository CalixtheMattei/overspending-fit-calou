# PRD-001 Import Audit + Table Visibility Fix Plan (2026-02-04)

## Purpose
Create a concise, decision-complete plan and context for a future vibe-coding session to:
1. Audit PRD-001 vs current implementation.
2. Fix table row interaction (drawer not opening).
3. Improve table row text visibility.

## Context Snapshot
Repo: `personal-expense`
Frontend: Vite + React + Untitled UI
Backend: FastAPI + Postgres
Primary route: `/imports`

Key files:
- `docs/PRD-001-import.md`
- `frontend/src/pages/imports-page.tsx`
- `frontend/src/components/application/table/table.tsx`
- `frontend/src/services/imports.ts`
- `backend/app/routers/imports.py`
- `frontend/src/providers/theme-provider.tsx`
- `frontend/src/styles/theme.css`

Observed user issue:
- Rows exist but text is hard to see or blends with background.
- Hover shows pointer but clicking does nothing.

## Audit Checklist (PRD-001 vs Current)
- [x] Import section at top with upload + stats + CTA.
- [x] Imports tab with history table (imported_at, file_name, account, stats).
- [x] Import results tab with summary cards + rows table.
- [x] Row drawer exists with raw_json + linked transaction preview.
- [ ] Normalization preview missing parsed dates + amount (PRD expects more fields).
- [ ] "Unlinked" filter label does not match behavior. It maps to `status=created`, which means rows that created a new transaction, not "no transaction linked".

## Root Cause Analysis
1. Row click does nothing:
   - `react-aria-components` Row ignores `onClick`. It wires `onAction`/Press events instead.
   - Current code uses `onClick` on `Table.Row` in `imports-page.tsx`, so actions are dropped.

2. Text visibility:
   - `TableCell` base class is `text-tertiary`, which is low contrast and easy to lose against light or dark backgrounds.
   - Some cells override to `text-primary`, but most remain tertiary.

## Decision-Complete Fix Plan
### A. Fix row interaction (imports history + import rows)
File: `frontend/src/pages/imports-page.tsx`
Change:
- Replace `onClick` on `Table.Row` with `onAction` (or `onPress`).

Targets:
- Imports history table rows.
- Import results table rows.

Expected behavior:
- Clicking a row triggers selection or opens drawer.

### B. Improve row text contrast
File: `frontend/src/components/application/table/table.tsx`
Change:
- `TableCell` base class `text-tertiary` -> `text-secondary`.

Keep existing overrides in `imports-page.tsx` for:
- `text-primary` labels.
- Amount color (`text-success-primary`/`text-error-primary`).

Expected behavior:
- Default table text is legible in both light and dark themes.

### C. Audit-only gaps (do not implement unless asked)
1. Normalization preview:
   - PRD expects parsed dates + amount in the drawer.
   - Current drawer only shows label_norm + inferred type/payee.
2. "Unlinked" filter semantics:
   - "Unlinked" label currently maps to `status=created`.
   - Decide whether to rename label or change backend filter to mean `transaction_id is null`.

## Implementation Notes
Row action hook for `react-aria-components`:
- Use `onAction` on `Table.Row`.
- If needed, pass `textValue` for accessibility, but not required for action only.

Backend endpoints in scope:
- `GET /imports`
- `GET /imports/{id}`
- `GET /imports/{id}/rows`
- `GET /imports/{id}/rows/{row_id}`

No API changes required.

## Test Checklist
1. `/imports` shows import history rows with readable text.
2. Clicking an import row switches to results tab and updates selection.
3. Import results rows show readable text across all columns.
4. Clicking a row opens drawer and loads row detail.
5. Filters (All / Unlinked / Errors) update rows correctly.
6. Verify contrast in both system light and dark themes.

## Assumptions
- Backend responses match types in `frontend/src/services/imports.ts`.
- Visibility issue is styling-related, not data-related.
- No new APIs or migrations are required.

## Deliverables
1. Code change in `imports-page.tsx` to use `onAction`.
2. Code change in `table.tsx` to adjust base text color.
3. Short audit note in PR or summary message covering the two gaps.
