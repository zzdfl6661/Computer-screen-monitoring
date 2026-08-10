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
    is_windows = platform.system() == 'Windows'
    feedback_result = {'type': None, 'activity_type': activity_type}
    
    if is_windows:
        try:
            root = tk.Tk()
            root.title("学习提醒")
            root.geometry("400x220")
            root.attributes('-topmost', True)
            
            tk.Label(root, text=message, wraplength=360, font=('Microsoft YaHei', 12)).pack(pady=20)
            
            frame = tk.Frame(root)
            frame.pack(pady=10)
            
            def on_false_positive():
                feedback_result['type'] = 'false_positive'
                root.destroy()
            
            def on_false_negative():
                feedback_result['type'] = 'false_negative'
                root.destroy()
            
            def on_ok():
                root.destroy()
            
            if activity_type:
                tk.Button(frame, text="误报", command=on_false_positive, 
                          width=12, bg='#fff3cd', fg='#856404').pack(side=tk.LEFT, padx=5)
                tk.Button(frame, text="漏报", command=on_false_negative, 
                          width=12, bg='#f8d7da', fg='#721c24').pack(side=tk.LEFT, padx=5)
            
            tk.Button(frame, text="确定", command=on_ok, width=12).pack(side=tk.LEFT, padx=5)
            
            root.mainloop()
        except Exception as e:
            logger.error(f"弹窗失败: {e}")
            logger.info(f"提示信息: {message}")
    else:
        logger.info(f"提示信息: {message}")
    
    return feedback_result
