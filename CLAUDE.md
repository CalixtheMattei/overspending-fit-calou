# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal expense tracker monorepo: Vite + React 19 + Untitled UI frontend, FastAPI + SQLAlchemy backend, PostgreSQL database. Designed for importing BoursoBank CSV exports with deduplication, split allocations, rules-based auto-categorization, and "Moments" overlay for event-based spending analysis.

## Commands

### Development
```bash
# Full stack with Docker
docker compose up --build

# Frontend only (http://localhost:5173)
cd frontend && npm install && npm run dev

# Backend only (http://localhost:8000)
cd backend && pip install -e . && uvicorn app.main:app --reload

# Database only
docker compose up -d db
```

### Build
```bash
cd frontend && npm run build    # TypeScript check + Vite production build
```

### Testing
```bash
cd backend && pytest                           # Requires TEST_DATABASE_URL env var
cd backend && pytest tests/test_import_service.py -v   # Single test file
```

### Database Migrations
```bash
cd backend && alembic upgrade head                      # Apply migrations
cd backend && alembic revision --autogenerate -m "msg"  # Generate migration
```

### Sanity Checks
```bash
scripts/sanity.ps1              # Windows
scripts/sanity.sh               # Linux/Mac
# Add -WithDb / WITH_DB=1 for migrations
# Add -WithDocker / WITH_DOCKER=1 for full Docker test
```

## Architecture

**Frontend** (`frontend/src/`):
- Pages: `pages/` - ImportsPage, LedgerPage, RulesPage, AnalyticsPage, MomentsPage
- Components: `components/` - Untitled UI structure (application/, base/, layouts/)
- API clients: `services/` - one service per domain (imports, transactions, payees, etc.)
- Path alias: `@/` maps to `src/`

**Backend** (`backend/app/`):
- Entry: `main.py` - FastAPI app with CORS and routers
- Models: `models/` - SQLAlchemy ORM (Transaction, Split, Import, ImportRow, etc.)
- Routes: `routers/` - REST endpoints per domain
- Business logic: `services/` - import_service.py (CSV parsing, deduping), ledger_validation.py

## Critical Invariants

1. **Split sum invariant**: `sum(splits.amount) == transaction.amount` exactly (to the cent). Backend enforces on every split update.

2. **Stable fingerprint deduplication**: `fingerprint = sha256(accountNum|dateVal|amount|label_norm_core)`. Overlapping CSV imports must not create duplicate transactions.

3. **Raw imports append-only**: Never discard raw_json from import_rows; required for audit trail.

4. **Transfers excluded from analytics**: Type "transfer" and keywords (livret a, epargne, revolut) exclude internal movements from spending calculations.

## CSV Format (BoursoBank)

Tab-separated with French decimal formatting:
- Amount: "-1 300,00" (spaces as thousands separator, comma as decimal)
- Headers: `dateOp, dateVal, label, category, categoryParent, supplierFound, amount, comment, accountNum, accountLabel, accountbalance`
- `supplierFound` seeds payee names

## UI Component Library

This repo uses **Untitled UI React components**. Always use existing components from `frontend/src/components/` when building or modifying UI to maintain design consistency.

## Documentation

Detailed requirements in `docs/`:
- `AGENTS.md` - Full contributor guide, invariants, milestone plan
- `PRD-000` through `PRD-005` - Feature specifications

## Agent Workflow

When implementing features:
1. Read relevant PRD in `docs/`
2. Implement backend endpoints + migrations first
3. Add frontend to exercise endpoints
4. Add integration tests for critical invariants
5. Commit with milestone label (M0-M5)
