# 智能劝学系统

基于多模态融合分析的学习行为监控与引导系统

## 项目介绍

智能劝学系统是一款基于屏幕理解的学习行为监控与引导工具，通过实时监控和分析学生的电脑使用行为，智能识别娱乐和学习活动，并在适当时候给予提醒，帮助学生建立良好的学习习惯。

系统采用 **FastAPI + PostgreSQL** 服务端架构和 **模块化客户端** 设计，支持 Docker 容器化部署，具备 JWT 设备认证、多模态融合识别、结构化日志、数据隐私保护等企业级特性。

## 系统架构

```
┌──────────────────┐         HTTP/JSON          ┌──────────────────────────┐
│    客户端 (本地)   │ ─────────────────────────→ │    服务端 (Docker)        │
│                  │   JWT 认证 + 活动上报      │                          │
│ · 屏幕捕获        │                           │ · FastAPI + SQLAlchemy    │
│ · 多模态融合识别   │                           │ · PostgreSQL 数据库       │
│ · 进程/窗口分析    │                           │ · JWT 设备认证            │
│ · 警告提示        │ ←─────────────────────────│ · 仪表盘 (ECharts)        │
│                  │      响应/反馈/提醒         │ · 数据隐私保护            │
└──────────────────┘                           └──────────────────────────┘
```

## 核心功能

### 1. 多模态融合活动识别
- **进程分析**（权重0.6）：检测学习/娱乐相关进程
- **窗口标题分析**（权重0.3）：分析当前活动窗口标题
- **ONNX 模型分类**（权重0.1）：MobileNetV3-Lite 图像分类（自动降级兼容）
- 加权融合三种识别结果，提高准确率
- 时间窗口分析，连续3次一致才触发提醒，减少误判

### 2. JWT 设备认证
- 设备自动注册与登录，获取访问令牌
- 未认证请求返回 401，保障数据安全

### 3. 数据反馈机制
- 误报/漏报反馈接口，收集用户标注数据
- 反馈数据用于后续模型优化

### 4. 数据隐私保护
- 敏感配置加密存储（cryptography.fernet）
- 数据保留策略，自动清理过期数据（默认30天）
- HTTPS 传输支持

### 5. 结构化日志
- Python logging 模块，JSON 格式输出
- 文件轮转，按日期分割

### 6. 现代化 Web 仪表盘
- 学习/娱乐统计卡片
- ECharts 数据可视化（分布饼图、趋势折线图）
- 活动日志搜索与筛选
- 响应式 Bootstrap 5 界面

## 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 服务端框架 | FastAPI | 异步 Web 服务，自动生成 OpenAPI 文档 |
| ORM | SQLAlchemy | 数据库操作 |
| 数据库 | PostgreSQL | 生产级关系型数据库 |
| 认证 | python-jose (JWT) | 设备认证与令牌管理 |
| 加密 | cryptography | 配置加密存储 |
| 客户端截图 | pyautogui | 屏幕捕获 |
| 客户端 OCR | pytesseract | 文字识别 |
| 客户端图像处理 | OpenCV | 图像预处理 |
| 模型推理 | onnxruntime | ONNX 模型推理 |
| 进程管理 | psutil | 进程检测 |
| GUI 提示 | tkinter | Windows 警告窗口 |
| 前端 UI | Bootstrap 5 | 响应式界面 |
| 数据可视化 | ECharts | 图表展示 |
| 部署 | Docker + Docker Compose | 容器化部署 |
| 日志 | python-json-logger | 结构化日志 |

## 快速开始

### 方式一：Docker 部署（推荐）

#### 前置条件
- 已安装 Docker Desktop
- 已安装 Python 3.11+（客户端需本地运行）

#### 1. 配置环境变量
在项目根目录创建 `.env` 文件：
```env
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_NAME=learning_app
JWT_SECRET_KEY=your_jwt_secret_key_here
APP_ENV=development
```

#### 2. 启动服务端容器
```powershell
docker compose up -d
```

#### 3. 验证服务端
访问 http://localhost:5000 查看仪表盘，访问 http://localhost:5000/docs 查看 API 文档。

#### 4. 启动客户端
```powershell
python main.py
```

### 方式二：本地直接运行

#### 1. 安装依赖
```bash
pip install -r requirements.txt
```

#### 2. 启动服务端
```bash
python fastapi_server.py
```

#### 3. 启动客户端
```bash
python main.py
```

## 项目文件结构

