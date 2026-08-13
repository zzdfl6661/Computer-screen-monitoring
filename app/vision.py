"""
服务端视觉分析（OCR + 规则判级）。

接收客户端上传的降采样截图（384px JPEG）：
  base64 解码 -> Tesseract OCR 提取界面文字 -> 站点声誉/关键词规则判级
  -> 返回 study/entertainment/idle + 置信度。图片与 OCR 文本由路由层入库。

规则列表与客户端 config.json 保持一致（服务端自包含，不依赖 client_package）。
后续可平滑升级为 VLM（qwen2.5vl:3b 等）而无需改动客户端协议。
"""
import base64
import io
import logging
import re

logger = logging.getLogger(__name__)

try:
    import pytesseract
except Exception:
    pytesseract = None

SITE_REPUTATION = {
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

ENTERTAINMENT_KEYWORDS = [
    "game", "games", "gaming", "play", "player", "steam", "epic", "origin",
    "uplay", "battlefield", "call of duty", "csgo", "valorant", "league of legends",
    "lol", "dota", "minecraft", "fortnite", "pubg", "apex", "overwatch",
    "world of warcraft", "wow", "fifa", "nba", "nfl", "mlb", "rocket league",
    "roblox", "among us", "游戏", "minecraft", "网游", "手游", "电竞",
    "王者荣耀", "英雄联盟", "绝地求生", "和平精英", "原神", "崩坏", "阴阳师",
    "第五人格", "我的世界", "穿越火线", "地下城与勇士", "梦幻西游", "问道",
    "剑网3", "天涯明月刀", "逆水寒", "video", "videos", "youtube", "bilibili",
    "netflix", "hulu", "disney+", "hbo", "twitch", "tiktok", "douyin", "kuaishou",
    "抖音", "快手", "爱奇艺", "优酷", "腾讯视频", "芒果tv", "哔哩哔哩", "b站",
    "电影", "电视剧", "综艺", "动漫", "视频", "搞笑", "music", "spotify",
    "apple music", "netease cloud music", "网易云音乐", "qq音乐", "酷狗音乐",
    "酷我音乐", "千千音乐", "虾米音乐", "weibo", "微博", "twitter", "facebook",
    "instagram", "snapchat", "聊天", "社交", "朋友圈", "小红书", "知乎", "贴吧", "论坛",
]

STUDY_KEYWORDS = [
    "study", "studying", "education", "learning", "course", "courses", "lecture",
    "lectures", "class", "classes", "homework", "assignment", "assignments", "exam",
    "exams", "test", "tests", "quiz", "quizzes", "practice", "exercise", "exercises",
    "math", "science", "physics", "chemistry", "biology", "history", "geography",
    "literature", "language", "programming", "coding", "python", "java", "javascript",
    "c++", "html", "css", "database", "algorithm", "tutorial", "tutorials",
    "documentation", "docs", "reference", "research", "paper", "papers", "article",
    "articles", "thesis", "dissertation", "note", "notes", "notebook", "textbook",
    "textbooks", "library", "lib", "university", "college", "school", "student",
    "teacher", "professor", "学习", "作业", "课程", "教材", "课本", "笔记", "复习",
    "预习", "考试", "测验", "练习", "习题", "数学", "物理", "化学", "生物", "历史",
    "地理", "语文", "英语", "政治", "编程", "代码", "开发", "教程", "文档", "论文",
    "研究", "大学", "学院", "学校", "学生", "老师", "教授", "图书馆", "在线教育",
    "慕课", "网课", "直播课", "录播课", "公开课", "精品课", "题库", "真题", "模拟题",
    "押题", "知识点", "考点", "重点", "难点", "学习计划", "学习目标", "学习进度",
    "学习笔记", "学习资料", "学习工具",
]

AMBIGUOUS_SITE_TOKENS = set(SITE_REPUTATION.get("ambiguous", []))


def match_token(text: str, token: str) -> bool:
    """边界感知匹配（与客户端 classify.py 一致）。"""
    if token.isascii():
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z])", text))
    return token in text


def match_site(low_text: str):
    for token in SITE_REPUTATION.get("entertainment", []):
        if token in low_text:
            return "entertainment", token
    for token in SITE_REPUTATION.get("study", []):
        if token in low_text:
            return "study", token
    for token in SITE_REPUTATION.get("ambiguous", []):
        if token in low_text:
            return "ambiguous", token
    return None, None


def classify_text(text: str):
    """把 OCR 提取的界面文本判为 study/entertainment/idle，返回 (category, confidence, detail)。"""
    if not text:
        return ("idle", 0.0, "empty")
    low = text.lower()
    site_cat, site_token = match_site(low)

    ent_hits = [k for k in ENTERTAINMENT_KEYWORDS
                if match_token(low, k) and k not in AMBIGUOUS_SITE_TOKENS]
    study_hits = [k for k in STUDY_KEYWORDS if match_token(low, k)]

    study_score = 0.0
    ent_score = 0.0
    if site_cat == "study":
        study_score += 0.85
    elif site_cat == "entertainment":
        ent_score += 0.85
    elif site_cat == "ambiguous":
        study_score += 0.40
        ent_score += 0.40

    study_score += min(len(study_hits) * 0.30, 0.60)
    ent_score += min(len(ent_hits) * 0.30, 0.60)

    if site_cat == "ambiguous":
        if study_hits and not ent_hits:
            study_score += 0.20
        elif ent_hits and not study_hits:
            ent_score += 0.20

    if study_score == 0 and ent_score == 0:
        return ("idle", 0.0, f"site={site_cat} no_signal")

    total = study_score + ent_score
    if study_score >= ent_score:
        cat = "study"
        conf = study_score / total
    else:
        cat = "entertainment"
        conf = ent_score / total
    conf = min(conf, 0.95)
    return (cat, round(conf, 3), f"site={site_cat}")


def ocr_bytes(data: bytes, lang: str = "chi_sim+eng") -> str:
    """对图片字节流做 OCR，返回提取文本；OCR 不可用/失败时返回空串。"""
    if pytesseract is None:
        logger.warning("pytesseract 未安装，OCR 不可用")
        return ""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        return (pytesseract.image_to_string(img, lang=lang) or "").strip()
    except Exception as e:
        logger.error(f"OCR 失败: {e}")
        return ""


def decode_base64_image(b64: str) -> bytes:
    return base64.b64decode(b64)
