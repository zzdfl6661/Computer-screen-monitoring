import pytesseract
import platform
import psutil
import ctypes
from ctypes import wintypes
import subprocess
import logging
import os

from .config import ConfigManager
from .capture import capture_screen
from logger import setup_logger

logger = setup_logger('classify')
config_manager = ConfigManager()

try:
    pytesseract.pytesseract.tesseract_cmd = r"D:\Program Files\Tesseract-OCR\tesseract.exe"
except:
    pass


class MLClassifier:
    def __init__(self):
        self.classifier = None
        self.model_manager = None
        self._initialized = False
        self._init_error = None

    def initialize(self):
        try:
            from .model import ModelManager, ONNXClassifier
            self.model_manager = ModelManager()
            
            if not self.model_manager.ensure_model(auto_update=True):
                logger.warning("模型下载失败，将使用进程检测作为主要分类方法")
                self._init_error = "模型下载失败"
                return False

            model_path = self.model_manager.get_model_path()
            if not os.path.exists(model_path):
                logger.warning(f"模型文件不存在: {model_path}")
                self._init_error = "模型文件不存在"
                return False

            self.classifier = ONNXClassifier(model_path)
            self._initialized = True
            logger.info("MLClassifier初始化成功")
            return True

        except ImportError as e:
            logger.warning(f"ML模型依赖未安装，跳过模型分类: {e}")
            self._init_error = "模型依赖未安装"
            return False
        except Exception as e:
            logger.error(f"MLClassifier初始化失败: {e}")
            self._init_error = str(e)
            return False

    def is_initialized(self):
        return self._initialized

    def classify(self, image):
        if not self._initialized or self.classifier is None:
            logger.warning("MLClassifier未初始化，返回默认结果")
            return {
                'label': 'idle',
                'confidence': 0.0,
                'probabilities': {'study': 0.2, 'gaming': 0.2, 'video': 0.2, 'social': 0.2, 'idle': 0.2},
                'inference_time': 0.0
            }

        try:
            return self.classifier.predict(image)
        except Exception as e:
            logger.error(f"ML分类失败: {e}")
            return {
                'label': 'idle',
                'confidence': 0.0,
                'probabilities': {'study': 0.2, 'gaming': 0.2, 'video': 0.2, 'social': 0.2, 'idle': 0.2},
                'inference_time': 0.0
            }

    def close(self):
        if self.classifier is not None:
            try:
                self.classifier.close()
            except:
                pass
            self.classifier = None
            self._initialized = False


ml_classifier = MLClassifier()


def analyze_image(img):
    text = pytesseract.image_to_string(img)
    lower_text = text.lower()

    entertainment_keywords = config_manager.get('entertainment_keywords')
    study_keywords = config_manager.get('study_keywords')

    for keyword in entertainment_keywords:
        if keyword in lower_text:
            return "entertainment"

    for keyword in study_keywords:
        if keyword in lower_text:
            return "study"

    return "study"


