# 智能劝学系统

基于多模态融合分析的学习行为监控与引导系统（面向青少年电脑使用监控）。

客户端在青少年电脑上**原生运行**（截屏、读前台进程、弹窗提醒），把判定结果上报给服务端；服务端集中部署（Docker：FastAPI + PostgreSQL），并提供一个**家长可视化看板**查看学习/娱乐情况（支持查看历史）。

## 系统架构

```
┌────────────────────────┐      HTTP/JSON (JWT)      ┌──────────────────────────────┐
│  客户端 main.py（桌面）  │ ────────────────────────→ │  服务端（Docker Compose）       │
│                        │   check_activity 上报      │  backend (FastAPI + uvicorn)  │
│ · 前台进程 + 标题/URL判定  │ ←──────────────────────── │  db      (PostgreSQL 15)      │
│ · 每 60 秒独立截图采样     │   响应/警告/规则          │ · JWT 设备认证                 │
│ · 可爱自绘提醒（连续触发） │                          │ · 视觉兜底: POST /analyze_image│
│ · 零模型（无下载）        │                          │   (三信号融合: 进程+标题+OCR)  │
└────────────────────────┘                          │ · 家长看板 http://localhost:5000│
                                                    └──────────────────────────────┘
```

要点：
- **客户端零模型**：识别依赖「数据库规则 + 前台进程 + 窗口标题 + 浏览器 URL(best-effort) + 家长覆盖规则」（无 onnxruntime / pytesseract 下载）；截屏采用 **Windows GDI**（ctypes + numpy），零第三方截屏库依赖。
- **固定截图采样**：客户端每 **60 秒**独立截取前台窗口，压缩为长边 768px、质量 80 的 JPEG 后上传。该任务与主监控、提醒和 OCR 相互独立，网络异常会在下一轮重试而不会阻塞监控。
- **服务端视觉兜底**：当本地融合仍为「不确定」时，客户端还会按视觉节流上传截图到 `/analyze_image`，服务端融合 **前台进程 + 窗口标题 + OCR 文本** 三信号判级。固定采样截图与 OCR 分析记录分别保存。
- 原客户端 ONNX 视觉模型（`mobilenetv3-lite.onnx`）已**下线**（下载地址 404），视觉能力统一收归服务端。

## 核心功能

### 当前版本：固定截图、数据库规则与动态提醒

- **每分钟截图留存**：无论当前判为学习、娱乐或未知，客户端都会独立采样一次前台窗口。图片以 JPEG 二进制写入 PostgreSQL `screenshots` 表（不是 Base64），同时记录设备、时间、进程、窗口标题、分类、置信度与可选人工标注；默认保留 **7 天**。
- **截图时间轴**：看板在活动日志前提供“打开截图时间轴”入口。时间轴在独立的大尺寸弹窗中展示缩略图，支持刷新、按当前设备查看、查看原图和元数据，并可将截图标为学习或娱乐，为后续视觉模型积累样本。
- **统一数据库规则**：`classification_rules` 是客户端与服务端 OCR 共用的规则来源。规则按“进程精确匹配 → 域名 → 标题/OCR”优先级参与判定，客户端每 5 分钟刷新缓存；断网时继续使用已下载缓存和本地兜底。
- **预置范围**：首次启动会幂等补齐常见游戏平台、游戏进程、视频/音乐客户端、社交和直播站点、IDE、办公/阅读工具、开发者文档、编程练习、在线课程与论文检索站点。已有数据库规则不会被覆盖、删除或重复写入。
- **OCR 的角色**：标题文字不是 OCR。只有规则仍不能可靠分类时才会触发 OCR 视觉兜底；OCR 会与进程和窗口标题共同判断，且通用界面词（如“学习”“娱乐”）不会单独成为高置信度结论。
- **动态提醒**：娱乐判定连续触发时只显示一个非阻塞的自绘提醒卡片：弹性进场、轻微漂浮与倒计时；点击“知道了”或按 `Esc` 收起，超时后缓慢淡出上移。

