"""
人工测试辅助 CLI：给定窗口标题(与可选进程)，打印新分类器判定与明细，
并对照旧分类器结果，便于人工快速验证各类场景。

用法示例：
  python eval/cli_test.py --title "微信" --process weixin.exe
  python eval/cli_test.py --title "B站 考研数学 网课" --process chrome.exe
  python eval/cli_test.py --title "英雄联盟 赛事直播" --process chrome.exe
  python eval/cli_test.py --title "" --process explorer.exe
  python eval/cli_test.py --title "LeetCode 两数之和" --process pycharm64.exe

多个进程用逗号分隔：--process "chrome.exe,idea64.exe"
"""
import argparse
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
legacy = _load('legacy_classify', os.path.join(HERE, 'legacy_classify.py'))


def main():
    ap = argparse.ArgumentParser(description='人工测试辅助：输入标题/进程，看分类结果')
    ap.add_argument('--title', default='', help='活动窗口标题')
    ap.add_argument('--process', default='', help='进程名，多个用逗号分隔')
    args = ap.parse_args()

    procs = [p.strip() for p in args.process.split(',') if p.strip()]

    new_act, dconf, br = classify.classify_from_signals(procs, args.title)
    old_act = legacy.legacy_classify(procs, args.title)

    print('-' * 60)
    print(f'输入  进程: {procs or "[]"}')
    print(f'      标题: {args.title!r}')
    print('-' * 60)
    print(f'进程信号 : {br["process"]}')
    print(f'标题信号 : {br["title"]}')
    print(f'融合明细 : {br.get("fusion")}')
    print('-' * 60)
    print(f'新分类器 : {new_act}   (决策置信度 {dconf})')
    print(f'旧分类器 : {old_act}')
    changed = '  <-- 有变化' if new_act != old_act else ''
    print(f'结论     : {"一致" if new_act == old_act else "新旧不一致"}{changed}')
    print('-' * 60)


if __name__ == '__main__':
    main()
