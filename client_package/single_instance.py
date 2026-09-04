"""Windows 客户端单实例保护，避免多个监控循环重复上报。"""

import ctypes
import hashlib
import os


class SingleInstance:
    """用当前用户专属的 Windows 命名互斥体守护一个客户端实例。"""

    _ERROR_ALREADY_EXISTS = 183

    def __init__(self, app_name="LearningAppMonitor"):
        identity = os.getenv("USERNAME", "default").encode("utf-8")
        suffix = hashlib.sha256(identity).hexdigest()[:16]
        self._name = f"Local\\{app_name}-{suffix}"
        self._handle = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            # 无法创建互斥体时不阻断客户端；避免权限异常变成无法监控。
            return True
        if ctypes.get_last_error() == self._ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self):
        if self._handle and os.name == "nt":
            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
            self._handle = None
