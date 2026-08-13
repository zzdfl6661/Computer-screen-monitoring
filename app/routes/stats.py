from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from ..database import get_db
from ..models import ActivityLog

router = APIRouter()


@router.get("/api/stats")
def get_stats(
    days: int = None,
    db: Session = Depends(get_db)
):
    """统计 study/entertainment/总数。
    days: None=今天（兼容旧版）；0=全部历史；N=最近 N 天（含今天）。"""
    query = db.query(
        ActivityLog.activity,
        func.count(ActivityLog.id).label('count')
    )

    if days == 0:
        pass  # 全部历史
    elif days and days > 0:
        start = (datetime.now() - timedelta(days=days - 1)).date().isoformat()
        query = query.filter(ActivityLog.timestamp >= start)
    else:
        today_date = datetime.now().date().isoformat()
        query = query.filter(ActivityLog.timestamp.like(f'{today_date}%'))

    stats = query.group_by(ActivityLog.activity).all()

    results = {row.activity: row.count for row in stats}
    study_count = results.get('study', 0)
    entertainment_count = results.get('entertainment', 0)
    total_count = sum(results.values())

    return {
        'study_count': study_count,
        'entertainment_count': entertainment_count,
        'total_count': total_count
    }