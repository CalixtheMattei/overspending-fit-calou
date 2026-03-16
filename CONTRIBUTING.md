# Contributing

Thanks for your interest in contributing to Personal Expense Tracker! This guide will help you get set up and submit your first PR.

## Development Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker & Docker Compose (for PostgreSQL)

### Getting Started

```bash
# 1. Fork and clone
git clone https://github.com/CalixtheMattei/overspending-fit-calou.git
cd overspending-fit-calou

# 2. Start the database
docker compose up -d db

# 3. Backend
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload    # http://localhost:8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

### Full Stack via Docker

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This gives you hot reload for both frontend and backend.

## Workflow

1. Create a branch from `master`: `git checkout -b feat/my-feature`
2. Implement backend changes first (models, migrations, endpoints)
3. Add frontend to exercise the new endpoints
4. Write tests for critical invariants
5. Run the sanity check before submitting:

```bash
# Windows
scripts/sanity.ps1

# Linux / macOS
scripts/sanity.sh
```

## Critical Invariants

These must never be broken:

1. **Split sum invariant** -- `sum(splits.amount) == transaction.amount` exactly, to the cent
2. **Stable fingerprint dedup** -- overlapping CSV imports must not create duplicate transactions
3. **Raw imports are append-only** -- never discard `raw_json` from `import_rows`
4. **Transfers excluded from analytics** -- internal movements must not appear in spending calculations

## Code Style

### Frontend
- TypeScript strict mode
- Prettier with Tailwind plugin for formatting
- Use existing Untitled UI components from `frontend/src/components/` -- do not introduce new UI libraries

### Backend
- Python 3.11+ type hints
- Follow existing patterns in `routers/` and `services/`
- Add Alembic migrations for any schema changes: `alembic revision --autogenerate -m "description"`

## Tests

```bash
cd backend
pytest                                    # Run all tests
pytest tests/test_import_service.py -v    # Single file
```

Tests require a `TEST_DATABASE_URL` environment variable pointing to a test PostgreSQL database.

## Pull Requests

- Keep PRs focused -- one feature or fix per PR
- Include a clear description of what changed and why
- Make sure the sanity check passes
- Screenshots are welcome for UI changes

## Questions?

Open an issue if you have questions or want to discuss a feature before implementing it.
