"""服务端规则缓存：数据库为唯一运行来源，静态列表只用于补充预置。"""
import time
from sqlalchemy.orm import Session

from .models import ClassificationRule

_CACHE_SECONDS = 30
_cache = {"at": 0.0, "rules": []}

# 只使用足够具体的进程/域名做高置信度匹配；通用中文词仅保留为低优先级标题线索。
# 预置覆盖依据公开的 Windows 游戏进程汇总、编程学习资源清单和在线课程分类整理，
# 但实际运行始终以数据库中的规则为准。
_ENTERTAINMENT_PROCESSES = [
    # 启动器与游戏平台
    "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "riotclientservices.exe",
    "riotclientux.exe", "battle.net.exe", "blizzard.exe", "eadesktop.exe", "origin.exe",
    "upc.exe", "ubisoftconnect.exe", "galaxyclient.exe", "goggalaxy.exe", "xboxpcapp.exe",
    "gamebar.exe", "gamebarftserver.exe", "wargaminggamecenter.exe", "hoyoplay.exe",
    "wegame.exe", "taptap.exe",
    # 常见游戏
    "valorant-win64-shipping.exe", "leagueclient.exe", "league of legends.exe", "dota2.exe",
    "cs2.exe", "csgo.exe", "minecraft.exe", "minecraftlauncher.exe", "robloxplayerbeta.exe",
    "genshinimpact.exe", "yuan shen.exe", "starrail.exe", "zenlesszonezero.exe", "overwatch.exe",
    "fortniteclient-win64-shipping.exe", "pubg.exe", "rainbowsix.exe", "r5apex.exe",
    "fallguys_client_game.exe", "among us.exe", "terraria.exe", "stardew valley.exe",
    "palworld-win64-shipping.exe", "eldenring.exe", "gta5.exe", "reddeadredemption2.exe",
    "worldoftanks.exe", "worldofwarcraft.exe", "ffxiv_dx11.exe", "wechatgames.exe",
    # 视频、直播与音乐桌面端
    "bilibili.exe", "douyin.exe", "kwai.exe", "iqiyi.exe", "youku.exe", "tencentvideo.exe",
    "huya.exe", "douyu.exe", "spotify.exe", "cloudmusic.exe", "qqmusic.exe", "kugou.exe", "kuwo.exe",
]

_ENTERTAINMENT_DOMAINS = [
    # 视频、直播、音乐与社区
    "bilibili.com", "b23.tv", "youtube.com", "youtu.be", "tiktok.com", "douyin.com", "kuaishou.com",
    "kwai.com", "twitch.tv", "netflix.com", "disneyplus.com", "hulu.com", "max.com", "primevideo.com",
    "iqiyi.com", "youku.com", "v.qq.com", "mgtv.com", "huya.com", "douyu.com", "weibo.com",
    "xiaohongshu.com", "tieba.baidu.com", "reddit.com", "instagram.com", "facebook.com", "twitter.com",
    "x.com", "discord.com", "spotify.com", "music.163.com", "y.qq.com",
    # 游戏站点与商店
    "steampowered.com", "steamcommunity.com", "epicgames.com", "riotgames.com", "ea.com", "ubisoft.com",
    "gog.com", "xbox.com", "hoyoverse.com", "mihoyo.com", "taptap.cn", "wegame.com",
]

_ENTERTAINMENT_TITLES = [
    "王者荣耀", "英雄联盟", "无畏契约", "瓦罗兰特", "原神", "崩坏", "绝地求生", "和平精英",
    "我的世界", "赛博朋克", "艾尔登法环", "游戏大厅", "直播", "番剧", "动漫", "电影", "电视剧",
    "哔哩哔哩", "抖音", "快手", "网易云音乐", "QQ音乐", "Steam 商店",
]

_STUDY_PROCESSES = [
    # 编辑器与 IDE
    "code.exe", "cursor.exe", "windsurf.exe", "zed.exe", "sublime_text.exe", "atom.exe", "pycharm64.exe",
    "idea64.exe", "webstorm64.exe", "goland64.exe", "clion64.exe", "rider64.exe", "datagrip64.exe",
    "studio64.exe", "devenv.exe", "eclipse.exe", "rstudio.exe", "matlab.exe", "octave-gui.exe",
    # 办公、阅读、知识管理与学习工具
    "winword.exe", "excel.exe", "powerpnt.exe", "onenote.exe", "wps.exe", "et.exe", "wpp.exe",
    "notepad++.exe", "typora.exe", "obsidian.exe", "notion.exe", "zotero.exe", "mendeley.exe",
    "calibre.exe", "anki.exe", "xmind.exe", "mindmanager.exe", "acrobat.exe", "acrord32.exe",
    "sumatrapdf.exe", "foxitpdfreader.exe",
]

