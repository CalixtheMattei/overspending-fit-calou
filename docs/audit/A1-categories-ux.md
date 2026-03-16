# A1 - Categories UI/UX Audit (Finary parity)

Status: Completed (2026-02-28)
Owner: A1

## Goal
Audit the Categories UX against the north-star Finary-style accordion pattern and define concrete, delegated next steps.

## Scope and evidence
- Primary page: `frontend/src/pages/ledger/categories-page.tsx`
- Shared visuals/labels/icons: `frontend/src/components/ledger/categories/category-visuals.tsx`
- Related picker touchpoints:
  - `frontend/src/pages/ledger/dashboard-page.tsx`
  - `frontend/src/components/ledger/splits/split-editor.tsx`
  - `frontend/src/components/ledger/splits/split-editor-modal.tsx`
  - `frontend/src/components/rules/action-builder.tsx`

## Current vs target snapshot notes

### Current (repo state)
- Categories list is rendered as neutral cards (`rounded-xl ... bg-primary`) with a small color dot, not a parent color row/tile treatment (`categories-page.tsx:359`, `categories-page.tsx:376`).
- The page is split into two sections (`Personalized` and `Category library`) with separate counts and empty states (`categories-page.tsx:461`, `categories-page.tsx:468`).
- Parent rows support expand/collapse and edit/delete for custom categories only (`categories-page.tsx:355`, `categories-page.tsx:339`).
- There is no inline "create subcategory" action within the parent row; creation starts from a global CTA and parent select (`categories-page.tsx:438`, `categories-page.tsx:191`).
- Category selection in `/ledger` drawer is flat alphabetical, not hierarchical (`dashboard-page.tsx:667`).
- Split editor uses a pseudo hierarchy with arrow-prefixed child labels (`->`), not accordion rows (`split-editor.tsx:93`, `split-editor.tsx:116`).

### Target (north-star parity)
- One clear accordion list where parent rows are visually dominant color rows/tiles.
- Expand parent -> reveal child rows in-context with strong hierarchy and quick actions.
- Per-parent contextual "create subcategory" action.
- Consistent hierarchical picker UX across categories page, ledger drawer, split editor, and rules action builder.

## Component map
- `CategoriesPage` (`categories-page.tsx`): data loading, search, sectioning, expansion state, CRUD modal state.
- `renderCard` (`categories-page.tsx`): parent row + child row rendering and per-row utility actions.
- `CategoryFormFields` (`categories-page.tsx`): create/edit inputs for name/parent/color/icon.
- `SplitEditor` (`split-editor.tsx`): builds category picker items including create shortcut.
- `SplitEditorModal` (`split-editor-modal.tsx`): create-category modal from split flow.
- `LedgerDashboardPage` (`dashboard-page.tsx`): quick category selector in transaction drawer.
- `ActionBuilder` (`action-builder.tsx`): rule action category select (flat list).

## Prioritized UX gaps

### P0
- Parent visual hierarchy is too weak vs target: parent color is only a swatch dot instead of colored row/tile.
- No in-context subcategory creation from a parent row; this breaks the "create in parent context" requirement.
- Picker parity is inconsistent across routes (`/ledger/categories`, `/ledger` drawer, split modal, rules modal); users learn multiple mental models.

### P1
- Two-section split (`Personalized` vs `Category library`) fragments scanning and is not aligned with a single canonical accordion taxonomy view.
- Row actions are custom-only; native rows are browse-only with no modifier path, conflicting with "per-row modifier action" as a universal pattern.
- Child hierarchy in split editor is represented by text prefix (`->`) rather than structured grouped UI, lowering readability.

### P2
- Search currently expands based on matches but does not provide explicit match highlighting or parent-level result summary.
- Deletion warning text is correct but does not offer a reassign path in-flow, which may increase accidental uncategorization.

## Acceptance criteria for coding delegation
- `/ledger/categories` renders parent categories as clearly colored rows/tiles with accessible contrast and retained iconography.
- Each parent row provides contextual actions including "create subcategory" (prefilled parent), plus edit/delete where allowed.
- Child rows are always visually grouped under parent expansion; expansion state is predictable during search and manual toggles.
- A shared hierarchical category picker is used in:
  - Ledger drawer quick category assign
  - Split editor category field
  - Rules action category select
- Picker child rendering uses indentation/grouping (not `->` text prefix), keeps color/icon hints, and supports keyboard navigation.
- Create/edit category UX uses consistent copy, validation, and success-refresh behavior across page and modal entry points.

## Delegation outputs (tickets)
- [x] Ticket A1-1: Rework Categories tab into Finary-style accordion with colored parent rows and contextual row actions.
- [x] Ticket A1-2: Build shared hierarchical category picker component and adopt it in ledger drawer, split editor, and rules action builder.
- [x] Ticket A1-3: Add in-context subcategory creation flow (from parent row and picker) with prefilled parent + parity validation UX.

## Suggested implementation order for next coding session
1. Build reusable category tree primitives (`CategoryAccordionList`, `CategoryTreePicker`) before page-specific wiring.
2. Migrate `/ledger/categories` UI to new primitives and preserve existing CRUD APIs.
3. Replace flat selectors in `dashboard-page.tsx` and `action-builder.tsx`.
4. Replace arrow-prefixed split editor picker rows with shared tree picker.
5. QA pass on search, keyboard nav, and CRUD refresh consistency across all entry points.
