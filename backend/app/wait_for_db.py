from __future__ import annotations

import os
import time

import psycopg

from .config import settings


def _read_positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be a number, got: {raw!r}") from exc
    if value <= 0:
        raise SystemExit(f"{name} must be greater than 0, got: {value}")
    return value


def main() -> None:
    dsn = settings.database_url
    if not dsn:
        raise SystemExit("Database DSN is not set")
    if dsn.startswith("postgresql+psycopg://"):
        dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)

    timeout_s = _read_positive_float("WAIT_FOR_DB_TIMEOUT", 60)
    interval_s = _read_positive_float("WAIT_FOR_DB_INTERVAL", 1)
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None

    while True:
        try:
            conn = psycopg.connect(dsn)
            conn.close()
            return
        except Exception as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                message = f"Timed out after {timeout_s:.0f}s waiting for db"
                if last_error:
                    message = f"{message}: {last_error}"
                raise SystemExit(message) from exc
            print("Waiting for db...", flush=True)
            time.sleep(interval_s)


if __name__ == "__main__":
    main()
