"""固定频率截图的上传与家长看板读取接口。"""
import base64
import hashlib
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_device
from ..auth.models import Device
from ..database import get_db
from ..models import Screenshot
from ..utils.rate_limit import rate_limiter

router = APIRouter(prefix="/api", tags=["screenshots"])
MAX_BASE64 = 2_000_000
MAX_IMAGE_SIDE = 2048


class ScreenshotUpload(BaseModel):
    image: str = Field(min_length=16)
    window_title: Optional[str] = None
    process: Optional[str] = None
    activity: Optional[str] = None
    confidence: Optional[float] = None
    subject: Optional[str] = None


def _decode_image(value: str):
    if len(value) > MAX_BASE64:
        raise HTTPException(status_code=413, detail="截图过大")
    try:
        raw = base64.b64decode(value, validate=True)
        from PIL import Image
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无效图片") from exc
    if image.format not in ("JPEG", "PNG", "WEBP"):
        raise HTTPException(status_code=400, detail="仅支持 JPEG、PNG 或 WEBP")
    if image.width > MAX_IMAGE_SIDE or image.height > MAX_IMAGE_SIDE:
        raise HTTPException(status_code=400, detail="图片尺寸过大")
    mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image.format]
    return raw, image.width, image.height, mime


@router.post("/screenshots", dependencies=[Depends(rate_limiter(limit=90, window_seconds=60))])
def upload_screenshot(
    payload: ScreenshotUpload,
    db: Session = Depends(get_db),
    device: Device = Depends(get_current_device),
):
    raw, width, height, mime = _decode_image(payload.image)
    row = Screenshot(
        device_id=device.device_token,
        image_bytes=raw,
        image_hash=hashlib.sha256(raw).hexdigest(),
        mime_type=mime,
        width=width,
        height=height,
        activity=payload.activity,
        confidence=payload.confidence,
        process=(payload.process or "")[:128] or None,
        window_title=(payload.window_title or "")[:512] or None,
        subject=(payload.subject or "")[:32] or None,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": "saved"}


@router.get("/screenshots")
def list_screenshots(
    device: Optional[str] = None,
    days: int = 7,
    limit: int = 60,
    before_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    days = max(1, min(days, 7))
    query = db.query(Screenshot).filter(Screenshot.created_at >= datetime.utcnow() - timedelta(days=days))
    if device:
        query = query.filter(Screenshot.device_id == device)
    if before_id:
        query = query.filter(Screenshot.id < before_id)
    rows = query.order_by(Screenshot.id.desc()).limit(max(1, min(limit, 120))).all()
    return {
        "items": [{
            "id": r.id, "device_id": r.device_id, "created_at": r.created_at.isoformat(),
            "width": r.width, "height": r.height, "activity": r.activity,
            "confidence": r.confidence, "process": r.process, "window_title": r.window_title,
            "subject": r.subject, "vision_label": r.vision_label,
            "image_url": f"/api/screenshots/{r.id}/image",
        } for r in rows],
        "next_before_id": rows[-1].id if rows else None,
    }


@router.get("/screenshots/{screenshot_id}/image")
def get_screenshot_image(screenshot_id: int, db: Session = Depends(get_db)):
    row = db.query(Screenshot).filter(Screenshot.id == screenshot_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="截图不存在或已过期")
    return Response(content=row.image_bytes, media_type=row.mime_type,
                    headers={"Cache-Control": "private, max-age=300"})


class VisionLabelUpdate(BaseModel):
    vision_label: Optional[str] = None


@router.put("/screenshots/{screenshot_id}/vision-label")
def update_vision_label(screenshot_id: int, payload: VisionLabelUpdate, db: Session = Depends(get_db)):
    if payload.vision_label not in (None, "study", "entertainment", "idle", "unknown"):
        raise HTTPException(status_code=422, detail="无效标注")
    row = db.query(Screenshot).filter(Screenshot.id == screenshot_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="截图不存在")
    row.vision_label = payload.vision_label
    db.commit()
    return {"status": "updated", "vision_label": row.vision_label}
