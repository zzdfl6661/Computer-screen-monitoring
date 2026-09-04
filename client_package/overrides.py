"""
家长标注覆盖规则拉取与匹配（标注飞轮客户端侧）。

家长在看板上对 unknown 样本一键标注 → 服务端生成覆盖规则 → 本模块定期拉取缓存，
在分类时权威覆盖规则判定（孩子自装应用等长尾是全局关键词表追不上的）。
接口：get_override(process, title) -> (activity, confidence) | None
网络不可用/未配置 → 返回 None，不影响主流程。
"""
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

try:
    from .config import ConfigManager
except Exception:
    from config import ConfigManager

try:
    from .http_client import urlopen
except Exception:
    from http_client import urlopen

logger = logging.getLogger(__name__)

_TIMEOUT = 5
_REFRESH_SECONDS = 600  # 每 10 分钟拉一次覆盖规则

_cache = None
_cache_ts = 0.0


def _ensure_token(cfg):
    token = cfg.get('access_token')
    if token:
        return token
    try:
        from .report import login_device
        return login_device()
    except Exception as e:
        logger.warning(f"覆盖规则获取令牌失败: {e}")
        return None


def _fetch_overrides():
    """从服务端拉取活跃覆盖规则，返回 [{process,title,activity}, ...]；失败返回 []。"""
    cfg = ConfigManager()
    token = _ensure_token(cfg)
    if not token:
        return []
    base = cfg.get('server_url') or ''
    url = base.replace('/check_activity', '/api/overrides')
    device_token = cfg.get('device_token')
    if device_token:
        url += '?' + urlencode({'device': device_token})
    req = urllib.request.Request(
        url, headers={'Authorization': f'Bearer {token}'}, method='GET')
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            import json
            rows = json.loads(resp.read().decode('utf-8'))
        rules = []
        for r in rows:
            rules.append({
                'process': (r.get('process') or '').lower(),
                'title': (r.get('title') or '').lower(),
                'activity': r.get('activity'),
                'hit_count': r.get('hit_count') or 1,
            })
        logger.info(f"已拉取 {len(rules)} 条家长覆盖规则")
        return rules
    except urllib.error.URLError as e:
        logger.debug(f"覆盖规则拉取失败（网络不可用）: {e}")
        return []
    except Exception as e:
        logger.debug(f"覆盖规则拉取失败: {e}")
        return []


def _ensure_cache():
    global _cache, _cache_ts
    now = time.time()
    if _cache is None or now - _cache_ts >= _REFRESH_SECONDS:
        _cache = _fetch_overrides()
        _cache_ts = now
    return _cache


def get_override(process, title):
    """按 (进程, 标题) 匹配家长覆盖规则。

    规则匹配：进程精确（小写），标题子串（若规则带标题）；匹配到返回
    (activity, 基于标注次数的置信度)；否则 None。
    """
    rules = _ensure_cache()
    if not rules:
        return None
    proc = (process or '').lower()
    tle = (title or '').lower()
    best = None
    for r in rules:
        if r.get('process') and r['process'] != proc:
            continue
        if r.get('title') and r['title'] not in tle:
            continue
        # 命中：标注次数越多越可信（0.80 + 0.05/次，上限 0.95）
        conf = min(0.80 + 0.05 * (r.get('hit_count') or 1), 0.95)
        if best is None or conf > best[1]:
            best = (r['activity'], conf)
    return best
