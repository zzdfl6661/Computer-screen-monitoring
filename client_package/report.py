import requests

from .config import ConfigManager
from .http_client import session
from database import DatabaseManager
from logger import setup_logger

logger = setup_logger('report')
config_manager = ConfigManager()
local_db = DatabaseManager('client_activity_logs.db')


def register_device():
    register_url = config_manager.get('server_url').replace('/check_activity', '/auth/device/register')
    try:
        response = session.post(register_url, json={"device_name": "LocalDevice", "device_type": "computer"}, timeout=5)
        if response.status_code == 200:
            result = response.json()
            device_token = result.get('device_token')
            if device_token:
                config_manager.set('device_token', device_token)
                logger.info("设备注册成功，设备令牌已安全保存")
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


def _response_detail(response):
    """安全读取 FastAPI 错误详情；非 JSON 响应则返回空字符串。"""
    try:
        return str(response.json().get("detail", ""))
    except (ValueError, AttributeError):
        return ""


def login_device(_retried_registration=False):
    device_token = config_manager.get('device_token')
    if not device_token:
        logger.info("未配置设备令牌，尝试自动注册设备...")
        device_token = register_device()
        if not device_token:
            logger.warning("设备注册失败，使用本地模式")
            return None

    login_url = config_manager.get('server_url').replace('/check_activity', '/auth/device/login')
    try:
        response = session.post(login_url, json={"device_token": device_token}, timeout=5)
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
        elif (response.status_code == 401
              and _response_detail(response) == "设备令牌无效"
              and not _retried_registration):
            # 切换到新的 Docker/PostgreSQL 数据库，或服务端数据卷被重建时，
            # 本地保存的设备令牌不再存在。自动注册一次即可恢复上报。
            logger.warning("保存的设备令牌不属于当前服务端，正在自动重新注册设备...")
            config_manager.set('device_token', '')
            config_manager.set('access_token', '')
            if register_device():
                return login_device(_retried_registration=True)
            return None
        else:
            logger.error(f"设备登录失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"设备登录请求异常: {e}")
        return None


def _local_fallback(activity_type):
    """服务端不可用时的本地兜底：写本地库，并明确标记为尚未同步。"""
    if activity_type == "entertainment":
        result = {"message": "你正在娱乐，请切换到学习！", "status": "warning"}
    elif activity_type == "idle":
        result = {"message": "当前空闲，无活动", "status": "neutral"}
    elif activity_type == "unknown":
        result = {"message": "无法判定当前活动", "status": "unknown"}
    else:
        result = {"message": "继续保持学习状态！", "status": "good"}
    result["delivery"] = "local_fallback"
    local_db.add_log(activity=activity_type, message=result.get('message'), source='local')
    logger.warning("服务端上报未成功：本次结果仅写入本地数据库，尚未同步")
    return result


def send_to_server(activity_type, confidence=None, decision_source=None, reason=None,
                   process=None, title=None, subject=None):
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
    if subject:
        payload["subject"] = subject

    # 有限次数重试（401 时重新登录后最多再试 1 次），避免无限递归
    for attempt in range(2):
        try:
            response = session.post(url, json=payload, headers=headers, timeout=5)
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {e}")
            return _local_fallback(activity_type)

        if response.status_code == 200:
            logger.info(f"服务器响应: {response.text}")
            result = response.json()
            result["delivery"] = "server"
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
