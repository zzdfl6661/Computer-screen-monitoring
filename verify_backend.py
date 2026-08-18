"""验证 docker 化后端的健康与鉴权链路：/health -> 设备注册 -> 设备登录 -> /check_activity"""
import requests

BASE = "http://127.0.0.1:5000"


def main():
    # 1) 健康检查
    r = requests.get(f"{BASE}/health", timeout=5)
    print("[health]", r.status_code, r.json())

    # 2) 设备注册
    r = requests.post(f"{BASE}/auth/device/register",
                      json={"device_name": "LocalDevice", "device_type": "computer"}, timeout=5)
    print("[register]", r.status_code, r.json())
    device_token = r.json().get("device_token")
    assert device_token, "注册未返回 device_token"

    # 3) 设备登录拿 JWT
    r = requests.post(f"{BASE}/auth/device/login",
                      json={"device_token": device_token}, timeout=5)
    print("[login]", r.status_code, r.json())
    access_token = r.json().get("access_token")
    assert access_token, "登录未返回 access_token"

    # 4) check_activity
    hdr = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    r1 = requests.post(f"{BASE}/check_activity", json={"activity": "entertainment"}, headers=hdr, timeout=5)
    print("[check entertainment]", r1.status_code, r1.json())
    r2 = requests.post(f"{BASE}/check_activity", json={"activity": "study"}, headers=hdr, timeout=5)
    print("[check study]", r2.status_code, r2.json())

    # 4.1) idle 应为 neutral（不再是 ERROR）
    r3 = requests.post(f"{BASE}/check_activity", json={"activity": "idle"}, headers=hdr, timeout=5)
    print("[check idle]", r3.status_code, r3.json())

    # 4.2) unknown 是合法状态
    r4 = requests.post(f"{BASE}/check_activity", json={"activity": "unknown"}, headers=hdr, timeout=5)
    print("[check unknown]", r4.status_code, r4.json())

    # 4.3) 非法枚举应 422（不再是 200+error）
    r5 = requests.post(f"{BASE}/check_activity", json={"activity": "garbage"}, headers=hdr, timeout=5)
    print("[check garbage]", r5.status_code, "(期望 422)")

    # 4.4) 带判定依据上报
    r6 = requests.post(f"{BASE}/check_activity",
                       json={"activity": "study", "confidence": 0.87,
                             "decision_source": "process", "reason": "study_proc:code.exe"},
                       headers=hdr, timeout=5)
    print("[check study+meta]", r6.status_code, r6.json())

    ok = (r1.json().get("status") == "warning"
          and r2.json().get("status") == "good"
          and r3.json().get("status") == "neutral"
          and r4.json().get("status") == "unknown"
          and r5.status_code == 422
          and r6.status_code == 200)
    print("RESULT:", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
