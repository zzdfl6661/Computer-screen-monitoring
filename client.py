import pyautogui
import requests
import time
import numpy as np
import cv2
import pytesseract
from PIL import Image
import tkinter as tk
from tkinter import messagebox, simpledialog
from database import DatabaseManager, ConfigManager
import psutil
import platform
from collections import deque

# 设置Tesseract路径
try:
    pytesseract.pytesseract.tesseract_cmd = r"D:\Program Files\Tesseract-OCR\tesseract.exe"
except:
    pass

# 初始化配置管理器
config_manager = ConfigManager()

# 初始化本地数据库
local_db = DatabaseManager('client_activity_logs.db')

# 显示配置窗口
def show_config_window():
    root = tk.Tk()
    root.title("学习辅助监控系统 - 配置")
    root.geometry("400x300")
    
    # 检查间隔设置
    tk.Label(root, text="检查间隔（秒）：").pack(pady=5)
    interval_var = tk.StringVar(value=str(config_manager.get('check_interval')))
    tk.Entry(root, textvariable=interval_var).pack(pady=5)
    
    # 服务器URL设置
    tk.Label(root, text="服务端URL：").pack(pady=5)
    server_url_var = tk.StringVar(value=config_manager.get('server_url'))
    tk.Entry(root, textvariable=server_url_var, width=40).pack(pady=5)
    
    # 保存按钮
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


# 屏幕截图
def capture_screen():
    screenshot = pyautogui.screenshot()
    img = np.array(screenshot)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


# 图像分析：判断是否在娱乐
def analyze_image(img):
    text = pytesseract.image_to_string(img)
    lower_text = text.lower()
    
    entertainment_keywords = config_manager.get('entertainment_keywords')
    study_keywords = config_manager.get('study_keywords')
    
    # 检查娱乐关键词
    for keyword in entertainment_keywords:
        if keyword in lower_text:
            return "entertainment"
    
    # 检查学习关键词
    for keyword in study_keywords:
        if keyword in lower_text:
            return "study"
    
    # 默认返回学习状态，避免误判
    return "study"


# 向服务端发送请求
def send_to_server(activity_type):
    url = config_manager.get('server_url')
    try:
        response = requests.post(url, json={"activity": activity_type}, timeout=5)
        if response.status_code == 200:
            print("服务器响应:", response.text)
        else:
            print("请求失败，状态码:", response.status_code)

        result = response.json()
        # 记录到本地数据库
        local_db.add_log(activity=activity_type, message=result.get('message'), source='server')
        return result
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        # 服务端不可用时，本地处理
        if activity_type == "entertainment":
            result = {"message": "你正在娱乐，请切换到学习！", "status": "warning"}
        else:
            result = {"message": "继续保持学习状态！", "status": "good"}
        # 记录到本地数据库
        local_db.add_log(activity=activity_type, message=result.get('message'), source='local')
        return result


# 显示劝学提示
def show_popup(message):
    """显示劝学提示，在Windows环境下总是显示GUI警告窗口"""
    import sys
    import platform
    
    # 检查是否在Windows环境下运行
    is_windows = platform.system() == 'Windows'
    
    if is_windows:
        # 在Windows环境下总是显示弹窗
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            root.attributes('-topmost', True)  # 确保弹窗在最上层
            messagebox.showwarning("学习提醒", message)  # 使用警告类型的弹窗
            root.destroy()
        except Exception as e:
            print(f"弹窗失败: {e}")
            print(f"提示信息: {message}")
    else:
        # 在非Windows环境中使用打印
        print(f"\n=== 提示信息 ===")
        print(f"{message}")
        print("================\n")


