"""
前后对比评测：旧分类器(legacy) vs 新分类器(置信度感知融合)。

运行：python eval/run_eval.py   （在 D:\\LearningApp 下，使用托管 Python）
输出：准确率、各类召回、混淆矩阵、由错转对的样本、以及新分类器的回归样本。
注：视觉模型(ONNX)与 VLM/文本LLM 离线不可用，本评测聚焦可离线运行的
    进程+标题+站点声誉 文本信号路径（即本次整改的核心）。
"""
import os
import sys
import json
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
CLIENT_PKG = os.path.join(PROJECT_ROOT, 'client_package')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, CLIENT_PKG)

LABELS = ['study', 'entertainment', 'idle']


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_samples():
    with open(os.path.join(HERE, 'samples.json'), 'r', encoding='utf-8') as f:
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


def main():
    samples = load_samples()
    classify = _load('classify', os.path.join(CLIENT_PKG, 'classify.py'))
    legacy = _load('legacy_classify', os.path.join(HERE, 'legacy_classify.py'))

    old_cm = {a: {b: 0 for b in LABELS} for a in LABELS}
    new_cm = {a: {b: 0 for b in LABELS} for a in LABELS}
    flipped = []     # 旧错 -> 新对
    regressed = []   # 旧对 -> 新错
    both_wrong = []

    for s in samples:
        proc, title, gt = s['processes'], s['title'], s['label']
        old = legacy.legacy_classify(proc, title)
        new = classify.classify_from_signals(proc, title)[0]
        old_cm[gt][old] += 1
        new_cm[gt][new] += 1
        oc, nc = (old == gt), (new == gt)
        if (not oc) and nc:
            flipped.append((s['id'], gt, old, new, title))
        elif oc and (not nc):
            regressed.append((s['id'], gt, old, new, title))
        elif (not oc) and (not nc):
            both_wrong.append((s['id'], gt, old, new, title))

    n = len(samples)
    old_acc = _accuracy(old_cm)
    new_acc = _accuracy(new_cm)

    out = []
    out.append("=" * 70)
    out.append("学习/娱乐分类器 前后对比评测")
    out.append("=" * 70)
    out.append(f"样本数: {n}")
    out.append("")
    out.append(f"旧分类器准确率 : {old_acc*100:5.1f}%   ({sum(old_cm[a][a] for a in LABELS)}/{n})")
    out.append(f"新分类器准确率 : {new_acc*100:5.1f}%   ({sum(new_cm[a][a] for a in LABELS)}/{n})")
    out.append(f"提升           : {(new_acc-old_acc)*100:+.1f} 个百分点")
    out.append("")
    out.append("-- 旧分类器 各类召回 --")
    for a in LABELS:
        out.append(f"  {a:>12}: {_recall(old_cm, a)*100:5.1f}%")
    out.append("-- 新分类器 各类召回 --")
    for a in LABELS:
        out.append(f"  {a:>12}: {_recall(new_cm, a)*100:5.1f}%")
    out.append("")
    out.append("-- 旧分类器 混淆矩阵 --")
    out.append(_fmt_cm(old_cm))
    out.append("")
    out.append("-- 新分类器 混淆矩阵 --")
    out.append(_fmt_cm(new_cm))
    out.append("")
    out.append(f"-- 由错转对 (旧错→新对): {len(flipped)} 个 --")
    for fid, gt, old, new, title in flipped:
        out.append(f"  [{fid}] 真值={gt}  旧={old} -> 新={new}  | {title}")
    out.append("")
    out.append(f"-- 回归 (旧对→新错): {len(regressed)} 个 --")
    for fid, gt, old, new, title in regressed:
        out.append(f"  [{fid}] 真值={gt}  旧={old} -> 新={new}  | {title}")
    out.append("")
    out.append(f"-- 仍双双错误: {len(both_wrong)} 个 --")
    for fid, gt, old, new, title in both_wrong:
        out.append(f"  [{fid}] 真值={gt}  旧={old} -> 新={new}  | {title}")
    out.append("=" * 70)

    report = "\n".join(out)
    print(report)

    with open(os.path.join(HERE, 'report.txt'), 'w', encoding='utf-8') as f:
        f.write(report)


if __name__ == '__main__':
    main()
