from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import ThreatItem
from ..schemas import ThreatItemOut

router = APIRouter(prefix="/news", tags=["news"])

@router.get("/", response_model=list[ThreatItemOut])
def list_news(
    q: str | None = Query(default=None),
    kev: bool | None = Query(default=None),
    exploit: bool | None = Query(default=None),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(ThreatItem)
    if q:
        like = f"%{q}%"
        query = query.filter(ThreatItem.title.ilike(like))
    if kev is not None:
        query = query.filter(ThreatItem.is_kev == kev)
    if exploit is not None:
        query = query.filter(ThreatItem.has_exploit == exploit)
    query = query.order_by(ThreatItem.published_at.desc().nullslast()).limit(limit).offset(offset)
    return query.all()
