from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# 用于存储活动数据
activity_log = []

# 处理客户端请求
@app.route('/check_activity', methods=['POST'])
def check_activity():
    data = request.get_json()  # 获取请求中的JSON数据
    activity = data.get('activity', '')
    message = ""

    if activity == 'entertainment':
        message = "你正在娱乐，请切换到学习！"
        activity_log.append({"activity": "entertainment", "message": message})
        return jsonify({"message": message, "status": "warning"}), 200
    elif activity == 'study':
        message = "继续保持学习状态！"
        activity_log.append({"activity": "study", "message": message})
        return jsonify({"message": message, "status": "good"}), 200
    else:
        message = "无法识别的活动"
        activity_log.append({"activity": "unknown", "message": message})
        return jsonify({"message": message, "status": "error"}), 400

# 创建一个简单的网页来显示活动日志
@app.route('/')
def index():
    return render_template('index.html', activity_log=activity_log)

# 启动服务器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)  # 监听所有接口，端口5000
