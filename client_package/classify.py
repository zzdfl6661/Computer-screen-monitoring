"""
学习/娱乐活动分类（置信度感知融合 + 分层信号）

信号来源（端侧，截图不出本机）：
  1. process  前台窗口所属进程名匹配（仅看前台；浏览器与 java 视为中性，交给标题判定）
  2. title    窗口标题 + 站点声誉（站点名/域名）语义判级
  3. text_llm 本地文本 LLM 判级（可选，pluggable，离线降级到规则）
  4. server_vlm 服务端视觉兜底（enable_server_vision：仅对“不确定”样本上传降采样截图，
     由服务端 OCR+规则判级；原客户端 ONNX 视觉模型已下线，不再下载）

融合：每个信号贡献 = 权重 × 自身置信度；总证据归一化后 argmax + 置信度阈值。
低置信 → 标记不确定 → 触发服务端视觉兜底；否则保守返回 idle（不误报）。
"""
import os
import platform
import re
import logging

# 健壮性：相对/绝对导入兜底，capture / psutil 延迟导入，
# 使本模块在没有 pyautogui / cv2 / psutil 时也能被评测脚本导入。
try:
    from .config import ConfigManager
except Exception:
    from config import ConfigManager

try:
    from logger import setup_logger
except Exception:
    def setup_logger(name):
        return logging.getLogger(name)

logger = setup_logger('classify')
config_manager = ConfigManager()


# ---------------------------------------------------------------------------
# 静态配置（可被 config.json 覆盖）
# ---------------------------------------------------------------------------
DEFAULT_SITE_REPUTATION = {
    "study": [
        "leetcode", "coursera", "edx", "khan", "khanacademy", "codecademy",
        "udacity", "mooc", "中国大学mooc", "腾讯课堂", "网易云课堂", "学堂在线",
        "juejin", "csdn", "stackoverflow", "github", "gitlab", "arxiv",
        "researchgate", "wikipedia", "wiki", "wolfram", "geogebra", "desmos",
        "docs", "notion", "腾讯会议", "钉钉", "学习通", "雨课堂", "百度文库",
        "道客巴巴", "知乎", "掘金", "博客园", "可汗",
    ],
    "entertainment": [
        "netflix", "hulu", "disney", "hbo", "twitch", "tiktok", "douyin",
        "抖音", "kuaishou", "快手", "weibo", "微博", "instagram", "facebook",
        "twitter", "snapchat", "spotify", "apple music", "netease cloud music",
        "网易云音乐", "qq音乐", "酷狗", "酷我", "steam", "epic", "origin",
        "uplay", "battlenet", "weixin", "wechat", "王者荣耀", "英雄联盟",
        "原神", "和平精英", "pubg", "fortnite", "steamcommunity",
        "xiaohongshu", "小红书", "tieba", "贴吧",
    ],
    "ambiguous": [
        "youtube", "bilibili", "哔哩哔哩", "b站", "iqiyi", "爱奇艺", "优酷",
        "腾讯视频", "芒果tv", "taobao", "淘宝", "jd", "京东", "baidu", "百度",
        "sogou", "搜狗",
    ],
}

DEFAULT_WEIGHTS = {
    "process": 0.45,
    "title": 0.30,
    "text_llm": 0.20,
}
DEFAULT_CONF_THRESHOLD = 0.45


def _cfg(key, default):
    val = config_manager.get(key)
    return val if val is not None else default


SITE_REPUTATION = _cfg('site_reputation', DEFAULT_SITE_REPUTATION)
WEIGHTS = _cfg('fusion_weights', DEFAULT_WEIGHTS)
CONF_THRESHOLD = float(_cfg('confidence_threshold', DEFAULT_CONF_THRESHOLD))
# “不确定”判定阈值（可配置）：赢家归一化分数低于下限、或与前一名差距过小 → uncertain
FUSION_MIN_CONF = float(_cfg('fusion_min_confidence', 0.40))
FUSION_MARGIN = float(_cfg('fusion_margin', 0.05))
AMBIGUOUS_SITE_TOKENS = set(SITE_REPUTATION.get('ambiguous', []))


# 浏览器进程（中性，交给标题/站点判定）
BROWSER_HINTS = [
    'chrome', 'chromium', 'firefox', 'edge', 'safari', 'opera', 'brave',
    'vivaldi', 'maxthon', '360se', '360浏览器', 'qqbrowser', 'qq浏览器',
    'sogou explorer', '搜狗浏览器', 'liebao', '猎豹浏览器', 'iexplore',
]
# 进程名含糊（java/javaw 既可能是编程 IDE，也可能是 Minecraft）
AMBIGUOUS_PROCESS_HINTS = ['java', 'javaw']