> 看板不展示内部“分类规则”管理表，避免把内部实现当作唯一判定逻辑；规则继续保存在数据库中并被客户端和 OCR 服务使用。

### 1. 学习/娱乐分类（置信度感知融合 + 分层信号）

> 评测集用于回归规则变化（v1 48 条、v2 165 条）。`unknown` 是保守拒判，不应把“拒判率”误读成学习/娱乐准确率；线上准确性以真实前台窗口、OCR 结果和家长反馈为准。

| 信号 | 权重 | 说明 |
|------|------|------|
| 前台进程 | 0.45 | **只看前台窗口所属进程**（后台 QQ/Steam++/抖音守护等不参与判定）；浏览器/java/origin 视为中性交给标题；VS Code、Codex/ChatGPT/Claude、PowerShell/Windows Terminal、Docker 等生产力工具判学习；边界感知匹配避免短词误命中 |
| 窗口标题+站点声誉 | 0.30 | 识别站点（coursera/知乎/B站/抖音…）：学习站→学习、娱乐站→娱乐、两栖站→关键词二次判定，**两栖站平票→弃权交视觉兜底**（不再默认判学习，鬼畜/综艺不再误判） |
| 本地文本 LLM | 0.20 | 可选（`enable_text_llm`，默认关），对 (进程,标题,站点) 语义判级，离线回退规则 |
| 浏览器 URL（best-effort） | 0.30(复用标题) | 前台浏览器时尝试读地址栏 URL（Windows UIA，可选依赖），两栖站按**路径细分**（zhihu `/question`→学习、`/zvideo`→娱乐；bilibili `/read`→学习、`/bangumi`→娱乐）。仅标题无定论时介入，避免双计。Chromium 未聚焦常读不到 → 自动降级标题 |
| 家长覆盖规则 | 权威覆盖 | 看板标注 unknown 样本 → 生成「进程/标题→学习/娱乐」个性化规则，客户端拉取后**最高优先级覆盖**（跳过视觉兜底），标注次数越多越可信 |

> **权重说明**：以上权重是**相对重要度**而非概率，**无需和为 1**——融合时每个信号贡献 = 权重 × 自身置信度，再对总证据**归一化**后取最大类。

- **融合**：信号贡献 = 权重 × 自身置信度，归一化后 argmax；赢家分数 < `fusion_min_confidence`（默认 0.40）或与前一名差距 < `fusion_margin`（默认 0.05）→ 判「不确定」。
- **空闲判定**：只在没有前台窗口（`no_foreground`）或前台是无标题的桌面外壳（`desktop_shell`）时判 `idle`；不再依据键鼠最后输入时间。浏览器/视频/小说窗口即使标题为空也保留为 `unknown`，交给 OCR 识别。
- **未知归一化**：服务端收到 `unknown` 时，若前台进程/标题有明确生产力或娱乐证据，会写回 `study`/`entertainment`；只有没有可靠证据的样本才保留 `unknown`。
- **提醒去抖**：客户端连续 3 次判定为娱乐时才弹出提醒，减少窗口切换造成的瞬时误提醒；活动结果仍按每个检查周期上报。
- **高 DPI 提醒窗**：客户端使用自绘高 DPI 卡片、清晰字体、确定按钮和 15 秒自动收起，避免默认 Tk 弹窗模糊。
- **视觉兜底（后置覆盖，不参与加权融合）**：仅「不确定」样本触发——`enable_server_vision`（默认开）上传截图到服务端 OCR 判级，或 `enable_vlm`（默认关）本地 Ollama VLM；结果置信度 ≥ `confidence_threshold`（默认 0.45）时**直接采纳**为最终判定。**家长覆盖规则优先级高于视觉兜底**。
- 连续 3 次一致才弹提醒，减少误判。

**完整判定流程（一图流）：**

