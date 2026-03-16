# IMPORTS_AGENT.md

Technical reference for AI agents working on the imports feature. Read this before modifying import-related code.

## Feature Overview

The imports feature handles CSV bank exports (BoursoBank format) with:
- **Deduplication**: Fingerprint-based matching prevents duplicate transactions across overlapping imports
- **Two-tab UI**: "Import History" (drill into specific imports) and "All Transactions" (cross-import view)
- **Upload workflow**: Drag-drop → Preview stats → Confirm import

## Critical Files

| Layer | File | Purpose |
|-------|------|---------|
| Frontend Page | `frontend/src/pages/imports-page.tsx` | Main component (~1,166 lines) |
| Frontend API | `frontend/src/services/imports.ts` | Fetch functions & TypeScript types |
| Backend Routes | `backend/app/routers/imports.py` | REST API endpoints |
| Data Models | `backend/app/models/import_models.py` | Import, ImportRow, ImportRowLink SQLAlchemy models |
| Import Service | `backend/app/services/import_service.py` | Core import logic (preview, confirm) |
| Normalization | `backend/app/services/import_normalization.py` | Parsing, label normalization, fingerprinting |

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/imports/preview` | Dry-run: validate CSV, return stats without storing |
| POST | `/imports` | Execute import: store Import + ImportRows + link to Transactions |
| GET | `/imports` | List all imports (ordered by imported_at DESC) |
| GET | `/imports/rows` | All rows across imports with filtering/pagination |
| GET | `/imports/{id}` | Single import with aggregated stats |
| GET | `/imports/{id}/rows` | Rows for specific import with filtering |
| GET | `/imports/{id}/rows/{row_id}` | Row detail with raw_json + normalization preview |
| GET | `/imports/{id}/file` | Download original CSV file |

## Data Models

### Import
```
id, account_id, file_name, file_hash, file_path, imported_at, notes
Aggregates: row_count, created_count, linked_count, duplicate_count, error_count
Relations: account, rows
```

### ImportRow
```
id, import_id, row_hash, raw_json (JSONB)
Parsed fields: date_op, date_val, label_raw, supplier_raw, amount, currency, category_raw, comment_raw, balance_after
Status: "created" | "linked" | "error"
Error tracking: error_code, error_message
Relations: import_, link (to ImportRowLink)
```

### ImportRowLink
```
id, import_row_id, transaction_id, linked_at
```
Join table linking import rows to canonical transactions.

### ImportRowStatus (Enum)
- `created`: New transaction was created from this row
- `linked`: Row matched an existing transaction (dedupe)
- `error`: Parsing or validation failed

## Import Processing Flow

1. **Parse CSV**: Auto-detect delimiter (tab, comma, semicolon)
2. **Normalize headers**: Case-insensitive, alphanumeric-only matching
3. **For each row**:
   - Validate required fields (accountNum)
   - Compute `row_hash` (SHA256 of normalized row JSON) for within-file duplicate detection
   - Parse dates (DD/MM/YYYY, DD/MM/YY, YYYY-MM-DD)
   - Parse amounts (French format: comma decimal, space thousands)
   - Normalize label (strip whitespace, lowercase, remove card prefix/suffix)
   - Infer transaction type (expense, income, transfer, refund, adjustment)
4. **Compute fingerprint**: `sha256(account_num | posted_at | amount | label_norm_core)`
5. **Get or create Transaction** by fingerprint
6. **Create ImportRow** with appropriate status
7. **Create ImportRowLink** to canonical transaction
8. **Update Import aggregate stats**

## CSV Column Mapping

Expected headers (case-insensitive, flexible matching):

| CSV Header | Model Field | Notes |
|------------|-------------|-------|
| `dateOp` | operation_at | Operation date |
| `dateVal` | posted_at | Posted date (used in fingerprint) |
| `label` | label_raw | Raw transaction label |
| `supplierFound` | supplier_raw | Payee hint from bank |
| `amount` | amount | French format: "-1 300,00", "2 848,02" |
| `category` | category_raw | Bank-provided category |
| `categoryParent` | category_parent_raw | Parent category |
| `comment` | comment_raw | User notes from bank |
| `accountNum` | → Account.account_num | Required, used for account lookup |
| `accountLabel` | → Account.label | Used to create new Account if needed |
| `accountbalance` | balance_after | Balance after transaction (optional) |

## Fingerprint Formula

```
fingerprint = sha256(account_num | posted_at | amount | label_norm_core)
```

This ensures:
- Same transaction from overlapping date-range exports links correctly
- Different transactions on same day with same amount are distinguished by label

## Frontend State Management

The component uses React hooks (no Redux/Context):

### Import History Tab
- `imports`: ImportSummary[]
- `expandedImportId`: number | null (which import row is expanded)
- `rows`: ImportRowSummary[] (for selected import)
- `rowsFilter`: "all" | "unlinked" | "errors"
- `rowsPage`, `importRowsLimit`: Pagination

### All Transactions Tab
- `allRows`: ImportRowWithImport[]
- `allRowsFilter`, `allRowsPage`, `allRowsLimit`: Pagination
- `allRowsSearch`: Text search (label/supplier)
- `allRowsDateRangeDraft`, `allRowsDateRangeApplied`: Date filtering
- `allRowsSort`: "date_val" | "amount"
- `allRowsSortDirection`: "ascending" | "descending"

### Upload State
- `selectedFile`: File | null
- `previewStats`: ImportStats | null
- `previewing`, `confirming`: boolean (loading states)
- `previewError`, `confirmError`: string | null
- `confirmSuccess`: boolean

### Drawer State
- `drawerContext`: {importId, rowId} | null
- `drawerRow`: ImportRowDetail | null

## Helper Functions (in imports-page.tsx)

| Function | Purpose |
|----------|---------|
| `formatDate()` | Format date to French locale (fr-FR) |
| `formatDateTime()` | Format with time |
| `formatAmount()` | Format as EUR currency |
| `amountClass()` | CSS class based on sign (expense=red, income=green) |
| `truncateHash()` | Show first 8 chars of file hash |
| `getStatusParam()` | Map filter state to API parameter |

## Key Sub-Components (in imports-page.tsx)

- `<RowsPerPageSelect />`: Dropdown for pagination size
- `<StatsInline />`: Compact stats display
- `<PreviewStatsGrid />`: Grid showing row_count, created, linked, duplicates, errors
- `<RowStatusBadge />`: Color-coded status badge
- `<FilterButton />`: Toggle buttons for row status filters
- `<SectionCard />`: Reusable section container

## TypeScript Types (frontend/src/services/imports.ts)

```typescript
ImportStats {
  row_count, created_count, linked_count, duplicate_count, error_count
}

