import sqlite3
from datetime import datetime, timedelta

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
        start_time = (now - timedelta(hours=hours)).isoformat()
        
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
