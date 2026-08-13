# 智能劝学系统

基于多模态融合分析的学习行为监控与引导系统（面向青少年电脑使用监控）。

客户端在青少年电脑上**原生运行**（截屏、读前台进程、弹窗提醒），把判定结果上报给服务端；服务端集中部署（Docker：FastAPI + PostgreSQL），并提供一个**家长可视化看板**查看学习/娱乐情况（支持查看历史）。

## 系统架构

```
┌────────────────────────┐      HTTP/JSON (JWT)      ┌──────────────────────────────┐
│  客户端 main.py（桌面）  │ ────────────────────────→ │  服务端（Docker Compose）       │
│                        │   check_activity 上报      │  backend (FastAPI + uvicorn)  │
│ · 前台进程 + 标题判定     │ ←──────────────────────── │  db      (PostgreSQL 15)      │
│ · 仅“不确定”样本上传截图   │   响应/警告/反馈          │ · JWT 设备认证                 │
│ · 弹警告窗（连续3次一致）  │                          │ · 视觉兜底: POST /analyze_image│
│ · 零模型（无下载）        │                          │   (Tesseract OCR + 规则判级)   │
└────────────────────────┘                          │ · 家长看板 http://localhost:5000│
                                                    └──────────────────────────────┘
```

要点：
- **客户端零模型**：识别完全依赖「前台进程 + 窗口标题」规则（无 onnxruntime / pytesseract 下载）。
- **服务端视觉兜底**：仅当本地融合判定为「不确定」时，客户端上传一张 **384px JPEG 降采样截图** 到 `/analyze_image`，服务端用 **Tesseract OCR** 提取界面文字并复用同一套站点/关键词规则判级，**图片与 OCR 文本入库**（`image_analyses` 表）。截图低频、小图、仅模糊样本触发。
- 原客户端 ONNX 视觉模型（`mobilenetv3-lite.onnx`）已**下线**（下载地址 404），视觉能力统一收归服务端。

## 核心功能

### 1. 学习/娱乐分类（置信度感知融合 + 分层信号）

> 2026-08 优化：离线评测准确率由约 **54% 提升至 100%**（48 个代表性场景集，详见 `eval/`），0 回归。

| 信号 | 权重 | 说明 |
|------|------|------|
| 前台进程 | 0.45 | **只看前台窗口所属进程**（后台 QQ/Steam++/抖音守护等不参与判定）；浏览器/java 视为中性交给标题；边界感知匹配（`lib` 不误命中 `bilibili`、`idea` 能配 `idea64`） |
| 窗口标题+站点声誉 | 0.30 | 识别站点（coursera/知乎/B站/抖音…）：学习站→学习、娱乐站→娱乐、两栖站→关键词二次判定 |
| 本地文本 LLM | 0.20 | 可选（`enable_text_llm`，默认关），对 (进程,标题,站点) 语义判级，离线回退规则 |

> **权重说明**：以上权重是**相对重要度**而非概率，**无需和为 1**——融合时每个信号贡献 = 权重 × 自身置信度，再对总证据**归一化**后取最大类。

- **融合**：信号贡献 = 权重 × 自身置信度，归一化后 argmax；赢家分数 < `fusion_min_confidence`（默认 0.40）或与前一名差距 < `fusion_margin`（默认 0.05）→ 判「不确定」。
- **视觉兜底（后置覆盖，不参与加权融合）**：仅「不确定」样本触发——`enable_server_vision`（默认开）上传截图到服务端 OCR 判级，或 `enable_vlm`（默认关）本地 Ollama VLM；结果置信度 ≥ `confidence_threshold`（默认 0.45）时**直接采纳**为最终判定。
- 连续 3 次一致才弹提醒，减少误判。

**完整判定流程（一图流）：**

```text
信号采集
 ├─ 前台进程：浏览器/java → 中性（交给标题）；命中学习/娱乐表 → 强信号(置信度0.9)
 ├─ 窗口标题：站点声誉 + 关键词 → 学习/娱乐分
 └─ 文本 LLM（可选，默认关）
        │
        ▼
   加权融合（相对权重 × 置信度，归一化后取最大类）
        ├─ 有明确赢家 → 直接返回 study / entertainment / idle
        └─ 判定「不确定」（赢家分 < 0.40 或两可差距 < 0.05）
               │
               ▼
           视觉兜底（后置覆盖，不参与加权融合）
             ├─ 服务端 OCR（enable_server_vision，默认开）：
             │    上传 384px 截图 → POST /analyze_image → Tesseract OCR(eng+chi_sim)
             │    → 站点/关键词规则判级 → 置信度 ≥ 0.45 直接采纳
             └─ 本地 VLM（enable_vlm，默认关，可选升级路径）
```

