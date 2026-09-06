"""客户端数据库规则缓存；网络不可用时自动保留上次规则并交给内置规则兜底。"""
import time
from .config import ConfigManager
from .http_client import session

_rules, _loaded_at = [], 0.0
_TTL_SECONDS = 300


def _url():
    return (ConfigManager().get("server_url") or "").replace("/check_activity", "/api/classification-rules")


def get_rules(force=False):
    global _rules, _loaded_at
    if not force and time.monotonic() - _loaded_at < _TTL_SECONDS:
        return _rules
    cfg = ConfigManager()
    headers = {"Authorization": f"Bearer {cfg.get('access_token')}"} if cfg.get("access_token") else {}
    try:
        response = session.get(_url(), params={"enabled": 1}, headers=headers, timeout=4)
        response.raise_for_status()
        _rules = response.json()
        _loaded_at = time.monotonic()
    except Exception:
        # 网络异常时不清空已下载规则，避免短暂断网造成分类抖动。
        _loaded_at = time.monotonic()
    return _rules


def match_rule(process="", title="", ocr_text="", domain=""):
    values = {"process": (process or "").lower(), "title": (title or "").lower(),
              "ocr": (ocr_text or "").lower(), "domain": (domain or "").lower()}
    for rule in get_rules():
        value, pattern = values.get(rule.get("signal_type"), ""), (rule.get("pattern") or "").lower().strip()
        if not value or not pattern:
            continue
        kind = rule.get("match_type")
        if kind == "exact": hit = value == pattern
        elif kind == "domain": hit = value == pattern or value.endswith("." + pattern)
        else: hit = pattern in value
        if hit:
            return rule
    return None
