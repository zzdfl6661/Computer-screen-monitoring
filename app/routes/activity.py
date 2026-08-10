from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import ActivityLog
from ..auth.dependencies import get_current_device
from ..auth.models import Device
from logger import setup_logger

router = APIRouter()
logger = setup_logger('activity_route')


class ActivityCheckRequest(BaseModel):
    activity: str


class ActivityCheckResponse(BaseModel):
    message: str
    status: str


@router.post("/check_activity", response_model=ActivityCheckResponse)
def check_activity(
    request: ActivityCheckRequest,
    db: Session = Depends(get_db),
    device: Device = Depends(get_current_device)
):
    activity = request.activity
    message = ""

    logger.info(f"收到活动检查请求: activity={activity}, device={device.device_name}")

    if activity == 'entertainment':
        message = "你正在娱乐，请切换到学习！"
        new_log = ActivityLog(
            timestamp=datetime.now().isoformat(),
            activity=activity,
            message=message,
            source='client'
        )
        db.add(new_log)
        db.commit()
        logger.warning(f"检测到娱乐活动: {message}")
        return {"message": message, "status": "warning"}
    elif activity == 'study':
        message = "继续保持学习状态！"
        new_log = ActivityLog(
            timestamp=datetime.now().isoformat(),
            activity=activity,
            message=message,
            source='client'
        )
        db.add(new_log)
        db.commit()
        logger.info(f"检测到学习活动: {message}")
        return {"message": message, "status": "good"}
    else:
        message = "无法识别的活动"
        new_log = ActivityLog(
            timestamp=datetime.now().isoformat(),
            activity=activity,
            message=message,
            source='client'
        )
        db.add(new_log)
        db.commit()
        logger.error(f"无法识别的活动: {activity}")
        return {"message": message, "status": "error"}