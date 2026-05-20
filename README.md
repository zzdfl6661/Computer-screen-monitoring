# 智能劝学系统

基于屏幕理解的学习行为监控与引导系统

## 项目介绍

智能劝学系统是一款基于屏幕理解的学习行为监控与引导工具，通过实时监控和分析学生的电脑使用行为，智能识别娱乐和学习活动，并在适当时候给予提醒，帮助学生建立良好的学习习惯。

## 系统架构

- **客户端**：负责屏幕捕获、活动分析、警告提示
- **服务端**：负责接收和处理客户端请求，记录活动日志
- **数据存储**：使用SQLite存储活动记录，JSON存储配置

## 核心功能

### 1. 多模态智能活动识别
- 通过屏幕图像OCR分析识别活动类型
- 通过系统进程分析识别活动类型  
- 通过窗口标题分析识别活动类型
- 加权融合三种识别结果，提高准确率（进程0.6, OCR0.3, 窗口0.1）
- 时间窗口分析，连续3次一致才触发提醒，减少误判

### 2. 实时提醒机制
- 当检测到娱乐活动时，及时弹出友好的劝学提示
- Windows环境显示GUI警告窗口，其他环境打印提示

### 3. 数据持久化
- SQLite数据库存储活动日志，服务重启数据不丢失
- JSON配置文件持久化，支持自定义设置
- 客户端和服务端独立数据库

### 4. 现代化Web界面
- 仪表盘展示关键指标（学习记录、娱乐记录、总记录）
- ECharts数据可视化（学习/娱乐分布饼图、时间趋势折线图）
- 时间筛选和搜索功能
- 响应式Bootstrap 5界面

## 技术栈

| 类别 | 技术/库 | 用途 |
|------|---------|------|
| 客户端 | Python | 核心编程语言 |
| 客户端 | pyautogui | 屏幕捕获 |
| 客户端 | pytesseract | OCR文字识别 |
| 客户端 | OpenCV | 图像处理 |
| 客户端 | psutil | 进程管理 |
| 客户端 | tkinter | GUI界面 |
| 服务端 | Flask | Web服务 |
| 服务端 | Jinja2 | 模板渲染 |
| 前端 | Bootstrap 5 | UI框架 |
| 前端 | ECharts | 数据可视化 |
| 通信 | requests | HTTP请求 |
| 数据存储 | SQLite | 本地数据库 |
| 配置管理 | JSON | 配置文件 |

## 快速开始

### 安装依赖

```bash
pip install flask pyautogui requests numpy opencv-python pytesseract pillow psutil
```

### 运行服务端

```bash
python server.py
```

访问 http://localhost:5000 查看Web界面

### 运行客户端

```bash
python client.py
```

## 项目文件结构

```
.
├── client.py              # 客户端代码
├── server.py              # 服务端代码
├── database.py            # 数据库管理模块
├── templates/             # 模板文件
│   └── index.html         # 服务端日志显示页面
├── config.json            # 配置文件（自动生成）
├── client_activity_logs.db  # 客户端数据库（自动生成）
├── server_activity_logs.db  # 服务端数据库（自动生成）
├── 课题方案.txt            # 项目课题方案
├── 优化建议文档.md         # 项目优化建议
└── README.md              # 项目说明文档
```

## 配置说明

首次运行会自动生成`config.json`配置文件，包含以下配置项：

- `check_interval`: 检查间隔（秒），默认5
- `server_url`: 服务端URL，默认 http://localhost:5000/check_activity
- `entertainment_keywords`: 娱乐关键词列表
- `study_keywords`: 学习关键词列表

## 注意事项

1. 本系统需要Tesseract-OCR支持，如未安装，会自动切换到进程+窗口标题检测模式
2. 本系统仅用于学习目的，使用时请注意保护隐私
3. 系统会定期捕获屏幕截图，可能会影响系统性能
4. 数据库文件和配置文件会自动生成在项目目录下

## 许可证

MIT
