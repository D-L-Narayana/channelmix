from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_cache
from app.models import Account
from app.schemas import AccountCreate, AccountOut, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_account_or_404(db: Session, account_id: int) -> Account:
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="account not found")
    return acc


@router.get("", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db), limit: int = 100, offset: int = 0):
    return db.scalars(select(Account).order_by(Account.id).limit(limit).offset(offset)).all()


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    acc = Account(name=payload.name, currency=payload.currency.upper())
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)):
    return get_account_or_404(db, account_id)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)):
    acc = get_account_or_404(db, account_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(acc, k, v.upper() if k == "currency" else v)
    db.commit()
    db.refresh(acc)
    return acc


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db), cache=Depends(get_cache)):
    acc = get_account_or_404(db, account_id)
    db.delete(acc)
    db.commit()
    cache.invalidate_account(account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
