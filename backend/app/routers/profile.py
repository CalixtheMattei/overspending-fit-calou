from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import UserProfile

router = APIRouter(prefix="/profile", tags=["profile"])

_NAME_MIN = 2
_NAME_MAX = 80
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
_AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2 MB

_DEFAULT_NAME = "Personal User"
_DEFAULT_EMAIL = "you@example.com"


def _avatar_url(request: Request, avatar_path: str | None) -> str | None:
    if not avatar_path:
        return None
    # When behind a reverse proxy that strips a path prefix (e.g. /api),
    # request.base_url reflects the internal host.  Use forwarded headers so
    # the returned URL is reachable from the browser.
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    prefix = request.headers.get("x-forwarded-prefix", "").rstrip("/")
    return f"{proto}://{host}{prefix}/static/avatars/{avatar_path}"


def _profile_response(profile: UserProfile | None, request: Request) -> dict:
    if profile is None:
        return {"id": 1, "name": _DEFAULT_NAME, "email": _DEFAULT_EMAIL, "avatar_url": None}
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "avatar_url": _avatar_url(request, profile.avatar_path),
    }


def _avatars_dir() -> Path:
    d = Path(settings.avatars_storage_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("")
def get_profile(request: Request, db: Session = Depends(get_db)) -> dict:
    profile = db.query(UserProfile).filter(UserProfile.id == 1).one_or_none()
    return jsonable_encoder(_profile_response(profile, request))


@router.put("")
def update_profile(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip()

    if not name or len(name) < _NAME_MIN or len(name) > _NAME_MAX:
        raise HTTPException(status_code=422, detail=f"Name must be {_NAME_MIN}–{_NAME_MAX} characters.")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email address.")

    profile = db.query(UserProfile).filter(UserProfile.id == 1).one_or_none()
    if profile is None:
        profile = UserProfile(id=1, name=name, email=email)
        db.add(profile)
    else:
        profile.name = name
        profile.email = email

    db.commit()
    db.refresh(profile)
    return jsonable_encoder(_profile_response(profile, request))


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image format. Use PNG, JPG, or WebP.")

    contents = await file.read()
    if len(contents) > _AVATAR_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image must be 2 MB or smaller.")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        ext = content_type.split("/")[-1]

    filename = f"avatar_{uuid.uuid4().hex}.{ext}"
    avatars = _avatars_dir()

    profile = db.query(UserProfile).filter(UserProfile.id == 1).one_or_none()

    # Delete old avatar file if it exists
    if profile and profile.avatar_path:
        old_file = avatars / profile.avatar_path
        if old_file.exists():
            old_file.unlink(missing_ok=True)

    (avatars / filename).write_bytes(contents)

    if profile is None:
        profile = UserProfile(id=1, name=_DEFAULT_NAME, email=_DEFAULT_EMAIL, avatar_path=filename)
        db.add(profile)
    else:
        profile.avatar_path = filename

    db.commit()
    db.refresh(profile)
    return jsonable_encoder(_profile_response(profile, request))


@router.delete("/avatar")
def delete_avatar(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    profile = db.query(UserProfile).filter(UserProfile.id == 1).one_or_none()
    if profile and profile.avatar_path:
        old_file = _avatars_dir() / profile.avatar_path
        old_file.unlink(missing_ok=True)
        profile.avatar_path = None
        db.commit()
        db.refresh(profile)
    return jsonable_encoder(_profile_response(profile, request))
