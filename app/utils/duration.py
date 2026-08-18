"""把“5 秒一次的采样次数”换算成近似时长（分钟）。

原理：按时间升序的日志序列中，连续且活动相同的样本视为同一个状态区间，
用相邻样本的时间戳差值累加该区间的秒数；相邻样本间隔超过 max_gap 视为
状态中断（关机/停客户端/周期断层），不计入时长。返回值四舍五入到 0.1 分钟。
"""
from datetime import datetime
from typing import Iterable, Tuple

# 相邻样本超过该秒数视为中断（默认 5 分钟）
MAX_GAP_SECONDS = 300


def compute_minutes(rows: Iterable[Tuple[str, str]], max_gap: float = MAX_GAP_SECONDS) -> dict:
    """rows: [(timestamp_iso, activity)]，按时间升序。返回 {activity: minutes}。"""
    totals: dict = {}
    prev_ts = None
    prev_act = None
    for ts_str, act in rows:
        try:
            ts = datetime.fromisoformat(ts_str)
        except (TypeError, ValueError):
            continue
        if prev_ts is not None and act == prev_act:
            delta = (ts - prev_ts).total_seconds()
            if 0 < delta <= max_gap:
                totals[act] = totals.get(act, 0.0) + delta
        prev_ts, prev_act = ts, act
    return {k: round(v / 60.0, 1) for k, v in totals.items()}
