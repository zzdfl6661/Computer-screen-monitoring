"""统一服务端业务时间。"""

import os
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.11 always has zoneinfo
    ZoneInfo = None


def _business_timezone():
    name = os.getenv("APP_TIMEZONE", "Asia/Shanghai")
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    return timezone(timedelta(hours=8))


BUSINESS_TZ = _business_timezone()


def now_local() -> datetime:
    """返回业务时区的当前时间（带 tzinfo，供日期计算使用）。"""
    return datetime.now(BUSINESS_TZ)


def now_local_iso() -> str:
    """返回业务时区的当前时间，精确到秒且不带时区后缀。"""
    return now_local().replace(tzinfo=None).isoformat(timespec="seconds")