```text
信号采集
 ├─ 前台进程：浏览器/java/origin → 中性（交给标题）；IDE、AI 助手、终端、Docker 等生产力工具 → 学习强信号
 ├─ 窗口标题：站点声誉 + 关键词 → 学习/娱乐分（两栖站平票→弃权）
 ├─ 浏览器 URL（best-effort）：两栖站路径细分（/question 学习、/zvideo 娱乐…）
 ├─ 家长覆盖规则：进程/标题 → 学习/娱乐（看板标注生成，权威覆盖）
 └─ 文本 LLM（可选，默认关）
        │
        ▼
   加权融合（相对权重 × 置信度，归一化后取最大类）
        ├─ 有明确赢家 → 直接返回 study / entertainment / idle
        └─ 判定「不确定」（赢家分 < 0.40 或两可差距 < 0.05）
               ├─ 家长覆盖规则命中 → 权威覆盖（最高优先级，跳过视觉）
               └─ 视觉兜底（后置覆盖，不参与加权融合）
                    ├─ 服务端 OCR（enable_server_vision，默认开）：
                    │    RapidOCR 提取界面文字 + 前台进程 + 窗口标题三信号融合；生产力进程保护 OCR 结果
                    │    （权重 0.45/0.30/0.25）→ 置信度 ≥ 0.45 直接采纳
                    └─ 本地 VLM（enable_vlm，默认关，可选升级路径）
```

> 说明：**服务端 OCR 是唯一真正上线的视觉识别能力**（默认开，仅在「不确定」样本触发）；此外每分钟固定采样截图保存到 `screenshots`，用于看板回看和后续人工标注。本地 VLM 是可选升级。

### 2. JWT 设备认证
- 设备自动注册/登录，`/check_activity`、`/analyze_image` 均需设备令牌（未认证返回 401）。

### 3. 服务端视觉分析（OCR）
- `POST /analyze_image`：收 base64 768px JPEG + 前台进程 + 窗口标题 → **RapidOCR（onnx，Tesseract 降级）** 提取界面文字 → **三信号融合判级**（前台进程 0.45 + 窗口标题 0.30 + OCR 文本 0.25，归一化后取最大类）→ 返回 `{activity, confidence, ocr_text}`，图片哈希与 OCR 文本写入 `image_analyses`。Codex/ChatGPT/Claude、终端和 Docker 等明确生产力进程不会被 OCR 中的“娱乐”字样覆盖。
- 后续可平滑升级为 VLM（如 qwen2.5vl:3b）而不改客户端协议。

### 4. 家长可视化看板
- `http://localhost:5000/`：统计卡（只统计已识别的学习/娱乐）、学习娱乐分布饼图、24h/48h/7天趋势折线图、活动日志表（可按活动/关键词/日期筛选）。
- **统计范围选择器**：今天 / 最近 7 天 / 最近 30 天 / 全部历史，一键联动统计卡、饼图、趋势与日志表，支持查看历史。
- **日期筛选**：开始/结束日期默认填充当天日期，避免只显示浏览器的 `yyyy/mm/日` 占位符。
- **判定上下文**：日志表显示前台进程和窗口标题，方便核对 Codex、浏览器、终端等是否被误判。
- **截图时间轴**：活动日志前提供独立入口；点击后打开大尺寸时间轴弹窗，浏览最近 7 天按设备保存的截图、放大原图并查看进程、标题、分类与时间。
- **未归类诊断**：unknown 不再占据主统计和饼图，只在折叠诊断区显示；有明确进程/标题的记录会自动归一化。
- **未知活动标注（标注飞轮）**：系统判不出（unknown）的界面以「进程/标题 + 出现次数」列出，家长点「学习/娱乐」即生成**个性化覆盖规则**（`classification_overrides` 表，重复标注递增 hit_count），客户端下次拉取后权威覆盖判定。这是规则系统追不上的长尾（孩子自装应用）的兜底，也是家长闭环修正的入口。
- “反馈核验”卡片已从看板移除；当前以 unknown 诊断、截图人工标注和数据库规则持续改善识别。
- 当前看板与 `/api/*` 默认**公开**（局域网内可访问），如需登录保护可后续接入 user 体系。

