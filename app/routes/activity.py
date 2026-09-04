from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityLog
from ..auth.dependencies import get_current_device
from ..auth.models import Device
from ..utils.rate_limit import rate_limiter
from ..utils.time import now_local_iso
from ..utils.classification import normalize_unknown, guard_productivity_result
from logger import setup_logger

router = APIRouter()
logger = setup_logger('activity_route')


class ActivityCheckRequest(BaseModel):
    """统一活动状态模型：study / entertainment / idle / unknown。
    不在枚举内的输入由 Pydantic 直接返回 422（不再伪装成 200 + error）。"""
    activity: Literal['study', 'entertainment', 'idle', 'unknown']
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    decision_source: Optional[str] = None  # process/title/text_llm/ocr/vlm/none
    reason: Optional[str] = None           # 原因码
    process: Optional[str] = None          # 前台进程名（unknown 诊断用）
    title: Optional[str] = None            # 窗口标题（unknown 诊断用）


class ActivityCheckResponse(BaseModel):
    message: str
    status: str


_ACTIVITY_RESULT = {
    'study': ("继续保持学习状态！", "good"),
    'entertainment': ("你正在娱乐，请切换到学习！", "warning"),
    'idle': ("当前空闲，无活动", "neutral"),
    'unknown': ("无法判定当前活动，已记录", "unknown"),
}


@router.post("/check_activity", response_model=ActivityCheckResponse,
             dependencies=[Depends(rate_limiter(limit=60, window_seconds=60))])
def check_activity(
    request: ActivityCheckRequest,
    db: Session = Depends(get_db),
    device: Device = Depends(get_current_device)
):
    activity, guarded_source, guarded_reason = guard_productivity_result(
        request.activity, request.process)
    activity, normalized_source, normalized_reason = normalize_unknown(
        activity, request.process, request.title)
    normalized_source = normalized_source or guarded_source
    normalized_reason = normalized_reason or guarded_reason
    confidence = request.confidence
    if normalized_source and (confidence is None or confidence < 0.85):
        confidence = 0.85
    message, status = _ACTIVITY_RESULT[activity]

    if normalized_source:
        original_source = request.decision_source
        decision_source = (
            normalized_source
            if not original_source or original_source == 'none'
            else f"{original_source}+{normalized_source}"
        )
    else:
        decision_source = request.decision_source
    reason = normalized_reason or request.reason

    logger.info(f"收到活动检查请求: activity={activity}, device={device.device_name}, "
                f"conf={confidence}, source={decision_source}, reason={reason}, "
                f"process={request.process!r}, title={request.title!r}")

    new_log = ActivityLog(
        timestamp=now_local_iso(),
        activity=activity,
        message=message,
        source='client',
        device_id=device.device_token,
        confidence=confidence,
        decision_source=decision_source,
        reason=reason,
        process=request.process,
        title=request.title,
    )
    try:
        db.add(new_log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"活动日志入库失败: {e}")
        raise

    if activity == 'entertainment':
        logger.warning(f"检测到娱乐活动: {message}")
    else:
        logger.info(f"检测到活动 {activity}: {message}")
    return {"message": message, "status": status}
