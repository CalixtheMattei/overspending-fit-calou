from __future__ import annotations

from typing import Literal, Mapping, TypedDict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..models import Category, Split
from ..models.category import _normalize_category_name
from ..services.category_canonicalization import CategoryMetadata, build_category_metadata_index
from ..services.category_catalog import (
    get_category_presets,
    get_default_color,
    get_default_icon,
    is_valid_preset_color,
    is_valid_preset_icon,
)

router = APIRouter(prefix="/categories", tags=["categories"])
UNKNOWN_NATIVE_SOURCE_REF = "35"
UNKNOWN_SUBCATEGORY_ERROR = "Unknown category cannot have subcategories"


class CategorySummaryRow(TypedDict):
    id: int
    name: str
    parent_id: int | None
    color: str
    icon: str
    sort_order: int
    is_custom: bool
    display_name: str | None
    is_deprecated: bool
    canonical_id: int | None
    group: str | None


class CategoryTreeRow(CategorySummaryRow, total=False):
    children: list[CategorySummaryRow]


@router.on_event("startup")
def startup_seed_native_categories() -> None:
    from ..config import settings

    if settings.demo_mode:
        return  # Already seeded by seed_demo.py running as demo_admin
    db = SessionLocal()
    try:
        from ..services.category_catalog import seed_native_categories

        seed_native_categories(db)
    finally:
        db.close()


class CategoryCreate(BaseModel):
    name: str
    parent_id: int | None = None
    color: str | None = None
    icon: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    color: str | None = None
    icon: str | None = None


class DeleteStrategy(BaseModel):
    split_action: Literal["uncategorize", "reassign"] = "uncategorize"
    reassign_category_id: int | None = None
    child_action: Literal["promote", "reparent"] = "promote"
    reparent_category_id: int | None = None


@router.get("")
def list_categories(
    q: str | None = Query(None, alias="q"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = db.query(Category)
    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(Category.name.ilike(search))
    categories = query.order_by(Category.parent_id.asc().nullsfirst(), Category.sort_order.asc(), Category.name.asc()).limit(limit).all()
    metadata_index = build_category_metadata_index(db)
    return jsonable_encoder([_category_summary(category, metadata_index=metadata_index) for category in categories])


@router.get("/presets")
def list_category_presets(db: Session = Depends(get_db)) -> dict[str, object]:
    categories = db.query(Category).order_by(Category.parent_id.asc().nullsfirst(), Category.sort_order.asc(), Category.name.asc()).all()
    metadata_index = build_category_metadata_index(db)
    enriched = [_category_summary(category, metadata_index=metadata_index) for category in categories]

    payload = get_category_presets()
    payload["categories"] = enriched
    payload["tree"] = _build_category_tree(enriched)
    return jsonable_encoder(payload)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    name = payload.name.strip() if payload.name else ""
    if not name:
        raise HTTPException(status_code=400, detail="Category name is required")

    if payload.parent_id is not None:
        parent = db.query(Category).filter(Category.id == payload.parent_id).one_or_none()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category not found")
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="Categories only support two levels")
        if _is_unknown_root_category(parent):
            raise HTTPException(status_code=400, detail=UNKNOWN_SUBCATEGORY_ERROR)

    color = (payload.color or "").strip() or get_default_color()
    icon = (payload.icon or "").strip() or get_default_icon()
    _validate_category_presets(color=color, icon=icon)

    normalized = _normalize_category_name(name)
    _check_sibling_uniqueness(db, parent_id=payload.parent_id, normalized_name=normalized, exclude_id=None)

    category = Category(
        name=name,
        normalized_name=normalized,
        parent_id=payload.parent_id,
        color=color,
        icon=icon,
        is_custom=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    metadata_index = build_category_metadata_index(db)
    return jsonable_encoder(_category_summary(category, metadata_index=metadata_index))


@router.patch("/{category_id}")
def update_category(category_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)) -> dict[str, object]:
    category = db.query(Category).filter(Category.id == category_id).one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if not category.is_custom:
        raise HTTPException(status_code=409, detail="Native categories are immutable")

    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Category name is required")
        category.name = name

    if "parent_id" in data:
        parent_id = data["parent_id"]
        if parent_id == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent")
        if parent_id is not None:
            parent = db.query(Category).filter(Category.id == parent_id).one_or_none()
            if not parent:
                raise HTTPException(status_code=400, detail="Parent category not found")
            if parent.parent_id is not None:
                raise HTTPException(status_code=400, detail="Categories only support two levels")
            if _is_unknown_root_category(parent):
                raise HTTPException(status_code=400, detail=UNKNOWN_SUBCATEGORY_ERROR)
            # Reject moving a category that already has children under another root
            # (would produce depth > 2)
            has_children = (
                db.query(Category.id).filter(Category.parent_id == category_id).first()
                is not None
            )
            if has_children:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot nest a category that already has children (max depth is 2)",
                )
        category.parent_id = parent_id
    if "color" in data and data["color"] is not None:
        color = data["color"].strip()
        _validate_category_presets(color=color, icon=None)
        category.color = color
    if "icon" in data and data["icon"] is not None:
        icon = data["icon"].strip()
        _validate_category_presets(color=None, icon=icon)
        category.icon = icon

    # Recompute normalized_name if name or parent_id changed, and check uniqueness
    if "name" in data or "parent_id" in data:
        normalized = _normalize_category_name(category.name)
        _check_sibling_uniqueness(
            db,
            parent_id=category.parent_id,
            normalized_name=normalized,
            exclude_id=category.id,
        )
        category.normalized_name = normalized

    db.commit()
    db.refresh(category)
    metadata_index = build_category_metadata_index(db)
    return jsonable_encoder(_category_summary(category, metadata_index=metadata_index))


