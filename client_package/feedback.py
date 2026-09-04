import requests
import hashlib
import logging

from .config import ConfigManager
from .capture import capture_screen
from .http_client import session
from logger import setup_logger

logger = setup_logger('feedback')
config_manager = ConfigManager()


def compute_image_hash(image):
    try:
        image_bytes = image.tobytes()
        hash_value = hashlib.sha256(image_bytes).hexdigest()
        return hash_value
    except Exception as e:
        logger.error(f"计算图像哈希失败: {e}")
        return None


def send_feedback(detected_activity, actual_activity, feedback_type):
    server_url = config_manager.get('server_url')
    access_token = config_manager.get('access_token')
    
    feedback_url = server_url.replace('/check_activity', '/api/feedback')
    
    screenshot_hash = None
    try:
        image = capture_screen()
        if image is not None:
            screenshot_hash = compute_image_hash(image)
            logger.info(f"截图哈希已生成: {screenshot_hash[:16]}...")
    except Exception as e:
        logger.warning(f"捕获截图失败: {e}")
    
    if not access_token:
        logger.warning("未获取到访问令牌，跳过反馈上传")
        return {"message": "未登录，无法提交反馈", "status": "error"}
    
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {
        "detected_activity": detected_activity,
        "actual_activity": actual_activity,
        "feedback_type": feedback_type,
        "screenshot_hash": screenshot_hash
    }
    
    try:
        response = session.post(feedback_url, json=data, headers=headers, timeout=5)
        if response.status_code == 200:
            logger.info(f"反馈提交成功: {response.text}")
            return response.json()
        elif response.status_code == 401:
            logger.warning("访问令牌已过期")
            config_manager.set('access_token', '')
            return {"message": "令牌过期", "status": "error"}
        else:
            logger.warning(f"反馈提交失败，状态码: {response.status_code}")
            return {"message": "反馈提交失败", "status": "error"}
    except requests.exceptions.RequestException as e:
        logger.error(f"反馈请求异常: {e}")
        return {"message": "网络异常", "status": "error"}
