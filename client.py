import pyautogui
import requests
import time
import numpy as np
import cv2
import pytesseract
from PIL import Image
import tkinter as tk
from tkinter import messagebox, simpledialog

# 设置Tesseract路径
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 配置类
class Config:
    def __init__(self):
        self.check_interval = 5  # 默认检查间隔（秒）
        self.server_url = "http://localhost:5000/check_activity"  # 服务端URL
        
        # 扩展的娱乐关键词，包含更多游戏和娱乐相关词汇
        self.entertainment_keywords = [
            # 英文游戏相关
            "game", "games", "gaming", "play", "player", "steam", "epic", "origin", "uplay",
            "battlefield", "call of duty", "csgo", "valorant", "league of legends", "lol",
            "dota", "minecraft", "fortnite", "pubg", "apex", "overwatch", "world of warcraft",
            "wow", "fifa", "nba", "nfl", "mlb", "rocket league", "roblox", "among us",
            # 中文游戏相关
            "游戏", "网游", "手游", "电竞", "王者荣耀", "英雄联盟", "绝地求生", "和平精英",
            "原神", "崩坏", "阴阳师", "第五人格", "我的世界", "穿越火线", "地下城与勇士",
            "梦幻西游", "问道", "剑网3", "天涯明月刀", "逆水寒", "天涯明月刀", "逆水寒",
            # 视频娱乐相关
            "video", "videos", "youtube", "bilibili", "netflix", "hulu", "disney+", "hbo",
            "twitch", "tiktok", "douyin", "kuaishou", "抖音", "快手", "爱奇艺", "优酷",
            "腾讯视频", "芒果tv", "哔哩哔哩", "b站", "电影", "电视剧", "综艺", "动漫",
            # 音乐娱乐相关
            "music", "spotify", "apple music", "netease cloud music", "网易云音乐",
            "qq音乐", "酷狗音乐", "酷我音乐", "千千音乐", "虾米音乐",
            # 其他娱乐应用
            "weibo", "微博", "twitter", "facebook", "instagram", "tiktok", "snapchat",
            "聊天", "社交", "朋友圈", "微博", "小红书", "知乎", "贴吧", "论坛"
        ]
        
        # 扩展的学习关键词，包含更多学习相关词汇
        self.study_keywords = [
            # 英文学习相关
            "study", "studying", "education", "learning", "course", "courses", "lecture",
            "lectures", "class", "classes", "homework", "assignment", "assignments",
            "exam", "exams", "test", "tests", "quiz", "quizzes", "practice", "exercise",
            "exercises", "math", "science", "physics", "chemistry", "biology", "history",
            "geography", "literature", "language", "programming", "coding", "python",
            "java", "javascript", "c++", "html", "css", "database", "algorithm",
            "tutorial", "tutorials", "documentation", "docs", "reference", "research",
            "paper", "papers", "article", "articles", "thesis", "dissertation",
            "note", "notes", "notebook", "textbook", "textbooks", "library", "lib",
            "university", "college", "school", "student", "teacher", "professor",
            # 中文学习相关
            "学习", "作业", "课程", "教材", "课本", "笔记", "复习", "预习", "考试",
            "测验", "练习", "习题", "数学", "物理", "化学", "生物", "历史", "地理",
            "语文", "英语", "政治", "编程", "代码", "开发", "教程", "文档", "论文",
            "研究", "大学", "学院", "学校", "学生", "老师", "教授", "图书馆",
            "在线教育", "慕课", "网课", "直播课", "录播课", "公开课", "精品课",
            "题库", "真题", "模拟题", "押题", "知识点", "考点", "重点", "难点",
            "学习计划", "学习目标", "学习进度", "学习笔记", "学习资料", "学习工具"
        ]

    def update_check_interval(self, interval):
        self.check_interval = interval

    def update_keywords(self, entertainment_keywords, study_keywords):
        self.entertainment_keywords = entertainment_keywords
        self.study_keywords = study_keywords

# 创建全局配置实例
config = Config()

# 显示配置窗口
def show_config_window():
    root = tk.Tk()
    root.title("学习辅助监控系统 - 配置")
    root.geometry("400x300")
    
    # 检查间隔设置
    tk.Label(root, text="检查间隔（秒）：").pack(pady=5)
    interval_var = tk.StringVar(value=str(config.check_interval))
    tk.Entry(root, textvariable=interval_var).pack(pady=5)
    
    # 保存按钮
    def save_config():
        try:
            new_interval = int(interval_var.get())
            if new_interval > 0:
                config.update_check_interval(new_interval)
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
    
    # 检查娱乐关键词
    for keyword in config.entertainment_keywords:
        if keyword in lower_text:
            return "entertainment"
    
    # 检查学习关键词
    for keyword in config.study_keywords:
        if keyword in lower_text:
            return "study"
    
    # 默认返回学习状态，避免误判
    return "study"


# 向服务端发送请求
def send_to_server(activity_type):
    url = config.server_url  # 使用配置中的服务端URL
    try:
        response = requests.post(url, json={"activity": activity_type}, timeout=5)
        if response.status_code == 200:
            print("服务器响应:", response.text)
        else:
            print("请求失败，状态码:", response.status_code)

        return response.json()  # 返回JSON响应数据
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        # 服务端不可用时，本地处理
        if activity_type == "entertainment":
            return {"message": "你正在娱乐，请切换到学习！", "status": "warning"}
        else:
            return {"message": "继续保持学习状态！", "status": "good"}


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

# 主程序
def main():
    print("学习辅助监控系统启动中...")
    
    # 测试Tesseract是否可用
    tesseract_available = False
    try:
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        test_text = pytesseract.image_to_string(test_img)
        tesseract_available = True
        print("Tesseract-OCR 初始化成功，使用图像识别模式")
    except Exception as e:
        print(f"Tesseract-OCR 初始化失败: {e}")
        print("将使用降级模式（进程检测）继续运行")
    
    # 禁用GUI元素，确保在非交互式环境中也能运行
    print("使用默认配置启动...")
    
    # 开始监控循环
    print(f"学习辅助监控系统已启动，检查间隔: {config.check_interval}秒，按Ctrl+C停止...")
    
    try:
        while True:
            print("\n开始新一轮检查...")
            
            # 根据Tesseract是否可用选择不同的分析方法
            if tesseract_available:
                img = capture_screen()  # 捕获屏幕截图
                print("屏幕截图成功")
                activity_type = analyze_image(img)  # 分析是否在娱乐
            else:
                activity_type = simple_analyze()  # 使用进程检测
            
            print(f"活动分析结果: {activity_type}")
            
            response = send_to_server(activity_type)  # 发送活动类型到服务端
            print(f"服务端响应: {response}")

            if response.get("status") == "warning":
                print(f"显示警告提示: {response['message']}")
                show_popup(response["message"])  # 如果是警告，弹窗显示提示
            
            print(f"等待 {config.check_interval} 秒...")
            time.sleep(config.check_interval)  # 使用配置的检查间隔
    except KeyboardInterrupt:
        print("监控系统已停止")
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
