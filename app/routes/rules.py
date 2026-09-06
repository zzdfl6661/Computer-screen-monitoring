"""数据库分类规则的管理与客户端分发接口。"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ClassificationRule
from ..rule_engine import invalidate

router = APIRouter(prefix="/api", tags=["classification-rules"])
VALID_ACTIVITY = {"study", "entertainment", "idle"}
VALID_SIGNAL = {"process", "title", "ocr", "domain"}
VALID_MATCH = {"exact", "contains", "domain"}


class RulePayload(BaseModel):
    activity: str
    signal_type: str
    match_type: str = "contains"
    pattern: str = Field(min_length=1, max_length=512)
    priority: int = Field(default=100, ge=0, le=1000)
    enabled: int = 1


def _validate(payload: RulePayload):
    if payload.activity not in VALID_ACTIVITY or payload.signal_type not in VALID_SIGNAL or payload.match_type not in VALID_MATCH:
        raise HTTPException(status_code=422, detail="规则分类、信号来源或匹配方式无效")


def _item(row: ClassificationRule):
    return {"id": row.id, "activity": row.activity, "signal_type": row.signal_type,
            "match_type": row.match_type, "pattern": row.pattern, "priority": row.priority,
            "enabled": row.enabled, "updated_at": row.updated_at.isoformat() if row.updated_at else None}


@router.get("/classification-rules")
def list_rules(enabled: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(ClassificationRule)
    if enabled is not None:
        query = query.filter(ClassificationRule.enabled == enabled)
    return [_item(r) for r in query.order_by(ClassificationRule.priority.desc(), ClassificationRule.id.asc()).all()]


@router.post("/classification-rules")
def create_rule(payload: RulePayload, db: Session = Depends(get_db)):
    _validate(payload)
    row = ClassificationRule(**payload.model_dump(), updated_at=datetime.utcnow())
    db.add(row); db.commit(); db.refresh(row)
    invalidate(); return _item(row)


@router.put("/classification-rules/{rule_id}")
def update_rule(rule_id: int, payload: RulePayload, db: Session = Depends(get_db)):
    _validate(payload)
    row = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if not row: raise HTTPException(status_code=404, detail="规则不存在")
    for key, value in payload.model_dump().items(): setattr(row, key, value)
    row.updated_at = datetime.utcnow(); db.commit(); db.refresh(row)
    invalidate(); return _item(row)


@router.post("/classification-rules/{rule_id}/toggle")
def toggle_rule(rule_id: int, db: Session = Depends(get_db)):
    row = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if not row: raise HTTPException(status_code=404, detail="规则不存在")
    row.enabled = 0 if row.enabled else 1; row.updated_at = datetime.utcnow(); db.commit()
    invalidate(); return _item(row)


@router.delete("/classification-rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    row = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if not row: raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(row); db.commit()
    invalidate(); return {"status": "deleted"}
