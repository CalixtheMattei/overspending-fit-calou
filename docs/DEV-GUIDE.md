# Development Guide

Quick reference for local development setup and common tasks.

## Structure
- `frontend/` Vite + React app (Untitled UI)
- `backend/` FastAPI app with SQLAlchemy + Alembic
- `docs/` Product requirements and contributor guidance

## Quickstart

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate      # Windows
source .venv/bin/activate     # Linux/Mac
pip install -e .
uvicorn app.main:app --reload
```

### Docker (prod-like: immutable images)
```bash
docker compose up --build
```
- Postgres data persists in the named volume `postgres_data`.
- To wipe all DB data (including imported bank data), run `docker compose down -v` (destructive).

### Docker fast dev (bind-mounted code + hot reload)
Use the base file plus the dev override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

`-f` means "compose file". Order matters:
- First file (`docker-compose.yml`) is the base config.
- Second file (`docker-compose.dev.yml`) overrides/adds dev-only settings (bind mounts, reload commands).

Dev workflow:
```bash
# Start/update containers
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Watch logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# Stop
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

Rebuild only when needed (Dockerfile/dependencies changed):
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

## Sanity Checks

Run sanity checks to verify your environment:

```bash
# Windows
scripts/sanity.ps1

# Linux/Mac
scripts/sanity.sh
```

Optional flags:
- `-WithDb` or `WITH_DB=1` — run Alembic migrations
- `-WithDocker` or `WITH_DOCKER=1` — spin up Docker and hit `/health`

## Health Check

```bash
curl http://localhost:8000/health
```

## Database Migrations

```bash
cd backend
alembic upgrade head                      # Apply all migrations
alembic revision --autogenerate -m "msg"  # Generate new migration
```

## Testing

```bash
cd backend
pytest                                    # Run all tests (requires TEST_DATABASE_URL)
pytest tests/test_import_service.py -v   # Run specific test file
```
