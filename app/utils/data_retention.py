from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import ActivityLog, Feedback, ImageAnalysis, DataRetentionPolicy, Screenshot
from logger import setup_logger
import threading
import time

logger = setup_logger('data_retention')

DEFAULT_RETENTION_DAYS = 30
SCREENSHOT_RETENTION_DAYS = 7
CLEANUP_INTERVAL_HOURS = 24

def get_retention_days(db: Session) -> int:
    policy = db.query(DataRetentionPolicy).first()
    if policy:
        return policy.retention_days
    return DEFAULT_RETENTION_DAYS

def set_retention_days(db: Session, days: int) -> DataRetentionPolicy:
    policy = db.query(DataRetentionPolicy).first()
    if policy:
        policy.retention_days = days
        policy.updated_at = datetime.utcnow()
    else:
        policy = DataRetentionPolicy(
            policy_name='default',
            retention_days=days,
            description='默认数据保留策略'
        )
        db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy

def cleanup_old_data(db: Session, retention_days: int = None):
    if retention_days is None:
        retention_days = get_retention_days(db)
    
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    activity_deleted = db.query(ActivityLog).filter(
        ActivityLog.created_at < cutoff_date
    ).delete(synchronize_session=False)
    
    feedback_deleted = db.query(Feedback).filter(
        Feedback.created_at < cutoff_date
    ).delete(synchronize_session=False)

    # 服务端视觉分析记录（含入库截图）同样按保留期清理，避免截图无限增长
    image_deleted = db.query(ImageAnalysis).filter(
        ImageAnalysis.created_at < cutoff_date
    ).delete(synchronize_session=False)
    # 固定频率截图数量更大，采用独立的 7 天默认保留期。
    screenshot_cutoff = datetime.utcnow() - timedelta(days=SCREENSHOT_RETENTION_DAYS)
    screenshot_deleted = db.query(Screenshot).filter(
        Screenshot.created_at < screenshot_cutoff
    ).delete(synchronize_session=False)
    
    db.commit()
    
    if activity_deleted > 0 or feedback_deleted > 0 or image_deleted > 0 or screenshot_deleted > 0:
        logger.info(f"数据清理完成: 活动日志 {activity_deleted} 条, 反馈 {feedback_deleted} 条, "
                    f"视觉分析 {image_deleted} 条, 截图 {screenshot_deleted} 条")
    else:
        logger.debug(f"数据清理: 无需删除, 保留期限 {retention_days} 天")
    
    return {
        'activity_logs_deleted': activity_deleted,
        'feedback_deleted': feedback_deleted,
        'image_analyses_deleted': image_deleted,
        'screenshots_deleted': screenshot_deleted,
        'retention_days': retention_days
    }

def cleanup_log_files(retention_days: int = DEFAULT_RETENTION_DAYS):
    import os
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        return
    
    cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
    
    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        if os.path.isfile(filepath):
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff_time:
                os.remove(filepath)
                logger.info(f"删除过期日志文件: {filepath}")

def start_auto_cleanup(db_session_maker, interval_hours: int = CLEANUP_INTERVAL_HOURS):
    def cleanup_loop():
        while True:
            try:
                db = db_session_maker()
                try:
                    cleanup_old_data(db)
                finally:
                    db.close()
                cleanup_log_files()
            except Exception as e:
                logger.error(f"自动清理任务执行失败: {e}")
            
            time.sleep(interval_hours * 60 * 60)
    
    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    logger.info(f"自动数据清理任务已启动，每隔 {interval_hours} 小时执行一次")
    return thread
