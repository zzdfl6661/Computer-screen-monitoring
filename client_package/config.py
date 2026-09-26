import json
import os

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

try:
    from cryptography.exceptions import InvalidToken
except ImportError:
    InvalidToken = Exception

KEY_FILE = '.encryption_key'
ENCRYPTED_FIELDS = ['device_token', 'access_token']

def _generate_key():
    return Fernet.generate_key()

def _load_or_create_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'rb') as f:
            return f.read()
    else:
        key = _generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
        return key

def encrypt_config(value, key=None):
    if key is None:
        key = _load_or_create_key()
    if Fernet is None:
        return value
    fernet = Fernet(key)
    return fernet.encrypt(value.encode()).decode()

def decrypt_config(encrypted_value, key=None):
    if not encrypted_value:
        return ''
    if key is None:
        key = _load_or_create_key()
    if Fernet is None:
        return encrypted_value
    fernet = Fernet(key)
    try:
        return fernet.decrypt(encrypted_value.encode()).decode()
    except InvalidToken:
        return ''

class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.key = _load_or_create_key()
        self.config = self._load_config()

    def _load_config(self):
        default_config = {
            'check_interval': 5,
            'server_url': 'http://127.0.0.1:5000/check_activity',
            'device_token': '',
            'access_token': '',
            'entertainment_keywords': [
                'game', 'games', 'gaming', 'play', 'player', 'steam', 'epic', 'origin', 'uplay',
                'battlefield', 'call of duty', 'csgo', 'valorant', 'league of legends', 'lol',
                'dota', 'minecraft', 'fortnite', 'pubg', 'apex', 'overwatch', 'world of warcraft',
                'wow', 'fifa', 'nba', 'nfl', 'mlb', 'rocket league', 'roblox', 'among us',
                '游戏', '网游', '手游', '电竞', '王者荣耀', '英雄联盟', '绝地求生', '和平精英',
                '原神', '崩坏', '阴阳师', '第五人格', '我的世界', '穿越火线', '地下城与勇士',
                '梦幻西游', '问道', '剑网3', '天涯明月刀', '逆水寒',
                'video', 'videos', 'youtube', 'bilibili', 'netflix', 'hulu', 'disney+', 'hbo',
                'twitch', 'tiktok', 'douyin', 'kuaishou', '抖音', '快手', '爱奇艺', '优酷',
                '腾讯视频', '芒果tv', '哔哩哔哩', 'b站', '电影', '电视剧', '综艺', '动漫',
                'music', 'spotify', 'apple music', 'netease cloud music', '网易云音乐',
                'qq音乐', '酷狗音乐', '酷我音乐', '千千音乐', '虾米音乐',
                'weibo', '微博', 'twitter', 'facebook', 'instagram', 'tiktok', 'snapchat',
                '聊天', '社交', '朋友圈', '微博', '小红书', '知乎', '贴吧', '论坛'
            ],
            'study_keywords': [
                'study', 'studying', 'education', 'learning', 'course', 'courses', 'lecture',
                'lectures', 'class', 'classes', 'homework', 'assignment', 'assignments',
                'exam', 'exams', 'test', 'tests', 'quiz', 'quizzes', 'practice', 'exercise',
                'exercises', 'math', 'science', 'physics', 'chemistry', 'biology', 'history',
                'geography', 'literature', 'language', 'programming', 'coding', 'python',
                'java', 'javascript', 'c++', 'html', 'css', 'database', 'algorithm',
                'tutorial', 'tutorials', 'documentation', 'docs', 'reference', 'research',
                'paper', 'papers', 'article', 'articles', 'thesis', 'dissertation',
                'note', 'notes', 'notebook', 'textbook', 'textbooks', 'library', 'lib',
                'university', 'college', 'school', 'student', 'teacher', 'professor',
                '学习', '作业', '课程', '教材', '课本', '笔记', '复习', '预习', '考试',
                '测验', '练习', '习题', '数学', '物理', '化学', '生物', '历史', '地理',
                '语文', '英语', '政治', '编程', '代码', '开发', '教程', '文档', '论文',
                '研究', '大学', '学院', '学校', '学生', '老师', '教授', '图书馆',
                '在线教育', '慕课', '网课', '直播课', '录播课', '公开课', '精品课',
                '题库', '真题', '模拟题', '押题', '知识点', '考点', '重点', '难点',
                '学习计划', '学习目标', '学习进度', '学习笔记', '学习资料', '学习工具'
            ],
            'enable_server_vision': True,
            # ImageNet-B0 影子探针：只记录 Top-K，不参与学习/娱乐判定。
            # 等使用真实截图微调出 game/non-game 权重并完成验证后再启用决策。
            'enable_efficientnet_probe': False,
            'vision_min_interval': 30,
        }
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                for key, value in loaded_config.items():
                    if key in ENCRYPTED_FIELDS:
                        default_config[key] = decrypt_config(value, self.key)
                    else:
                        default_config[key] = value
        except FileNotFoundError:
            pass
        
        return default_config

    def save_config(self):
        config_to_save = {}
        for key, value in self.config.items():
            if key in ENCRYPTED_FIELDS:
                config_to_save[key] = encrypt_config(value, self.key) if value else ''
            else:
                config_to_save[key] = value
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