# 降级模式：简单的活动检测
def simple_analyze():
    """当Tesseract不可用时的简单活动检测方法"""
    import os
    import psutil
    
    # 系统进程列表（需要排除）
    system_processes = [
        "system", "system idle process", "registry", "smss.exe", "csrss.exe",
        "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "lsm.exe",
        "svchost.exe", "explorer.exe", "taskhost.exe", "dwm.exe", "conhost.exe",
        "rundll32.exe", "dllhost.exe", "ctfmon.exe", "audiodg.exe", "wmpnetwk.exe",
        "spoolsv.exe", "schedsvc.exe", "msmpeng.exe", "searchindexer.exe",
        "wmiapsrv.exe", "unsecapp.exe", "wmiadap.exe", "wmiprvse.exe",
        "taskmgr.exe", "cmd.exe", "powershell.exe", "conhost.exe",
        "python.exe", "pythonw.exe", "trae-sandbox.exe"
    ]
    
    # 扩展的娱乐应用进程名，包含更多游戏和娱乐相关进程
    entertainment_processes = [
        # 游戏平台和启动器
        "steam", "steamwebhelper", "steamservice", "epicgameslauncher", "epicwebhelper",
        "origin", "ea desktop", "uplay", "ubisoft connect", "battle.net", "battlenet",
        "gog galaxy", "itch", "minecraft launcher", "tlauncher", "java", "javaw",
        
        # 常见游戏进程
        "game", "games", "gaming", "valorant", "valorant-win64-shipping",
        "league of legends", "lol", "leagueclient", "riot client", "riot client ux",
        "dota", "dota2", "steamapps", "csgo", "csgo64", "csgo_launcher",
        "minecraft", "minecraftserver", "fortnite", "fortniteclient-win64-shipping",
        "pubg", "pubg lite", "apex", "apex legends", "apexlauncher",
        "overwatch", "overwatch.exe", "world of warcraft", "wow", "wow64",
        "fifa", "fifa20", "fifa21", "fifa22", "fifa23", "fifa24",
        "nba", "nfl", "mlb", "rocket league", "rocketleague",
        "roblox", "robloxplayer", "robloxplayerbeta", "among us", "amongus",
        "genshin impact", "genshinimpact", "yuanshen", "honkai impact",
        "honkai impact 3rd", "honkai", "honkai3rd", "崩坏3", "原神",
        "王者荣耀", "honor of kings", "英雄联盟", "leagueclientux",
        "绝地求生", "pubg mobile", "和平精英", "crossfire", "穿越火线",
        "dnf", "地下城与勇士", "梦幻西游", "问道", "剑网3", "jx3",
        "天涯明月刀", "逆水寒", "第五人格", "identity v",
        
        # 视频和音乐应用
        "bilibili", "bilibili client", "bilibili pc", "bilibili app",
        "youtube", "youtube music", "youtube gaming", "youtube desktop",
        "netflix", "netflix app", "hulu", "disney+", "disneyplus",
        "hbo max", "hbomax", "twitch", "twitch studio",
        "spotify", "spotify.exe", "apple music", "itunes",
        "netease cloud music", "cloudmusic", "网易云音乐", "qqmusic", "qq音乐",
        "kugou", "酷狗音乐", "kuwo", "酷我音乐", "qianqian", "千千音乐",
        "xiami", "虾米音乐", "vlc", "vlc.exe", "wmplayer", "windows media player",
        "potplayer", "gom player", "kmplayer", "mpc-hc", "mpc-be",
        
        # 社交和娱乐应用
        "weixin", "wechat", "wechatweb", "qq", "qq.exe", "qqmusic",
        "weibo", "weibo.exe", "微博", "twitter", "facebook", "instagram",
        "tiktok", "douyin", "抖音", "kuaishou", "快手",
        "xhs", "小红书", "zhihu", "知乎", "tieba", "贴吧",
        "snapchat", "telegram", "discord", "slack", "zoom", "teams",
        "skype", "line", "kakaotalk", "whatsapp", "viber",
        
        # 浏览器（可能用于娱乐）
        "chrome", "chromium", "firefox", "edge", "safari", "opera",
        "brave", "vivaldi", "maxthon", "360se", "360浏览器", "qqbrowser", "qq浏览器",
        "sogou explorer", "搜狗浏览器", "liebao", "猎豹浏览器",
        
        # 其他娱乐相关
        "emulator", "模拟器", "nox", "noxplayer", "bluestacks", "蓝叠",
        "memu", "ldplayer", "雷电模拟器", "tencent gaming buddy", "gameloop",
        "virtualbox", "vmware", "vmwareplayer", "vmwareworkstation"
    ]
    
    # 学习相关进程（用于排除误判）
    study_processes = [
        "word", "excel", "powerpoint", "powerpnt", "outlook", "onenote",
        "notepad", "notepad++", "sublime", "sublime text", "vscode", "code",
        "pycharm", "idea", "intellij", "eclipse", "netbeans", "visual studio",
        "adobe reader", "acrobat", "pdf", "pdf reader", "foxit reader",
        "zotero", "endnote", "mendeley", "citavi", "jabref",
        "matlab", "mathematica", "maple", "spss", "sas", "stata",
        "origin", "originpro", "graphpad", "sigmaplot", "chemdraw",
        "autocad", "solidworks", "catia", "ansys", "abaqus"
    ]
    
    try:
        # 获取所有运行的进程
        running_processes = []
        for proc in psutil.process_iter(['name']):
            try:
                process_name = proc.info['name'].lower()
                # 排除系统进程
                if not any(sys_proc in process_name for sys_proc in system_processes):
                    running_processes.append(process_name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # 首先检查是否有学习进程在运行（优先级更高）
        for process in study_processes:
            for running_process in running_processes:
                if process in running_process:
                    print(f"检测到学习进程: {running_process}")
                    return "study"
        
        # 检查是否有娱乐进程在运行
        for process in entertainment_processes:
            for running_process in running_processes:
                if process in running_process:
                    print(f"检测到娱乐进程: {running_process}")
                    return "entertainment"
        
        # 默认返回学习状态
        return "study"
        
    except Exception as e:
        print(f"进程检测失败: {e}")
        # 默认返回学习状态，避免误判
        return "study"


# 获取活动窗口标题
def get_active_window_title():
    """跨平台获取活动窗口标题"""
    try:
        system = platform.system()
        if system == 'Windows':
            try:
                import win32gui
                window = win32gui.GetForegroundWindow()
                return win32gui.GetWindowText(window)
            except ImportError:
                try:
                    import ctypes
                    from ctypes import wintypes
                    user32 = ctypes.WinDLL('user32', use_last_error=True)
                    user32.GetForegroundWindow.argtypes = ()
                    user32.GetForegroundWindow.restype = wintypes.HWND
                    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
                    user32.GetWindowTextLengthW.restype = ctypes.c_int
                    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
                    user32.GetWindowTextW.restype = ctypes.c_int
                    
                    hwnd = user32.GetForegroundWindow()
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length == 0:
                        return ""
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    return buffer.value
                except Exception as e:
                    print(f"Windows窗口标题获取失败: {e}")
                    return ""
        elif system == 'Darwin':
            try:
                from AppKit import NSWorkspace
                return NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()
            except ImportError:
                try:
                    import subprocess
                    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
                    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
                    return result.stdout.strip()
                except Exception as e:
                    print(f"macOS窗口标题获取失败: {e}")
                    return ""
        elif system == 'Linux':
            try:
                import subprocess
                result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                       capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception as e:
                print(f"Linux窗口标题获取失败: {e}")
                return ""
        return ""
    except Exception as e:
        print(f"窗口标题获取失败: {e}")
        return ""


# 分析窗口标题
def analyze_window_title(title):
    """通过窗口标题分析活动类型"""
    lower_title = title.lower()
    
    entertainment_keywords = config_manager.get('entertainment_keywords')
    study_keywords = config_manager.get('study_keywords')
    
    for keyword in entertainment_keywords:
        if keyword in lower_title:
            return "entertainment"
    
    for keyword in study_keywords:
        if keyword in lower_title:
            return "study"
    
    return "study"


# 多模态融合识别
def multimodal_fusion_analysis(tesseract_available):
    """
    多模态融合识别：进程(0.6) + OCR(0.3) + 窗口标题(0.1)
    当OCR不可用时，降级为进程(0.7) + 窗口标题(0.3)
    """
    weights = {
        'process': 0.6,
        'ocr': 0.3,
        'window': 0.1
    }
    
    if not tesseract_available:
        weights = {
            'process': 0.7,
            'window': 0.3
        }
    
    results = {}
    scores = {}
    
    try:
        results['process'] = simple_analyze()
    except Exception as e:
        print(f"进程分析失败: {e}")
        results['process'] = "study"
    
    try:
        window_title = get_active_window_title()
        print(f"活动窗口: {window_title}")
        results['window'] = analyze_window_title(window_title)
    except Exception as e:
        print(f"窗口标题分析失败: {e}")
        results['window'] = "study"
    
    if tesseract_available:
        try:
            img = capture_screen()
            results['ocr'] = analyze_image(img)
        except Exception as e:
            print(f"OCR分析失败: {e}")
            results['ocr'] = "study"
    
    scores['entertainment'] = 0.0
    scores['study'] = 0.0
    
    for source, result in results.items():
        if source in weights:
            if result == 'entertainment':
                scores['entertainment'] += weights[source]
            else:
                scores['study'] += weights[source]
    
    print(f"多模态融合结果:")
    print(f"  进程分析: {results.get('process')}")
    if tesseract_available:
        print(f"  OCR分析: {results.get('ocr')}")
    print(f"  窗口标题: {results.get('window')}")
    print(f"  娱乐分数: {scores['entertainment']:.2f}")
    print(f"  学习分数: {scores['study']:.2f}")
    
    if scores['entertainment'] > scores['study']:
        return "entertainment"
    else:
        return "study"

# 主程序
def main():
    print("学习辅助监控系统启动中...")
    
    # 测试Tesseract是否可用
    tesseract_available = False
    try:
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        test_text = pytesseract.image_to_string(test_img)
        tesseract_available = True
        print("Tesseract-OCR 初始化成功，使用多模态融合识别模式")
    except Exception as e:
        print(f"Tesseract-OCR 初始化失败: {e}")
        print("将使用降级模式（进程+窗口标题检测）继续运行")
    
    # 初始化时间窗口队列，保存最近5次检测结果
    result_queue = deque(maxlen=5)
    
    # 禁用GUI元素，确保在非交互式环境中也能运行
    print("使用配置文件启动...")
    
    check_interval = config_manager.get('check_interval')
    # 开始监控循环
    print(f"学习辅助监控系统已启动，检查间隔: {check_interval}秒，按Ctrl+C停止...")
    
    try:
        while True:
            print("\n开始新一轮检查...")
            
            # 使用多模态融合识别
            activity_type = multimodal_fusion_analysis(tesseract_available)
            
            print(f"活动分析结果: {activity_type}")
            
            # 将结果加入队列
            result_queue.append(activity_type)
            
            # 检查是否需要触发提醒
            should_trigger = False
            if len(result_queue) >= 3:
                # 检查最近3次结果是否一致
                recent_3 = list(result_queue)[-3:]
                if all(r == recent_3[0] for r in recent_3):
                    should_trigger = True
                    print(f"连续3次结果一致: {recent_3[0]}")
            
            # 发送到服务器（每次都发送数据）
            response = send_to_server(activity_type)
            print(f"响应: {response}")

            # 只有连续3次结果一致才触发提醒
            if should_trigger and response.get("status") == "warning":
                print(f"显示警告提示: {response['message']}")
                show_popup(response["message"])
            
            print(f"等待 {check_interval} 秒...")
            time.sleep(check_interval)
    except KeyboardInterrupt:
        print("监控系统已停止")
        local_db.close()
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        local_db.close()


if __name__ == "__main__":
    main()
