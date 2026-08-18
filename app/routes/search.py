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
    device: str = None,
    since_id: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db)
):
    """活动日志检索。

    since_id：仅返回 id > since_id 的记录（用于看板增量刷新，避免每 10s 全量重渲染大表）。
    不传则按当前过滤条件取最近 limit 条。
    """
    query = db.query(ActivityLog)

    if activity:
        query = query.filter(ActivityLog.activity == activity)

    if keyword:
        query = query.filter(
            or_(
                ActivityLog.message.like(f'%{keyword}%'),
                ActivityLog.source.like(f'%{keyword}%'),
                ActivityLog.reason.like(f'%{keyword}%'),
            )
        )

    if start_date:
        query = query.filter(ActivityLog.timestamp >= start_date)

    if end_date:
        query = query.filter(ActivityLog.timestamp <= end_date)

    if device:
        query = query.filter(ActivityLog.device_id == device)

    if since_id and since_id > 0:
        # 增量：只取新行
        results = query.filter(ActivityLog.id > since_id).order_by(ActivityLog.id.asc()).all()
    else:
        # 全量：按时间倒序，限制条数
        results = query.order_by(ActivityLog.timestamp.desc()).limit(min(limit, 1000)).all()

    return [
        {
            'id': log.id,
            'timestamp': log.timestamp,
            'activity': log.activity,
            'message': log.message,
            'source': log.source,
            'device_id': log.device_id,
            'confidence': log.confidence,
            'decision_source': log.decision_source,
            'reason': log.reason,
        }
        for log in results
    ]
