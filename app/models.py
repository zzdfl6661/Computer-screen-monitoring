from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from .database import Base
from datetime import datetime

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String, nullable=False)
    activity = Column(String, nullable=False)
    message = Column(String, nullable=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String, nullable=False)
    device_id = Column(String, nullable=False)
    detected_activity = Column(String, nullable=False)
    actual_activity = Column(String, nullable=False)
    feedback_type = Column(String, nullable=False)
    screenshot_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policy"

    id = Column(Integer, primary_key=True, index=True)
    policy_name = Column(String, nullable=False, unique=True)
    retention_days = Column(Integer, nullable=False, default=30)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ImageAnalysis(Base):
    """服务端视觉分析（OCR）记录：图片入库 + OCR 文本 + 判定结果。"""
    __tablename__ = "image_analyses"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, nullable=False)
    image_base64 = Column(Text, nullable=False)          # 384px JPEG 的 base64
    ocr_text = Column(Text, nullable=True)               # OCR 提取的界面文字
    activity = Column(String, nullable=False)            # 判定结果 study/entertainment/idle
    confidence = Column(Float, nullable=True)
    window_title = Column(String, nullable=True)
    process = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)