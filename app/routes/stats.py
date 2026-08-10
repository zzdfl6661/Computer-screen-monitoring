from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from ..database import get_db
from ..models import ActivityLog

router = APIRouter()


@router.get("/api/stats")
def get_stats(
    db: Session = Depends(get_db)
):
    today_date = datetime.now().date().isoformat()
    
    stats = db.query(
        ActivityLog.activity,
        func.count(ActivityLog.id).label('count')
    ).filter(ActivityLog.timestamp.like(f'{today_date}%'))\
     .group_by(ActivityLog.activity)\
     .all()
    
    results = {row.activity: row.count for row in stats}
    
    study_count = results.get('study', 0)
    entertainment_count = results.get('entertainment', 0)
    
    total_count = db.query(func.count(ActivityLog.id)).scalar() or 0
    
    return {
        'study_count': study_count,
        'entertainment_count': entertainment_count,
        'total_count': total_count
    }