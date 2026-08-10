from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import ActivityLog

router = APIRouter()


@router.get("/api/distribution")
def get_distribution(
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        ActivityLog.activity,
        func.count(ActivityLog.id).label('count')
    )
    
    if start_date:
        query = query.filter(ActivityLog.timestamp >= start_date)
    if end_date:
        query = query.filter(ActivityLog.timestamp <= end_date)
    
    results = query.group_by(ActivityLog.activity).all()
    
    return {row.activity: row.count for row in results}