ImportSummary {
  id, file_name, file_hash, imported_at, account, stats: ImportStats
}

ImportRowSummary {
  id, status, error_code, error_message,
  date_op, date_val, label_raw, supplier_raw, amount, category_raw,
  transaction_id
}

ImportRowWithImport extends ImportRowSummary {
  import_id, imported_at, file_name, account
}

ImportRowDetail extends ImportRowSummary {
  raw_json, normalization_preview, transaction
}
```

## Known Gaps

1. **Normalization preview incomplete**: PRD expects parsed dates + amount in drawer; currently only shows label_norm + inferred type/payee
2. **"Unlinked" filter semantics unclear**: Label says "Unlinked" but maps to `status=created`, which means rows that created new transactions (opposite of what "unlinked" implies)

## Invariants

1. **Sum of stats**: `created_count + linked_count + error_count + duplicate_count = row_count`
2. **Every successful row links to a Transaction**: Via ImportRowLink join table
3. **Fingerprint uniqueness**: Transactions are upserted by fingerprint; no duplicates
4. **Raw data preservation**: `raw_json` always stores original CSV row

## Testing Checklist

- [ ] Import same file twice → 0 new transactions (all linked)
- [ ] Overlapping date range import → no duplicates
- [ ] French decimal parsing works ("-1 300,00" → -1300.00)
- [ ] Error rows display in UI with error_message
- [ ] Drawer opens on row click and shows detail
- [ ] Filters (All/Unlinked/Errors) work correctly
- [ ] Pagination works in both tabs
- [ ] Date range and search filters work in "All Transactions" tab
