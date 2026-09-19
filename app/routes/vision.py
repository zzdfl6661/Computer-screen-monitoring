"""服务端视觉分析路由：POST /analyze_image（客户端仅在"不确定"样本触发上传）。

隐私：默认只保存截图 SHA-256 哈希与 OCR 文本；仅当 STORE_IMAGE_RAW=1 才存原始 base64。
兜底分层：OCR + 规则融合判不出（unknown）且界面几乎无文字时，才调用云端 VLM
（VLM_API_KEY 未配置则整条 VLM 路径自动关闭）；结果按 (进程, 标题) 缓存并按
置信度沉淀为数据库规则，同一程序只花一次 API 钱。
"""
import hashlib
import io
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_device
from ..auth.models import Device
from ..database import get_db
from ..models import ClassificationRule, ImageAnalysis
from ..utils.rate_limit import rate_limiter
from ..vision import (
    AMBIGUOUS_VLM_PROC_HINTS,
    BROWSER_PROCESS_HINTS,
    classify_fused,
    classify_subject,
    classify_vlm,
    decode_base64_image,
    ocr_bytes,
    vlm_configured,
)

router = APIRouter()
logger = logging.getLogger("vision_route")

MAX_BASE64 = 2_000_000  # 384px JPEG 的 base64 一般 < 200KB，留足余量
MAX_IMAGE_SIDE = 2048   # 超出该边长的图片拒绝（客户端已降采样到 384px）
STORE_IMAGE_RAW = os.getenv("STORE_IMAGE_RAW", "0") == "1"

# ---- VLM 兜底成本控制参数 ----
VLM_OCR_MIN_CHARS = int(os.getenv("VLM_OCR_MIN_CHARS", "5"))      # OCR 有效字符 < 该值视为"无文字界面"
VLM_CACHE_TTL_SECONDS = int(os.getenv("VLM_CACHE_TTL_HOURS", "6")) * 3600  # 同 (进程,标题) 结果复用
VLM_KEY_RETRY_SECONDS = int(os.getenv("VLM_KEY_RETRY_SECONDS", "300"))     # 同 key 失败后最小重试间隔
VLM_GLOBAL_MIN_SECONDS = int(os.getenv("VLM_GLOBAL_MIN_SECONDS", "60"))    # 全局最小调用间隔
VLM_RULE_MIN_CONF = float(os.getenv("VLM_RULE_MIN_CONF", "0.70"))          # 达标才沉淀为数据库规则

_vlm_cache = {}   # (process, title) -> {"activity", "confidence", "subject", "ts"}
_vlm_attempts = {}  # (process, title) -> 上次真实调用 VLM 的 monotonic 时间
_global_last_call = [0.0]


class ImageAnalysisRequest(BaseModel):
    image: str                       # base64 编码的 JPEG（客户端已降采样到 384px）
    window_title: Optional[str] = None
    process: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    activity: str
    confidence: float
    ocr_text: str
    subject: Optional[str] = None


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


def _vlm_cache_key(process, title):
    return ((process or "").strip().lower(), (title or "").strip())


