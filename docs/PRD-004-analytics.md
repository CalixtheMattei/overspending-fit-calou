# PRD-004 — Analytics (v1)

## Goal
Give clear visibility into spending with:
- time filtering (month/year/custom)
- category breakdown
- transfer-exclusion by default
- moment overlay toggles (exclude/include moments)

## UI (v1)
Sidebar tab: Analytics

### Controls
- date range selector: Month (default), Year, Custom range
- toggles:
  - Exclude transfers (default ON)
  - Exclude moments (default OFF)
  - Only this moment (select, optional v1)

### Charts (v1 minimal)
- Spend by category (bar)
- Net cashflow over time (line) [income + expenses]
- Top payees (table) optional

### Tables
- transactions list under charts reflecting filters
- export view optional

## Data rules
- Spend by category uses splits.
- Uncategorized transactions show under “Uncategorized” bucket (if no splits).
- Transfers excluded when toggle ON.

## Acceptance criteria
- December view shows expected category distribution.
- Excluding transfers removes "Virement depuis LIVRET A" and "VIR Epargne" effects on spending.
