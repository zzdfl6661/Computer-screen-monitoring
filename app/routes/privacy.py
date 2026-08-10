from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.data_retention import get_retention_days, set_retention_days
from pydantic import BaseModel

router = APIRouter(prefix="/privacy", tags=["privacy"])

class RetentionPolicyRequest(BaseModel):
    retention_days: int

class PrivacyPolicyResponse(BaseModel):
    title: str
    version: str
    last_updated: str
    data_collection: dict
    data_storage: dict
    data_retention: dict
    security_measures: list
    user_rights: list
    contact_info: str

@router.get("/", response_model=PrivacyPolicyResponse)
def get_privacy_policy(db: Session = Depends(get_db)):
    retention_days = get_retention_days(db)
    
    return {
        "title": "智能劝学系统数据隐私政策",
        "version": "1.0.0",
        "last_updated": "2026-07-10",
        "data_collection": {
            "description": "系统收集的用户数据类型",
            "activity_logs": "电脑使用活动日志，包括窗口标题、活动类型判断结果",
            "feedback": "用户反馈数据，用于优化分类算法",
            "device_info": "设备标识，用于区分不同设备"
        },
        "data_storage": {
            "description": "数据存储方式",
            "encryption": "客户端敏感数据（device_token、access_token）使用 Fernet 加密存储",
            "https": "服务端数据传输使用 HTTPS 加密",
            "local_processing": "截图仅在本地处理，不传输到服务端"
        },
        "data_retention": {
            "description": "数据保留策略",
            "retention_days": retention_days,
            "auto_cleanup": "超过保留期限的数据将自动删除",
            "policy_table": "data_retention_policy"
        },
        "security_measures": [
            "客户端敏感数据加密存储",
            "服务端 HTTPS 数据传输",
            "定期数据清理",
            "最小权限原则"
        ],
        "user_rights": [
            "查看自己的活动日志",
            "修改数据保留期限",
            "删除自己的数据",
            "导出数据"
        ],
        "contact_info": "如有隐私问题，请联系系统管理员"
    }

@router.get("/retention")
def get_retention_policy(db: Session = Depends(get_db)):
    retention_days = get_retention_days(db)
    return {"retention_days": retention_days}

@router.put("/retention")
def update_retention_policy(request: RetentionPolicyRequest, db: Session = Depends(get_db)):
    if request.retention_days < 1:
        return {"error": "保留天数必须大于0"}
    if request.retention_days > 365:
        return {"error": "保留天数不能超过365天"}
    
    policy = set_retention_days(db, request.retention_days)
    return {
        "retention_days": policy.retention_days,
        "message": f"数据保留期限已更新为 {policy.retention_days} 天"
    }