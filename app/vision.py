"""
服务端视觉分析（OCR + 规则判级，多信号融合）。

接收客户端上传的降采样截图（768px JPEG）+ 前台进程 + 窗口标题：
  1. OCR 提取界面文字（灰度/放大/对比度预处理 + psm 6/11 择优）
  2. 融合三个证据：前台进程、窗口标题、OCR 文本 → 判 study/entertainment/idle/unknown
  3. 生产力工具（Docker Desktop/IDE）与开发终端（docker/powershell/cmd/WindowsTerminal/wsl）
     使用组合规则：工具进程 + 标题/OCR 含开发词 → 学习证据，避免把终端一律判学习

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

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

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

# ---- 生产力工具与开发终端规则（服务端融合用）----

# 高置信生产力工具：前台进程是它们 → 直接给学习/生产力证据
PRODUCTIVITY_PROCESSES = [
    "docker desktop", "dockerdesktop", "idea64", "pycharm", "webstorm", "goland",
    "rider", "clion", "datagrip", "phpstorm", "rubymine", "intellij",
    "eclipse", "code.exe", "vscode", "visual studio", "devenv",
    "notepad++", "sublime", "zotero", "obsidian", "typora", "wps", "word", "excel",
    "powerpoint", "onenote", "matlab", "anaconda", "jupyter",
]

# 中性开发工具：本身不等于学习，需标题/OCR 含开发词才给证据
NEUTRAL_DEV_PROCESSES = [
    "docker", "docker.exe", "dockerd", "com.docker.build", "podman",
    "powershell", "powershell.exe", "pwsh", "cmd", "cmd.exe", "conhost",
    "windowsterminal", "windows terminal", "wt.exe", "terminal",
    "wsl", "wsl.exe", "alacritty", "wezterm", "mintty", "git bash", "git-bash",
    "ssh", "ssh.exe", "xshell", "securecrt",
]

# 明确的后台/守护进程：不作为前台活动依据
IGNORED_BACKGROUND_PROCESSES = [
    "com.docker.backend", "com.docker.service", "docker desktop backend",
    "vmmem", "vmms", "wslservice", "wslhost",
]

# 开发/生产力关键词：中性工具命中这些词才算学习证据
DEV_KEYWORDS = [
    "docker", "compose", "kubectl", "helm", "k8s", "kubernetes", "python",
    "npm", "node", "yarn", "pnpm", "git", "pip", "conda", "ssh", "vim",
    "代码", "部署", "镜像", "容器", "编译", "调试", "服务器", "终端",
    "console", "terminal", "command line", "develop", "coding", "program",
]


def _has_dev_keyword(*texts) -> bool:
    joined = " ".join((t or "") for t in texts).lower()
    return any(match_token(joined, k) for k in DEV_KEYWORDS)


def _match_process(process, hints) -> bool:
    p = (process or "").lower()
    return any(h in p for h in hints)


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
    """把 OCR 提取的界面文本判为 study/entertainment/unknown。

    语义统一：无信号返回 unknown（规则未覆盖），不再用 idle 混充"无法判断"。
    返回 (category, confidence, detail)。
    """
    if not text:
        return ("unknown", 0.0, "empty")
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
        return ("unknown", 0.0, f"site={site_cat} no_signal")

    total = study_score + ent_score
    if study_score >= ent_score:
        cat = "study"
        conf = study_score / total
    else:
        cat = "entertainment"
        conf = ent_score / total
    conf = min(conf, 0.95)
    return (cat, round(conf, 3), f"site={site_cat}")


def classify_fused(ocr_text: str, window_title: str = None, process: str = None):
    """融合 前台进程 + 窗口标题 + OCR 文本 三个证据判级。

    返回 (category, confidence, detail)。规则优先级：
      - 后台守护进程（com.docker.backend 等）不参与判定（中性 0 贡献）
      - 高置信生产力工具（Docker Desktop/IDE）→ study 0.90
      - 中性开发工具（docker/powershell/cmd/WindowsTerminal/wsl）→ 仅当标题或 OCR
        含开发词（docker/compose/python/git…）才给 study 0.75；否则 0 贡献
      - 标题与 OCR 文本各自走站点声誉/关键词打分
    三信号按 0.45/0.30/0.25 加权，归一化后取最大类；赢家分 < 0.40 或两可差距 < 0.05
    或总证据为 0 → unknown。
    """
    scores = {"study": 0.0, "entertainment": 0.0}
    total = 0.0
    details = []

    # 1) 进程信号
    p_low = (process or "").lower()
    if p_low and _match_process(p_low, IGNORED_BACKGROUND_PROCESSES):
        details.append(f"proc:{process}=ignored_bg")
    elif p_low and _match_process(p_low, PRODUCTIVITY_PROCESSES):
        scores["study"] += 0.45 * 0.90
        total += 0.45 * 0.90
        details.append(f"proc:{process}=prod")
    elif p_low and _match_process(p_low, NEUTRAL_DEV_PROCESSES):
        if _has_dev_keyword(window_title, ocr_text):
            scores["study"] += 0.45 * 0.75
            total += 0.45 * 0.75
            details.append(f"proc:{process}=dev_tool+keyword")
        else:
            details.append(f"proc:{process}=dev_tool_no_keyword")
    else:
        details.append(f"proc:{process or 'none'}=neutral")

    # 2) 标题信号
    t_cat, t_conf, _ = classify_text(window_title or "") if (window_title or "").strip() else ("unknown", 0.0, "empty_title")
    if t_conf > 0 and t_cat in scores:
        scores[t_cat] += 0.30 * t_conf
        total += 0.30 * t_conf
        details.append(f"title:{window_title}=>{t_cat}/{t_conf}")

    # 3) OCR 文本信号
    o_cat, o_conf, _ = classify_text(ocr_text)
    if o_conf > 0 and o_cat in scores:
        scores[o_cat] += 0.25 * o_conf
        total += 0.25 * o_conf
        details.append(f"ocr:{o_cat}/{o_conf}")

    if total <= 0:
        return ("unknown", 0.0, "|".join(details) or "no_signal")

    norm_study = scores["study"] / total
    norm_ent = scores["entertainment"] / total
    if norm_study >= norm_ent:
        cat, conf = "study", norm_study
    else:
        cat, conf = "entertainment", norm_ent
    conf = min(round(conf, 3), 0.95)
    if conf < 0.40 or abs(norm_study - norm_ent) < 0.05:
        return ("unknown", conf, "|".join(details))
    return (cat, conf, "|".join(details))


def _preprocess_ocr_image(img):
    """OCR 前预处理：灰度 → 2x 放大 → 自动对比度增强，提升小字体/深色界面识别率。"""
    if Image is None:
        return img
    try:
        img = img.convert("L")
        w, h = img.size
        img = img.resize((w * 2, h * 2), Image.LANCZOS)
        img = ImageOps.autocontrast(img)
    except Exception as e:
        logger.warning(f"OCR 图片预处理失败: {e}")
    return img


def ocr_bytes(data: bytes, lang: str = "chi_sim+eng") -> str:
    """对图片字节流做 OCR，返回提取文本；OCR 不可用/失败时返回空串。

    改进：预处理（灰度/放大/对比度）后，分别用 --psm 6（块）与 --psm 11（稀疏文本）
    各跑一次，取识别出文字更多的一次（终端/IDE/小字体界面效果更好）。
    容错：tessdata 缺 chi_sim 时自动回退到 eng，避免整个 OCR 静默失败。
    """
    if pytesseract is None or Image is None:
        logger.warning("pytesseract/PIL 不可用，OCR 不可用")
        return ""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        logger.error(f"图片打开失败: {e}")
        return ""
    img = _preprocess_ocr_image(img)

    best_text = ""
    for psm in ("6", "11"):
        for attempt_lang in (lang, "eng", ""):
            try:
                text = (pytesseract.image_to_string(
                    img, lang=attempt_lang, config=f"--psm {psm}") or "").strip()
            except Exception as e:
                # 降噪：OCR 抛退出码（多半是某种 ps/lang 组合 tesseract 不接）
                # 不影响融合结果（process+title 信号会兜底），仅 debug 留痕
                logger.debug(f"OCR 跳过 psm{psm}/{attempt_lang or 'default'}: {e}")
                continue
            if len(text) > len(best_text):
                best_text = text
    if not best_text:
        logger.debug("OCR 三种语言+两种 psm 都未提取到文本（融合器会靠 process/title 兜底）")
    return best_text


def decode_base64_image(b64: str) -> bytes:
    return base64.b64decode(b64)
