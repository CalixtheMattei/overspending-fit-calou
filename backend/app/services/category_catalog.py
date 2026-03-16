from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from sqlalchemy.orm import Session

from ..models import Category

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

FALLBACK_COLOR = "#9CA3AF"
FALLBACK_ICON = "tag"


class NativeCategorySpec(TypedDict):
    source_id: int
    name: str
    color: str
    icon: str
    source_parent_id: int | None
    display_name: str | None
    is_deprecated: bool
    canonical_source_id: int | None
    group: str | None


class CategoryCatalog(TypedDict):
    default_color: str
    default_icon: str
    colors: list[str]
    icons: list[str]
    native_categories: list[NativeCategorySpec]


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "category_catalog.json"


@lru_cache(maxsize=1)
def load_category_catalog() -> CategoryCatalog:
    # Accept BOM-prefixed JSON files (common on Windows editors).
    payload = json.loads(_catalog_path().read_text(encoding="utf-8-sig"))

    colors = [color for color in payload.get("colors", []) if isinstance(color, str) and HEX_COLOR_RE.match(color)]
    icons = [icon for icon in payload.get("icons", []) if isinstance(icon, str) and icon.strip()]

    default_color = payload.get("default_color")
    if not isinstance(default_color, str) or not HEX_COLOR_RE.match(default_color):
        default_color = FALLBACK_COLOR

    default_icon = payload.get("default_icon")
    if not isinstance(default_icon, str) or not default_icon.strip():
        default_icon = FALLBACK_ICON

    if default_color not in colors:
        colors.append(default_color)
    if default_icon not in icons:
        icons.append(default_icon)

    native_categories: list[NativeCategorySpec] = []
    seen_source_ids: set[int] = set()
    for row in payload.get("native_categories", []):
        if not isinstance(row, dict):
            continue
        source_id = row.get("source_id")
        source_parent_id = row.get("source_parent_id")
        canonical_source_id = row.get("canonical_source_id")
        name = row.get("name")
        color = row.get("color")
        icon = row.get("icon")
        if not isinstance(source_id, int):
            continue
        if source_id in seen_source_ids:
            raise ValueError(f"Duplicate category source_id in catalog: {source_id}")
        if source_parent_id is not None and not isinstance(source_parent_id, int):
            continue
        if canonical_source_id is not None and not isinstance(canonical_source_id, int):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(color, str) or color not in colors:
            color = default_color
        if not isinstance(icon, str) or icon not in icons:
            icon = default_icon

        display_name = row.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = None
        else:
            display_name = display_name.strip()

        is_deprecated = row.get("is_deprecated")
        if not isinstance(is_deprecated, bool):
            is_deprecated = False

        group = row.get("group")
        if not isinstance(group, str) or not group.strip():
            group = None
        else:
            group = group.strip()

        seen_source_ids.add(source_id)
        native_categories.append(
            {
                "source_id": source_id,
                "name": name.strip(),
                "color": color,
                "icon": icon,
                "source_parent_id": source_parent_id,
                "display_name": display_name,
                "is_deprecated": is_deprecated,
                "canonical_source_id": canonical_source_id,
                "group": group,
            }
        )

    source_ids = {row["source_id"] for row in native_categories}
    for row in native_categories:
        source_parent_id = row["source_parent_id"]
        canonical_source_id = row["canonical_source_id"]

        if source_parent_id is not None and source_parent_id not in source_ids:
            raise ValueError(f"Unknown source_parent_id {source_parent_id} in category catalog")
        if canonical_source_id is not None and canonical_source_id not in source_ids:
            raise ValueError(f"Unknown canonical_source_id {canonical_source_id} in category catalog")
        if canonical_source_id is not None and canonical_source_id == row["source_id"]:
            raise ValueError(f"canonical_source_id cannot point to itself for source_id={row['source_id']}")
        if canonical_source_id is not None and not row["is_deprecated"]:
            raise ValueError(
                f"canonical_source_id requires is_deprecated=true for source_id={row['source_id']}"
            )

    return {
        "default_color": default_color,
        "default_icon": default_icon,
        "colors": sorted(set(colors)),
        "icons": sorted(set(icons)),
        "native_categories": native_categories,
    }


def get_category_presets() -> dict[str, object]:
    catalog = load_category_catalog()
    return {
        "colors": list(catalog["colors"]),
        "icons": list(catalog["icons"]),
        "default_color": catalog["default_color"],
        "default_icon": catalog["default_icon"],
    }


def get_default_color() -> str:
    return load_category_catalog()["default_color"]


def get_default_icon() -> str:
    return load_category_catalog()["default_icon"]


