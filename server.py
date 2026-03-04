from datetime import datetime
import os
import sqlite3
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
DB_PATH = os.getenv("ACTIVITY_DB_PATH", "activity.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT NOT NULL,
            message TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence REAL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def build_message_and_status(activity: str):
    if activity == "entertainment":
        return "你正在娱乐，请切换到学习！", "warning"
    if activity == "study":
        return "继续保持学习状态！", "good"
    return "当前状态不确定，请确认是否在学习", "unknown"


init_db()


@app.route('/check_activity', methods=['POST'])
def check_activity():
    data = request.get_json(silent=True) or {}
    activity = data.get('activity', 'unknown')
    source = data.get('source', 'client')
    confidence = data.get('confidence')

    if activity not in {"entertainment", "study", "unknown"}:
        activity = "unknown"

    message, status = build_message_and_status(activity)
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO activity_log (activity, message, source, confidence, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (activity, message, source, confidence, created_at),
    )
    conn.commit()
    conn.close()

    return jsonify({"message": message, "status": status}), 200


@app.route('/')
def index():
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT activity, message, source, confidence, created_at
        FROM activity_log
        ORDER BY id DESC
        LIMIT 200
        """
    ).fetchall()
    conn.close()
    return render_template('index.html', activity_log=rows)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
