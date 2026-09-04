from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from ..database import get_db
from ..models import ActivityLog
from ..utils.time import now_local

router = APIRouter()


@router.get("/api/distribution")
def get_distribution(
    start_date: str = None,
    end_date: str = None,
    days: int = None,
    device: str = None,
    db: Session = Depends(get_db)
):
    """学习/娱乐分布。days: 0=全部；N=最近 N 天（含今天）；None=不按天数过滤。
    也可用 start_date/end_date 精确指定范围（与 days 二选一）。device 可选，按设备过滤。"""
    query = db.query(
        ActivityLog.activity,
        func.count(ActivityLog.id).label('count')
    ).filter(ActivityLog.activity.in_(['study', 'entertainment']))

    if device:
        query = query.filter(ActivityLog.device_id == device)

    if days == 0:
        pass  # 全部历史
    elif days and days > 0:
        start = (now_local() - timedelta(days=days - 1)).date().isoformat()
        query = query.filter(ActivityLog.timestamp >= start)

    if start_date:
        query = query.filter(ActivityLog.timestamp >= start_date)
    if end_date:
        # 日期输入代表整天；用次日零点作为排他上界，避免遗漏结束日的记录。
        if len(end_date) == 10:
            try:
                end_boundary = (datetime.fromisoformat(end_date) + timedelta(days=1)).isoformat()
            except ValueError:
                end_boundary = end_date
        else:
            end_boundary = end_date
        query = query.filter(ActivityLog.timestamp < end_boundary)

    results = query.group_by(ActivityLog.activity).all()

    return {row.activity: row.count for row in results}