_STUDY_DOMAINS = [
    # 开发、文档与知识库
    "github.com", "gitlab.com", "bitbucket.org", "stackoverflow.com", "stackexchange.com", "superuser.com",
    "serverfault.com", "wikipedia.org", "wikibooks.org", "wikiversity.org", "mdn.mozilla.org",
    "developer.mozilla.org", "docs.python.org", "learn.microsoft.com", "docs.oracle.com", "w3schools.com",
    "readthedocs.io", "npmjs.com", "pypi.org", "rubygems.org", "crates.io",
    # 编程练习与在线课程
    "freecodecamp.org", "codecademy.com", "theodinproject.com", "exercism.org", "codewars.com",
    "hackerrank.com", "leetcode.com", "kaggle.com", "coursera.org", "edx.org", "udemy.com", "udacity.com",
    "khanacademy.org", "ocw.mit.edu", "openstax.org", "brilliant.org", "duolingo.com", "moodle.org",
    "classroom.google.com", "icourse163.org", "mooc.cn", "xuetangx.com", "chaoxing.com", "zhihuishu.com",
    "study.163.com", "open.163.com",
    # 学术检索、论文与资料库
    "arxiv.org", "doi.org", "semanticscholar.org", "researchgate.net", "scholar.google.com",
    "pubmed.ncbi.nlm.nih.gov", "cnki.net", "wanfangdata.com.cn", "cqvip.com", "dblp.org", "openreview.net",
    "xueshu.baidu.com", "wenku.baidu.com", "jstor.org", "springer.com", "sciencedirect.com", "nature.com",
]

_STUDY_TITLES = [
    "课程", "作业", "题库", "习题", "学习", "复习", "考试", "论文", "文档", "教材", "笔记",
    "Visual Studio Code", "PyCharm", "IntelliJ", "Jupyter", "Notebook", "GitHub", "LeetCode",
    "Stack Overflow", "开发者文档", "在线课堂", "慕课", "实验报告",
]

_DEFAULTS = (
    [("entertainment", "process", "exact", x, 900) for x in _ENTERTAINMENT_PROCESSES]
    + [("study", "process", "exact", x, 900) for x in _STUDY_PROCESSES]
    + [("entertainment", "domain", "domain", x, 700) for x in _ENTERTAINMENT_DOMAINS]
    + [("study", "domain", "domain", x, 700) for x in _STUDY_DOMAINS]
    + [("entertainment", "title", "contains", x, 300) for x in _ENTERTAINMENT_TITLES]
    + [("study", "title", "contains", x, 300) for x in _STUDY_TITLES]
)


def seed_default_rules(db: Session):
    """幂等补齐官方预置，不覆盖、更新或删除数据库中已有规则。"""
    existing = {
        (r.activity, r.signal_type, r.match_type, r.pattern.strip().lower())
        for r in db.query(ClassificationRule).all()
    }
    additions, seen = [], set()
    for activity, signal_type, match_type, pattern, priority in _DEFAULTS:
        key = (activity, signal_type, match_type, pattern.strip().lower())
        if key not in existing and key not in seen:
            additions.append(ClassificationRule(
                activity=activity, signal_type=signal_type, match_type=match_type,
                pattern=pattern, priority=priority,
            ))
            seen.add(key)
    if additions:
        db.add_all(additions)
        db.commit()
        invalidate()
    return len(additions)


def invalidate():
    _cache["at"] = 0.0


def _rules(db: Session):
    now = time.monotonic()
    if now - _cache["at"] > _CACHE_SECONDS:
        _cache["rules"] = db.query(ClassificationRule).filter(
            ClassificationRule.enabled == 1).order_by(ClassificationRule.priority.desc(), ClassificationRule.id.asc()).all()
        _cache["at"] = now
    return _cache["rules"]


def match_rule(db: Session, process: str = "", title: str = "", ocr_text: str = "", domain: str = ""):
    """返回最高优先级规则的 (activity, priority)，无命中返回 None。"""
    values = {"process": (process or "").lower(), "title": (title or "").lower(),
              "ocr": (ocr_text or "").lower(), "domain": (domain or "").lower()}
    for rule in _rules(db):
        value = values.get(rule.signal_type, "")
        pattern = rule.pattern.lower().strip()
        if not value or not pattern:
            continue
        hit = value == pattern if rule.match_type == "exact" else (
            value == pattern or value.endswith("." + pattern) if rule.match_type == "domain" else pattern in value)
        if hit:
            return rule.activity, rule.priority
    return None
