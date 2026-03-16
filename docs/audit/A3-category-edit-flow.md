# A3 - Category Create/Edit/Picker Flow Audit

Status: Complete (2026-02-28)
Owner: A3
Commit baseline: `773fd310aa724159902383f9bdc2f5e33b038777`

## Goal
Audit category creation/editing/picker flows for Finary parity and define modal/state behavior.

## Quick repo context
- Main page and modal flows: `frontend/src/pages/ledger/categories-page.tsx`
- Transaction drawer and split modal usage: `frontend/src/pages/ledger/dashboard-page.tsx`, `frontend/src/components/ledger/splits/split-editor-modal.tsx`
- API client: `frontend/src/services/categories.ts`
- Backend behavior: `backend/app/routers/categories.py`, `backend/tests/test_categories.py`

## Flow map (current behavior)
1. Categories page create flow (`/ledger/categories`)
- Single CTA (`Create a personalized category`) opens create modal.
- Parent select includes all root categories (native + custom); there is no in-context "Add subcategory" action per parent row.
- Save calls `POST /categories` and appends the result to local state.

2. Categories page edit flow
- Edit action exists only on custom categories.
- Edit modal supports name, parent, color, icon; update calls `PATCH /categories/{id}`.
- Native categories are read-only in UI and API.

3. Categories page delete flow
- Delete action exists only on custom categories.
- UI prefetches usage count via `GET /transactions?status=all&category_id={id}&limit=1`.
- Confirm calls `DELETE /categories/{id}`.
- Backend behavior on delete: set `splits.category_id = null` for direct matches, detach children to root (`children.parent_id = null`), then delete category.
- No merge/reassign path in UI. No child-impact summary in the modal.

4. Transaction drawer picker flow (`/ledger` right drawer)
- If `splits_count > 1`, category picker is replaced with "Edit split" CTA.
- If `splits_count = 0`, selecting a category creates one split for full transaction amount.
- If `splits_count = 1`, picker recategorizes that split.
- Picker supports existing categories only (no inline create).

5. Split editor picker flow (`/ledger` split modal)
- Category select has hierarchical options plus a `Create category` option at top.
- Choosing `Create category` opens a nested create modal.
- On successful create, new category is auto-assigned to the active split.
- Split modal create UI uses dropdown selects for color/icon (different from categories page icon/color grid treatment).

## Modal/state inventory
- Categories page create/edit modal:
  - State: `createOpen`, `createDraft`, `editTarget`, `editDraft`.
  - Supports inline validation (`Name is required`) and backend error passthrough.
  - Uses icon grid with selected-state rings and color swatches.
- Categories page delete modal:
  - State: `deleteState` with `category`, `count`, `loading`, `error`.
  - Shows usage count only; no decision branching by impact.
- Split editor category modal:
  - State: `categoryModal` with `targetIndex`, `name`, `parentId`, `color`, `icon`, `error`.
  - Nested modal flow from split row category picker.
  - Creates category and immediately assigns it to the active split.

## Key gaps vs A3 target
1. Missing in-context subcategory creation on parent rows (north-star requires parent-context creation).
2. Category create experience is inconsistent across surfaces (grid in categories page vs dropdowns in split modal).
3. Delete flow is destructive by default for direct split usage (uncategorization) and silent about children detachment impact.
4. No reassignment/merge UX path for delete even though this is the highest-risk category action.
5. No dedicated regression coverage for custom-category delete behavior with direct split usage and child categories.

## Deletion rule proposal (A3 UX contract)
1. Keep immediate delete only for zero-impact categories:
- No direct split usage.
- No children.
2. For in-use or parent categories, require explicit strategy in a two-step modal:
- Direct split handling: reassign to selected category OR confirm uncategorize.
- Child handling: move children to another parent OR promote to root.
3. Preferred default: reassign direct splits to a target category (not uncategorize).
4. API shape to coordinate with A2:
- Add preview endpoint for impact (`direct_split_count`, `child_count`, optional top examples).
- Extend delete endpoint with explicit strategy payload instead of implicit uncategorize.

## Deliverable checklist
- [x] `docs/audit/A3-category-edit-flow.md` with flow map and states.
- [x] Deletion rule proposal (block vs reassign vs merge).
- [x] Coding tickets for categories tab/picker/modal parity.

## Delegation outputs (next coding session tickets)
1. Ticket A3-1: In-context subcategory CTA on parent rows
- Add `Add subcategory` action in parent card actions.
- Open create modal with `parentId` prefilled and locked to parent by default.
- Acceptance: one-click subcategory creation path without leaving parent context.

2. Ticket A3-2: Unify category create modal across Categories page and Split editor
- Extract shared `CategoryCreateForm` with same color/icon presentation and validation.
- Keep action row pinned and consistent (`Cancel` + primary create button).
- Acceptance: identical field behavior and selection affordances across both entry points.

3. Ticket A3-3: Upgrade delete flow to impact-aware strategy modal
- Step 1: impact summary (direct usage + children count).
- Step 2: required handling choices when impact exists (reassign/uncategorize + child reparent/promote).
- Acceptance: no destructive delete without explicit user choice for impacted records.

4. Ticket A3-4: Extend transaction drawer category picker parity
- Add optional "Create category" action from drawer category control for 0/1-split transactions.
- Reuse shared create form and refresh category options without full page reload.
- Acceptance: user can create + assign category from drawer in one flow.
