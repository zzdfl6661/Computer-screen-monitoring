"""服务端视觉分析路由：POST /analyze_image（客户端仅在"不确定"样本触发上传）。

隐私：默认只保存截图 SHA-256 哈希与 OCR 文本；仅当 STORE_IMAGE_RAW=1 才存原始 base64。
兜底分层：OCR + 规则融合判不出（unknown）时，可按频率调用云端 VLM
（VLM_API_KEY 未配置则整条 VLM 路径自动关闭）；结果按 (进程, 标题, URL) 缓存。
VLM 默认只辅助本次判定，不会自动写入长期规则。
"""
import hashlib
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_device
from ..auth.models import Device
from ..database import get_db
from ..models import ClassificationRule, ImageAnalysis, Screenshot
from ..utils.rate_limit import rate_limiter
from ..vlm_prompt import sanitize_url
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
VLM_REQUIRE_LOW_OCR = os.getenv("VLM_REQUIRE_LOW_OCR", "0") == "1"  # 兼容旧策略：仅无文字时调用
VLM_CACHE_TTL_SECONDS = int(os.getenv("VLM_CACHE_TTL_HOURS", "6")) * 3600  # 同 (进程,标题) 结果复用
VLM_KEY_RETRY_SECONDS = int(os.getenv("VLM_KEY_RETRY_SECONDS", "300"))     # 同 key 失败后最小重试间隔
VLM_GLOBAL_MIN_SECONDS = int(os.getenv("VLM_GLOBAL_MIN_SECONDS", "60"))    # 全局最小调用间隔
VLM_ACCEPT_MIN_CONF = float(os.getenv("VLM_ACCEPT_MIN_CONF", "0.75"))      # 达标才覆盖 unknown
VLM_MAX_IMAGES = max(1, min(3, int(os.getenv("VLM_MAX_IMAGES", "3"))))
VLM_FRAME_LOOKBACK_SECONDS = max(0, int(os.getenv("VLM_FRAME_LOOKBACK_SECONDS", "180")))
VLM_AUTO_RULE_ENABLED = os.getenv("VLM_AUTO_RULE_ENABLED", "0") == "1"
VLM_RULE_MIN_CONF = float(os.getenv("VLM_RULE_MIN_CONF", "0.90"))
VLM_RULE_CONFIRMATIONS = max(1, int(os.getenv("VLM_RULE_CONFIRMATIONS", "2")))

_vlm_cache = {}   # (device, process, title, url) -> 高置信 VLM 结果
_vlm_attempts = {}  # 同 key 上次真实调用 VLM 的 monotonic 时间
_global_last_call = [0.0]
_vlm_rule_votes = {}  # key -> {activity, count}，仅在显式启用自动规则时使用


class ImageAnalysisRequest(BaseModel):
    image: str                       # base64 编码的 JPEG（客户端已降采样到 384px）
    window_title: Optional[str] = Field(default=None, max_length=512)
    process: Optional[str] = Field(default=None, max_length=128)
    url: Optional[str] = Field(default=None, max_length=2048)


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


def _vlm_cache_key(process, title, url=None, device_id=None):
    return (
        (device_id or "").strip(),
        (process or "").strip().lower(),
        (title or "").strip(),
        sanitize_url(url).lower(),
    )


def _recent_vlm_frames(db: Session, device_id: str, current_raw: bytes,
                       process: str = None):
    """取同设备、同前台进程的近期固定采样截图，与当前帧组成旧→新序列。"""
    if VLM_MAX_IMAGES <= 1 or VLM_FRAME_LOOKBACK_SECONDS <= 0:
        return [current_raw]
    query = db.query(Screenshot).filter(
        Screenshot.device_id == device_id,
        Screenshot.created_at >= datetime.utcnow() - timedelta(seconds=VLM_FRAME_LOOKBACK_SECONDS),
    )
    if process:
        query = query.filter(Screenshot.process == process)
    rows = query.order_by(Screenshot.created_at.desc()).limit(VLM_MAX_IMAGES * 4).all()
    current_hash = hashlib.sha256(current_raw).hexdigest()
    seen = {current_hash}
    previous = []
    for row in rows:
        if not row.image_bytes or row.image_hash in seen:
            continue
        seen.add(row.image_hash)
        previous.append(row.image_bytes)
        if len(previous) >= VLM_MAX_IMAGES - 1:
            break
    return list(reversed(previous)) + [current_raw]


