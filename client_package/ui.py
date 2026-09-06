import sys
import platform
import ctypes
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import logging
import threading

from .config import ConfigManager
from logger import setup_logger

logger = setup_logger('ui')
config_manager = ConfigManager()

_DPI_PREPARED = False


def _prepare_tk_dpi():
    """在创建 Tk 根窗口前启用 Windows Per-Monitor V2 高 DPI 感知。

    不设置 DPI awareness 时，Windows 会对 Tk 的位图和文字做整窗缩放，
    在 125%/150% 显示器上尤其容易出现“字糊、按钮糊”的观感。
    """
    global _DPI_PREPARED
    if _DPI_PREPARED or platform.system() != 'Windows':
        return
    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            shcore = ctypes.WinDLL('shcore', use_last_error=True)
            shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception as e:
            logger.debug(f"启用高 DPI 感知失败，使用系统默认缩放: {e}")
    _DPI_PREPARED = True


def show_config_window():
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


_popup_lock = threading.Lock()
_popup_showing = False


def _show_animated_popup(message, activity_type):
    """Tk 的 after 帧循环实现进场、呼吸和退场，独立线程不堵塞监控循环。"""
    global _popup_showing
    try:
        _prepare_tk_dpi()
        root = tk.Tk()
        root.title("学习小提醒")
        root.overrideredirect(True); root.resizable(False, False)
        root.configure(bg="#fff7ed"); root.attributes("-topmost", True); root.attributes("-alpha", 0.0)
        card = tk.Frame(root, bg="#fff7ed", highlightbackground="#fdba74", highlightthickness=2)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="🌟", bg="#fff7ed", fg="#fb923c", font=("Segoe UI Emoji", 32)).pack(pady=(14, 0))
        tk.Label(card, text="学习小提醒", bg="#fff7ed", fg="#9a3412",
                 font=("Microsoft YaHei UI", 16, "bold")).pack(pady=(0, 4))
        subtitle = "休息一下，再继续加油吧～" if activity_type == "entertainment" else "慢慢来，你做得很好～"
        tk.Label(card, text=subtitle, bg="#fff7ed", fg="#c2410c", font=("Microsoft YaHei UI", 10)).pack()
        tk.Label(card, text=message, bg="#fff7ed", fg="#431407", font=("Microsoft YaHei UI", 13),
                 wraplength=420, justify="center").pack(padx=28, pady=(9, 10))
        countdown = tk.Label(card, bg="#fed7aa", fg="#9a3412", font=("Microsoft YaHei UI", 9))
        countdown.pack(fill="x", padx=28)
        button = tk.Button(card, text="知道啦 ✨", bg="#fb923c", fg="white", activebackground="#f97316",
                           relief="flat", bd=0, cursor="hand2", font=("Microsoft YaHei UI", 11, "bold"),
                           padx=18, pady=7)
        button.pack(pady=14)
        root.update_idletasks()
        width, height = max(490, root.winfo_reqwidth()), max(245, root.winfo_reqheight())
        x, y = root.winfo_pointerx() - width // 2, root.winfo_pointery() - height // 2
        base_y = max(0, y); x = max(0, x)
        started, closing = __import__('time').monotonic(), [False]

        def finish():
            if closing[0]: return
            closing[0] = True
            def out(frame=0):
                alpha = max(0.0, 1 - frame / 22)
                try:
                    root.attributes("-alpha", alpha)
                    root.geometry(f"{width}x{height}+{x}+{base_y - int(frame * 2)}")
                    if frame < 22: root.after(60, lambda: out(frame + 1))
                    else: root.destroy()
                except tk.TclError: pass
            out()

        def animate(frame=0):
            if closing[0]: return
            elapsed = __import__('time').monotonic() - started
            if frame < 14:
                # 弹性滑入：由下方 32px 轻轻弹进来。
                progress = frame / 13
                root.attributes("-alpha", min(1.0, progress * 1.25))
                root.geometry(f"{width}x{height}+{x}+{base_y + int((1-progress)**2 * 32)}")
            else:
                import math
                root.geometry(f"{width}x{height}+{x}+{base_y + int(math.sin(elapsed * 3) * 3)}")
            left = max(0, int(12 - elapsed))
            countdown.config(text=f"  {left} 秒后会轻轻消失" + " ·" * (1 + frame % 3))
            if elapsed >= 12: finish(); return
            root.after(50, lambda: animate(frame + 1))

        button.config(command=finish)
        root.bind("<Return>", lambda _e: finish()); root.bind("<Escape>", lambda _e: finish())
        root.geometry(f"{width}x{height}+{x}+{base_y + 32}"); root.lift(); root.focus_force()
        root.after(0, animate); root.mainloop()
    except Exception as exc:
        logger.error(f"动态弹窗失败: {exc}")
    finally:
        with _popup_lock: _popup_showing = False


def show_popup(message, activity_type=None):
    """显示单例、非阻塞的可爱提醒；重复触发时保持当前提醒，避免窗口轰炸。"""
    global _popup_showing
    if platform.system() != "Windows":
        logger.info(f"提示信息: {message}")
        return {"type": None, "activity_type": activity_type}
    with _popup_lock:
        if _popup_showing:
            return {"type": None, "activity_type": activity_type, "status": "already_showing"}
        _popup_showing = True
    threading.Thread(target=_show_animated_popup, args=(message, activity_type), daemon=True,
                     name="friendly-reminder").start()
    return {"type": None, "activity_type": activity_type}
