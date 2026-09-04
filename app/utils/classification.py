"""服务端活动归一化规则。

客户端通常已经完成分类，但旧客户端、OCR 无法判断或规则版本不一致时，
服务端仍需要一个保守的最后兜底，避免家长看板被大量 unknown 淹没。
这里只处理有明确进程/标题证据的 unknown；没有证据的记录继续保留 unknown，
供看板诊断和人工标注，不把所有未知强行猜成学习或娱乐。
"""

import re


STUDY_PROCESS_HINTS = (
    "chatgpt", "codex", "openai", "claude", "claudecode", "cursor", "windsurf",
    "copilot", "codeium", "github desktop", "code.exe", "vscode", "visual studio",
    "pycharm", "idea64", "intellij", "eclipse", "devenv", "notepad++", "sublime",
    "docker desktop", "dockerdesktop", "powershell", "pwsh", "windowsterminal",
    "windows terminal", "wt.exe", "cmd.exe", "conhost", "terminal", "wsl",
    "word", "winword", "excel", "powerpoint", "onenote", "notion", "obsidian",
    "typora", "zotero", "adobe reader", "acrobat", "pdf", "matlab", "jupyter",
)

ENTERTAINMENT_PROCESS_HINTS = (
    "steam", "epic", "game", "gaming", "genshin", "honkai", "minecraft", "valorant",
    "league", "dota", "pubg", "fortnite", "roblox", "bilibili", "spotify", "tiktok",
    "douyin", "kuaishou", "qq.exe", "weixin", "wechat", "potplayer", "vlc", "wmplayer",
)

STUDY_TITLE_HINTS = (
    "learningapp", "visual studio", "vs code", "vscode", "powershell", "terminal", "命令提示符",
    "python", "docker", "compose", "代码", "开发", "调试", "项目", "课程", "学习", "作业",
    "论文", "文档", "教程", "题库", "notebook", "chatgpt", "codex", "claude", "cursor",
)

ENTERTAINMENT_TITLE_HINTS = (
    "steam", "游戏", "网游", "手游", "电竞", "抖音", "快手", "短视频", "bilibili", "哔哩哔哩",
    "youtube", "netflix", "爱奇艺", "优酷", "腾讯视频", "芒果tv", "电视剧", "综艺", "动漫",
    "音乐", "spotify", "qq音乐", "酷狗", "电影",
)


def _contains_token(value: str, hints) -> bool:
    text = (value or "").lower()
    for hint in hints:
        hint = hint.lower()
        if hint.isascii():
            if re.search(r"(?<![a-z0-9])" + re.escape(hint) + r"(?![a-z])", text):
                return True
        elif hint in text:
            return True
    return False


def infer_activity(process: str = None, title: str = None):
    """从明确的进程/标题证据推断活动，返回 (activity, source) 或 (None, None)。"""
    if _contains_token(process, STUDY_PROCESS_HINTS):
        return "study", "process_fallback"
    if _contains_token(process, ENTERTAINMENT_PROCESS_HINTS):
        return "entertainment", "process_fallback"

    # 标题只接受强特征，避免普通网页标题的偶然词命中。
    if _contains_token(title, STUDY_TITLE_HINTS):
        return "study", "title_fallback"
    if _contains_token(title, ENTERTAINMENT_TITLE_HINTS):
        return "entertainment", "title_fallback"
    return None, None


def normalize_unknown(activity: str, process: str = None, title: str = None):
    """只把有明确证据的 unknown 归一化；无证据仍返回 unknown。"""
    if activity != "unknown":
        return activity, None, None
    inferred, source = infer_activity(process, title)
    if inferred:
        return inferred, source, "normalized_unknown"
    return "unknown", None, None


def guard_productivity_result(activity: str, process: str = None):
    """防止 OCR 把明确的生产力进程误报成娱乐。"""
    if activity == "entertainment" and _contains_token(process, STUDY_PROCESS_HINTS):
        return "study", "process_guard", "productivity_process_guard"
    return activity, None, None


def normalize_existing_unknowns(db) -> int:
    """回填历史 unknown，返回修改行数；可重复执行且幂等。"""
    from ..models import ActivityLog

    messages = {
        "study": "继续保持学习状态！",
        "entertainment": "你正在娱乐，请切换到学习！",
    }
    changed = 0
    rows = db.query(ActivityLog).filter(ActivityLog.activity == "unknown").all()
    for row in rows:
        activity, source, reason = normalize_unknown(row.activity, row.process, row.title)
        if source:
            row.activity = activity
            row.message = messages[activity]
            row.decision_source = source
            row.reason = reason
            changed += 1
    if changed:
        db.commit()
    return changed


def correct_productivity_misclassifications(db) -> int:
    """纠正历史上明确生产力进程被 OCR 写成 entertainment 的记录。"""
    from ..models import ActivityLog

    changed = 0
    rows = db.query(ActivityLog).filter(ActivityLog.activity == "entertainment").all()
    for row in rows:
        activity, source, reason = guard_productivity_result(row.activity, row.process)
        if source:
            row.activity = activity
            row.message = "继续保持学习状态！"
            row.decision_source = source
            row.reason = reason
            changed += 1
    if changed:
        db.commit()
    return changed