### 5. 数据与隐私
- 数据入库：`activity_logs`（每次判定）、`image_analyses`（OCR 分析结果）、`screenshots`（每分钟 JPEG 采样及元数据）、`feedback`（兼容历史接口）、`classification_rules`（统一分类规则）、`classification_overrides`（家长标注覆盖规则）。
- 数据保留策略：默认 30 天自动清理活动/视觉分析等记录；`screenshots` 独立按默认 **7 天**自动清理。
- 敏感配置（`device_token`/`access_token`）用 cryptography(Fernet) 加密存储；HTTPS 可选（`--ssl`）。

### 6. 结构化日志
- JSON 格式，写 `logs/app.log`（10MB×7 轮转）；容器内同时输出到 stdout（`docker logs -f learning-app-backend`）。
- 宿主机 `logs/app.log` 由 compose 挂载持久化，容器停止/重建不影响。

## 2026-08-18 健壮性修复（v1.1）

针对实际运行中"无法识别"场景的整改，服务端不再把合法状态误记为错误：

1. **统一活动状态模型**：`study / entertainment / idle / unknown`。后端把 `idle` 正常处理为
   `status=neutral`（不再是 ERROR），`unknown` 为合法状态；枚举外的输入直接返回 422。
2. **不确定样本走视觉兜底**：只有存在前台界面但本地规则无法判级时才标记
   `unknown + uncertain` 并上传服务端 OCR；真正没有前台窗口/无标题桌面外壳仍是 `idle`，不截图；
   `vision_min_interval` 默认 5s 节流，避免高频刷图。
3. **区分 idle 与 unknown**：无前台或无标题的桌面外壳 → `idle`（原因码
   `no_foreground/desktop_shell`）；有界面但规则未命中（包括浏览器标题为空）→ `unknown`
   （原因码 `rules_uncovered`），并记录判定依据 `decision_source`。
4. **记录判定依据**：`activity_logs` 新增 `device_id/confidence/decision_source/reason` 列，
   客户端上报元数据，看板日志表直接展示"为什么判成这个结果"。
5. **家长统计口径**：主卡片与分布图只统计 `study + entertainment`；idle/unknown
   仅作为诊断字段，不再混入家长要看的学习/娱乐结果。服务启动时会把有明确进程/标题证据的历史
   unknown 归一化为 study/entertainment，并纠正明确生产力进程被 OCR 写成 entertainment 的历史记录。
6. **隐私与权限**：设置 `ADMIN_PASSWORD` 后看板与 `/api/*` 需登录（`/login` 密码门，
   HttpOnly Cookie，24h）；固定采样截图以 JPEG 二进制保存 7 天，日志带 `device_id`
   支持设备隔离筛选。
7. **接口健壮性**：`/analyze_image` 校验图片格式/尺寸、DB 失败回滚；`/check_activity`
   与 `/analyze_image` 按设备限流（60/min、12/min）；客户端 401 重试改为有限次数循环。
8. **数据库自动迁移**：启动时对旧库补齐新增列（SQLite/PostgreSQL 均支持），无需手动重建。

> 部署提醒：`.env` 增加可选 `ADMIN_PASSWORD=你的看板密码` 与 `STORE_IMAGE_RAW=0`。
> 本地未装中文语言包时 OCR 自动回退到 `eng`（Docker 镜像已含 `chi_sim`）。

### v1.1 补充：服务端三信号融合 + 看板实时化 + 客户端 GDI 截屏

- **`/analyze_image` 三信号融合**（`app/vision.py::classify_fused`）：不再只靠 OCR 文本，
  融合 **前台进程 + 窗口标题 + OCR 文本**（权重 0.45/0.30/0.25，归一化后取最大类）。
  生产力工具（Docker Desktop / IDE / Codex/ChatGPT/Claude）和前台开发终端直接给学习证据；
  `com.docker.backend` 等后台守护进程不参与判定。服务端还会保护生产力进程，避免 OCR 看到代码文本中的
  “entertainment” 就把 Codex 误报成娱乐。
