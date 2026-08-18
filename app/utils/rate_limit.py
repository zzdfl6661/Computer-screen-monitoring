"""轻量内存限流：按设备令牌 + 路径做滑动窗口计数，防止刷接口。"""
import threading
import time

from fastapi import Depends, HTTPException, Request

from ..auth.dependencies import get_current_device
from ..auth.models import Device

_lock = threading.Lock()
_buckets = {}  # key -> (last_seen, [timestamps])


def _prune(now: float):
    """清理超过 2 个窗口未访问的 key，防止字典无限增长。"""
    stale = [k for k, (last, _) in _buckets.items() if now - last > 120]
    for k in stale:
        _buckets.pop(k, None)


def rate_limiter(limit: int, window_seconds: float = 60.0):
    """返回一个 FastAPI 依赖：同一设备在窗口内超过 limit 次则 429。"""
    def dependency(
        request: Request,
        device: Device = Depends(get_current_device),
    ):
        now = time.monotonic()
        key = f"{device.device_token}:{request.url.path}"
        with _lock:
            if len(_buckets) > 5000:
                _prune(now)
            entry = _buckets.setdefault(key, [now, []])
            entry[0] = now
            window_start = now - window_seconds
            entry[1] = [t for t in entry[1] if t > window_start]
            if len(entry[1]) >= limit:
                raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
            entry[1].append(now)
    return dependency
