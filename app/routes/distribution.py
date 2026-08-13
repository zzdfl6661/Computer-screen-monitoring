from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from ..database import get_db
from ..models import ActivityLog

router = APIRouter()


@router.get("/api/distribution")
def get_distribution(
    start_date: str = None,
    end_date: str = None,
    days: int = None,
    db: Session = Depends(get_db)
):
    """学习/娱乐分布。days: 0=全部；N=最近 N 天（含今天）；None=不按天数过滤。
    也可用 start_date/end_date 精确指定范围（与 days 二选一）。"""
    query = db.query(
        ActivityLog.activity,
        func.count(ActivityLog.id).label('count')
    )

    if days == 0:
        pass  # 全部历史
    elif days and days > 0:
        start = (datetime.now() - timedelta(days=days - 1)).date().isoformat()
        query = query.filter(ActivityLog.timestamp >= start)

    if start_date:
        query = query.filter(ActivityLog.timestamp >= start_date)
    if end_date:
        query = query.filter(ActivityLog.timestamp <= end_date)

    results = query.group_by(ActivityLog.activity).all()

    return {row.activity: row.count for row in results}