SYSTEM_PROCESSES = [
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "lsm.exe",
    "svchost.exe", "explorer.exe", "taskhost.exe", "dwm.exe", "conhost.exe",
    "rundll32.exe", "dllhost.exe", "ctfmon.exe", "audiodg.exe", "wmpnetwk.exe",
    "spoolsv.exe", "schedsvc.exe", "msmpeng.exe", "searchindexer.exe",
    "wmiapsrv.exe", "unsecapp.exe", "wmiadap.exe", "wmiprvse.exe",
    "taskmgr.exe", "cmd.exe", "powershell.exe", "trae-sandbox.exe",
]

# 娱乐进程（已移除浏览器与 java，避免“浏览器一律娱乐”的致命误判）
ENTERTAINMENT_PROCESSES = [
    "steam", "steamwebhelper", "steamservice", "epicgameslauncher", "epicwebhelper",
    "origin", "ea desktop", "uplay", "ubisoft connect", "battle.net", "battlenet",
    "gog galaxy", "itch", "minecraft launcher", "tlauncher",
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
    "bilibili client", "bilibili pc", "bilibili app",
    "youtube music", "youtube gaming", "youtube desktop",
    "netflix app", "hulu", "disney+", "disneyplus",
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
    "emulator", "模拟器", "nox", "noxplayer", "bluestacks", "蓝叠",
    "memu", "ldplayer", "雷电模拟器", "tencent gaming buddy", "gameloop",
]

STUDY_PROCESSES = [
    "word", "excel", "powerpoint", "powerpnt", "outlook", "onenote",
    "notepad", "notepad++", "sublime", "sublime text", "vscode", "code",
    "workbuddy", "codebuddy", "trae",
    "pycharm", "idea", "intellij", "eclipse", "netbeans", "visual studio",
    "adobe reader", "acrobat", "pdf", "pdf reader", "foxit reader",
    "zotero", "endnote", "mendeley", "citavi", "jabref",
    "matlab", "mathematica", "maple", "spss", "sas", "stata",
    "origin", "originpro", "graphpad", "sigmaplot", "chemdraw",
    "autocad", "solidworks", "catia", "ansys", "abaqus",
]


def _match_token(text, token):
    """边界感知匹配：ascii 令牌用 \\b 边界（允许末尾数字，避免 'idea' 漏配 'idea64'，
    但阻止 'code' 命中 'vscode'/'decode'、'lib' 命中 'bilibili'）；中文退化为子串。"""
    if token.isascii():
        return bool(re.search(r'(?<![a-z0-9])' + re.escape(token) + r'(?![a-z])', text))
    return token in text


def _get_running_processes():
    try:
        import psutil
    except Exception:
        return []
    running = []
    try:
        for proc in psutil.process_iter(['name']):
            try:
                name = (proc.info['name'] or '').lower()
                if name and not any(s in name for s in SYSTEM_PROCESSES):
                    running.append(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"进程枚举失败: {e}")
    return running


def _get_foreground_process():
    """返回前台窗口所属进程名（小写）；无法获取时返回 None。
    修复：后台挂着的娱乐应用（QQ/Steam++/抖音守护等）不再污染进程信号，
    只有真正在前台的窗口进程参与判定。"""
    system = platform.system()
    try:
        if system == 'Windows':
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            user32.GetForegroundWindow.argtypes = ()
            user32.GetForegroundWindow.restype = wintypes.HWND
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return None
            import psutil
            return (psutil.Process(pid.value).name() or '').lower()
        elif system == 'Darwin':
            from AppKit import NSWorkspace
            name = NSWorkspace.sharedWorkspace().frontmostApplication().localizedName()
            return (name or '').lower()
        elif system == 'Linux':
            import subprocess
            out = subprocess.run(['xdotool', 'getactivewindow', 'getwindowpid'],
                                 capture_output=True, text=True)
            pid = out.stdout.strip()
            if pid.isdigit():
                import psutil
                return (psutil.Process(int(pid)).name() or '').lower()
    except Exception as e:
        logger.error(f"获取前台进程失败: {e}")
    return None


def analyze_processes(running_processes):
    """返回 (category, confidence, detail)。浏览器/java 视为中性（confidence=0，不贡献）。"""
    for proc in running_processes:
        for hint in BROWSER_HINTS:
            if _match_token(proc, hint):
                return ('idle', 0.0, f'browser:{proc}')
        for hint in AMBIGUOUS_PROCESS_HINTS:
            if _match_token(proc, hint):
                return ('idle', 0.0, f'ambiguous_proc:{proc}')
        for sp in STUDY_PROCESSES:
            if _match_token(proc, sp):
                return ('study', 0.90, f'study_proc:{proc}')
        for ep in ENTERTAINMENT_PROCESSES:
            if _match_token(proc, ep):
                return ('entertainment', 0.90, f'ent_proc:{proc}')
    return ('idle', 0.0, 'no_match')


