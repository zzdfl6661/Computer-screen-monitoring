"""验证服务端视觉分析链路：/analyze_image 的 OCR + 规则判级（合成带文字图片）。"""
import base64
import io
import requests

BASE = "http://127.0.0.1:5000"


def make_image_b64(text: str) -> str:
    import cv2
    import numpy as np
    img = np.full((300, 1000, 3), 255, dtype=np.uint8)
    cv2.putText(img, text, (30, 170), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 3)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return base64.b64encode(buf).decode("utf-8")


def main():
    # 1) 设备注册 + 登录
    r = requests.post(f"{BASE}/auth/device/register",
                      json={"device_name": "VisionTest", "device_type": "computer"}, timeout=5)
    device_token = r.json()["device_token"]
    r = requests.post(f"{BASE}/auth/device/login",
                      json={"device_token": device_token}, timeout=5)
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}

    # 2) 学习场景：Coursera
    r = requests.post(f"{BASE}/analyze_image",
                      json={"image": make_image_b64("Coursera Machine Learning"),
                            "window_title": "Coursera 机器学习", "process": "chrome.exe"},
                      headers=hdr, timeout=30)
    print("[study img]", r.status_code, r.json())

    # 3) 娱乐场景：League of Legends
    r = requests.post(f"{BASE}/analyze_image",
                      json={"image": make_image_b64("League of Legends"),
                            "window_title": "英雄联盟", "process": "leagueclient.exe"},
                      headers=hdr, timeout=30)
    print("[ent img]", r.status_code, r.json())

    # 4) 无鉴权应 401
    r = requests.post(f"{BASE}/analyze_image",
                      json={"image": make_image_b64("hello")}, timeout=5)
    print("[no auth]", r.status_code, "(期望 401)")


if __name__ == "__main__":
    main()