def is_valid_preset_color(color: str) -> bool:
    return color in _color_set()


def is_valid_preset_icon(icon: str) -> bool:
    return icon in _icon_set()


@lru_cache(maxsize=1)
def native_specs_by_source_id() -> dict[int, NativeCategorySpec]:
    return {row["source_id"]: row for row in load_category_catalog()["native_categories"]}


def seed_native_categories(db: Session) -> None:
    catalog = load_category_catalog()
    native_rows = catalog["native_categories"]

    categories_by_parent: dict[int | None, list[Category]] = {}
    categories = db.query(Category).order_by(Category.id.asc()).all()
    for category in categories:
        categories_by_parent.setdefault(category.parent_id, []).append(category)

    source_ref_to_category: dict[int, Category] = {}
    for category in categories:
        source_ref = _parse_native_source_ref(category)
        if source_ref is None:
            continue
        source_ref_to_category[source_ref] = category

    source_id_to_db_id: dict[int, int] = {}

    root_rows = sorted(
        (row for row in native_rows if row["source_parent_id"] is None),
        key=lambda item: item["source_id"],
    )
    for row in root_rows:
        category = _upsert_native_category(
            db,
            row=row,
            parent_db_id=None,
            categories_by_parent=categories_by_parent,
            source_ref_to_category=source_ref_to_category,
        )
        source_id_to_db_id[row["source_id"]] = category.id

    children = [row for row in native_rows if row["source_parent_id"] is not None]
    for row in sorted(children, key=lambda item: item["source_id"]):
        source_parent_id = row["source_parent_id"]
        if source_parent_id is None:
            continue
        parent_db_id = source_id_to_db_id.get(source_parent_id)
        if parent_db_id is None:
            continue

        category = _upsert_native_category(
            db,
            row=row,
            parent_db_id=parent_db_id,
            categories_by_parent=categories_by_parent,
            source_ref_to_category=source_ref_to_category,
        )
        source_id_to_db_id[row["source_id"]] = category.id

    db.commit()


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _find_category_match(categories_by_parent: dict[int | None, list[Category]], parent_id: int | None, name: str) -> Category | None:
    """Find an existing category by normalized name, but only match native rows.

    Custom categories (is_custom=True with source != 'native_catalog') are
    never matched, so the startup seed cannot accidentally overwrite user-created
    categories.
    """
    target = _normalize_name(name)
    for category in categories_by_parent.get(parent_id, []):
        # Skip custom categories — only match rows that are already native or
        # legacy rows with no source set (pre-source-field migration).
        if category.is_custom and category.source != "native_catalog":
            continue
        if _normalize_name(category.name) == target:
            return category
    return None


def _upsert_native_category(
    db: Session,
    *,
    row: NativeCategorySpec,
    parent_db_id: int | None,
    categories_by_parent: dict[int | None, list[Category]],
    source_ref_to_category: dict[int, Category],
) -> Category:
    category = source_ref_to_category.get(row["source_id"])
    if category is None:
        category = _find_category_match(categories_by_parent, parent_id=parent_db_id, name=row["name"])

    previous_parent_id = category.parent_id if category is not None else None
    if category is None:
        category = Category(
            name=row["name"],
            normalized_name=_normalize_name(row["name"]),
            parent_id=parent_db_id,
            color=row["color"],
            icon=row["icon"],
            is_custom=False,
            source="native_catalog",
            source_ref=str(row["source_id"]),
        )
        db.add(category)
        db.flush()
        categories_by_parent.setdefault(parent_db_id, []).append(category)
    else:
        category.name = row["name"]
        category.normalized_name = _normalize_name(row["name"])
        category.parent_id = parent_db_id
        category.color = row["color"]
        category.icon = row["icon"]
        category.is_custom = False
        category.source = "native_catalog"
        category.source_ref = str(row["source_id"])

        if previous_parent_id != parent_db_id:
            previous_siblings = categories_by_parent.get(previous_parent_id, [])
            categories_by_parent[previous_parent_id] = [item for item in previous_siblings if item.id != category.id]
            categories_by_parent.setdefault(parent_db_id, []).append(category)

    source_ref_to_category[row["source_id"]] = category
    return category


def _parse_native_source_ref(category: Category) -> int | None:
    if category.source != "native_catalog":
        return None
    if not category.source_ref:
        return None
    try:
        return int(category.source_ref)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _color_set() -> set[str]:
    return set(load_category_catalog()["colors"])


@lru_cache(maxsize=1)
def _icon_set() -> set[str]:
    return set(load_category_catalog()["icons"])