def simple_analyze():
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

    entertainment_processes = [
        "steam", "steamwebhelper", "steamservice", "epicgameslauncher", "epicwebhelper",
        "origin", "ea desktop", "uplay", "ubisoft connect", "battle.net", "battlenet",
        "gog galaxy", "itch", "minecraft launcher", "tlauncher", "java", "javaw",
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
        "bilibili", "bilibili client", "bilibili pc", "bilibili app",
        "youtube", "youtube music", "youtube gaming", "youtube desktop",
        "netflix", "netflix app", "hulu", "disney+", "disneyplus",
        "hbo max", "hbomax", "twitch", "twitch studio",
        "spotify", "spotify.exe", "apple music", "itunes",
        "netease cloud music", "cloudmusic", "网易云音乐", "qqmusic", "qq音乐",
        "kugou", "酷狗音乐", "kuwo", "酷我音乐", "qianqian", "千千音乐",
        "xiami", "虾米音乐", "vlc", "vlc.exe", "wmplayer", "windows media player",
        "potplayer", "gom player", "kmplayer", "mpc-hc", "mpc-be",
        "weixin", "wechat", "wechatweb", "qq", "qq.exe", "qqmusic",
        "weibo", "weibo.exe", "微博", "twitter", "facebook", "instagram",
        "tiktok", "douyin", "抖音", "kuaishou", "快手",
        "xhs", "小红书", "zhihu", "知乎", "tieba", "贴吧",
        "snapchat", "telegram", "discord", "slack", "zoom", "teams",
        "skype", "line", "kakaotalk", "whatsapp", "viber",
        "chrome", "chromium", "firefox", "edge", "safari", "opera",
        "brave", "vivaldi", "maxthon", "360se", "360浏览器", "qqbrowser", "qq浏览器",
        "sogou explorer", "搜狗浏览器", "liebao", "猎豹浏览器",
        "emulator", "模拟器", "nox", "noxplayer", "bluestacks", "蓝叠",
        "memu", "ldplayer", "雷电模拟器", "tencent gaming buddy", "gameloop",
        "virtualbox", "vmware", "vmwareplayer", "vmwareworkstation"
    ]

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
        running_processes = []
        for proc in psutil.process_iter(['name']):
            try:
                process_name = proc.info['name'].lower()
                if not any(sys_proc in process_name for sys_proc in system_processes):
                    running_processes.append(process_name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        for process in study_processes:
            for running_process in running_processes:
                if process in running_process:
                    logger.info(f"检测到学习进程: {running_process}")
                    return "study"

        for process in entertainment_processes:
            for running_process in running_processes:
                if process in running_process:
                    logger.info(f"检测到娱乐进程: {running_process}")
                    return "entertainment"

        return "idle"

    except Exception as e:
        logger.error(f"进程检测失败: {e}")
        return "idle"


def get_active_window_title():
    try:
        system = platform.system()
        if system == 'Windows':
            try:
                import win32gui
                window = win32gui.GetForegroundWindow()
                return win32gui.GetWindowText(window)
            except ImportError:
                try:
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
                    logger.error(f"Windows窗口标题获取失败: {e}")
                    return ""
        elif system == 'Darwin':
            try:
                from AppKit import NSWorkspace
                return NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()
            except ImportError:
                try:
                    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
                    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
                    return result.stdout.strip()
                except Exception as e:
                    logger.error(f"macOS窗口标题获取失败: {e}")
                    return ""
        elif system == 'Linux':
            try:
                result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'],
                                       capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception as e:
                logger.error(f"Linux窗口标题获取失败: {e}")
                return ""
        return ""
    except Exception as e:
        logger.error(f"窗口标题获取失败: {e}")
        return ""


def analyze_window_title(title):
    lower_title = title.lower()

    entertainment_keywords = config_manager.get('entertainment_keywords')
    study_keywords = config_manager.get('study_keywords')

    for keyword in entertainment_keywords:
        if keyword in lower_title:
            return "entertainment"

    for keyword in study_keywords:
        if keyword in lower_title:
            return "study"

    return "idle"


def _map_to_primary_category(label):
    entertainment_labels = ['gaming', 'video', 'social']
    if label in entertainment_labels:
        return 'entertainment'
    elif label == 'study':
        return 'study'
    else:
        return 'idle'


def multimodal_fusion_analysis(tesseract_available=False):
    weights = {
        'model': 0.5,
        'process': 0.3,
        'window': 0.2
    }

    results = {}
    scores = {'study': 0.0, 'entertainment': 0.0, 'idle': 0.0}

    try:
        results['process'] = simple_analyze()
    except Exception as e:
        logger.error(f"进程分析失败: {e}")
        results['process'] = "idle"

    try:
        window_title = get_active_window_title()
        logger.info(f"活动窗口: {window_title}")
        results['window'] = analyze_window_title(window_title)
    except Exception as e:
        logger.error(f"窗口标题分析失败: {e}")
        results['window'] = "idle"

    try:
        if not ml_classifier.is_initialized():
            ml_classifier.initialize()

        if ml_classifier.is_initialized():
            img = capture_screen()
            model_result = ml_classifier.classify(img)
            results['model'] = model_result['label']
            results['model_confidence'] = model_result['confidence']
            results['model_probabilities'] = model_result['probabilities']
            logger.info(f"模型分类结果: {model_result['label']} (置信度: {model_result['confidence']:.4f})")
        else:
            results['model'] = "idle"
            weights['process'] += weights['model'] / 2
            weights['window'] += weights['model'] / 2
            del weights['model']
            logger.warning("ML模型不可用，调整权重分配")

    except Exception as e:
        logger.error(f"模型分类失败: {e}")
        results['model'] = "idle"
        if 'model' in weights:
            weights['process'] += weights['model'] / 2
            weights['window'] += weights['model'] / 2
            del weights['model']

    for source, result in results.items():
        if source in weights:
            primary_category = _map_to_primary_category(result)
            scores[primary_category] += weights[source]

    logger.info(f"多模态融合结果:")
    logger.info(f"  进程分析: {results.get('process')}")
    logger.info(f"  窗口标题: {results.get('window')}")
    if 'model' in results:
        logger.info(f"  模型分类: {results.get('model')} (置信度: {results.get('model_confidence', 0):.4f})")
    logger.info(f"  学习分数: {scores['study']:.2f}")
    logger.info(f"  娱乐分数: {scores['entertainment']:.2f}")
    logger.info(f"  空闲分数: {scores['idle']:.2f}")

    if scores['entertainment'] > scores['study'] and scores['entertainment'] > scores['idle']:
        return "entertainment"
    elif scores['study'] > scores['entertainment'] and scores['study'] > scores['idle']:
        return "study"
    else:
        return "idle"
