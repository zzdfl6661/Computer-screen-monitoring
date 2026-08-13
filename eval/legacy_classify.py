"""
复刻“优化前”的分类逻辑，用于公平的前后对比。

关键缺陷（即本次要修复的）：
  1. 浏览器进程（chrome/edge/firefox…）被直接列入娱乐进程 → 任何浏览器使用一律娱乐。
  2. 进程匹配为朴素子串（'java' 会误伤编程进程）。
  3. 融合固定权重，模型离线时 process/window 各 0.55，纯 argmax，无置信度阈值。
  4. 窗口标题娱乐关键词优先，无站点/语义区分。
"""
try:
    from config import ConfigManager
except Exception:
    from client_package.config import ConfigManager

config_manager = ConfigManager()

# 原始娱乐进程表（含浏览器 & java，即 bug 来源）
ENTERTAINMENT_PROCESSES = [
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
    "virtualbox", "vmware", "vmwareplayer", "vmwareworkstation",
]

STUDY_PROCESSES = [
    "word", "excel", "powerpoint", "powerpnt", "outlook", "onenote",
    "notepad", "notepad++", "sublime", "sublime text", "vscode", "code",
    "pycharm", "idea", "intellij", "eclipse", "netbeans", "visual studio",
    "adobe reader", "acrobat", "pdf", "pdf reader", "foxit reader",
    "zotero", "endnote", "mendeley", "citavi", "jabref",
    "matlab", "mathematica", "maple", "spss", "sas", "stata",
    "origin", "originpro", "graphpad", "sigmaplot", "chemdraw",
    "autocad", "solidworks", "catia", "ansys", "abaqus",
]


def _simple_analyze(running_processes):
    for proc in running_processes:
        for sp in STUDY_PROCESSES:
            if sp in proc:
                return "study"
        for ep in ENTERTAINMENT_PROCESSES:
            if ep in proc:
                return "entertainment"
    return "idle"


def _analyze_window_title(title):
    low = title.lower()
    ent_kw = config_manager.get('entertainment_keywords') or []
    study_kw = config_manager.get('study_keywords') or []
    for k in ent_kw:
        if k in low:
            return "entertainment"
    for k in study_kw:
        if k in low:
            return "study"
    return "idle"


def _map(label):
    return "entertainment" if label == "entertainment" else (
        "study" if label == "study" else "idle")


def legacy_classify(running_processes, title):
    # 离线（无视觉模型）时，原逻辑把未用的 0.5 权重平分给 process/window
    weights = {"process": 0.55, "window": 0.55}
    results = {
        "process": _simple_analyze(running_processes),
        "window": _analyze_window_title(title),
    }
    scores = {"study": 0.0, "entertainment": 0.0, "idle": 0.0}
    for source, result in results.items():
        if source in weights:
            scores[_map(result)] += weights[source]
    if scores["entertainment"] > scores["study"] and scores["entertainment"] > scores["idle"]:
        return "entertainment"
    elif scores["study"] > scores["entertainment"] and scores["study"] > scores["idle"]:
        return "study"
    else:
        return "idle"
