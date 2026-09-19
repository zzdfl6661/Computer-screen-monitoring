"""
服务端视觉分析（OCR + 规则判级，多信号融合）。

接收客户端上传的降采样截图（768px JPEG）+ 前台进程 + 窗口标题：
  1. OCR 提取界面文字（RapidOCR 主路径，对中文截图 UI/深色主题/小字体识别率远高于
     tesseract；回退 pytesseract psm 6/11 择优 + chi_sim→eng 语言回退）
  2. 融合三个证据：前台进程、窗口标题、OCR 文本 → 判 study/entertainment/idle/unknown
  3. 生产力工具（Docker Desktop/IDE）与开发终端（docker/powershell/cmd/WindowsTerminal/wsl）
     使用组合规则：工具进程 + 标题/OCR 含开发词 → 学习证据，避免把终端一律判学习

规则列表与客户端 config.json 保持一致（服务端自包含，不依赖 client_package）。
后续可平滑升级为 VLM（qwen2.5vl:3b 等）而无需改动客户端协议。
"""
import base64
import io
import json
import logging
import os
import re
import urllib.request

logger = logging.getLogger(__name__)

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from rapidocr_onnxruntime import RapidOCR
    _rapidocr = RapidOCR()
except Exception as exc:
    # 不再静默降级：依赖缺失时启动日志必须明确说明实际会使用 Tesseract。
    logger.warning("RapidOCR 初始化失败，将回退 Tesseract: %s", exc)
    _rapidocr = None

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None


def active_ocr_engine() -> str:
    """返回服务端当前真正可用的 OCR 引擎，供启动日志和健康检查诊断。"""
    if _rapidocr is not None:
        return "rapidocr"
    if pytesseract is not None and Image is not None:
        return "tesseract"
    return "unavailable"

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
        "网易云音乐", "qq音乐", "酷狗", "酷我", "steam", "epic",
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
    "game", "games", "gaming", "play", "player", "steam", "epic",
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
# 这些词常出现在本系统自己的看板、提示和导航中，单独出现不是内容分类证据。
GENERIC_OCR_UI_TOKENS = {"学习", "娱乐", "活动", "状态", "监控", "提醒", "继续"}

# ---- 学科分类（subject）：对已判为 study 的文本再细分学科 ----
# 只收"能指认学科"的词，通用学习词（课程/作业/学习…）不进表；负向短语先剔除，
# 避免"历史记录/浏览历史"这类 UI 词把网页误标成历史学科。
SUBJECT_KEYWORDS = {
    "math": [
        "数学", "函数", "方程", "几何", "代数", "微积分", "导数", "三角函数",
        "正弦", "余弦", "正切", "概率", "统计", "数列", "向量", "不等式",
        "因式分解", "二次函数", "圆锥曲线", "立体几何", "线性代数", "高等数学", "奥数",
        "math", "mathematics", "algebra", "geometry", "calculus", "trigonometry",
        "arithmetic", "equation", "probability", "wolfram", "geogebra", "desmos",
    ],
    "programming": [
        "编程", "代码", "程序设计", "算法", "数据结构", "前端", "后端", "全栈",
        "机器学习", "深度学习", "人工智能",
        "python", "java", "javascript", "typescript", "c++", "c#", "golang",
        "rust", "php", "ruby", "swift", "kotlin", "html", "css", "sql", "mysql",
        "mongodb", "redis", "git", "github", "gitlab", "leetcode", "力扣",
        "linux", "docker", "kubernetes", "numpy", "pandas", "django", "flask",
        "spring", "vue", "react", "node", "npm", "pip", "scratch",
    ],
    "chinese": [
        "语文", "文言文", "古诗文", "古诗", "阅读理解", "作文", "造句", "拼音",
        "汉字", "成语", "病句", "修辞", "散文", "记叙文", "议论文", "唐诗",
        "宋词", "诗歌鉴赏", "名著导读", "现代文",
    ],
    "english": [
        "英语", "英文", "grammar", "vocabulary", "ielts", "toefl",
        "四级", "六级", "雅思", "托福", "新概念", "口语", "听力", "语法", "单词",
    ],
    "physics": [
        "物理", "力学", "电磁", "光学", "热学", "声学", "电路", "牛顿定律",
        "相对论", "physics", "mechanics", "electromagnetism",
    ],
    "chemistry": [
        "化学", "元素周期表", "分子式", "化学方程", "有机化学", "无机化学",
        "滴定", "chemistry", "chemical",
    ],
    "biology": [
        "生物", "细胞", "基因", "光合作用", "呼吸作用", "遗传", "生态系统",
        "新陈代谢", "biology", "genetics", "dna", "rna",
    ],
    "history": [
        "历史", "历史课", "朝代", "古代史", "近代史", "现代史", "世界史",
        "中国史", "辛亥革命", "工业革命", "文艺复兴", "history",
    ],
    "geography": [
        "地理", "地图", "经纬度", "经度", "纬度", "气候", "地形", "板块",
        "洋流", "geography",
    ],
    "politics": [
        "政治", "思想品德", "道德与法治", "哲学", "马原", "毛概",
    ],
}

