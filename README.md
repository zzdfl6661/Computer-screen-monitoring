# 电脑屏幕学习/娱乐监控（原型）

## 项目概览
本项目由两个部分组成：
- `client.py`：客户端，周期性截图并通过 OCR + 关键词判断当前更偏向 `study` / `entertainment` / `unknown`，若 OCR 不可用则降级为进程名检测，并将结果上报服务端。
- `server.py`：Flask 服务端，接收客户端上报，写入 SQLite（默认 `activity.db`），并在网页展示最近 200 条日志。

## 当前可行性结论（再次遍历代码后）
- **可以用于课程设计/演示原型**：链路完整（采集 → 判断 → 上报 → 可视化），且服务端已做 SQLite 持久化，不再是纯内存日志。
- **不建议直接用于严肃监督场景**：核心判断仍是关键词规则 + 进程匹配，误报/漏报风险较高；且隐私合规、权限管理、审计等能力尚未工程化。

## 运行环境
- Python 3.9+
- 操作系统：
  - 客户端推荐 Windows（含弹窗能力）
  - 服务端 Windows/Linux/macOS 都可运行
- OCR 依赖：需安装系统级 Tesseract（可选；不装会自动降级为进程检测）

## 安装依赖
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 启动方法

### 1) 启动服务端
```bash
python server.py
```
默认监听：`0.0.0.0:5000`。

可选环境变量：
- `ACTIVITY_DB_PATH`：SQLite 文件路径（默认 `activity.db`）

示例：
```bash
ACTIVITY_DB_PATH=./data/activity.db python server.py
```

### 2) 启动客户端
```bash
python client.py
```
客户端默认上报地址为 `http://localhost:5000/check_activity`，默认每 5 秒检测一次。

可选环境变量：
- `TESSERACT_CMD`：Tesseract 可执行文件路径（例如 Windows: `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`）

示例（Windows PowerShell）：
```powershell
$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"
python client.py
```

### 3) 查看日志页面
浏览器访问：
- `http://localhost:5000/`

## 常见问题
- **客户端提示 Tesseract 初始化失败**：可忽略，程序会进入进程检测模式继续运行。
- **Linux 无桌面环境截图失败**：`pyautogui` 依赖图形环境，需在带桌面的会话中运行客户端。
- **服务端不可达**：客户端会本地给出提示结果，但不会写入服务端日志。
