"""停止正在运行的 main.py 客户端进程（开发辅助脚本）。"""
import psutil

killed = False
for p in psutil.process_iter(["pid", "name", "cmdline"]):
    try:
        cmd = " ".join(p.info["cmdline"] or [])
        name = (p.info["name"] or "").lower()
        if "python" in name and "main.py" in cmd:
            p.kill()
            killed = True
            print("已停止", p.info["pid"], cmd[:120])
    except Exception:
        pass
if not killed:
    print("没有发现 main.py 进程在跑")
