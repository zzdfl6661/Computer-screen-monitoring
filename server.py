from flask import Flask, request, jsonify, render_template
from database import DatabaseManager

app = Flask(__name__)

# 初始化数据库
db = DatabaseManager('server_activity_logs.db')

# 处理客户端请求
@app.route('/check_activity', methods=['POST'])
def check_activity():
    data = request.get_json()
    activity = data.get('activity', '')
    message = ""

    if activity == 'entertainment':
        message = "你正在娱乐，请切换到学习！"
        db.add_log(activity=activity, message=message, source='client')
        return jsonify({"message": message, "status": "warning"}), 200
    elif activity == 'study':
        message = "继续保持学习状态！"
        db.add_log(activity=activity, message=message, source='client')
        return jsonify({"message": message, "status": "good"}), 200
    else:
        message = "无法识别的活动"
        db.add_log(activity=activity, message=message, source='client')
        return jsonify({"message": message, "status": "error"}), 400

# 创建一个简单的网页来显示活动日志
@app.route('/')
def index():
    activity_log = db.get_all_logs()
    return render_template('index.html', activity_log=activity_log)

# API：获取统计数据
@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = db.get_today_stats()
    return jsonify(stats)

# API：获取活动分布
@app.route('/api/distribution', methods=['GET'])
def get_distribution():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    distribution = db.get_activity_distribution(start_date, end_date)
    return jsonify(distribution)

# API：获取时间趋势
@app.route('/api/trend', methods=['GET'])
def get_trend():
    hours = request.args.get('hours', 24, type=int)
    trend = db.get_time_trend(hours)
    return jsonify(trend)

# API：搜索日志
@app.route('/api/search', methods=['GET'])
def search_logs():
    activity = request.args.get('activity')
    keyword = request.args.get('keyword')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    logs = db.search_logs(activity, keyword, start_date, end_date)
    return jsonify(logs)

# 启动服务器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
