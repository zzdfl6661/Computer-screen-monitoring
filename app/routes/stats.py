from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import timedelta

from ..database import get_db
from ..models import ActivityLog
from ..auth.models import Device
from ..utils.duration import compute_minutes
from ..utils.time import now_local

router = APIRouter()


def _period_filter(query, days: int = None, device: str = None):
    """公共时间/设备过滤：days=None 今天（兼容旧版）；0=全部；N=最近 N 天（含今天）。"""
    if device:
        query = query.filter(ActivityLog.device_id == device)
    if days == 0:
        pass
    elif days and days > 0:
        start = (now_local() - timedelta(days=days - 1)).date().isoformat()
        query = query.filter(ActivityLog.timestamp >= start)
    else:
        today_date = now_local().date().isoformat()
        query = query.filter(ActivityLog.timestamp.like(f'{today_date}%'))
    return query


@router.get("/api/stats")
def get_stats(
    days: int = None,
    device: str = None,
    db: Session = Depends(get_db)
):
    """统计与时长。

    家长口径：total_count 只统计已归类的 study + entertainment；
    idle/unknown 保留为诊断字段，不再进入“有效记录”主卡片。
    时长由连续同活动样本分段聚合得到（见 utils/duration.py）。
    """
    base = _period_filter(db.query(ActivityLog), days, device)

    counts = {row.activity: row.count for row in
              base.with_entities(ActivityLog.activity, func.count(ActivityLog.id).label('count'))
              .group_by(ActivityLog.activity).all()}

    study_count = counts.get('study', 0)
    entertainment_count = counts.get('entertainment', 0)
    idle_count = counts.get('idle', 0)
    unknown_count = counts.get('unknown', 0)
    total_count = study_count + entertainment_count

    rows = base.with_entities(ActivityLog.timestamp, ActivityLog.activity).order_by(
        ActivityLog.timestamp.asc()).all()
    minutes = compute_minutes(rows)

    return {
        'study_count': study_count,
        'entertainment_count': entertainment_count,
        'idle_count': idle_count,
        'unknown_count': unknown_count,
        'total_count': total_count,
        'classified_count': total_count,
        'study_minutes': minutes.get('study', 0.0),
        'entertainment_minutes': minutes.get('entertainment', 0.0),
        'idle_minutes': minutes.get('idle', 0.0),
        'unknown_minutes': minutes.get('unknown', 0.0),
    }


@router.get("/api/devices")
def get_devices(db: Session = Depends(get_db)):
    """已注册设备列表（看板设备隔离筛选用）。"""
    devices = db.query(Device).order_by(Device.created_at.asc()).all()
    return [
        {"device_token": d.device_token, "device_name": d.device_name, "device_type": d.device_type}
        for d in devices
    ]


@router.get("/api/unknown-top")
def get_unknown_top(
    days: int = 7,
    limit: int = 20,
    device: str = None,
    db: Session = Depends(get_db)
):
    """unknown 诊断：聚合最近 N 天 unknown 样本的前台进程 / 窗口标题 TOP。

    用于定向补规则（比猜测性加进程名有效得多）：家长看 TOP 是哪些应用/标题
    判不出，再决定加入 study/entertainment 关键词或站点规则。
    """
    query = db.query(ActivityLog).filter(ActivityLog.activity == 'unknown')
    if device:
        query = query.filter(ActivityLog.device_id == device)
    if days and days > 0:
        start = (now_local() - timedelta(days=days - 1)).date().isoformat()
        query = query.filter(ActivityLog.timestamp >= start)

    rows = query.all()

    from collections import Counter
    proc_counter = Counter()
    title_counter = Counter()
    samples = []
    for r in rows:
        if r.process:
            proc_counter[r.process] += 1
        if r.title:
            title_counter[r.title] += 1
        if len(samples) < 30 and (r.process or r.title):
            samples.append({
                'timestamp': r.timestamp,
                'process': r.process,
                'title': r.title,
                'device_id': r.device_id,
                'confidence': r.confidence,
                'reason': r.reason,
            })

    return {
        'total_unknown': len(rows),
        'top_processes': [{'name': k, 'count': v} for k, v in proc_counter.most_common(limit)],
        'top_titles': [{'name': k, 'count': v} for k, v in title_counter.most_common(limit)],
        'samples': samples,
    }