# 命中前先从文本中剔除：这些 UI 复合词包含学科关键字，但不是学科内容
SUBJECT_NEGATIVE_PHRASES = ["历史记录", "浏览历史", "清除历史", "搜索历史", "历史版本"]

SUBJECT_LABELS = {
    "math": "数学", "programming": "编程", "chinese": "语文", "english": "英语",
    "physics": "物理", "chemistry": "化学", "biology": "生物", "history": "历史",
    "geography": "地理", "politics": "政治",
}


def classify_subject(text: str):
    """按学科关键词带权打分，返回 (subject, confidence)；无信号或平手返回 (None, 0.0)。

    subject 取值见 SUBJECT_KEYWORDS 的键（math/programming/chinese/...），
    展示名见 SUBJECT_LABELS。仅供 activity=study 的记录细分，不影响主判定。
    """
    if not text:
        return (None, 0.0)
    low = text.lower()
    for phrase in SUBJECT_NEGATIVE_PHRASES:
        low = low.replace(phrase, " ")
    scores = {}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        hits = [k for k in keywords if match_token(low, k)]
        if hits:
            scores[subject] = len(hits)
    if not scores:
        return (None, 0.0)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    if best_score <= second_score:
        return (None, 0.0)  # 两个学科命中数打平 → 学科不明确
    conf = best_score / (best_score + second_score)
    return (best, round(min(conf, 0.95), 3))

# ---- 生产力工具与开发终端规则（服务端融合用）----

# 高置信生产力工具：前台进程是它们 → 直接给学习/生产力证据
PRODUCTIVITY_PROCESSES = [
    "docker desktop", "dockerdesktop", "idea64", "pycharm", "webstorm", "goland",
    "rider", "clion", "datagrip", "phpstorm", "rubymine", "intellij",
    "eclipse", "code.exe", "vscode", "visual studio", "devenv",
    "notepad++", "sublime", "zotero", "obsidian", "typora", "wps", "word", "excel",
    "powerpoint", "onenote", "matlab", "anaconda", "jupyter",
    # AI 编程/学习助手与前台开发终端：不能因为 OCR 看到了“娱乐”字样就误报
    "chatgpt", "codex", "openai", "claude", "claudecode", "cursor", "windsurf",
    "copilot", "codeium", "github desktop", "powershell", "pwsh", "windowsterminal",
    "windows terminal", "wt.exe", "cmd.exe", "conhost", "terminal", "wsl",
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
                if match_token(low, k) and k not in AMBIGUOUS_SITE_TOKENS and k not in GENERIC_OCR_UI_TOKENS]
    study_hits = [k for k in STUDY_KEYWORDS
                  if match_token(low, k) and k not in GENERIC_OCR_UI_TOKENS]

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

    # 两栖站无关键词佐证 → 打平，不默认判 study（与客户端 classify.py 一致）
    if abs(study_score - ent_score) < 1e-9:
        return ("unknown", 0.0, f"site={site_cat} ambiguous_tie")

    total = study_score + ent_score
    if study_score >= ent_score:
        cat = "study"
        conf = study_score / total
    else:
        cat = "entertainment"
        conf = ent_score / total
    conf = min(conf, 0.95)
    return (cat, round(conf, 3), f"site={site_cat}")