- **语义统一**：服务端 `classify_text` 无信号返回 `unknown`（不再用 idle 混充"无法判断"）。
- **OCR 输入改进**：客户端截图优先截前台窗口（Windows），上传长边 **768px**；
  RapidOCR 主路径负责中文界面识别，Tesseract 仅作降级路径。
- **unknown 可诊断**：`activity_logs` 新增 `process/title` 列，客户端随上报携带；
  新增 `GET /api/unknown-top?days=&limit=` 聚合 unknown 的进程/标题 TOP N，定向补规则。
- **看板实时更新**：`/api/search` 支持 `since_id` 增量拉取；看板每 **10 秒**统一刷新
  统计/饼图/趋势/日志（日志增量追加到表格顶部，切换时段/设备时全量重拉）；
  卡片标题显示"上次刷新：HH:MM:SS"。
- **反馈核验**：`GET /api/feedback` 历史接口保留兼容，但反馈核验卡片已从看板移除。
- **移除弹窗误报/漏报按钮**：孩子不会给准确反馈，弹窗只保留"确定"；`feedback` 表与
  接口保留供家长端/程序化使用。
- **修改后必须重新构建镜像**：`docker compose up -d --build`（容器内旧代码不会自动更新；
  若日志仍出现 `ERROR - 无法识别的活动` 即为旧镜像）。
- **客户端 GDI 截屏**：`client_package/capture.py` 改用 **Windows GDI**（ctypes + user32 + gdi32，
  BitBlt 截屏），零第三方截屏库依赖（无需 pyautogui / pyscreeze / Pillow）；优先截前台窗口区域，
  失败回退全屏。`requirements-client.txt` 已移除 PyAutoGUI 和 Pillow。
- **连接错误诊断**：`vlm_classifier.py` 增加 `URLError` 专门分支，后端容器未启动时明确提示
  "请 docker compose up -d"，替代隐晦的 urlopen error。
- **真实运行验证**：Docker backend 健康、RapidOCR 可用；看板主统计只返回学习/娱乐，
  日志包含前台进程/窗口标题，客户端可持续上报。

## 技术栈

| 类别 | 技术 |
|------|------|
| 服务端 | FastAPI + uvicorn + SQLAlchemy |
| 数据库 | PostgreSQL 15（Docker）/ SQLite（本地兜底） |
| 认证 | python-jose (JWT)、passlib |
| 服务端视觉 | RapidOCR（主路径）+ Tesseract/pytesseract/Pillow（降级） |
| 客户端 | numpy / opencv-python / psutil / requests / Windows GDI（ctypes 截屏，零第三方依赖） |
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
> 截屏采用 Windows GDI（ctypes + numpy），**无需安装 PyAutoGUI 或 Pillow**；客户端依赖仅 numpy / opencv-python / psutil / requests / cryptography / sqlalchemy / python-json-logger，另有**可选** `comtypes`（浏览器 URL 读取，未装自动降级）。

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
│   ├── vision.py               # 服务端视觉：三信号融合（OCR+进程+标题）
│   ├── auth/                   # JWT 认证（注册/登录/依赖）
│   ├── routes/                 # activity / stats / distribution / trend /
│   │                           # search / privacy / vision / screenshots / rules / label
│   ├── rule_engine.py          # PostgreSQL 分类规则预置、缓存与匹配
│   ├── utils/classification.py # unknown 归一化与生产力进程误报保护
│   └── utils/data_retention.py # 数据保留清理（含 image_analyses）
│
├── client_package/             # 客户端模块
│   ├── classify.py             # 核心分类：数据库规则+进程+标题+URL+覆盖规则融合
│   ├── screenshots.py          # 每分钟截图采样、压缩与异步上传
│   ├── rule_cache.py           # 服务端分类规则缓存与离线回退
│   ├── overrides.py            # 家长覆盖规则拉取与匹配（标注飞轮客户端侧）
│   ├── browser_url.py          # 浏览器 URL 读取（UIA，可选依赖，best-effort）
│   ├── vlm_classifier.py       # 视觉兜底（server 分支：上传截图；ollama 分支可选）
│   ├── llm_judge.py            # 本地文本 LLM（可选）
│   ├── capture.py             # GDI 截屏（ctypes+numpy，零第三方依赖，优先截前台窗口）
│   ├── report.py / ui.py / feedback.py / config.py
│
├── templates/index.html        # 家长看板（学习/娱乐主统计 + 折叠诊断区 + 日期筛选）
├── eval/                       # 评测与测试
│   ├── run_eval.py             # 回归评测（v1 48 条 / v2 165 条，允许 unknown 拒判）
│   ├── grid_search.py          # 融合参数网格搜索（结论：当前参数已在平台期）
│   ├── samples.json / samples_v2.json / report.txt / grid_search_report.txt
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
| `vision_min_interval` | 5 | 视觉兜底最小间隔（秒，节流截图上送频率） |
| 固定截图采样 | 60 秒 | 独立任务；不受 `unknown`、OCR 或提醒状态影响，上传失败在下一轮重试 |
| 数据库规则缓存 | 5 分钟 | 客户端拉取 `classification_rules` 的刷新间隔；断网保留最近一次成功缓存 |
| `enable_text_llm` / `enable_vlm` | false | 本地 LLM / 端侧 VLM（可选） |
| `site_reputation` / `study_keywords` / `entertainment_keywords` | […] | 站点声誉与关键词 |
| `url_path_rules` | {…} | 两栖站路径细分规则（zhihu `/question`→study 等，URL 可读时生效） |

