import sqlite3
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name='activity_logs.db'):
        self.db_name = db_name
        self.connection = None
        self._connect()
        self._init_tables()

    def _connect(self):
        self.connection = sqlite3.connect(self.db_name, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def _init_tables(self):
        cursor = self.connection.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                activity TEXT NOT NULL,
                message TEXT,
                source TEXT
            )
        ''')
        self.connection.commit()

    def add_log(self, activity, message=None, source=None):
        cursor = self.connection.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO activity_logs (timestamp, activity, message, source)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, activity, message, source))
        self.connection.commit()
        return cursor.lastrowid

    def get_all_logs(self, limit=None, offset=None):
        cursor = self.connection.cursor()
        query = 'SELECT * FROM activity_logs ORDER BY timestamp DESC'
        params = []
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)
        if offset is not None:
            query += ' OFFSET ?'
            params.append(offset)
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_logs_by_activity(self, activity, limit=None):
        cursor = self.connection.cursor()
        query = 'SELECT * FROM activity_logs WHERE activity = ? ORDER BY timestamp DESC'
        params = [activity]
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def delete_log(self, log_id):
        cursor = self.connection.cursor()
        cursor.execute('DELETE FROM activity_logs WHERE id = ?', (log_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def clear_all_logs(self):
        cursor = self.connection.cursor()
        cursor.execute('DELETE FROM activity_logs')
        self.connection.commit()

    def get_today_stats(self):
        cursor = self.connection.cursor()
        today_date = datetime.now().date().isoformat()
        cursor.execute('''
            SELECT activity, COUNT(*) as count 
            FROM activity_logs 
            WHERE timestamp LIKE ? 
            GROUP BY activity
        ''', (f'{today_date}%',))
        results = {row['activity']: row['count'] for row in cursor.fetchall()}
        
        study_count = results.get('study', 0)
        entertainment_count = results.get('entertainment', 0)
        
        cursor.execute('SELECT COUNT(*) as total FROM activity_logs')
        total_count = cursor.fetchone()['total']
        
        return {
            'study_count': study_count,
            'entertainment_count': entertainment_count,
            'total_count': total_count
        }
    
    def get_activity_distribution(self, start_date=None, end_date=None):
        cursor = self.connection.cursor()
        query = '''
            SELECT activity, COUNT(*) as count 
            FROM activity_logs 
            WHERE 1=1
        '''
        params = []
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        query += ' GROUP BY activity'
        cursor.execute(query, params)
        return {row['activity']: row['count'] for row in cursor.fetchall()}
    
    def get_time_trend(self, hours=24):
        cursor = self.connection.cursor()
        now = datetime.now()
        start_time = (now - datetime.timedelta(hours=hours)).isoformat()
        
        cursor.execute('''
            SELECT timestamp, activity 
            FROM activity_logs 
            WHERE timestamp >= ? 
            ORDER BY timestamp ASC
        ''', (start_time,))
        
        logs = [dict(row) for row in cursor.fetchall()]
        
        study_data = []
        entertainment_data = []
        labels = []
        
        if logs:
            current_hour = None
            study_count = 0
            entertainment_count = 0
            
            for log in logs:
                log_time = datetime.fromisoformat(log['timestamp'])
                hour_key = log_time.strftime('%Y-%m-%d %H:00')
                
                if current_hour and hour_key != current_hour:
                    labels.append(current_hour)
                    study_data.append(study_count)
                    entertainment_data.append(entertainment_count)
                    study_count = 0
                    entertainment_count = 0
                
                current_hour = hour_key
                if log['activity'] == 'study':
                    study_count += 1
                elif log['activity'] == 'entertainment':
                    entertainment_count += 1
            
            if current_hour:
                labels.append(current_hour)
                study_data.append(study_count)
                entertainment_data.append(entertainment_count)
        
        return {
            'labels': labels,
            'study_data': study_data,
            'entertainment_data': entertainment_data
        }
    
    def search_logs(self, activity=None, keyword=None, start_date=None, end_date=None):
        cursor = self.connection.cursor()
        query = 'SELECT * FROM activity_logs WHERE 1=1'
        params = []
        
        if activity:
            query += ' AND activity = ?'
            params.append(activity)
        
        if keyword:
            query += ' AND (message LIKE ? OR source LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%'])
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        query += ' ORDER BY timestamp DESC'
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        if self.connection:
            self.connection.close()


class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self):
        default_config = {
            'check_interval': 5,
            'server_url': 'http://localhost:5000/check_activity',
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
            ]
        }
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                default_config.update(loaded_config)
        except FileNotFoundError:
            pass
        
        return default_config

    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
