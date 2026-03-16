# Personal Expense Tracker

A self-hosted personal finance app for importing bank transactions, categorizing with splits, and analyzing spending patterns. Built as an alternative to Finary's limited budgeting tools.

## Why This Exists

- **Split transactions** -- Shared purchases and reimbursements are first-class citizens
- **Deduplication** -- Import overlapping CSV exports without duplicates
- **Deterministic rules** -- Auto-categorize transactions based on patterns
- **Moments** -- Tag spending for specific events (vacation, moving, etc.) separate from regular categories
- **MCP Server** -- Query and manage your finances directly from any MCP host like Claude or Codex

## Features

- **CSV Import** -- Drag-and-drop BoursoBank CSV exports with automatic deduplication across overlapping date ranges
- **Ledger View** -- Browse, filter, and search all transactions
- **Split Allocations** -- Allocate a single transaction across multiple categories
- **Smart Categorization** -- Rules engine that auto-categorizes transactions by payee, label, or amount patterns
- **Payee Management** -- Clean up raw bank labels into meaningful payee names
- **Moments** -- Tag date ranges as events (vacation, move, project) and overlay spending analysis
- **Analytics** -- Spending breakdowns by category, payee, and time period
- **Internal Accounts** -- Track transfers between your own accounts without polluting analytics

## Tech Stack

| Layer      | Technology                                                    |
| ---------- | ------------------------------------------------------------- |
| Frontend   | React 19, Vite, TypeScript, Tailwind CSS v4, Untitled UI      |
| Backend    | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic                  |
| Database   | PostgreSQL 16                                                 |
| MCP Server | Python 3.12, FastMCP, httpx — stdio & SSE transports          |
| Infra      | Docker Compose                                                |

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/CalixtheMattei/overspending-fit-calou.git
cd overspending-fit-calou
docker compose up --build
```

- **App:** http://localhost:5173
- **API docs:** http://localhost:8000/docs

Startup sequence is health-driven:
- `db` must become `healthy`
- `migrate` runs once and exits with code `0`
- `backend` starts and becomes `healthy`
- `frontend` starts after backend health passes

Check status with:

```bash
docker compose ps
```

### Docker Dev Loop (hot reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Use this for day-to-day coding with bind mounts and live reload for both frontend and backend.

### Private VPS Deployment (host Nginx + Tailscale)

Use this when host-level Nginx owns ports `80/443` and proxies to local Docker ports.

```bash
# 1) Install Docker + Compose plugin (Ubuntu)
curl -fsSL https://get.docker.com | sh

# 2) Clone project
git clone https://github.com/CalixtheMattei/overspending-fit-calou.git
cd overspending-fit-calou

# 3) Create deployment env file
cp .env.example .env
# Edit .env and set strong POSTGRES_PASSWORD before first deploy
# Optionally set DATABASE_URL; if omitted, backend builds it from POSTGRES_*

# 4) Deploy with VPS override (localhost-only published ports)
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
```

Logs and status:

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f
docker compose -f docker-compose.yml -f docker-compose.vps.yml logs -f backend frontend db
```

### Manual Setup

**Prerequisites:** Node.js 20+, Python 3.11+, PostgreSQL 16

```bash
# 1. Start the database
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                               # Edit POSTGRES_* (or optional DATABASE_URL)
alembic upgrade head
uvicorn app.main:app --reload                      # http://localhost:8000

# 3. Frontend (in a new terminal)
cd frontend
npm install
npm run dev                                        # http://localhost:5173
```

## MCP Server

