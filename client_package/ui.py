import sys
import os
import json
import platform
import ctypes
import subprocess
import tkinter as tk
from tkinter import messagebox
import threading
import logging

from .config import ConfigManager
from logger import setup_logger

logger = setup_logger('ui')
config_manager = ConfigManager()

_DPI_PREPARED = False


def _prepare_tk_dpi():
    """在创建 Tk 根窗口前启用 Windows Per-Monitor V2 高 DPI 感知。"""
    global _DPI_PREPARED
    if _DPI_PREPARED or platform.system() != 'Windows':
        return
    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            shcore = ctypes.WinDLL('shcore', use_last_error=True)
            shcore.SetProcessDpiAwareness(2)
        except Exception as e:
            logger.debug(f"启用高 DPI 感知失败，使用系统默认缩放: {e}")
    _DPI_PREPARED = True


def show_config_window():
    """配置窗口（用户主动打开，在主线程运行，没问题）。"""
    _prepare_tk_dpi()
    root = tk.Tk()
    root.title("学习辅助监控系统 - 配置")
    root.geometry("400x300")

    tk.Label(root, text="检查间隔（秒）：").pack(pady=5)
    interval_var = tk.StringVar(value=str(config_manager.get('check_interval')))
    tk.Entry(root, textvariable=interval_var).pack(pady=5)

    tk.Label(root, text="服务端URL：").pack(pady=5)
    server_url_var = tk.StringVar(value=str(config_manager.get('server_url')))
    tk.Entry(root, textvariable=server_url_var, width=40).pack(pady=5)

    def save_config():
        try:
            new_interval = int(interval_var.get())
            if new_interval > 0:
                config_manager.set('check_interval', new_interval)
                config_manager.set('server_url', server_url_var.get())
                messagebox.showinfo("成功", "配置已保存")
                root.destroy()
            else:
                messagebox.showerror("错误", "检查间隔必须大于0")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")

    tk.Button(root, text="保存", command=save_config).pack(pady=20)
    root.mainloop()


# ===== 弹窗（独立子进程，避免 tkinter 子线程死锁） =====

_popup_lock = threading.Lock()
_popup_process = None


def show_popup(message, activity_type=None):
    """用独立子进程弹窗，完全隔离，tkinter 崩了也不影响主监控循环。"""
    global _popup_process

    if platform.system() != "Windows":
        logger.info(f"提示信息: {message}")
        return {"type": None, "activity_type": activity_type}

    with _popup_lock:
        # 上一个弹窗还在显示就不重复弹
        if _popup_process and _popup_process.poll() is None:
            return {"type": None, "activity_type": activity_type, "status": "already_showing"}

        try:
            payload = json.dumps({
                "message": message,
                "activity_type": activity_type or "entertainment"
            })
            # popup_worker.py 在项目根目录
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "popup_worker.py"
            )
            # 优先用 pythonw.exe 避免弹黑色控制台窗口
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable

            _popup_process = subprocess.Popen(
                [python_exe, script_path, payload],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True
            )
            logger.info(f"弹窗子进程已启动: pid={_popup_process.pid}")
        except Exception as e:
            logger.error(f"弹窗子进程启动失败: {e}", exc_info=True)

    return {"type": None, "activity_type": activity_type}