def _match_site(low_title):
    for token in SITE_REPUTATION.get('entertainment', []):
        if token in low_title:
            return 'entertainment', token
    for token in SITE_REPUTATION.get('study', []):
        if token in low_title:
            return 'study', token
    for token in SITE_REPUTATION.get('ambiguous', []):
        if token in low_title:
            return 'ambiguous', token
    return None, None


def analyze_title(title):
    """返回 (category, confidence, site_token, detail)。"""
    if not title:
        return ('idle', 0.0, None, 'empty')
    low = title.lower()
    site_cat, site_token = _match_site(low)

    ent_kw = config_manager.get('entertainment_keywords') or []
    study_kw = config_manager.get('study_keywords') or []

    # 两栖站点令牌不计入娱乐关键词，避免 bilibili/youtube 被自动判娱乐；
    # 关键词同样用边界感知匹配，避免 'lib' 误命中 'bilibili' 等子串问题
    ent_hits = [k for k in ent_kw if _match_token(low, k) and k not in AMBIGUOUS_SITE_TOKENS]
    study_hits = [k for k in study_kw if _match_token(low, k)]

    study_score = 0.0
    ent_score = 0.0
    if site_cat == 'study':
        study_score += 0.85
    elif site_cat == 'entertainment':
        ent_score += 0.85
    elif site_cat == 'ambiguous':
        study_score += 0.40
        ent_score += 0.40

    study_score += min(len(study_hits) * 0.30, 0.60)
    ent_score += min(len(ent_hits) * 0.30, 0.60)

    if site_cat == 'ambiguous':
        if study_hits and not ent_hits:
            study_score += 0.20
        elif ent_hits and not study_hits:
            ent_score += 0.20

    if study_score == 0 and ent_score == 0:
        return ('idle', 0.0, site_token, 'no_signal')

    total = study_score + ent_score
    if study_score >= ent_score:
        cat = 'study'
        conf = study_score / total
    else:
        cat = 'entertainment'
        conf = ent_score / total
    conf = min(conf, 0.95)
    return (cat, round(conf, 3), site_token, f'site={site_cat}')


def fuse_signals(signals):
    """置信度感知融合。返回 (activity, decision_conf, scores, uncertain)。"""
    scores = {'study': 0.0, 'entertainment': 0.0, 'idle': 0.0}
    total = 0.0
    for s in signals:
        cat, w, cf = s['category'], s['weight'], s['confidence']
        if cat in scores and cf > 0 and w > 0:
            scores[cat] += w * cf
            total += w * cf
    if total <= 0:
        return 'idle', 0.0, scores, False
    norm = {k: v / total for k, v in scores.items()}
    ranked = sorted(norm.items(), key=lambda x: -x[1])
    top_cat, top_val = ranked[0]
    second_val = ranked[1][1]
    if top_cat == 'idle':
        return 'idle', round(top_val, 3), scores, True
    if top_val < FUSION_MIN_CONF or (top_val - second_val) < FUSION_MARGIN:
        return 'idle', round(top_val, 3), scores, True
    return top_cat, round(top_val, 3), scores, False


def classify_from_signals(running_processes, title,
                          use_model=False, use_text_llm=False, use_vlm=False):
    """纯函数：给定 (进程列表, 窗口标题) 返回分类结果。供评测与测试使用（离线）。
    use_model 参数保留兼容：客户端 ONNX 视觉模型已下线，忽略。"""

    signals = []
    pcat, pconf, pdetail = analyze_processes(running_processes)
    if pconf > 0:
        signals.append({'category': pcat, 'weight': WEIGHTS['process'], 'confidence': pconf})
    tcat, tconf, site, tdetail = analyze_title(title)
    if tconf > 0:
        signals.append({'category': tcat, 'weight': WEIGHTS['title'], 'confidence': tconf})

    activity, dconf, scores, uncertain = fuse_signals(signals)
    breakdown = {
        'process': (pcat, pconf, pdetail),
        'title': (tcat, tconf, site, tdetail),
        'uncertain': uncertain,
    }

    if use_text_llm and _cfg('enable_text_llm', False):
        try:
            from .llm_judge import TextJudge
            judge = TextJudge()
            lcat, lconf, lreason = judge.judge(running_processes, title, site)
            if lconf > 0:
                signals.append({'category': lcat, 'weight': WEIGHTS['text_llm'], 'confidence': lconf})
            breakdown['text_llm'] = (lcat, lconf, lreason)
        except Exception as e:
            logger.error(f"文本LLM判级失败: {e}")

    activity, dconf, scores, uncertain = fuse_signals(signals)
    breakdown['fusion'] = (activity, dconf, scores, uncertain)

    if uncertain and use_vlm and (_cfg('enable_vlm', False) or _cfg('enable_server_vision', False)):
        try:
            from .capture import capture_screen
            from .vlm_classifier import VLMClassifier
            img = capture_screen()
            vlm = VLMClassifier()
            vcat, vconf = vlm.classify(img)
            breakdown['vlm'] = (vcat, vconf, 'fallback')
            if vconf >= CONF_THRESHOLD and vcat in ('study', 'entertainment'):
                activity = vcat
        except Exception as e:
            logger.error(f"VLM兜底失败: {e}")

    return activity, dconf, breakdown


