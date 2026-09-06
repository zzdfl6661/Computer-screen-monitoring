"""独立截图采样任务：不依赖 unknown，不阻塞监控和提醒窗口。"""
import base64
import threading

import cv2

from .capture import capture_screen
from .config import ConfigManager
from .http_client import session

_context_lock = threading.Lock()
_context = {"activity": None, "confidence": None, "process": None, "window_title": None}


def update_capture_context(**values):
    with _context_lock:
        _context.update({k: v for k, v in values.items() if k in _context})


def _payload():
    image = capture_screen()
    if image is None:
        return None
    h, w = image.shape[:2]
    scale = min(1.0, 768 / max(h, w))
    if scale < 1:
        image = cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))))
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        return None
    with _context_lock:
        metadata = dict(_context)
    metadata["image"] = base64.b64encode(encoded.tobytes()).decode("ascii")
    return metadata


class ScreenshotScheduler:
    def __init__(self, interval_seconds=60):
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, name="screenshot-sampler", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        # 启动即采样一次，之后严格以一整分钟间隔运行。
        while not self.stop_event.is_set():
            cfg = ConfigManager()
            token = cfg.get("access_token")
            if not token:
                try:
                    from .report import login_device
                    token = login_device()
                except Exception:
                    token = None
            payload = _payload()
            if payload and token:
                url = (cfg.get("server_url") or "").replace("/check_activity", "/api/screenshots")
                try:
                    session.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=12)
                except Exception:
                    pass  # 下一分钟重试；绝不影响主监控循环
            self.stop_event.wait(self.interval_seconds)
