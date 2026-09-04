from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ..database import get_db
from ..models import ActivityLog
from ..utils.time import now_local

router = APIRouter()


@router.get("/api/trend")
def get_trend(
    hours: int = 24,
    db: Session = Depends(get_db)
):
    now = now_local().replace(tzinfo=None)
    start_time = (now - timedelta(hours=hours)).isoformat()
    
    logs = db.query(ActivityLog.timestamp, ActivityLog.activity)\
             .filter(ActivityLog.timestamp >= start_time)\
             .order_by(ActivityLog.timestamp.asc())\
             .all()
    
    study_data = []
    entertainment_data = []
    labels = []
    
    if logs:
        current_hour = None
        study_count = 0
        entertainment_count = 0
        
        for log in logs:
            log_time = datetime.fromisoformat(log.timestamp)
            hour_key = log_time.strftime('%Y-%m-%d %H:00')
            
            if current_hour and hour_key != current_hour:
                labels.append(current_hour)
                study_data.append(study_count)
                entertainment_data.append(entertainment_count)
                study_count = 0
                entertainment_count = 0
            
            current_hour = hour_key
            if log.activity == 'study':
                study_count += 1
            elif log.activity == 'entertainment':
                entertainment_count += 1
        
        if current_hour:
            labels.append(current_hour)
            study_data.append(study_count)
            entertainment_data.append(entertainment_count)
    
    return {
        'labels': labels,
        'study_data': study_data,
        'entertainment_data': entertainment_data
    }
