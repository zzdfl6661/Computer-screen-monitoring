"""
浏览器地址栏 URL 读取（Windows UI Automation，comtypes，可选依赖）。

为什么：浏览器时段只靠窗口标题（尾部站点名）噪声大——两栖站（bilibili/知乎/
百度）的学习与娱乐内容无法区分，而 URL 的域名+路径是最干净的信号。
依赖：comtypes（纯 Python，轻量）。未安装/读取失败/非 Windows → 返回 None，
分类器自动退回纯标题判定，不影响主流程。
"""
import logging
import platform

try:
    from .config import ConfigManager
except Exception:
    from config import ConfigManager

logger = logging.getLogger(__name__)

# UIA 属性/条件常量（UIAutomationClient）
_UIA_CONTROL_TYPE_PROPERTY_ID = 30003
_UIA_EDIT_CONTROL_TYPE_ID = 50004
_UIA_VALUE_VALUE_PROPERTY_ID = 30011
_UIA_TREE_SCOPE_DESCENDANTS = 0x4

_uia = None          # 进程级缓存：IUIAutomation 实例
_uia_ready = False   # 初始化已尝试标记（失败不重试，避免每 5 秒报错刷屏）


def _init_uia():
    global _uia, _uia_ready
    if _uia_ready:
        return _uia
    _uia_ready = True
    if platform.system() != 'Windows':
        return None
    try:
        import comtypes
        import comtypes.client
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
        comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
        _uia = comtypes.client.CreateObject(
            CUIAutomation, interface=IUIAutomation)
    except Exception as e:
        logger.info(f"UIA 初始化失败（浏览器 URL 信号不可用，退回标题判定）: {e}")
        _uia = None
    return _uia


def get_browser_url(hwnd=None):
    """读浏览器窗口地址栏 URL。hwnd 为 None 时取前台窗口。

    返回 URL 字符串；任何失败返回 None（调用方降级）。
    Chrome/Edge 主窗口后代中的第一个 Edit 控件即 omnibox；名字含
    「地址」/「Address」的 Edit 优先（更稳，页面内输入框不会误中）。
    """
    uia = _init_uia()
    if uia is None:
        return None
    try:
        import ctypes
        import comtypes
        import comtypes.automation

        if hwnd is None:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None

        root = uia.ElementFromHandle(hwnd)
        if root is None:
            return None

        cond = uia.CreatePropertyCondition(
            _UIA_CONTROL_TYPE_PROPERTY_ID,
            comtypes.automation.VARIANT(_UIA_EDIT_CONTROL_TYPE_ID))
        arr = root.FindAll(_UIA_TREE_SCOPE_DESCENDANTS, cond)
        if arr is None or arr.Length == 0:
            return None

        edit = None
        for i in range(arr.Length):
            el = arr.GetElement(i)
            try:
                name = el.CurrentName or ''
            except Exception:
                name = ''
            if '地址' in name or 'address' in name.lower():
                edit = el
                break
            if edit is None:
                edit = el
        if edit is None:
            return None

        val = edit.GetCurrentPropertyValue(_UIA_VALUE_VALUE_PROPERTY_ID)
        url = val.value if val is not None else None
        if url and url.startswith(('http://', 'https://', 'file://')):
            return url
        return None
    except Exception as e:
        logger.debug(f"浏览器 URL 读取失败: {e}")
        return None


if __name__ == '__main__':
    # 手动冒烟：把某个浏览器窗口置前后运行本文件
    print(get_browser_url())
