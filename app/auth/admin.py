"""家长看板鉴权（轻量密码门）。

- 环境变量 ADMIN_PASSWORD 未设置 → 开放模式（保持向后兼容，默认不拦截）。
- 设置后：/ 与 /api/* 需要登录；/login 提交密码换取 HttpOnly Cookie。
- 会话令牌 = 时间戳 + HMAC-SHA256(JWT_SECRET_KEY, 时间戳)，24 小时有效。
- /health、/docs、/auth/* 等不受影响（设备侧走 JWT，与家长看板无关）。
"""
import hmac
import hashlib
import os
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

SESSION_COOKIE = "admin_session"
SESSION_TTL = 24 * 3600
EXEMPT_PREFIXES = (
    "/login", "/logout", "/health", "/docs", "/redoc",
    "/openapi.json", "/favicon.ico", "/auth/",
)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def admin_enabled() -> bool:
    return bool(ADMIN_PASSWORD)


def _secret() -> str:
    return os.getenv("JWT_SECRET_KEY", "learning-app-secret") + ":admin-gate"


def _make_session() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(_secret().encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"


def _check_session(cookie: str) -> bool:
    try:
        ts, sig = cookie.split(".", 1)
        expect = hmac.new(_secret().encode(), ts.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return False
        return (time.time() - int(ts)) < SESSION_TTL
    except (ValueError, TypeError):
        return False


def is_authed(request: Request) -> bool:
    if not admin_enabled():
        return True  # 开放模式
    return _check_session(request.cookies.get(SESSION_COOKIE, ""))


def is_exempt(path: str) -> bool:
    return path.startswith(EXEMPT_PREFIXES)


router = APIRouter(tags=["admin"])

LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>家长登录 - 活动监控仪表盘</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{background:#f8f9fa;display:flex;align-items:center;justify-content:center;min-height:100vh}.card{width:340px}</style>
</head>
<body>
<div class="card shadow-sm">
  <div class="card-body p-4">
    <h4 class="card-title text-center mb-4">🔒 家长登录</h4>
    <form id="login-form">
      <div class="mb-3">
        <label class="form-label">访问密码</label>
        <input type="password" id="password" name="password" class="form-control" required autofocus>
      </div>
      <button type="submit" class="btn btn-primary w-100">进入看板</button>
    </form>
    <div id="error-box"></div>
  </div>
</div>
<script>
document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pwd = document.getElementById('password').value;
  const resp = await fetch('/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({password: pwd})
  });
  if (resp.ok) { location.href = '/'; }
  else {
    const box = document.getElementById('error-box');
    box.className = 'alert alert-danger mt-3 mb-0 py-2';
    box.textContent = '密码错误，请重试';
  }
});
</script>
</body>
</html>"""


class LoginRequest(BaseModel):
    password: str


@router.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(LOGIN_HTML)


@router.post("/login")
def login(req: LoginRequest):
    if not admin_enabled():
        return RedirectResponse("/", status_code=303)
    if not hmac.compare_digest(req.password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="密码错误")
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, _make_session(), httponly=True, max_age=SESSION_TTL,
                    samesite="lax")
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp
