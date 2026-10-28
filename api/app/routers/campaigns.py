from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import events
from app.auth import current_workspace
from app.db import get_db
from app.deps import get_cache
from app.models import Campaign, Channel, Workspace
from app.schemas import CampaignCreate, CampaignOut, CampaignUpdate

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def get_campaign_or_404(db: Session, workspace_id: int, campaign_id: int) -> Campaign:
    camp = db.get(Campaign, campaign_id)
    if not camp or camp.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="campaign not found")
    return camp


def _emit(db: Session, camp: Campaign, action: str) -> None:
    events.emit(
        db,
        camp.workspace_id,
        events.CAMPAIGN_CHANGED,
        {
            "campaign_id": camp.id,
            "action": action,
            "channel": camp.channel.value if isinstance(camp.channel, Channel) else camp.channel,
            "name": camp.name,
            "status": camp.status,
        },
    )


@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    channel: Channel | None = None,
    status_: str | None = Query(default=None, alias="status"),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
):
    stmt = select(Campaign).where(Campaign.workspace_id == ws.id)
    if channel:
        stmt = stmt.where(Campaign.channel == channel)
    if status_:
        stmt = stmt.where(Campaign.status == status_)
    return db.scalars(stmt.order_by(Campaign.id)).all()


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignCreate,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    camp = Campaign(workspace_id=ws.id, **payload.model_dump())
    db.add(camp)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="campaign with this channel/external_id exists") from exc
    _emit(db, camp, "created")
    db.commit()
    db.refresh(camp)
    cache.invalidate_workspace(ws.id)
    return camp


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    return get_campaign_or_404(db, ws.id, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    camp = get_campaign_or_404(db, ws.id, campaign_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(camp, k, v)
    _emit(db, camp, "updated")
    db.commit()
    db.refresh(camp)
    cache.invalidate_workspace(ws.id)
    return camp


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: int,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
    cache=Depends(get_cache),
):
    camp = get_campaign_or_404(db, ws.id, campaign_id)
    _emit(db, camp, "deleted")
    db.delete(camp)
    db.commit()
    cache.invalidate_workspace(ws.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