@router.get("/{category_id}/delete-preview")
def delete_preview(category_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    category = db.query(Category).filter(Category.id == category_id).one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    direct_split_count = (
        db.query(func.count(Split.id))
        .filter(Split.category_id == category_id)
        .scalar()
        or 0
    )

    children = (
        db.query(Category)
        .filter(Category.parent_id == category_id)
        .order_by(Category.name.asc())
        .all()
    )

    return {
        "direct_split_count": direct_split_count,
        "child_count": len(children),
        "children": [{"id": c.id, "name": c.name} for c in children],
    }


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    strategy: DeleteStrategy | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    category = db.query(Category).filter(Category.id == category_id).one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if not category.is_custom:
        raise HTTPException(status_code=409, detail="Native categories cannot be deleted")

    # Count impacted items
    direct_split_count = (
        db.query(func.count(Split.id))
        .filter(Split.category_id == category_id)
        .scalar()
        or 0
    )
    child_count = (
        db.query(func.count(Category.id))
        .filter(Category.parent_id == category_id)
        .scalar()
        or 0
    )

    has_impact = direct_split_count > 0 or child_count > 0

    # For zero-impact categories, strategy is optional — use defaults
    if strategy is None:
        if has_impact:
            raise HTTPException(
                status_code=400,
                detail="Strategy is required when category has splits or children",
            )
        strategy = DeleteStrategy()

    # Validate reassign target
    splits_reassigned = 0
    if strategy.split_action == "reassign":
        if strategy.reassign_category_id is None:
            raise HTTPException(
                status_code=400,
                detail="reassign_category_id is required when split_action is 'reassign'",
            )
        if strategy.reassign_category_id == category_id:
            raise HTTPException(
                status_code=400,
                detail="reassign_category_id cannot be the category being deleted",
            )
        target = db.query(Category).filter(Category.id == strategy.reassign_category_id).one_or_none()
        if not target:
            raise HTTPException(
                status_code=400,
                detail="reassign_category_id does not exist",
            )
        splits_reassigned = (
            db.query(func.count(Split.id))
            .filter(Split.category_id == category_id)
            .scalar()
            or 0
        )
        db.query(Split).filter(Split.category_id == category_id).update(
            {Split.category_id: strategy.reassign_category_id},
            synchronize_session=False,
        )
    else:
        # uncategorize
        splits_reassigned = (
            db.query(func.count(Split.id))
            .filter(Split.category_id == category_id)
            .scalar()
            or 0
        )
        db.query(Split).filter(Split.category_id == category_id).update(
            {Split.category_id: None},
            synchronize_session=False,
        )

    # Handle children
    children_moved = 0
    if strategy.child_action == "reparent":
        if strategy.reparent_category_id is None:
            raise HTTPException(
                status_code=400,
                detail="reparent_category_id is required when child_action is 'reparent'",
            )
        if strategy.reparent_category_id == category_id:
            raise HTTPException(
                status_code=400,
                detail="reparent_category_id cannot be the category being deleted",
            )
        reparent_target = db.query(Category).filter(Category.id == strategy.reparent_category_id).one_or_none()
        if not reparent_target:
            raise HTTPException(
                status_code=400,
                detail="reparent_category_id does not exist",
            )
        if reparent_target.parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail="reparent_category_id must be a root category",
            )
        children_moved = (
            db.query(func.count(Category.id))
            .filter(Category.parent_id == category_id)
            .scalar()
            or 0
        )
        db.query(Category).filter(Category.parent_id == category_id).update(
            {Category.parent_id: strategy.reparent_category_id},
            synchronize_session=False,
        )
    else:
        # promote to root
        children_moved = (
            db.query(func.count(Category.id))
            .filter(Category.parent_id == category_id)
            .scalar()
            or 0
        )
        db.query(Category).filter(Category.parent_id == category_id).update(
            {Category.parent_id: None},
            synchronize_session=False,
        )

    db.delete(category)
    db.commit()

    return {"deleted": True, "splits_reassigned": splits_reassigned, "children_moved": children_moved}


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderPayload(BaseModel):
    parent_id: int | None = None
    items: list[ReorderItem]


