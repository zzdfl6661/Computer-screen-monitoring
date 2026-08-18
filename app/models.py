from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from .database import Base
from datetime import datetime

class ActivityLog(Base):
    """活动判定日志。

    activity 取值：study / entertainment / idle / unknown（统一状态模型）。
    decision_source：process / title / text_llm / ocr / vlm / none（判定依据）。
    reason：原因码（no_foreground / desktop_shell / browser_blank / rules_uncovered /
            low_confidence / margin_tie / signal 等），供看板解释“为什么判成这个结果”。
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String, nullable=False)
    activity = Column(String, nullable=False)
    message = Column(String, nullable=True)
    source = Column(String, nullable=True)
    device_id = Column(String, nullable=True)          # 设备令牌（设备隔离/溯源）
    confidence = Column(Float, nullable=True)          # 判定置信度 0~1
    decision_source = Column(String, nullable=True)    # 判定依据来源
    reason = Column(String, nullable=True)             # 原因码
    process = Column(String, nullable=True)            # 前台进程名（诊断 unknown 用）
    title = Column(String, nullable=True)              # 窗口标题（诊断 unknown 用）
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
    """服务端视觉分析（OCR）记录。

    隐私默认：只保存截图 SHA-256 哈希与 OCR 提取文本，不保存原始截图；
    仅当环境变量 STORE_IMAGE_RAW=1 时才把 384px base64 截图入库。
    """
    __tablename__ = "image_analyses"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, nullable=False)
    image_base64 = Column(Text, nullable=True)          # 仅 STORE_IMAGE_RAW=1 时存原始截图
    image_hash = Column(String, nullable=True)          # SHA-256，默认只存哈希
    ocr_text = Column(Text, nullable=True)               # OCR 提取的界面文字
    activity = Column(String, nullable=False)            # 判定结果 study/entertainment/idle/unknown
    confidence = Column(Float, nullable=True)
    window_title = Column(String, nullable=True)
    process = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)