from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_workspace, generate_api_key, hash_api_key, new_slug
from app.config import get_settings
from app.db import get_db
from app.models import Campaign, DailyMetric, Import, Workspace
from app.schemas import WorkspaceCreate, WorkspaceCreated, WorkspaceMe

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceCreated, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)):
    """Self-serve tenant creation. The API key is returned once and stored only as a SHA-256 hash."""
    key = generate_api_key()
    slug = new_slug(payload.name)
    while db.scalar(select(Workspace.id).where(Workspace.slug == slug)):  # pragma: no cover - 1/65k collision
        slug = new_slug(payload.name)
    ws = Workspace(slug=slug, name=payload.name.strip(), email=str(payload.email), api_key_hash=hash_api_key(key))
    db.add(ws)
    db.commit()
    db.refresh(ws)
    web = get_settings().public_web_url.rstrip("/")
    return WorkspaceCreated(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        email=ws.email,
        created_at=ws.created_at,
        api_key=key,
        workspace_url=f"{web}/w/{ws.slug}?key={key}",
    )


@router.get("/me", response_model=WorkspaceMe)
def me(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    campaigns = db.scalar(select(func.count()).select_from(Campaign).where(Campaign.workspace_id == ws.id)) or 0
    row = db.execute(
        select(func.count(DailyMetric.id), func.min(DailyMetric.day), func.max(DailyMetric.day))
        .join(Campaign, Campaign.id == DailyMetric.campaign_id)
        .where(Campaign.workspace_id == ws.id)
    ).one()
    imports = db.scalar(select(func.count()).select_from(Import).where(Import.workspace_id == ws.id)) or 0
    return {
        "id": ws.id,
        "slug": ws.slug,
        "name": ws.name,
        "email": ws.email,
        "created_at": ws.created_at,
        "stats": {
            "campaigns": campaigns,
            "metric_rows": row[0] or 0,
            "imports": imports,
            "first_day": row[1],
            "last_day": row[2],
        },
    }
