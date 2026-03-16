#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_DB="${WITH_DB:-0}"
WITH_DOCKER="${WITH_DOCKER:-0}"

say() {
  printf "\n%s\n" "$1"
}

say "Frontend: install and build"
cd "$ROOT_DIR/frontend"
if [[ "${CI:-}" == "true" ]]; then
  npm ci
else
  npm install
fi
npm run build

say "Backend: venv, install, import check"
cd "$ROOT_DIR/backend"
if [[ ! -d ".venv" ]]; then
  python -m venv .venv
fi
source .venv/bin/activate
python -m pip install -e .
python -c "from app.main import app; print('backend import ok')"

if [[ "$WITH_DB" == "1" ]]; then
  say "Backend: alembic upgrade head"
  python -m alembic upgrade head
fi

deactivate || true

if [[ "$WITH_DOCKER" == "1" ]]; then
  say "Docker: compose up and health check"
  cd "$ROOT_DIR"
  docker compose up --build -d
  sleep 5
  curl -fsS http://localhost:8000/health
  docker compose down
fi

say "Sanity checks complete"