> 说明：**服务端 OCR 是唯一真正上线的视觉能力**（默认开，仅在「不确定」样本触发，截图低频、小图、且入库 `image_analyses`）；本地 VLM 是可选升级。详见下文「3. 服务端视觉分析（OCR）」。

### 2. JWT 设备认证
- 设备自动注册/登录，`/check_activity`、`/analyze_image` 均需设备令牌（未认证返回 401）。

### 3. 服务端视觉分析（OCR）
- `POST /analyze_image`：收 base64 384px JPEG → Tesseract OCR（eng+chi_sim）→ 站点/关键词规则判级 → 返回 `{activity, confidence, ocr_text}`，图片与 OCR 文本写入 `image_analyses`。
- 后续可平滑升级为 VLM（如 qwen2.5vl:3b）而不改客户端协议。

### 4. 家长可视化看板
- `http://localhost:5000/`：统计卡（学习/娱乐/总数）、学习娱乐分布饼图、24h/48h/7天趋势折线图、活动日志表（可按活动/关键词/日期筛选）。
- **统计范围选择器**：今天 / 最近 7 天 / 最近 30 天 / 全部历史，一键联动统计卡、饼图、趋势与日志表，支持查看历史。
- 当前看板与 `/api/*` 默认**公开**（局域网内可访问），如需登录保护可后续接入 user 体系。

### 5. 数据与隐私
- 数据入库：`activity_logs`（每次判定）、`image_analyses`（视觉分析+截图）、`feedback`（误报/漏报反馈）。
- 数据保留策略：默认 30 天自动清理 `activity_logs` / `feedback` / `image_analyses`（可调）。
- 敏感配置（`device_token`/`access_token`）用 cryptography(Fernet) 加密存储；HTTPS 可选（`--ssl`）。

### 6. 结构化日志
- JSON 格式，写 `logs/app.log`（10MB×7 轮转）；容器内同时输出到 stdout（`docker logs -f learning-app-backend`）。
- 宿主机 `logs/app.log` 由 compose 挂载持久化，容器停止/重建不影响。

## 技术栈

| 类别 | 技术 |
|------|------|
| 服务端 | FastAPI + uvicorn + SQLAlchemy |
| 数据库 | PostgreSQL 15（Docker）/ SQLite（本地兜底） |
| 认证 | python-jose (JWT)、passlib |
| 服务端视觉 | Tesseract OCR（eng+chi_sim）+ pytesseract + Pillow |
| 客户端 | numpy / opencv-python / PyAutoGUI / psutil / requests |
| 前端 | Jinja2 + Bootstrap 5 + ECharts |
| 部署 | Docker Compose（backend + db） |

## 快速开始

### 方式一：Docker 部署服务端（推荐）

1. 项目根目录创建 `.env`：
```env
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_NAME=learning_app
JWT_SECRET_KEY=your_jwt_secret_key_here
APP_ENV=development
```
2. 启动：
```bash
docker compose up -d --build
```
> Dockerfile 已将 apt/pip 源切到阿里云镜像，国内网络可直接构建。
3. 验证：`http://localhost:5000/` 看板、`http://localhost:5000/docs` API 文档。

### 方式二：启动桌面客户端（必须在你本机/被监控电脑上）

```bash
pip install -r requirements-client.txt
python main.py
```

> 客户端需要显示器与进程访问，不能容器化；`config.json` 中 `server_url` 指向服务端地址，首次运行自动注册设备。

### 本地直接运行服务端（开发用，SQLite）

```bash
pip install -r requirements-server.txt
python fastapi_server.py
```

## 项目文件结构