def _accept_vlm(activity: str, confidence: float) -> bool:
    return activity in ("study", "entertainment", "idle") and confidence >= VLM_ACCEPT_MIN_CONF


def _maybe_persist_vlm_rule(db: Session, key, activity: str, confidence: float,
                            process: str, title: str) -> None:
    """自动规则默认关闭；启用后也要求同一上下文连续多次同结论。"""
    if not VLM_AUTO_RULE_ENABLED or activity not in ("study", "entertainment"):
        return
    if confidence < VLM_RULE_MIN_CONF:
        return
    vote = _vlm_rule_votes.get(key)
    count = vote["count"] + 1 if vote and vote["activity"] == activity else 1
    _vlm_rule_votes[key] = {"activity": activity, "count": count}
    if count >= VLM_RULE_CONFIRMATIONS:
        _persist_vlm_rule(db, activity, process, title)


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
        key = _vlm_cache_key(
            request.process, request.window_title, request.url,
            device.device_token)
        cached = _vlm_cache.get(key)
        now = time.monotonic()
        if cached and now - cached["ts"] < VLM_CACHE_TTL_SECONDS:
            vlm_label = cached["activity"]
            vlm_raw = cached.get("raw")
            activity = cached["activity"]
            confidence = cached["confidence"]
            detail = f"{detail}|vlm_cache" if detail else "vlm_cache"
            logger.info("VLM 缓存命中 %s -> %s (%.2f)",
                        key, cached["activity"], cached["confidence"])
        else:
            ocr_chars = len(re.sub(r"\s+", "", ocr_text))
            throttled = (now - _vlm_attempts.get(key, 0.0) < VLM_KEY_RETRY_SECONDS
                         or now - _global_last_call[0] < VLM_GLOBAL_MIN_SECONDS)
            trigger_allowed = not VLM_REQUIRE_LOW_OCR or ocr_chars < VLM_OCR_MIN_CHARS
            if trigger_allowed and not throttled:
                _vlm_attempts[key] = now
                _global_last_call[0] = now
                frames = _recent_vlm_frames(
                    db, device.device_token, raw, request.process)
                v_activity, v_conf, v_raw_content = classify_vlm(
                    frames, request.window_title, request.process, request.url)
                if v_activity:
                    vlm_label = v_activity
                    vlm_raw = v_raw_content
                    accepted = _accept_vlm(v_activity, v_conf)
                    if accepted:
                        activity, confidence = v_activity, v_conf
                        detail = f"{detail}|vlm:{v_activity}/{v_conf}" if detail else f"vlm:{v_activity}/{v_conf}"
                    else:
                        suffix = f"vlm_rejected:{v_activity}/{v_conf}"
                        detail = f"{detail}|{suffix}" if detail else suffix
                    v_subject = None
                    try:
                        v_subject = json.loads(v_raw_content).get("subject")
                    except Exception:
                        v_subject = None
                    if accepted:
                        # 只缓存被采纳的稳定结论。低置信结果由同 key 5 分钟节流，
                        # 之后允许结合新截图重试，不会被 6 小时缓存锁死。
                        _vlm_cache[key] = {
                            "activity": v_activity, "confidence": v_conf,
                            "subject": v_subject, "raw": v_raw_content,
                            "ts": time.monotonic(),
                        }
                        _maybe_persist_vlm_rule(
                            db, key, v_activity, v_conf,
                            request.process, request.window_title)
                    logger.info(
                        "VLM 兜底判定: %s (%.2f, accepted=%s, frames=%s) process=%s title=%s",
                        v_activity, v_conf, accepted, len(frames),
                        request.process, request.window_title)
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