## API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 家长看板 | 公开 |
| GET | `/health` | 健康检查 | 公开 |
| GET | `/docs` | Swagger 文档 | 公开 |
| POST | `/check_activity` | 客户端上报判定 | 设备令牌 |
| POST | `/analyze_image` | 服务端视觉分析（RapidOCR 三信号融合，图片入库） | 设备令牌 |
| POST | `/api/screenshots` | 客户端上传固定采样截图（JPEG Base64 传输，服务端以二进制保存） | 设备令牌 |
| GET | `/api/screenshots` | 看板分页读取最近 7 天截图（可按设备过滤） | 公开 |
| GET | `/api/screenshots/{id}/image` | 流式读取单张截图 | 公开 |
| PUT | `/api/screenshots/{id}/vision-label` | 为截图写入人工学习/娱乐标注 | 公开 |
| GET | `/api/stats?days=` | 统计（`days`：1/7/30/0=全部） | 公开 |
| GET | `/api/distribution?days=` | 学习/娱乐分布 | 公开 |
| GET | `/api/trend?hours=` | 时间趋势 | 公开 |
| GET | `/api/search` | 日志搜索（activity/keyword/日期，支持 `since_id` 增量拉取） | 公开 |
| GET | `/api/feedback` | 误报/漏报统计与明细 | 公开 |
| GET | `/api/unknown-top?days=&limit=` | unknown 进程/标题 TOP N 聚合 | 公开 |
| POST | `/api/label` | 家长标注 unknown 样本 → 生成覆盖规则 | 公开 |
| GET | `/api/overrides` | 客户端拉取覆盖规则（按设备过滤） | 公开 |
| POST | `/api/overrides/{id}/toggle` | 停用/启用一条覆盖规则 | 公开 |
| GET | `/api/classification-rules` | 客户端读取启用的统一分类规则 | 公开 |
| POST/PUT/DELETE | `/api/classification-rules...` | 分类规则内部维护接口（看板默认不展示） | 公开 |
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
2. **服务端视觉兜底默认开启**（`enable_server_vision`）：仅「不确定」样本走 OCR；此外固定采样任务每 60 秒上传一张 768px JPEG，截图二进制独立保存并默认保留 7 天。
3. 看板与 `/api/*` 默认公开访问；如需登录保护，可后续接入 `users` 账号体系。
4. `.env`、`config.json`、`*.db`、`logs/`、`.encryption_key` 均已 gitignore，勿提交。
5. 数据库：Docker 部署用 PostgreSQL（数据卷 `postgres_data` 持久）；本地直接运行 `fastapi_server.py` 用 SQLite（仅开发）。

## 许可证

MIT
