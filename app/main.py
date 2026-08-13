from fastapi import FastAPI, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles

from .database import engine, get_db, SessionLocal
from .models import Base, ActivityLog
from .routes import activity, stats, distribution, trend, search, feedback, privacy, vision
from .auth import routes as auth_routes
from .auth.models import User, Device
from .utils.data_retention import start_auto_cleanup, cleanup_old_data
from logger import setup_logger

logger = setup_logger('fastapi_server')

Base.metadata.create_all(bind=engine)

app = FastAPI(title="活动监控服务", description="青少年电脑使用监控的智能劝学系统", version="1.0.0")

templates = Jinja2Templates(directory="templates")

app.include_router(auth_routes.router)
app.include_router(activity)
app.include_router(stats)
app.include_router(distribution)
app.include_router(trend)
app.include_router(search)
app.include_router(feedback)
app.include_router(privacy)
app.include_router(vision)

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
            'source': log.source
        }
        for log in activity_log
    ]
    return templates.TemplateResponse("index.html", {"request": request, "activity_log": logs_dict})


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "活动监控服务"}