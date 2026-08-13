"""诊断：为什么进程信号会一直判"娱乐"。
对比 全量进程扫描(现逻辑) vs 只取前台进程(修复方向)。
"""
import sys

sys.path.insert(0, 'D:/LearningApp')
sys.path.insert(0, 'D:/LearningApp/client_package')

from client_package.classify import (
    _get_running_processes, analyze_processes,
    analyze_title, get_active_window_title, fuse_signals, WEIGHTS,
)

running = _get_running_processes()
print(f"== 当前机器运行进程数: {len(running)} ==")

print("\n-- 现逻辑: 全量进程扫描 analyze_processes(all) --")
pcat, pconf, pdetail = analyze_processes(running)
print(f"process signal: {pcat} conf={pconf} detail={pdetail}")

print("\n-- 每个进程单独会被判成什么 --")
for p in running:
    r = analyze_processes([p])
    if r[1] > 0 or 'browser' in r[2] or 'ambiguous' in r[2]:
        print(f"  {p:30s} -> {r}")

title = get_active_window_title()
print(f"\n== 前台窗口标题: {title!r} ==")
tcat, tconf, site, tdetail = analyze_title(title)
print(f"title signal: {tcat} conf={tconf} site={site} detail={tdetail}")

print("\n== 融合（现逻辑: 全量进程 + 标题）==")
signals = []
if pconf > 0:
    signals.append({'category': pcat, 'weight': WEIGHTS['process'], 'confidence': pconf})
if tconf > 0:
    signals.append({'category': tcat, 'weight': WEIGHTS['title'], 'confidence': tconf})
print("signals:", signals)
act, dconf, scores, unc = fuse_signals(signals)
print(f"fusion -> {act} (conf={dconf}, scores={scores}, uncertain={unc})")

print("\n== 复现: 后台娱乐应用 + 前台 IDE ==")
for combo in (['qq.exe', 'code.exe'], ['code.exe', 'qq.exe'],
              ['wechat.exe', 'pycharm64.exe'], ['spotify.exe', 'Code.exe']):
    r = analyze_processes(combo)
    print(f"  analyze_processes({combo}) -> {r}")

print("\n== 修复后: 只取前台窗口所属进程 ==")
from client_package.classify import _get_foreground_process
fg = _get_foreground_process()
print(f"前台进程: {fg!r}")
if fg:
    r = analyze_processes([fg])
    print(f"analyze_processes([{fg}]) -> {r}")
    print(f"后台 Steam++/VMware/抖音即使开着，也不再参与判定")
