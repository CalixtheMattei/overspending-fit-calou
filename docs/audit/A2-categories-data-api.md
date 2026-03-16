# A2 - Categories Data and API Audit

Status: Completed
Owner: A2
Audit date: 2026-02-28
Commit context: `773fd310aa724159902383f9bdc2f5e33b038777`

## Goal
Audit category backend contracts (models, routers, migrations) and identify schema/API changes required for Finary-like UX.

## Scope and evidence
- Router: `backend/app/routers/categories.py`
- Model: `backend/app/models/category.py`
- Catalog/canonicalization: `backend/app/services/category_catalog.py`, `backend/app/services/category_canonicalization.py`
- Migrations: `backend/alembic/versions/0001_initial_schema.py`, `0006_category_metadata_and_native_seed.py`, `0007_rules_engine_lineage.py`
- Tests: `backend/tests/test_categories.py`

## Current contract snapshot (verified)
- `GET /categories` and `GET /categories/presets` sort by `parent_id` then category name; there is no explicit persisted order field.
- `POST /categories` and `PATCH /categories/{category_id}` enforce "parent must be a root" but only on the target parent row.
- `PATCH`/`DELETE` are blocked for native categories (`is_custom = false`).
- `DELETE /categories/{category_id}` for custom categories:
  - computes distinct transaction usage count from splits,
  - nulls `splits.category_id`,
  - detaches child categories (`parent_id = NULL`),
  - deletes the category.
- Category metadata available to UI payloads: `color`, `icon`, `display_name`, `is_deprecated`, `canonical_id`, `group`.
- Cross-flow behavior:
  - transactions/rules canonicalize deprecated category ids before applying category actions.
  - business branch is blocked for income transactions during split assignment.

## Findings (severity ordered)

### P0 - Two-level invariant can be bypassed via re-parenting
- Evidence:
  - create/update only check whether the chosen parent already has a parent (`categories.py:100-105`, `145-150`).
  - update directly assigns `category.parent_id = parent_id` (`categories.py:151`) without checking whether the moving category already has children.
- Impact:
  - a 3-level tree can be produced by moving a parent-with-children under another root.
  - this breaks the documented 2-level contract and can destabilize tree-based UI assumptions.

### P1 - Delete API is destructive and lacks a safe reassign/merge contract
- Evidence: delete nulls split category ids and unparents children (`categories.py:182-188`), then returns only `{deleted, transaction_count}` (`categories.py:193`).
- Impact:
  - category deletions can create large uncategorized backlogs.
  - no API contract exists for "replace with category X" or merge semantics.

### P1 - No explicit ordering contract for categories
- Evidence:
  - list endpoints sort alphabetically (`categories.py:77`, `84`).
  - tree sorting uses display/name sort key (`categories.py:252-255`).
  - schema has no `sort_order` column (`0001_initial_schema.py:35-43`, `category.py`).
- Impact:
  - cannot support stable manual ordering required by a Finary-like curated accordion.

### P1 - Category identity constraints are weak for custom rows
- Evidence:
  - no uniqueness constraint on `(parent_id, normalized_name)` in categories schema (`0001_initial_schema.py:35-43`).
  - create/update do not check duplicates in API layer (`categories.py`).
- Impact:
  - duplicate sibling names are allowed and can create ambiguous picker/search behavior.

### P2 - Native catalog seed can absorb matching custom rows
- Evidence:
  - startup seeding can match by normalized name + parent (`category_catalog.py:235-239`, `251-254`).
  - matched row is rewritten as native (`is_custom=False`, source fields overwritten) (`category_catalog.py:274-276`).
- Impact:
  - custom categories that collide with native names can be silently converted on startup.

## Test coverage assessment
- Covered:
  - metadata fields and presets payload shape (`test_categories.py:47-88`),
  - preset validation and custom CRUD baseline (`91-147`),
  - native immutability/deletion block (`149-161`),
  - canonicalization and business-income guard in split/rules paths (`164+`).
- Missing:
  - test proving update cannot create 3-level hierarchy,
  - delete reassign/merge behavior (currently unsupported),
  - duplicate sibling name rejection (currently unsupported),
  - startup seed collision behavior for existing custom categories.
- Note:
  - `pytest tests/test_categories.py -q` could not run locally because `TEST_DATABASE_URL` is not set (suite skipped in `tests/conftest.py`).

## Proposed schema/API changes (delegation-ready)

### A2-T1: Enforce category tree and identity invariants
- Add server-side validation on update to reject moves that would produce depth > 2.
- Add DB-level normalized sibling uniqueness (`parent_id`, `normalized_name`) for custom categories.
- Add regression tests for both invariants.

### A2-T2: Add stable ordering contract
- Add `categories.sort_order` (integer, non-null, indexed).
- Return `sort_order` in category payloads and sort by `(parent_id, sort_order, name)`.
- Add reorder API (`PATCH /categories/reorder`) scoped to siblings.

### A2-T3: Safe delete/merge/reassign API
- Extend delete contract to support modes:
  - `uncategorize` (current behavior),
  - `reassign_to_category_id`,
  - `merge_into_category_id` (children + split links).
- Validate merge targets and preserve two-level invariant.
- Add tests for transaction/split counts and child handling per mode.

### A2-T4: Guard startup native seed from mutating custom rows
- Restrict native upsert matching to rows already marked as native (`source=native_catalog`) unless explicitly running a one-off migration mode.
- Add test to prove custom rows are not rewritten during startup seed.
