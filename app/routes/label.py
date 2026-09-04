"""家长标注飞轮：看板一键标注 unknown 样本 → 生成个性化覆盖规则 → 客户端拉取合并。

与看板其他 /api/* 一致默认公开（局域网内家长访问）。标注时由请求体带 device_id，
缺省 'unknown'；客户端拉取 /api/overrides 时带 Bearer 设备令牌自动认证。

- POST /api/label       家长标注「进程/标题 → 学习/娱乐」，同一组合重复标注递增 hit_count
- GET  /api/overrides   客户端拉取覆盖规则（按设备过滤，只返回活跃规则）
- POST /api/overrides/{id}/toggle   家长停用/启用一条规则
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import ClassificationOverride
from logger import setup_logger

router = APIRouter(prefix="/api")
logger = setup_logger('label_route')

VALID_ACTIVITIES = ('study', 'entertainment', 'idle')


class LabelRequest(BaseModel):
    activity: str                      # study / entertainment / idle
    process: str = ""                  # 前台进程名（小写精确匹配）
    title: str = ""                    # 窗口标题子串（模糊匹配，可空=仅进程）
    device_id: str = None              # 设备标识（缺省 'unknown'）


class OverrideItem(BaseModel):
    id: int
    device_id: str
    process: str
    title: str
    activity: str
    hit_count: int
    active: int


class LabelResponse(BaseModel):
    message: str
    status: str
    override_id: int = None


@router.post("/label", response_model=LabelResponse)
def create_label(req: LabelRequest, db: Session = Depends(get_db)):
    """家长标注：进程/标题 → 活动类型。写覆盖规则，供客户端拉取。"""
    if req.activity not in VALID_ACTIVITIES:
        raise HTTPException(status_code=422, detail="activity 必须是 study/entertainment/idle")
    if not req.process and not req.title:
        raise HTTPException(status_code=422, detail="process 与 title 至少填一个")

    device_id = (req.device_id or 'unknown').strip()
    proc = (req.process or '').strip().lower()
    title = (req.title or '').strip()

    # 去重：同一 (device, process, title) 重复标注 → 递增 hit_count，不新增行
    q = db.query(ClassificationOverride).filter(
        ClassificationOverride.device_id == device_id,
        ClassificationOverride.activity == req.activity)
    if proc:
        q = q.filter(ClassificationOverride.process == proc)
    if title:
        q = q.filter(ClassificationOverride.title == title)

    existing = q.first()
    if existing:
        existing.hit_count = (existing.hit_count or 0) + 1
        existing.active = 1
        existing.updated_at = datetime.utcnow()
        db.commit()
        return LabelResponse(message="标注已更新（计数+1）", status="updated",
                             override_id=existing.id)

    row = ClassificationOverride(
        device_id=device_id, process=proc or None, title=title or None,
        activity=req.activity, hit_count=1, active=1,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"新覆盖规则: device={device_id} proc={proc or '-'} title={title or '-'} "
                f"-> {req.activity}")
    return LabelResponse(message="覆盖规则已创建", status="created", override_id=row.id)


@router.get("/overrides", response_model=list[OverrideItem])
def get_overrides(device: str = None, db: Session = Depends(get_db)):
    """客户端拉取覆盖规则。可传 device 过滤；缺省返回全部活跃规则。"""
    q = db.query(ClassificationOverride).filter(ClassificationOverride.active == 1)
    if device:
        q = q.filter(ClassificationOverride.device_id == device)
    rows = q.order_by(ClassificationOverride.hit_count.desc()).all()
    return [OverrideItem(
        id=r.id, device_id=r.device_id, process=r.process or "", title=r.title or "",
        activity=r.activity, hit_count=r.hit_count or 1, active=r.active or 1,
    ) for r in rows]


@router.post("/overrides/{oid}/toggle")
def toggle_override(oid: int, db: Session = Depends(get_db)):
    """家长停用/启用一条规则。"""
    row = db.query(ClassificationOverride).filter(ClassificationOverride.id == oid).first()
    if not row:
        raise HTTPException(status_code=404, detail="规则不存在")
    row.active = 0 if (row.active or 1) == 1 else 1
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "已停用" if row.active == 0 else "已启用", "active": row.active}
