"""
视觉兜底分类（pluggable）。

仅在融合“不确定”时触发。两种后端：
  - server（默认，推荐）：把降采样截图 POST 到服务端 /analyze_image，
    由服务端 OCR+规则判级（图片入库）；截图不落本地、无模型下载。
  - ollama：端侧本地视觉模型（moondream / llava / qwen2-vl 等），
    需本机安装 Ollama；不可用时优雅返回 (None, 0.0)。

接口：VLMClassifier().classify(image_bgr) -> (label|None, confidence)
"""
import base64
import json
import logging
import urllib.error
import urllib.request

try:
    from .config import ConfigManager
except Exception:
    from config import ConfigManager

logger = logging.getLogger(__name__)

VLM_PROMPT = (
    "判断这张电脑截图里的人是在学习还是娱乐？"
    "只回答 study / entertainment / idle，并给一句简短中文理由。"
)

_TIMEOUT = 15
_DOWNSAMPLE = 768  # 服务端 OCR 对小字/深色界面更友好；仍远小于原图，控制带宽


class VLMClassifier:
    def __init__(self):
        self.cfg = ConfigManager()
        self.endpoint = self.cfg.get('vlm_endpoint') or 'http://localhost:11434'
        self.model = self.cfg.get('vlm_model') or 'moondream'
        self.backend = self.cfg.get('vlm_backend') or 'ollama'
        self.server_url = self.cfg.get('server_url') or 'http://127.0.0.1:5000/check_activity'

    def classify(self, image):
        try:
            if self.cfg.get('enable_server_vision'):
                return self._classify_server(image)
            if self.backend == 'ollama':
                return self._classify_ollama(image)
            logger.warning(f"未知的 vlm_backend: {self.backend}")
            return (None, 0.0)
        except urllib.error.URLError as e:
            # 最常见的根因：后端 Docker 容器没启动/被停止，客户端发 /analyze_image 连接被拒
            logger.warning(
                f"⚠️ 视觉兜底无法连接后端 {self.server_url}（{e.reason}）。"
                f"请确认后端已启动：cd D:\\LearningApp && docker compose up -d"
            )
            return (None, 0.0)
        except Exception as e:
            logger.warning(f"视觉兜底不可用，跳过: {e}")
            return (None, 0.0)

    # ------------------------------------------------------------------
    def _encode_jpg_b64(self, image):
        import cv2
        h, w = image.shape[:2]
        scale = min(1.0, _DOWNSAMPLE / max(h, w))
        small = cv2.resize(image, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode('.jpg', small, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return None
        return base64.b64encode(buf).decode('utf-8')

    def _ensure_access_token(self):
        token = self.cfg.get('access_token')
        if token:
            return token
        try:
            from .report import login_device
            return login_device()
        except Exception as e:
            logger.warning(f"获取访问令牌失败: {e}")
            return None

    def _context(self):
        try:
            from .classify import get_active_window_title, _get_foreground_process
            return get_active_window_title(), _get_foreground_process()
        except Exception:
            return None, None

    def _classify_server(self, image):
        """上传降采样截图到服务端 /analyze_image，由服务端 OCR+规则判级并入库。"""
        b64 = self._encode_jpg_b64(image)
        if not b64:
            return (None, 0.0)

        token = self._ensure_access_token()
        if not token:
            return (None, 0.0)

        url = self.server_url.replace('/check_activity', '/analyze_image')
        title, proc = self._context()
        payload = {"image": b64, "window_title": title, "process": proc}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {token}'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        activity = data.get('activity')
        confidence = float(data.get('confidence') or 0.0)
        if activity in ('study', 'entertainment', 'idle', 'unknown'):
            return (activity, confidence)
        return (None, 0.0)

    # ------------------------------------------------------------------
    def _classify_ollama(self, image):
        import cv2

        b64 = self._encode_jpg_b64(image)
        if not b64:
            return (None, 0.0)

        payload = {
            "model": self.model,
            "prompt": VLM_PROMPT,
            "images": [b64],
            "stream": False,
        }
        req = urllib.request.Request(
            self.endpoint.rstrip('/') + '/api/generate',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        text = (data.get('response', '') or '').lower()

        if 'study' in text and 'entertain' not in text:
            label = 'study'
        elif 'entertain' in text:
            label = 'entertainment'
        else:
            label = 'idle'
        conf = 0.70 if label != 'idle' else 0.0
        return (label, conf)
