"""截屏工具（GDI 直采，零第三方依赖）。

历史方案 → 问题：
- pyautogui.screenshot() → 依赖 pyscreeze，无法 import 时整个截屏失败
- PIL.ImageGrab.grab()     → 依赖 Pillow；当前 .venv 未装 Pillow 仍会失败

本模块：纯 ctypes 调用 Windows GDI（user32 + gdi32）做 BitBlt 截屏，
仅依赖 numpy + cv2（已装）。任何 Windows + Python 环境即可运行。
"""
import numpy as np


def _foreground_window_region():
    """Windows：返回前台窗口的 (left, top, width, height)；失败返回 None。

    截前台窗口比截全屏的好处：OCR 聚焦目标界面、减少无关画面噪声、
    缩小传输体积（可裁掉任务栏/多显示器空白）。
    """
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        left, top = max(rect.left, 0), max(rect.top, 0)
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0 or width > 4096 or height > 4096:
            return None
        return (left, top, width, height)
    except Exception:
        return None


def _gdi_capture():
    """Windows GDI BitBlt 全屏截屏。返回 BGR ndarray (H, W, 3)。

    SRCCOPY=0x00CC0020；桌面 hwnd=0；BI_RGB=top-down（负 biHeight）。
    """
    import ctypes

    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0

    user32 = ctypes.WinDLL('user32')
    gdi32 = ctypes.WinDLL('gdi32')

    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    if w <= 0 or h <= 0:
        return None

    class BMI(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    hdc_screen = user32.GetWindowDC(0)  # 0 = 桌面
    if not hdc_screen:
        return None

    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbm = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    gdi32.SelectObject(hdc_mem, hbm)
    try:
        if not gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, SRCCOPY):
            return None

        bmi = BMI()
        bmi.biSize = 40
        bmi.biWidth = w
        bmi.biHeight = -h           # 负值=top-down DIB，方便 numpy 直接得到正向图像
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0       # BI_RGB

        buf = (ctypes.c_uint8 * (w * h * 4))()
        bits_copied = gdi32.GetDIBits(hdc_mem, hbm, 0, h, ctypes.byref(buf), ctypes.byref(bmi), DIB_RGB_COLORS)
        if not bits_copied:
            return None

        arr = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(h, w, 4)
        # GDI 返回 BGRA → 取前 3 通道即 BGR
        img = np.ascontiguousarray(arr[:, :, :3])
        return img
    finally:
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)


def capture_screen():
    """优先截前台窗口（先 GDI 全屏再裁切），失败回退 GDI 全屏。返回 BGR ndarray；None=全失败。

    依赖：ctypes（标准库）+ numpy（已装）。零第三方截屏库，pyautogui/pyscreeze/Pillow
    装不上也不影响。
    """
    full = _gdi_capture()
    if full is None:
        return None
    region = _foreground_window_region()
    if not region:
        return full
    l, t, w, h = region
    H, W = full.shape[:2]
    l = max(0, l)
    t = max(0, t)
    r = min(l + w, W)
    b = min(t + h, H)
    if r <= l or b <= t:
        return full
    return full[t:b, l:r].copy()
