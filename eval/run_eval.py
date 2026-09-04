"""
前后对比评测：旧分类器(legacy) vs 新分类器(置信度感知融合)。

运行：python eval/run_eval.py   （在 D:\\LearningApp 下，使用托管 Python）
输出：
  - samples.json     (v1, 48 条代表性场景)
  - samples_v2.json  (v2, 165 条真实场景 + 对抗/语义难例 + 规则盲区，带 tag)
指标：
  - 严格准确率（unknown 视为错误）
  - 决策准确率（仅在给出 study/entertainment/idle 判定的样本上计算）
  - 弃权率（unknown 比例——过高说明规则覆盖不足，会大量触发视觉兜底）
  - 各类召回 / 混淆矩阵 / 回归样本 / v2 分 tag 准确率
注：视觉模型(ONNX)与 VLM/文本LLM 离线不可用，本评测聚焦可离线运行的
    进程+标题+站点声誉 文本信号路径（即本次整改的核心）。
"""
import os
import sys
import json
import importlib.util
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
CLIENT_PKG = os.path.join(PROJECT_ROOT, 'client_package')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, CLIENT_PKG)

LABELS = ['study', 'entertainment', 'idle']
DECIDED = set(LABELS)


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_samples(name):
    with open(os.path.join(HERE, name), 'r', encoding='utf-8') as f:
        return json.load(f)


def _accuracy(cm):
    total = sum(cm[a][b] for a in LABELS for b in LABELS)
    correct = sum(cm[a][a] for a in LABELS)
    return (correct / total) if total else 0.0


def _recall(cm, label):
    denom = sum(cm[label][b] for b in LABELS)
    return (cm[label][label] / denom) if denom else 0.0


def _fmt_cm(cm):
    lines = ["                预测", "              " + " ".join(f"{b:>12}" for b in LABELS)]
    for a in LABELS:
        lines.append(f"实际 {a:>8}  " + " ".join(f"{cm[a][b]:>12}" for b in LABELS))
    return "\n".join(lines)


def run_set(classify, legacy, samples, set_name):
    """跑一个样本集，返回 (lines, summary)。"""
    old_cm = {a: {b: 0 for b in LABELS} for a in LABELS}
    new_cm = {a: {b: 0 for b in LABELS} for a in LABELS}
    abstain = defaultdict(int)          # gt -> unknown 次数（弃权）
    tag_stats = defaultdict(lambda: {'n': 0, 'ok': 0, 'abstain': 0})
    regressed = []
    wrong = []

    for s in samples:
        proc, title, gt = s['processes'], s['title'], s['label']
        tag = s.get('tag', 'plain')
        old = legacy.legacy_classify(proc, title)
        new = classify.classify_from_signals(proc, title)[0]
        if old in DECIDED:
            old_cm[gt][old] += 1
        if new in DECIDED:
            new_cm[gt][new] += 1
        else:
            abstain[gt] += 1
        oc, nc = (old == gt), (new == gt)
        tag_stats[tag]['n'] += 1
        if nc:
            tag_stats[tag]['ok'] += 1
        elif new not in DECIDED:
            tag_stats[tag]['abstain'] += 1
        if oc and not nc:
            regressed.append((s['id'], gt, old, new, title))
        if not nc:
            wrong.append((s['id'], gt, old, new, title, tag))

    n = len(samples)
    n_abstain = sum(abstain.values())
    old_acc = _accuracy(old_cm)
    new_acc = _accuracy(new_cm)
    # 决策准确率：unknown 不计入分母（弃权交给视觉兜底，不算判错）
    decided_total = sum(new_cm[a][b] for a in LABELS for b in LABELS)
    decided_correct = sum(new_cm[a][a] for a in LABELS)
    decided_acc = (decided_correct / decided_total) if decided_total else 0.0

    out = []
    out.append("-" * 70)
    out.append(f"样本集 {set_name}: {n} 条")
    out.append(f"  旧分类器准确率       : {old_acc*100:5.1f}%")
    out.append(f"  新分类器 严格准确率  : {new_acc*100:5.1f}%   ({sum(new_cm[a][a] for a in LABELS)}/{n})")
    out.append(f"  新分类器 决策准确率  : {decided_acc*100:5.1f}%   "
               f"({decided_correct}/{decided_total}, 不含弃权)")
    out.append(f"  弃权率(unknown)      : {n_abstain*100/n:5.1f}%   ({n_abstain}/{n})  → 交视觉兜底")
    out.append("  -- 新分类器 各类召回 --")
    for a in LABELS:
        out.append(f"    {a:>14}: {_recall(new_cm, a)*100:5.1f}%   (弃权 {abstain.get(a, 0)} 条)")
    out.append("  -- 新分类器 混淆矩阵 --")
    out.append("  " + _fmt_cm(new_cm).replace("\n", "\n  "))

    if any(t != 'plain' for t in tag_stats):
        out.append("  -- 分 tag 统计 (ok/abstain/n) --")
        for tag in sorted(tag_stats, key=lambda t: -tag_stats[t]['n']):
            st = tag_stats[tag]
            out.append(f"    {tag:>12}: {st['ok']:3}/{st['abstain']:2}弃权/{st['n']:3}  "
                       f"严格准确率 {st['ok']/st['n']*100:5.1f}%")

    if regressed:
        out.append(f"  -- 回归 (旧对→新错): {len(regressed)} 个 --")
        for fid, gt, old, new, title in regressed:
            out.append(f"    [{fid}] 真值={gt}  旧={old} -> 新={new}  | {title}")
    if wrong:
        out.append(f"  -- 新分类器未命对样本: {len(wrong)} 个 (含弃权) --")
        for fid, gt, old, new, title, tag in wrong:
            out.append(f"    [{fid}][{tag}] 真值={gt} -> 预测={new}  | {title}")
    summary = {
        'n': n, 'old_acc': old_acc, 'new_acc': new_acc,
        'decided_acc': decided_acc, 'abstain': n_abstain,
        'wrong': len(wrong),
    }
    return out, summary


def main():
    classify = _load('classify', os.path.join(CLIENT_PKG, 'classify.py'))
    legacy = _load('legacy_classify', os.path.join(HERE, 'legacy_classify.py'))

    out = []
    out.append("=" * 70)
    out.append("学习/娱乐分类器 前后对比评测")
    out.append("=" * 70)
    summaries = {}
    for name, fname in [("v1 代表性场景集", 'samples.json'),
                        ("v2 真实+对抗+盲区集", 'samples_v2.json')]:
        lines, summary = run_set(classify, legacy, load_samples(fname), name)
        out.extend(lines)
        summaries[name] = summary

    out.append("=" * 70)
    out.append("汇总:")
    for k, s in summaries.items():
        out.append(f"  {k}: 旧 {s['old_acc']*100:.1f}% -> 新 严格 {s['new_acc']*100:.1f}% / "
                   f"决策 {s['decided_acc']*100:.1f}% (弃权 {s['abstain']}/{s['n']})")

    report = "\n".join(out)
    print(report)
    with open(os.path.join(HERE, 'report.txt'), 'w', encoding='utf-8') as f:
        f.write(report)


if __name__ == '__main__':
    main()
