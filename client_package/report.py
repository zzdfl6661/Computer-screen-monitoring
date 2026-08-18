import requests
import logging

from .config import ConfigManager
from database import DatabaseManager
from logger import setup_logger

logger = setup_logger('report')
config_manager = ConfigManager()
local_db = DatabaseManager('client_activity_logs.db')


def register_device():
    register_url = config_manager.get('server_url').replace('/check_activity', '/auth/device/register')
    try:
        response = requests.post(register_url, json={"device_name": "LocalDevice", "device_type": "computer"}, timeout=5)
        if response.status_code == 200:
            result = response.json()
            device_token = result.get('device_token')
            if device_token:
                config_manager.set('device_token', device_token)
                logger.info(f"设备注册成功，设备令牌: {device_token}")
                return device_token
            else:
                logger.error("设备注册成功，但未获取到设备令牌")
                return None
        else:
            logger.error(f"设备注册失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"设备注册请求异常: {e}")
        return None


def login_device():
    device_token = config_manager.get('device_token')
    if not device_token:
        logger.info("未配置设备令牌，尝试自动注册设备...")
        device_token = register_device()
        if not device_token:
            logger.warning("设备注册失败，使用本地模式")
            return None
    
    login_url = config_manager.get('server_url').replace('/check_activity', '/auth/device/login')
    try:
        response = requests.post(login_url, json={"device_token": device_token}, timeout=5)
        if response.status_code == 200:
            result = response.json()
            access_token = result.get('access_token')
            if access_token:
                config_manager.set('access_token', access_token)
                logger.info("设备登录成功，获取到访问令牌")
                return access_token
            else:
                logger.error("设备登录成功，但未获取到访问令牌")
                return None
        else:
            logger.error(f"设备登录失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"设备登录请求异常: {e}")
        return None


def _local_fallback(activity_type):
    """服务端不可用时的本地兜底：写本地库并返回本地提示。"""
    if activity_type == "entertainment":
        result = {"message": "你正在娱乐，请切换到学习！", "status": "warning"}
    elif activity_type == "idle":
        result = {"message": "当前空闲，无活动", "status": "neutral"}
    elif activity_type == "unknown":
        result = {"message": "无法判定当前活动", "status": "unknown"}
    else:
        result = {"message": "继续保持学习状态！", "status": "good"}
    local_db.add_log(activity=activity_type, message=result.get('message'), source='local')
    return result


def send_to_server(activity_type, confidence=None, decision_source=None, reason=None,
                   process=None, title=None):
    url = config_manager.get('server_url')
    access_token = config_manager.get('access_token')

    if not access_token:
        logger.info("尝试自动登录设备...")
        access_token = login_device()
        if not access_token:
            logger.error("无法获取访问令牌，使用本地模式")
            return _local_fallback(activity_type)

    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"activity": activity_type}
    if confidence is not None:
        payload["confidence"] = confidence
    if decision_source:
        payload["decision_source"] = decision_source
    if reason:
        payload["reason"] = reason
    if process:
        payload["process"] = process
    if title:
        payload["title"] = title

    # 有限次数重试（401 时重新登录后最多再试 1 次），避免无限递归
    for attempt in range(2):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5)
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {e}")
            return _local_fallback(activity_type)

        if response.status_code == 200:
            logger.info(f"服务器响应: {response.text}")
            result = response.json()
            local_db.add_log(activity=activity_type, message=result.get('message'), source='server')
            return result
        elif response.status_code == 401 and attempt == 0:
            logger.warning("访问令牌已过期，重新登录后重试...")
            config_manager.set('access_token', '')
            access_token = login_device()
            if not access_token:
                break
            headers = {"Authorization": f"Bearer {access_token}"}
            continue
        elif response.status_code == 422:
            logger.warning(f"服务端拒绝该活动值: {activity_type} (422)")
            return _local_fallback(activity_type)
        else:
            logger.warning(f"请求失败，状态码: {response.status_code}")
            return _local_fallback(activity_type)

    logger.error("重试后仍无法获取访问令牌，使用本地模式")
    return _local_fallback(activity_type)