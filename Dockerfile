FROM python:3.11-slim

WORKDIR /app

# 系统级组件：Tesseract OCR（eng + chi_sim）作为服务端视觉分析的兜底。
# apt/pip 使用国内镜像（阿里云），避免 deb.debian.org / pypi.org 连接不稳导致构建失败
RUN (sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true) \
    && (sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true) \
    && apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

# 仅安装服务端依赖：不含客户端才用的 opencv / onnxruntime / pyautogui
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt -i https://mirrors.aliyun.com/pypi/simple/

# 服务端只需 app/ 包、顶层 logger.py 与 templates/ 看板页面（不含客户端代码、eval、文档等）
COPY app ./app
COPY logger.py ./logger.py
COPY templates ./templates

# 非 root 运行，降低攻击面（root 仅用于构建阶段）
RUN useradd --uid 1000 --create-home app && chown -R app:app /app
USER app

EXPOSE 5000

ENV DATABASE_URL=sqlite:///./server_activity_logs.db \
    APP_ENV=development \
    PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5000/health').status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000", "--log-level", "info", "--no-access-log", "--no-use-colors"]
