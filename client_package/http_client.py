"""客户端本机 HTTP 连接。

监控服务、OCR 服务和默认 Ollama 都运行在 localhost；这些请求不应继承系统的
HTTP(S)_PROXY。否则代理软件可能把 localhost 转发到代理端口，产生 502，而请求
实际上从未到达 Docker。
"""

import urllib.request

import requests


session = requests.Session()
session.trust_env = False

url_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def urlopen(request, timeout=None):
    return url_opener.open(request, timeout=timeout)
