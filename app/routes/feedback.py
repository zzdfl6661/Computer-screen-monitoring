from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import Feedback
from ..auth.dependencies import get_current_device
from ..auth.models import Device
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
        timestamp=datetime.now().isoformat(),
        device_id=str(device.id),
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