import sys
import platform
import tkinter as tk
from tkinter import messagebox, simpledialog
import logging

from .config import ConfigManager
from logger import setup_logger

logger = setup_logger('ui')
config_manager = ConfigManager()


def show_config_window():
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
            root = tk.Tk()
            root.title("学习提醒")
            root.geometry("360x160")
            root.attributes('-topmost', True)

            tk.Label(root, text=message, wraplength=320, font=('Microsoft YaHei', 12)).pack(pady=24)

            def on_ok():
                root.destroy()

            tk.Button(root, text="确定", command=on_ok, width=12).pack(pady=10)

            root.mainloop()
        except Exception as e:
            logger.error(f"弹窗失败: {e}")
            logger.info(f"提示信息: {message}")
    else:
        logger.info(f"提示信息: {message}")

    return feedback_result