# ---------------------------------------------------------------------------
# 兼容桩：原客户端 ONNX 视觉模型已下线（下载地址 404，视觉已迁服务端 OCR）。
# 保留类结构以兼容旧调用，但永不初始化、不参与判定。
# ---------------------------------------------------------------------------
class MLClassifier:
    def __init__(self):
        self._initialized = False
        self._init_attempted = False
        self._init_error = None

    def initialize(self):
        if self._init_attempted:
            return self._initialized
        self._init_attempted = True
        self._init_error = "视觉模型已下线，交由服务端 OCR 兜底"
        return False

    def is_initialized(self):
        return self._initialized

    def close(self):
        self._initialized = False
        self._init_attempted = False


ml_classifier = MLClassifier()


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
                    logger.error(f"Windows窗口标题获取失败: {e}")
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
                    logger.error(f"macOS窗口标题获取失败: {e}")
                    return ""
        elif system == 'Linux':
            try:
                import subprocess
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


def multimodal_fusion_analysis(tesseract_available=False):
    """端到端分类（真实运行环境）。返回字符串 activity。"""
    signals = []
    breakdown = {}

    running = _get_running_processes()
    fg = _get_foreground_process()
    if fg:
        # 只分析“前台窗口所属进程”：后台娱乐应用（QQ/Steam++/抖音守护等）不再污染判定
        pcat, pconf, pdetail = analyze_processes([fg])
    else:
        pcat, pconf, pdetail = ('idle', 0.0, 'no_foreground')
    if pconf > 0:
        signals.append({'category': pcat, 'weight': WEIGHTS['process'], 'confidence': pconf})
    breakdown['process'] = (pcat, pconf, pdetail)

    title = get_active_window_title()
    tcat, tconf, site, tdetail = analyze_title(title)
    if tconf > 0:
        signals.append({'category': tcat, 'weight': WEIGHTS['title'], 'confidence': tconf})
    breakdown['title'] = (tcat, tconf, site, tdetail)

    image = None
    # 客户端视觉模型已下线（下载地址 404）：不再做本地 OCR/ONNX 识别，
    # 视觉兜底统一走服务端（仅"不确定"样本上传截图，见下方 VLM/server_vision 分支）
    breakdown['model'] = ('idle', 0.0, 'removed')

    if _cfg('enable_text_llm', False):
        try:
            from .llm_judge import TextJudge
            judge = TextJudge()
            lcat, lconf, lreason = judge.judge(running, title, site)
            if lconf > 0:
                signals.append({'category': lcat, 'weight': WEIGHTS['text_llm'], 'confidence': lconf})
            breakdown['text_llm'] = (lcat, lconf, lreason)
        except Exception as e:
            logger.error(f"文本LLM判级失败: {e}")
            breakdown['text_llm'] = ('idle', 0.0, 'error')

    activity, dconf, scores, uncertain = fuse_signals(signals)
    breakdown['fusion'] = (activity, dconf, scores, uncertain)

    if uncertain and (_cfg('enable_vlm', False) or _cfg('enable_server_vision', False)):
        try:
            from .vlm_classifier import VLMClassifier
            if image is None:
                from .capture import capture_screen
                image = capture_screen()
            vlm = VLMClassifier()
            vcat, vconf = vlm.classify(image)
            breakdown['vlm'] = (vcat, vconf, 'fallback')
            if vconf >= CONF_THRESHOLD and vcat in ('study', 'entertainment'):
                activity = vcat
                logger.info(f"VLM兜底判定: {vcat} (置信度 {vconf:.3f})")
        except Exception as e:
            logger.error(f"VLM兜底失败: {e}")
            breakdown['vlm'] = ('idle', 0.0, 'error')

    logger.info(f"融合结果: {activity} (决策置信度 {dconf}) 明细 {breakdown}")
    return activity
