"""服务端视觉分析路由：POST /analyze_image（客户端仅在"不确定"样本触发上传）。"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_device
from ..auth.models import Device
from ..database import get_db
from ..models import ImageAnalysis
from ..vision import classify_text, decode_base64_image, ocr_bytes

router = APIRouter()
logger = logging.getLogger("vision_route")

MAX_BASE64 = 2_000_000  # 384px JPEG 的 base64 一般 < 200KB，留足余量


class ImageAnalysisRequest(BaseModel):
    image: str                       # base64 编码的 JPEG（客户端已降采样到 384px）
    window_title: Optional[str] = None
    process: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    activity: str
    confidence: float
    ocr_text: str


@router.post("/analyze_image", response_model=ImageAnalysisResponse)
def analyze_image(
    request: ImageAnalysisRequest,
    db: Session = Depends(get_db),
    device: Device = Depends(get_current_device),
):
    if len(request.image) > MAX_BASE64:
        raise HTTPException(status_code=400, detail="图片过大")
    try:
        raw = decode_base64_image(request.image)
    except Exception:
        raise HTTPException(status_code=400, detail="base64 解码失败")

    ocr_text = ocr_bytes(raw)
    activity, confidence, detail = classify_text(ocr_text)

    row = ImageAnalysis(
        device_id=device.device_token,
        image_base64=request.image,
        ocr_text=ocr_text,
        activity=activity,
        confidence=confidence,
        window_title=request.window_title,
        process=request.process,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()

    logger.info(
        f"视觉分析 device={device.device_name} activity={activity} "
        f"conf={confidence} ocr_len={len(ocr_text)} detail={detail}"
    )

    return {"activity": activity, "confidence": confidence, "ocr_text": ocr_text}