def classify_fused(ocr_text: str, window_title: str = None, process: str = None, db=None):
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
    # 数据库规则优先于静态兼容规则：管理台调整后无需改代码。
    if db is not None:
        try:
            from .rule_engine import match_rule
            matched = match_rule(db, process=process, title=window_title, ocr_text=ocr_text)
            if matched:
                return (matched[0], 0.98, f"db_rule:priority={matched[1]}")
        except Exception as exc:
            logger.warning("数据库规则匹配失败，回退内置规则: %s", exc)

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

    引擎优先级：RapidOCR（onnx，中文截图 UI 识别率远高于 tesseract，pip 即装，
    无需系统级 tesseract 二进制与 chi_sim 训练数据）→ 回退 pytesseract（psm 6/11
    择优 + chi_sim→eng 语言回退）。两者都不可用时融合器靠 process/title 兜底。
    """
    # 1) RapidOCR 主路径：直接吃 JPEG 字节解码后的 ndarray，无需 PIL 预处理
    #    （RapidOCR 内部自带 det+rec+多语言，对深色主题/小字体友好）
    if _rapidocr is not None:
        try:
            import numpy as np
            import cv2
            arr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                result, _ = _rapidocr(img)
                texts = [r[1] for r in (result or []) if r and r[1]]
                joined = " ".join(texts).strip()
                if joined:
                    return joined
                logger.debug("RapidOCR 未提取到文本，回退 pytesseract")
        except Exception as e:
            logger.warning(f"RapidOCR 失败，回退 pytesseract: {e}")

    # 2) pytesseract 回退路径（需要系统安装 tesseract + chi_sim 训练数据）
    if pytesseract is None or Image is None:
        logger.debug("pytesseract/PIL 不可用，OCR 返回空（融合器靠 process/title 兜底）")
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
                logger.debug(f"OCR 跳过 psm{psm}/{attempt_lang or 'default'}: {e}")
                continue
            if len(text) > len(best_text):
                best_text = text
    return best_text


def decode_base64_image(b64: str) -> bytes:
    return base64.b64decode(b64)


# ---- 云端多模态兜底（VLM）：OCR 无文字/判不出的界面，用看图判定补齐 ----
# 配置走环境变量（未配置 VLM_API_KEY 时整条路径自动关闭，行为与旧版一致）：
#   VLM_API_KEY   必填才启用；GLM/Qwen/OpenAI 兼容接口均可
#   VLM_BASE_URL  默认智谱 https://open.bigmodel.cn/api/paas/v4（glm-4v-flash 免费）
#   VLM_MODEL     默认 glm-4v-flash
#   VLM_TIMEOUT   单次请求超时秒数，默认 25
BROWSER_PROCESS_HINTS = [
    "chrome", "chromium", "msedge", "edge", "firefox", "opera", "brave",
    "vivaldi", "browser", "360se", "360chrome", "qqbrowser", "sogouexplorer",
    "liebao", "iexplore", "maxthon",
]
# 同名冲突进程（java 既是 IDE 也是 Minecraft）：不能按进程沉淀规则，只按标题
AMBIGUOUS_VLM_PROC_HINTS = ["java", "javaw", "origin"]

VLM_PROMPT = (
    "你是青少年电脑使用监控的判定助手。请根据这张电脑屏幕截图判断使用者当前"
    "在学习还是娱乐。玩游戏（包括没有文字的全屏游戏画面）、看娱乐视频、刷短视频、"
    "聊天、听歌属于 entertainment；上课、写作业、看教材课件、编程、查资料属于 study；"
    "锁屏/纯桌面/待机属于 idle；画面确实无法判断时用 unknown。"
    "只输出一个 JSON 对象，不要输出其他内容："
    '{"activity": "study|entertainment|idle|unknown", '
    '"confidence": 0到1的小数, '
    '"subject": "math|programming|chinese|english|physics|chemistry|biology|'
    'history|geography|politics 或 null（仅 study 时填写）", '
    '"reason": "不超过20字的中文理由"}'
)


def vlm_configured() -> bool:
    return bool(os.getenv("VLM_API_KEY", "").strip())


def classify_vlm(image_bytes: bytes, window_title: str = None, process: str = None):
    """云端多模态 API 判级（OpenAI 兼容 /chat/completions 协议）。

    返回 (activity, confidence, raw_content)；未配置、请求失败或输出不可解析时
    返回 (None, 0.0, 错误说明)。调用方需自行做缓存与节流控制成本。
    """
    api_key = os.getenv("VLM_API_KEY", "").strip()
    if not api_key or not image_bytes:
        return (None, 0.0, "vlm_not_configured")
    base_url = (os.getenv("VLM_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
    model = os.getenv("VLM_MODEL") or "glm-4v-flash"
    timeout = float(os.getenv("VLM_TIMEOUT") or "25")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    hint = ""
    if process or window_title:
        hint = f"\n辅助信息（仅供参考，以画面为准）——前台进程: {process or '未知'}，窗口标题: {window_title or '无'}"
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": VLM_PROMPT + hint},
            ],
        }],
        "temperature": 0.1,
        "max_tokens": 300,
    }
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = (data["choices"][0].get("message") or {}).get("content") or ""
    except Exception as exc:
        logger.warning("VLM 判定失败: %s", exc)
        return (None, 0.0, f"vlm_error:{exc}")

    activity, confidence, subject = _parse_vlm_content(content)
    if activity is None:
        logger.warning("VLM 输出不可解析: %r", content[:200])
        return (None, 0.0, "vlm_unparseable")
    return (activity, confidence, json.dumps(
        {"activity": activity, "confidence": confidence, "subject": subject,
         "reason": content}, ensure_ascii=False))


def _parse_vlm_content(content: str):
    """从 VLM 回复中稳健提取 JSON（容忍 markdown 代码块/前后缀文本）。"""
    text = (content or "").strip()
    if "```" in text:  # 去掉 ```json ... ``` 围栏
        parts = text.split("```")
        text = max(parts, key=len) if len(parts) > 1 else text
        text = text.replace("json", "", 1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return (None, 0.0, None)
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return (None, 0.0, None)
    activity = obj.get("activity")
    if activity not in ("study", "entertainment", "idle", "unknown"):
        return (None, 0.0, None)
    try:
        confidence = max(0.0, min(1.0, float(obj.get("confidence") or 0.0)))
    except (TypeError, ValueError):
        confidence = 0.0
    subject = obj.get("subject")
    if subject not in SUBJECT_KEYWORDS:
        subject = None
    return (activity, round(confidence, 3), subject)
