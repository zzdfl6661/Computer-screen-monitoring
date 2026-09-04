from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Feedback
from ..auth.dependencies import get_current_device
from ..auth.models import Device
from ..utils.time import now_local_iso
from logger import setup_logger

router = APIRouter(prefix="/api")
logger = setup_logger('feedback_route')


class FeedbackRequest(BaseModel):
    detected_activity: str
    actual_activity: str
    feedback_type: str
    screenshot_hash: str = None


class FeedbackResponse(BaseModel):
    message: str
    status: str


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    device: Device = Depends(get_current_device)
):
    logger.info(f"收到反馈请求: device={device.id}, detected={request.detected_activity}, "
                f"actual={request.actual_activity}, type={request.feedback_type}")

    new_feedback = Feedback(
        timestamp=now_local_iso(),
        device_id=device.device_token,
        detected_activity=request.detected_activity,
        actual_activity=request.actual_activity,
        feedback_type=request.feedback_type,
        screenshot_hash=request.screenshot_hash
    )

    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    logger.info(f"反馈数据已保存: id={new_feedback.id}")
    return {"message": "反馈提交成功", "status": "success"}


class FeedbackSummaryResponse(BaseModel):
    total: int
    false_positive_count: int
    false_negative_count: int
    false_positive_rate: float      # 误报率 = 误报数 / 总数
    false_negative_rate: float      # 漏报率 = 漏报数 / 总数
    device: str = None
    items: list = []                # 最近反馈明细（按时间倒序）


@router.get("/feedback", response_model=FeedbackSummaryResponse)
def get_feedback_summary(
    device: str = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """家长看板：反馈统计（误报/漏报率）+ 最近反馈列表。

    由看板鉴权门保护（/api/* 需 ADMIN_PASSWORD 登录）；限流由前端调用频率决定，数据量小不额外限制。
    """
    query = db.query(Feedback)
    if device:
        query = query.filter(Feedback.device_id == device)

    total = query.count()
    fp_count = query.filter(Feedback.feedback_type == 'false_positive').count()
    fn_count = query.filter(Feedback.feedback_type == 'false_negative').count()

    rows = query.order_by(Feedback.timestamp.desc()).limit(min(limit, 200)).all()
    items = [
        {
            'id': f.id,
            'timestamp': f.timestamp,
            'device_id': f.device_id,
            'detected_activity': f.detected_activity,
            'actual_activity': f.actual_activity,
            'feedback_type': f.feedback_type,
            'screenshot_hash': f.screenshot_hash,
        }
        for f in rows
    ]

    def _rate(n):
        return round(n / total, 3) if total else 0.0

    summary = {
        'total': total,
        'false_positive_count': fp_count,
        'false_negative_count': fn_count,
        'false_positive_rate': _rate(fp_count),
        'false_negative_rate': _rate(fn_count),
        'items': items,
    }
    if device:
        summary['device'] = device
    return summary
