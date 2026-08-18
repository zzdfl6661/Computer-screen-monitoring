from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import engine, get_db, SessionLocal, migrate_schema
from .models import Base, ActivityLog
from .routes import activity, stats, distribution, trend, search, feedback, privacy, vision
from .auth import routes as auth_routes
from .auth import admin as admin_auth
from .auth.models import User, Device
from .utils.data_retention import start_auto_cleanup, cleanup_old_data
from logger import setup_logger

logger = setup_logger('fastapi_server')

Base.metadata.create_all(bind=engine)
migrate_schema()

app = FastAPI(title="活动监控服务", description="青少年电脑使用监控的智能劝学系统", version="1.1.0")

templates = Jinja2Templates(directory="templates")

app.include_router(auth_routes.router)
app.include_router(admin_auth.router)
app.include_router(activity)
app.include_router(stats)
app.include_router(distribution)
app.include_router(trend)
app.include_router(search)
app.include_router(feedback)
app.include_router(privacy)
app.include_router(vision)


# 家长看板鉴权门：设置 ADMIN_PASSWORD 后，/ 与 /api/* 需登录；
# /auth/*（设备 JWT）、/health、/login、/logout 等不受影响。
@app.middleware("http")
async def admin_gate(request: Request, call_next):
    path = request.url.path
    if admin_auth.admin_enabled() and not admin_auth.is_exempt(path):
        if not admin_auth.is_authed(request):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "需要家长登录"}, status_code=401)
            return RedirectResponse("/login", status_code=303)
    return await call_next(request)


try:
    db = SessionLocal()
    cleanup_old_data(db)
    start_auto_cleanup(SessionLocal)
finally:
    db.close()


@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    activity_log = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).all()
    logs_dict = [
        {
            'id': log.id,
            'timestamp': log.timestamp,
            'activity': log.activity,
            'message': log.message,
            'source': log.source,
            'device_id': log.device_id,
            'confidence': log.confidence,
            'decision_source': log.decision_source,
            'reason': log.reason,
        }
        for log in activity_log
    ]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "activity_log": logs_dict,
        "admin_enabled": admin_auth.admin_enabled(),
    })


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "活动监控服务"}