The MCP server exposes the backend as [Model Context Protocol](https://modelcontextprotocol.io) tools so Claude can query and manage your finances directly — no copy-pasting data into prompts.

**14 tools across 6 domains:**

| Domain       | Tools                                                                 |
| ------------ | --------------------------------------------------------------------- |
| Transactions | `list_transactions`, `get_transaction`, `get_transaction_summary`     |
| Analytics    | `get_spending_flow`, `get_payee_analytics`, `get_category_analytics`  |
| Moments      | `list_moments`, `get_moment`, `create_moment`, `list_moment_tagged_splits` |
| Categories   | `list_categories`, `get_category_tree`                                |
| Payees       | `list_payees`, `list_automatic_payee_suggestions`                     |
| Rules        | `list_rules`, `get_rule_impacts`                                      |

### Claude Code / Claude Desktop (stdio)

Create a `.mcp.json` at the repo root (gitignored — adjust the Python command for your environment):

```json
{
  "mcpServers": {
    "personal-expense": {
      "command": "python",
      "args": ["mcp-server/server.py"],
      "env": { "API_BASE_URL": "http://localhost:8000" }
    }
  }
}
```

The backend must be running before Claude Code starts for the tools to activate.

### Docker (SSE)

The `mcp` service is included in `docker-compose.yml` and runs on port 3001:

```bash
docker compose up mcp        # alongside the rest of the stack
```

Point any SSE-capable MCP client at `http://localhost:3001/sse`.

> **Security:** The MCP server has no built-in authentication. Run it on a private network (Tailscale, localhost, internal Docker network). Do not expose port 3001 to the public internet.

## Configuration

Copy `.env.example` to `.env` and adjust values as needed:

```bash
cp .env.example .env
```

For Docker, override database credentials via environment variables:

```bash
POSTGRES_PASSWORD=my_secure_password docker compose up --build
```

Do not keep the default `postgres/postgres` credentials outside local-only development.

| Variable               | Default                          | Description                                                                 |
| ---------------------- | -------------------------------- | --------------------------------------------------------------------------- |
| `DATABASE_URL`         | _(unset)_                        | Optional full DSN; if set, takes precedence over `POSTGRES_*`               |
| `POSTGRES_USER`        | `postgres`                       | Database username                                                           |
| `POSTGRES_PASSWORD`    | `postgres`                       | Database password                                                           |
| `POSTGRES_HOST`        | `localhost` / `db` (Docker)      | Database host                                                               |
| `POSTGRES_PORT`        | `5432`                           | Database port                                                               |
| `POSTGRES_DB`          | `personal_expense`               | Database name                                                               |
| `CORS_ORIGINS`         | `["http://localhost:5173"]`      | Allowed frontend origins (JSON list preferred; CSV/single also accepted)    |
| `APP_ENV`              | `development`                    | `development` or `production`                                               |
| `WAIT_FOR_DB_TIMEOUT`  | `60`                             | Max seconds to wait for DB readiness                                        |
| `WAIT_FOR_DB_INTERVAL` | `1`                              | Seconds between DB readiness retries                                        |
| `MCP_HOST_PORT`        | `3001`                           | Host port for MCP SSE transport (Docker only)                               |

## Project Structure

```
overspending-fit-calou/
├── frontend/src/
│   ├── pages/          # ImportsPage, LedgerPage, RulesPage, AnalyticsPage, MomentsPage
│   ├── components/     # Untitled UI component library
│   └── services/       # API client layer (one service per domain)
├── backend/app/
│   ├── models/         # SQLAlchemy ORM models
│   ├── routers/        # FastAPI REST endpoints
│   └── services/       # Business logic (CSV parsing, dedup, rules engine)
├── mcp-server/
│   └── tools/          # One module per domain (transactions, analytics, moments, …)
├── docs/               # PRDs and contributor guides
├── docker-compose.yml      # Production-like deployment
└── docker-compose.dev.yml  # Dev overrides (hot reload, exposed ports)
```

## CSV Format

Designed for **BoursoBank** tab-separated CSV exports with French decimal formatting:

| Field           | Example            | Notes                             |
| --------------- | ------------------ | --------------------------------- |
| `amount`        | `-1 300,00`        | French formatting (space + comma) |
| `dateOp`        | `2024-01-15`       | Operation date                    |
| `label`         | `CARTE 15/01 ...`  | Raw bank label                    |
| `supplierFound` | `Carrefour`        | Seeds payee name                  |

Other French banks with similar CSV formats may work with minimal adaptation.

## Roadmap

- [x] **M0** -- Project skeleton (Docker, Alembic, routing)
- [x] **M1** -- CSV import with deduplication
- [x] **M2** -- Ledger, splits, and payees
- [x] **M3** -- Rules engine for auto-categorization
- [x] **M4** -- Analytics dashboards
- [x] **M5** -- Moments overlay

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) -- Development setup, coding conventions, PR guidelines
- [CLAUDE.md](CLAUDE.md) -- AI assistant guidance
- [docs/AGENTS.md](docs/AGENTS.md) -- Contributor guide and invariants
- `docs/PRD-*.md` -- Feature specifications

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding conventions, and PR guidelines.

## License

[MIT](LICENSE)