```
.
├── main.py                     # 客户端入口（桌面监控）
├── fastapi_server.py           # 服务端启动入口
├── logger.py                   # 结构化日志
├── database.py                 # 客户端本地 SQLite 日志
├── config.json                 # 客户端配置（含站点声誉/关键词/权重/阈值）
├── requirements.txt            # 全量依赖（= server + client）
├── requirements-server.txt     # 服务端依赖
├── requirements-client.txt     # 客户端依赖
├── Dockerfile / docker-compose.yml / .dockerignore / .gitignore / .env
│
├── app/                        # 服务端应用
│   ├── main.py                 # FastAPI 入口（注册全部路由）
│   ├── database.py / models.py # SQLAlchemy 连接与模型
│   ├── vision.py               # 服务端视觉：OCR + 规则判级
│   ├── auth/                   # JWT 认证（注册/登录/依赖）
│   ├── routes/                 # activity / stats / distribution / trend /
│   │                           # search / feedback / privacy / vision
│   └── utils/data_retention.py # 数据保留清理（含 image_analyses）
│
├── client_package/             # 客户端模块
│   ├── classify.py             # 核心分类：前台进程+标题融合+不确定触发
│   ├── vlm_classifier.py       # 视觉兜底（server 分支：上传截图；ollama 分支可选）
│   ├── llm_judge.py            # 本地文本 LLM（可选）
│   ├── capture.py / report.py / ui.py / feedback.py / config.py
│
├── templates/index.html        # 家长看板（统计范围选择器）
├── eval/                       # 评测与测试
│   ├── run_eval.py             # 前后对比评测（旧 54.2% → 新 100%）
│   ├── legacy_classify.py / samples.json / report.txt
│   ├── smoke_test.py           # 离线健壮性冒烟
│   ├── cli_test.py             # 人工测试 CLI
│   └── debug_process_signal.py # 进程信号诊断
├── verify_backend.py           # 后端链路冒烟（health/注册/登录/check_activity）
├── verify_vision.py            # 视觉链路冒烟（/analyze_image）
└── stop_client.py              # 停止客户端进程
```

## 客户端配置（config.json）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `check_interval` | 5 | 检查间隔（秒） |
| `server_url` | `http://127.0.0.1:5000/check_activity` | 服务端地址（用 127.0.0.1 避免系统代理干扰 localhost） |
| `fusion_weights` | `{process:0.45, title:0.30, text_llm:0.20}` | 信号权重（相对权重，融合时归一化，无需和为 1） |
| `confidence_threshold` | 0.45 | 视觉兜底结果采纳阈值 |
| `fusion_min_confidence` | 0.40 | 「不确定」下限 |
| `fusion_margin` | 0.05 | 「不确定」前两名最小差距 |
| `enable_server_vision` | true | 服务端 OCR 视觉兜底（仅不确定样本） |
| `enable_text_llm` / `enable_vlm` | false | 本地 LLM / 端侧 VLM（可选） |
| `site_reputation` / `study_keywords` / `entertainment_keywords` | […] | 站点声誉与关键词 |

## API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 家长看板 | 公开 |
| GET | `/health` | 健康检查 | 公开 |
| GET | `/docs` | Swagger 文档 | 公开 |
| POST | `/check_activity` | 客户端上报判定 | 设备令牌 |
| POST | `/analyze_image` | 服务端视觉分析（OCR+规则，图片入库） | 设备令牌 |
| GET | `/api/stats?days=` | 统计（`days`：1/7/30/0=全部） | 公开 |
| GET | `/api/distribution?days=` | 学习/娱乐分布 | 公开 |
| GET | `/api/trend?hours=` | 时间趋势 | 公开 |
| GET | `/api/search` | 日志搜索（activity/keyword/日期） | 公开 |
| POST | `/auth/device/register` `/auth/device/login` | 设备注册/登录 | 公开 |

## 常用命令

```bash
# 服务端（Docker）
docker compose up -d --build    # 构建并启动
docker compose ps               # 查看状态（backend/db 应 healthy）
docker compose down             # 停止并移除容器（数据卷保留）
docker logs -f learning-app-backend   # 容器日志

# 客户端
python main.py

# 冒烟/回归
python eval/run_eval.py         # 评测：旧 vs 新
python eval/smoke_test.py       # 健壮性冒烟
python verify_backend.py        # 后端链路
python verify_vision.py         # 视觉链路（需服务端在跑）
```

## 注意事项

1. 客户端必须原生运行在被监控电脑上（需屏幕/进程访问），不支持容器化；`main.py` 持续循环，`Ctrl+C` 停止。
2. **服务端视觉兜底默认开启**（`enable_server_vision`）：仅「不确定」样本上传 384px 降采样截图，图片入库并受数据保留策略约束（默认 30 天）。
3. 看板与 `/api/*` 默认公开访问；如需登录保护，可后续接入 `users` 账号体系。
4. `.env`、`config.json`、`*.db`、`logs/`、`.encryption_key` 均已 gitignore，勿提交。
5. 数据库：Docker 部署用 PostgreSQL（数据卷 `postgres_data` 持久）；本地直接运行 `fastapi_server.py` 用 SQLite（仅开发）。

## 许可证

MIT