```
.
├── main.py                        # 客户端入口
├── fastapi_server.py              # 服务端启动入口
├── logger.py                      # 结构化日志配置
├── database.py                    # 客户端数据库管理
├── ssl_config.py                  # HTTPS 配置
├── requirements.txt               # Python 依赖
├── Dockerfile                     # 服务端镜像构建
├── docker-compose.yml             # 容器编排配置
├── .dockerignore                  # Docker 构建忽略
├── .gitignore                     # Git 忽略
│
├── app/                           # 服务端应用
│   ├── main.py                    # FastAPI 应用入口
│   ├── database.py                # SQLAlchemy 数据库连接
│   ├── models.py                  # 数据模型
│   ├── auth/                      # JWT 认证模块
│   │   ├── routes.py              # 认证路由（注册/登录）
│   │   ├── dependencies.py        # 认证依赖
│   │   ├── models.py              # 用户/设备模型
│   │   ├── schemas.py             # Pydantic 模型
│   │   └── utils.py               # JWT 工具
│   ├── routes/                    # API 路由
│   │   ├── activity.py            # 活动检查接口
│   │   ├── stats.py               # 统计数据接口
│   │   ├── distribution.py        # 分布数据接口
│   │   ├── trend.py               # 趋势数据接口
│   │   ├── search.py              # 日志搜索接口
│   │   ├── feedback.py            # 反馈数据接口
│   │   └── privacy.py             # 隐私管理接口
│   └── utils/
│       └── data_retention.py      # 数据保留策略
│
├── client_package/                # 客户端模块
│   ├── capture.py                 # 屏幕捕获
│   ├── classify.py                # 多模态融合分类
│   ├── report.py                  # 数据上报与设备认证
│   ├── ui.py                      # GUI 警告提示
│   ├── feedback.py                # 反馈上报
│   ├── config.py                  # 配置管理（加密存储）
│   └── model/                     # ONNX 模型模块
│       ├── onnx_classifier.py     # ONNX 推理器
│       ├── image_preprocessor.py  # 图像预处理
│       └── model_manager.py       # 模型管理
│
├── templates/
│   └── index.html                 # 仪表盘页面
│
└── models/
    └── model_config.json          # 模型配置
```

## 配置说明

### 客户端配置
首次运行自动生成 `config.json`，主要配置项：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `check_interval` | 5 | 检查间隔（秒） |
| `server_url` | `http://localhost:5000/check_activity` | 服务端地址 |
| `device_token` | 自动生成 | 设备认证令牌 |
| `study_keywords` | [...] | 学习进程关键词 |
| `entertainment_keywords` | [...] | 娱乐进程关键词 |

### Docker 部署配置

| 环境变量 | 说明 |
|----------|------|
| `DATABASE_URL` | PostgreSQL 连接字符串 |
| `JWT_SECRET_KEY` | JWT 签名密钥 |
| `APP_ENV` | 运行环境（development/production） |
| `DB_USER` | 数据库用户名 |
| `DB_PASSWORD` | 数据库密码 |
| `DB_NAME` | 数据库名称 |

## 常用命令

```powershell
# Docker 部署
docker compose up -d          # 启动并创建容器
docker compose start          # 启动已停止的容器
docker compose stop           # 停止容器（保留）
docker compose down          # 停止并移除容器
docker compose up -d --build # 重新构建镜像并启动

# 客户端
python main.py                # 启动客户端

# 服务端（本地运行）
python fastapi_server.py      # 启动服务端
```

## API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 仪表盘页面 | 公开 |
| GET | `/health` | 健康检查 | 公开 |
| GET | `/docs` | API 文档（Swagger） | 公开 |
| POST | `/check_activity` | 上报活动数据 | 设备令牌 |
| GET | `/api/stats` | 统计数据 | 公开 |
| GET | `/api/distribution` | 活动分布 | 公开 |
| GET | `/api/trend` | 时间趋势 | 公开 |
| GET | `/api/search` | 日志搜索 | 公开 |
| POST | `/auth/device/register` | 设备注册 | 公开 |
| POST | `/auth/device/login` | 设备登录 | 公开 |

## 注意事项

1. 客户端需要本地运行（需访问屏幕、进程），不支持容器化
2. 客户端可选依赖 Tesseract-OCR 和 onnxruntime，未安装时自动降级到进程+窗口检测模式
3. Docker 部署的服务端通过 `http://localhost:5000` 访问
4. `.env` 文件包含敏感信息，已在 `.gitignore` 中排除，请勿提交
5. 数据库使用 PostgreSQL（Docker 部署）或 SQLite（本地运行）

## 许可证

MIT
