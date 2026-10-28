from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_cache
from app.models import Campaign, Channel
from app.routers.accounts import get_account_or_404
from app.schemas import CampaignCreate, CampaignOut, CampaignUpdate

router = APIRouter(prefix="/accounts/{account_id}/campaigns", tags=["campaigns"])


def _get_campaign(db: Session, account_id: int, campaign_id: int) -> Campaign:
    camp = db.get(Campaign, campaign_id)
    if not camp or camp.account_id != account_id:
        raise HTTPException(status_code=404, detail="campaign not found")
    return camp


@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    account_id: int,
    channel: Channel | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
):
    get_account_or_404(db, account_id)
    stmt = select(Campaign).where(Campaign.account_id == account_id)
    if channel:
        stmt = stmt.where(Campaign.channel == channel)
    if status_filter:
        stmt = stmt.where(Campaign.status == status_filter)
    return db.scalars(stmt.order_by(Campaign.id)).all()


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(account_id: int, payload: CampaignCreate, db: Session = Depends(get_db), cache=Depends(get_cache)):
    get_account_or_404(db, account_id)
    camp = Campaign(account_id=account_id, **payload.model_dump())
    db.add(camp)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="campaign with this channel/external_id exists") from exc
    db.refresh(camp)
    cache.invalidate_account(account_id)
    return camp


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(account_id: int, campaign_id: int, db: Session = Depends(get_db)):
    return _get_campaign(db, account_id, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    account_id: int,
    campaign_id: int,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    camp = _get_campaign(db, account_id, campaign_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(camp, k, v)
    db.commit()
    db.refresh(camp)
    cache.invalidate_account(account_id)
    return camp


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(account_id: int, campaign_id: int, db: Session = Depends(get_db), cache=Depends(get_cache)):
    camp = _get_campaign(db, account_id, campaign_id)
    db.delete(camp)
    db.commit()
    cache.invalidate_account(account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
