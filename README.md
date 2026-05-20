# 智能劝学系统

基于屏幕理解的学习行为监控与引导系统

## 项目介绍

智能劝学系统是一款基于屏幕理解的学习行为监控与引导工具，通过实时监控和分析学生的电脑使用行为，智能识别娱乐和学习活动，并在适当时候给予提醒，帮助学生建立良好的学习习惯。

## 系统架构

- **客户端**：负责屏幕捕获、活动分析、警告提示
- **服务端**：负责接收和处理客户端请求，记录活动日志
- **数据存储**：存储活动记录和分析结果

## 核心功能

1. **智能活动识别**：通过多模态分析（屏幕图像和系统进程）准确识别学生的电脑活动类型
2. **实时提醒机制**：当检测到娱乐活动时，及时弹出友好的劝学提示
3. **学习行为分析**：记录和分析学生的学习和娱乐时间分布，提供数据支持
4. **用户友好界面**：提供简洁直观的配置和监控界面

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

### 运行客户端

```bash
python client.py
```

## 核心功能（更新）

### 数据持久化（新增）
1. **SQLite数据库存储**：
   - 新增`database.py`模块，提供`DatabaseManager`类管理活动日志
   - 支持活动日志的存储、查询、删除等操作
   - 数据库表结构：id, timestamp, activity, message, source

2. **配置文件持久化**：
   - 使用`config.json`存储配置信息
   - 支持检查间隔、服务端URL、关键词等配置的持久化
   - 提供`ConfigManager`类简化配置管理

3. **客户端和服务端数据库**：
   - 客户端使用`client_activity_logs.db`存储本地活动记录
   - 服务端使用`server_activity_logs.db`存储接收到的活动记录
   - 保持向后兼容性，现有功能不受影响

## 项目文件结构

```
.
├── client.py              # 客户端代码（已更新，支持数据库和配置）
├── server.py              # 服务端代码（已更新，使用数据库存储）
├── database.py            # 新增：数据库管理模块
├── config.json            # 新增：配置文件（自动生成）
├── client_activity_logs.db  # 新增：客户端数据库（自动生成）
├── server_activity_logs.db  # 新增：服务端数据库（自动生成）
├── templates/             # 模板文件
│   └── index.html         # 服务端日志显示页面（已更新）
├── 服务端活动日志.html    # 活动日志模板
├── 课题方案.txt            # 项目课题方案
└── README.md              # 项目说明文档
```

## 推送代码到GitHub

由于网络连接问题，暂时无法直接推送代码到GitHub。当网络连接恢复后，请执行以下命令：

```bash
git push -u origin master
```

## 注意事项

1. 本系统需要Tesseract-OCR支持，如未安装，会自动切换到进程检测模式
2. 本系统仅用于学习目的，使用时请注意保护隐私
3. 系统会定期捕获屏幕截图，可能会影响系统性能

## 许可证

MIT
