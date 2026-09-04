import sys
import platform
import ctypes
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import logging

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


def show_popup(message, activity_type=None):
    """弹出学习提醒弹窗。

    设计原则：青少年/小孩不会给出准确的"误报/漏报"反馈（甚至会报复性乱选），
    因此弹窗只保留"确定"按钮——确认看到了就行，不再让孩子做主观标注。
    反馈数据仍然走 `feedback` 表（POST 接口保留），供家长端或程序化使用。
    """
    is_windows = platform.system() == 'Windows'
    feedback_result = {'type': None, 'activity_type': activity_type}

    if is_windows:
        try:
            _prepare_tk_dpi()
            root = tk.Tk()
            root.title("学习提醒")
            root.overrideredirect(True)
            root.resizable(False, False)
            root.configure(bg="#0f172a")
            root.attributes('-topmost', True)

            # 自绘卡片：比默认 Tk messagebox 更清晰，也不受系统主题的低对比度影响。
            card = tk.Frame(
                root,
                bg="#0f172a",
                highlightbackground="#334155",
                highlightcolor="#334155",
                highlightthickness=1,
                bd=0,
            )
            card.pack(fill="both", expand=True)

            header = tk.Frame(card, bg="#1e293b", height=68)
            header.pack(fill="x")
            header.pack_propagate(False)

            title_font = ("Microsoft YaHei UI", 16, "bold")
            body_font = ("Microsoft YaHei UI", 15)
            small_font = ("Microsoft YaHei UI", 10)

            tk.Label(
                header,
                text="⚠",
                bg="#1e293b",
                fg="#fbbf24",
                font=("Segoe UI Symbol", 25, "bold"),
                width=3,
            ).pack(side="left", padx=(18, 0))
            tk.Label(
                header,
                text="学习提醒",
                bg="#1e293b",
                fg="#f8fafc",
                font=title_font,
                anchor="w",
            ).pack(side="left", padx=4)

            body = tk.Frame(card, bg="#0f172a")
            body.pack(fill="both", expand=True, padx=26, pady=(20, 8))
            subtitle = "检测到连续娱乐活动" if activity_type == "entertainment" else "请确认当前状态"
            tk.Label(
                body,
                text=subtitle,
                bg="#0f172a",
                fg="#94a3b8",
                font=small_font,
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                body,
                text=message,
                bg="#0f172a",
                fg="#f8fafc",
                font=body_font,
                justify="left",
                anchor="w",
                wraplength=455,
            ).pack(fill="x", pady=(7, 0))

            footer = tk.Frame(card, bg="#0f172a")
            footer.pack(fill="x", padx=26, pady=(4, 20))

            def on_ok():
                root.destroy()

            button = tk.Button(
                footer,
                text="知道了",
                command=on_ok,
                bg="#2563eb",
                fg="#ffffff",
                activebackground="#1d4ed8",
                activeforeground="#ffffff",
                disabledforeground="#ffffff",
                relief="flat",
                bd=0,
                cursor="hand2",
                font=("Microsoft YaHei UI", 12, "bold"),
                padx=22,
                pady=8,
            )
            button.pack(side="right")
            root.bind("<Return>", lambda _event: on_ok())
            root.bind("<Escape>", lambda _event: on_ok())

            # 先计算真实尺寸，再在鼠标所在屏幕居中，避免多显示器上弹到错误位置。
            root.update_idletasks()
            width = max(520, root.winfo_reqwidth())
            height = max(245, root.winfo_reqheight())
            px, py = root.winfo_pointerx(), root.winfo_pointery()
            root.geometry(f"{width}x{height}+{max(0, px - width // 2)}+{max(0, py - height // 2)}")
            root.lift()
            root.focus_force()
            # 提醒不应永久阻塞监控循环；用户未操作时 15 秒自动收起。
            root.after(15000, lambda: root.winfo_exists() and root.destroy())

            root.mainloop()
        except Exception as e:
            logger.error(f"弹窗失败: {e}")
            logger.info(f"提示信息: {message}")
    else:
        logger.info(f"提示信息: {message}")

    return feedback_result
