from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import ActivityLog

router = APIRouter()


@router.get("/api/search")
def search_logs(
    activity: str = None,
    keyword: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(ActivityLog)
    
    if activity:
        query = query.filter(ActivityLog.activity == activity)
    
    if keyword:
        query = query.filter(
            or_(
                ActivityLog.message.like(f'%{keyword}%'),
                ActivityLog.source.like(f'%{keyword}%')
            )
        )
    
    if start_date:
        query = query.filter(ActivityLog.timestamp >= start_date)
    
    if end_date:
        query = query.filter(ActivityLog.timestamp <= end_date)
    
    results = query.order_by(ActivityLog.timestamp.desc()).all()
    
    return [
        {
            'id': log.id,
            'timestamp': log.timestamp,
            'activity': log.activity,
            'message': log.message,
            'source': log.source
        }
        for log in results
    ]