def _persist_vlm_rule(db: Session, activity: str, process: str, title: str) -> None:
    """把高置信 VLM 判定沉淀为数据库规则（飞轮）：后续同程序直接命中，零 API 成本。

    浏览器/同名冲突进程（chrome/java/origin）只沉淀标题规则，避免进程级规则误伤
    该进程的其它用途；其余沉淀进程精确规则。家长可在 /rules 接口或看板调整。
    """
    proc = (process or "").strip().lower()
    title = (title or "").strip()
    is_browser = proc and any(h in proc for h in BROWSER_PROCESS_HINTS)
    is_ambiguous = proc and any(h in proc for h in AMBIGUOUS_VLM_PROC_HINTS)
    if proc and not is_browser and not is_ambiguous:
        signal_type, match_type, pattern, priority = "process", "exact", proc[:512], 850
    elif title:
        signal_type, match_type, pattern, priority = "title", "contains", title[:200], 600
    else:
        return
    exists = db.query(ClassificationRule).filter(
        ClassificationRule.signal_type == signal_type,
        ClassificationRule.pattern == pattern,
        ClassificationRule.origin == "vlm",
    ).first()
    if exists:
        return
    db.add(ClassificationRule(
        activity=activity, signal_type=signal_type, match_type=match_type,
        pattern=pattern, priority=priority, enabled=1, origin="vlm",
        updated_at=datetime.utcnow(),
    ))
    db.commit()
    from ..rule_engine import invalidate
    invalidate()
    logger.info("VLM 判定已沉淀为规则: %s规则 %s=%s -> %s",
                "进程" if signal_type == "process" else "标题", signal_type, pattern, activity)


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
    activity, confidence, detail = classify_fused(ocr_text, request.window_title, request.process, db=db)

    vlm_label = None
    vlm_raw = None
    if activity == "unknown" and vlm_configured():
        key = _vlm_cache_key(request.process, request.window_title)
        cached = _vlm_cache.get(key)
        now = time.monotonic()
        if cached and now - cached["ts"] < VLM_CACHE_TTL_SECONDS:
            activity = cached["activity"]
            confidence = cached["confidence"]
            vlm_label = cached["activity"]
            if activity == "study":
                subject = cached.get("subject")
            detail = f"{detail}|vlm_cache" if detail else "vlm_cache"
            logger.info("VLM 缓存命中 %s -> %s (%.2f)", key, activity, confidence)
        else:
            ocr_chars = len(re.sub(r"\s+", "", ocr_text))
            throttled = (now - _vlm_attempts.get(key, 0.0) < VLM_KEY_RETRY_SECONDS
                         or now - _global_last_call[0] < VLM_GLOBAL_MIN_SECONDS)
            # 仅"OCR 几乎无文字且融合判不出"的界面才花钱调 VLM（无文字全屏游戏等）
            if ocr_chars < VLM_OCR_MIN_CHARS and not throttled:
                _vlm_attempts[key] = now
                _global_last_call[0] = now
                v_activity, v_conf, v_raw_content = classify_vlm(
                    raw, request.window_title, request.process)
                if v_activity:
                    vlm_label = v_activity
                    vlm_raw = v_raw_content
                    activity, confidence = v_activity, v_conf
                    detail = f"{detail}|vlm:{v_activity}/{v_conf}" if detail else f"vlm:{v_activity}/{v_conf}"
                    v_subject = None
                    try:
                        v_subject = json.loads(v_raw_content).get("subject")
                    except Exception:
                        v_subject = None
                    _vlm_cache[key] = {"activity": v_activity, "confidence": v_conf,
                                       "subject": v_subject, "ts": time.monotonic()}
                    if (v_activity in ("study", "entertainment")
                            and v_conf >= VLM_RULE_MIN_CONF):
                        _persist_vlm_rule(db, v_activity, request.process, request.window_title)
                    logger.info("VLM 兜底判定: %s (%.2f) process=%s title=%s",
                                v_activity, v_conf, request.process, request.window_title)
                else:
                    detail = f"{detail}|{v_raw_content}" if detail else str(v_raw_content)
                    logger.info("VLM 兜底未出结果 (%s)，节流 %ss", v_raw_content, VLM_KEY_RETRY_SECONDS)

    subject = None
    if activity == "study":
        if vlm_label == "study" and vlm_raw:
            try:
                subject = json.loads(vlm_raw).get("subject")
            except Exception:
                subject = None
        if not subject:
            subject, _ = classify_subject(f"{request.window_title or ''} {ocr_text}")

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
        subject=subject,
        vlm_label=vlm_label,
        vlm_raw=vlm_raw,
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
        f"conf={confidence} ocr_len={len(ocr_text)} subject={subject} "
        f"detail={detail} store_raw={STORE_IMAGE_RAW}"
    )

    return {"activity": activity, "confidence": confidence, "ocr_text": ocr_text,
            "subject": subject}
