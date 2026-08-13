"""
冒烟测试：验证分类器在“离线 + 可选模型缺失”时的健壮性。
重点确认：开启文本LLM/VLM 开关但本机无推理服务时，系统优雅降级、不崩溃。
运行：python eval/smoke_test.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'client_package'))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


classify = _load('classify', os.path.join(ROOT, 'client_package', 'classify.py'))
llm = _load('llm_judge', os.path.join(ROOT, 'client_package', 'llm_judge.py'))
vlm = _load('vlm_classifier', os.path.join(ROOT, 'client_package', 'vlm_classifier.py'))


def ok(name, cond, extra=''):
    print(('[PASS] ' if cond else '[FAIL] ') + name + (('  -> ' + extra) if extra else ''))


def main():
    print('=== 冒烟测试 ===')

    # 1) 主路径：浏览器学习场景应判 study
    act, dconf, br = classify.classify_from_signals(['chrome.exe'], 'coursera 机器学习')
    ok('主路径-浏览器学习判 study', act == 'study', f'act={act} conf={dconf}')

    # 2) 文本LLM 开启但本机无 ollama -> 优雅回退规则，不崩溃
    try:
        cat, conf, reason = llm.TextJudge().judge(['chrome.exe'], 'coursera 机器学习', 'coursera')
        ok('文本LLM 离线优雅回退', cat in ('study', 'entertainment', 'idle') and conf >= 0,
           f'cat={cat} conf={conf} reason={reason}')
    except Exception as e:
        ok('文本LLM 离线优雅回退', False, repr(e))

    # 3) VLM 模型/截屏缺失 -> 优雅降级，不崩溃
    # 构造假图像：有 numpy 用真数组（生产环境），无则传占位符（classify 内部因缺 cv2 同样优雅降级）
    try:
        try:
            import numpy as np
            fake_img = np.zeros((64, 64, 3), dtype=np.uint8)
        except Exception:
            fake_img = None
        cat, conf = vlm.VLMClassifier().classify(fake_img)
        ok('VLM 缺失优雅降级', cat in (None, 'study', 'entertainment', 'idle') and conf >= 0,
           f'cat={cat} conf={conf}')
    except Exception as e:
        ok('VLM 缺失优雅降级', False, repr(e))

    # 4) 主分类在多种输入下不崩溃
    try:
        for proc, title in [
            (['code.exe'], 'main.py - Visual Studio Code'),
            (['chrome.exe'], '抖音 搞笑视频'),
            (['explorer.exe'], ''),
            (['idea64.exe'], 'MyProject - IntelliJ IDEA'),
        ]:
            a, _, _ = classify.classify_from_signals(proc, title)
            assert a in ('study', 'entertainment', 'idle')
        ok('主分类多输入不崩溃', True)
    except Exception as e:
        ok('主分类多输入不崩溃', False, repr(e))

    print('=== 完成 ===')


if __name__ == '__main__':
    main()
