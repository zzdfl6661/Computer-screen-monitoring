"""服务端视觉分析路由：POST /analyze_image（客户端仅在"不确定"样本触发上传）。

隐私：默认只保存截图 SHA-256 哈希与 OCR 文本；仅当 STORE_IMAGE_RAW=1 才存原始 base64。
"""
import hashlib
import io
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_device
from ..auth.models import Device
from ..database import get_db
from ..models import ImageAnalysis
from ..utils.rate_limit import rate_limiter
from ..vision import classify_fused, decode_base64_image, ocr_bytes

router = APIRouter()
logger = logging.getLogger("vision_route")

MAX_BASE64 = 2_000_000  # 384px JPEG 的 base64 一般 < 200KB，留足余量
MAX_IMAGE_SIDE = 2048   # 超出该边长的图片拒绝（客户端已降采样到 384px）
STORE_IMAGE_RAW = os.getenv("STORE_IMAGE_RAW", "0") == "1"


class ImageAnalysisRequest(BaseModel):
    image: str                       # base64 编码的 JPEG（客户端已降采样到 384px）
    window_title: Optional[str] = None
    process: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    activity: str
    confidence: float
    ocr_text: str


def _validate_image(raw: bytes) -> None:
    """校验 base64 解出的字节确为有效图片（格式 + 尺寸），非法返回 400。"""
    try:
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise HTTPException(status_code=400, detail="图片解析失败：不是有效的图片文件")
    if img.format not in ("JPEG", "PNG", "WEBP"):
        raise HTTPException(status_code=400, detail=f"不支持的图片格式: {img.format}")
    if img.width > MAX_IMAGE_SIDE or img.height > MAX_IMAGE_SIDE:
        raise HTTPException(status_code=400, detail="图片尺寸过大")


@router.post("/analyze_image", response_model=ImageAnalysisResponse,
             dependencies=[Depends(rate_limiter(limit=12, window_seconds=60))])
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
    _validate_image(raw)

    ocr_text = ocr_bytes(raw)
    # 多信号融合：process + window_title + OCR 文本（Docker/IDE/终端标题不再被丢弃）
    activity, confidence, detail = classify_fused(ocr_text, request.window_title, request.process)

    row = ImageAnalysis(
        device_id=device.device_token,
        # Use an empty sentinel when raw storage is disabled.  Older PostgreSQL
        # databases created before the privacy change still have a NOT NULL
        # constraint on this legacy column; an empty value preserves the
        # no-raw-image policy while keeping those databases compatible until
        # the migration is applied.
        image_base64=request.image if STORE_IMAGE_RAW else "",
        image_hash=hashlib.sha256(raw).hexdigest(),
        ocr_text=ocr_text,
        activity=activity,
        confidence=confidence,
        window_title=request.window_title,
        process=request.process,
        created_at=datetime.utcnow(),
    )
    try:
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"视觉分析入库失败: {e}")
        raise HTTPException(status_code=500, detail="保存失败")

    logger.info(
        f"视觉分析 device={device.device_name} activity={activity} "
        f"conf={confidence} ocr_len={len(ocr_text)} detail={detail} "
        f"store_raw={STORE_IMAGE_RAW}"
    )

    return {"activity": activity, "confidence": confidence, "ocr_text": ocr_text}
