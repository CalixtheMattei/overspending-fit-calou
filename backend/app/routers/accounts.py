from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
def list_accounts(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    accounts = db.query(Account).order_by(Account.label.asc()).all()
    return jsonable_encoder([_account_summary(account) for account in accounts])


def _account_summary(account: Account) -> dict[str, object]:
    return {
        "id": account.id,
        "account_num": account.account_num,
        "label": account.label,
        "currency": account.currency,
    }
