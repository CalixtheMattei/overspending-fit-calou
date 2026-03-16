from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "demo_mode": settings.demo_mode}
