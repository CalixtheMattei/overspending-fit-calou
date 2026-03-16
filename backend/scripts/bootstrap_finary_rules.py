from __future__ import annotations

import argparse
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from app.db import SessionLocal
from app.services.category_catalog import seed_native_categories
from app.services.rules_bootstrap import bootstrap_finary_rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap deterministic rules from Finary exports.")
    parser.add_argument(
        "--rules-path",
        default="../docs/transactions_rules.json",
        help="Path to transactions_rules.json",
    )
    parser.add_argument(
        "--categories-path",
        default="../docs/configuration_categories.json",
        help="Path to configuration_categories.json",
    )
    args = parser.parse_args()

    rules_path = Path(args.rules_path).resolve()
    categories_path = Path(args.categories_path).resolve()

    if not rules_path.exists():
        raise SystemExit(f"Rules file not found: {rules_path}")
    if not categories_path.exists():
        raise SystemExit(f"Categories file not found: {categories_path}")

    db = SessionLocal()
    try:
        seed_native_categories(db)
        summary = bootstrap_finary_rules(
            db,
            rules_path=rules_path,
            categories_path=categories_path,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Bootstrap complete")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