@router.patch("/reorder")
def reorder_categories(payload: ReorderPayload, db: Session = Depends(get_db)) -> dict[str, object]:
    """Reorder sibling categories under a given parent_id."""
    parent_id = payload.parent_id

    # Validate parent exists if provided
    if parent_id is not None:
        parent = db.query(Category).filter(Category.id == parent_id).one_or_none()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category not found")

    # Get all sibling IDs under this parent
    sibling_ids = set(
        row[0]
        for row in db.query(Category.id).filter(
            Category.parent_id == parent_id if parent_id is not None else Category.parent_id.is_(None)
        ).all()
    )

    # Validate all items belong to the given parent
    request_ids = {item.id for item in payload.items}
    invalid_ids = request_ids - sibling_ids
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Category IDs {sorted(invalid_ids)} are not siblings under parent_id={parent_id}",
        )

    # Apply sort orders
    for item in payload.items:
        db.query(Category).filter(Category.id == item.id).update(
            {Category.sort_order: item.sort_order},
            synchronize_session=False,
        )

    db.commit()

    # Return updated siblings
    siblings = (
        db.query(Category)
        .filter(
            Category.parent_id == parent_id if parent_id is not None else Category.parent_id.is_(None)
        )
        .order_by(Category.sort_order.asc(), Category.name.asc())
        .all()
    )
    metadata_index = build_category_metadata_index(db)
    return {
        "parent_id": parent_id,
        "items": jsonable_encoder(
            [_category_summary(c, metadata_index=metadata_index) for c in siblings]
        ),
    }


def _check_sibling_uniqueness(
    db: Session,
    *,
    parent_id: int | None,
    normalized_name: str,
    exclude_id: int | None,
) -> None:
    """Raise 409 if a sibling with the same normalized name already exists."""
    query = db.query(Category.id).filter(
        Category.parent_id == parent_id if parent_id is not None else Category.parent_id.is_(None),
        Category.normalized_name == normalized_name,
    )
    if exclude_id is not None:
        query = query.filter(Category.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=409,
            detail="A sibling category with the same name already exists",
        )


def _is_unknown_root_category(category: Category) -> bool:
    if category.parent_id is not None:
        return False
    if category.source == "native_catalog" and (category.source_ref or "").strip() == UNKNOWN_NATIVE_SOURCE_REF:
        return True
    return _normalize_category_name(category.name) == "unknown"


def _validate_category_presets(color: str | None, icon: str | None) -> None:
    if color is not None and not is_valid_preset_color(color):
        raise HTTPException(status_code=400, detail="Invalid category color preset")
    if icon is not None and not is_valid_preset_icon(icon):
        raise HTTPException(status_code=400, detail="Invalid category icon preset")


def _category_summary(
    category: Category,
    *,
    metadata_index: Mapping[int, CategoryMetadata] | None = None,
) -> CategorySummaryRow:
    metadata = metadata_index.get(category.id) if metadata_index else None
    return {
        "id": category.id,
        "name": category.name,
        "parent_id": category.parent_id,
        "color": category.color,
        "icon": category.icon,
        "sort_order": category.sort_order,
        "is_custom": category.is_custom,
        "display_name": metadata.get("display_name") if metadata else None,
        "is_deprecated": bool(metadata.get("is_deprecated")) if metadata else False,
        "canonical_id": metadata.get("canonical_id") if metadata else None,
        "group": metadata.get("group") if metadata else None,
    }


def _build_category_tree(categories: list[CategorySummaryRow]) -> list[CategoryTreeRow]:
    rows_by_id = {row["id"]: row for row in categories}
    children_by_parent: dict[int, list[CategorySummaryRow]] = {}
    for row in categories:
        parent_id = row["parent_id"]
        if parent_id is None:
            continue
        children_by_parent.setdefault(parent_id, []).append(row)

    for children in children_by_parent.values():
        children.sort(key=_category_sort_key)

    root_rows = [row for row in categories if row["parent_id"] is None]
    root_rows.sort(key=_category_sort_key)

    tree: list[CategoryTreeRow] = []
    for root in root_rows:
        root_id = root["id"]
        tree.append(_summary_row_with_children(root, children_by_parent.get(root_id, [])))

    # Include orphans as root-level entries to avoid dropping rows.
    orphan_parents = sorted(parent_id for parent_id in children_by_parent if parent_id not in rows_by_id)
    for parent_id in orphan_parents:
        for row in children_by_parent[parent_id]:
            tree.append(_summary_row_to_tree_row(row))

    return tree


def _category_sort_key(category_row: CategorySummaryRow) -> tuple[int, str, str]:
    display_name = category_row["display_name"]
    name = display_name if display_name and display_name.strip() else category_row["name"]
    return (category_row["sort_order"], name.lower(), category_row["name"].lower())


def _summary_row_to_tree_row(row: CategorySummaryRow) -> CategoryTreeRow:
    return {
        "id": row["id"],
        "name": row["name"],
        "parent_id": row["parent_id"],
        "color": row["color"],
        "icon": row["icon"],
        "sort_order": row["sort_order"],
        "is_custom": row["is_custom"],
        "display_name": row["display_name"],
        "is_deprecated": row["is_deprecated"],
        "canonical_id": row["canonical_id"],
        "group": row["group"],
    }


def _summary_row_with_children(
    row: CategorySummaryRow,
    children: list[CategorySummaryRow],
) -> CategoryTreeRow:
    tree_row = _summary_row_to_tree_row(row)
    tree_row["children"] = children
    return tree_row
