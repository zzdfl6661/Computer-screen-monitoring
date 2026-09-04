"""
融合参数网格搜索：fusion_min_confidence / fusion_margin / process / title 权重。

运行：python eval/grid_search.py
目标：v1+v2 全样本「严格准确率」最大化（unknown 视为错误），
     同时报告弃权率（弃权交视觉兜底，不算错但有成本）。
说明：直接改写 classify 模块级变量（FUSION_MIN_CONF / FUSION_MARGIN / WEIGHTS），
     不落盘 config.json；最优参数由人工确认后写入配置。
"""
import os
import sys
import json
import itertools
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
CLIENT_PKG = os.path.join(PROJECT_ROOT, 'client_package')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, CLIENT_PKG)


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    classify = _load('classify', os.path.join(CLIENT_PKG, 'classify.py'))
    samples = []
    for fname in ('samples.json', 'samples_v2.json'):
        with open(os.path.join(HERE, fname), encoding='utf-8') as f:
            samples.extend(json.load(f))

    grid = {
        'process': [0.35, 0.40, 0.45, 0.50, 0.55],
        'title': [0.25, 0.30, 0.35],
        'min_conf': [0.30, 0.35, 0.40, 0.45, 0.50],
        'margin': [0.03, 0.05, 0.08, 0.10],
    }

    results = []
    for wp, wt, mc, mg in itertools.product(grid['process'], grid['title'],
                                            grid['min_conf'], grid['margin']):
        classify.WEIGHTS['process'] = wp
        classify.WEIGHTS['title'] = wt
        classify.FUSION_MIN_CONF = mc
        classify.FUSION_MARGIN = mg
        ok = abstain = 0
        for s in samples:
            pred = classify.classify_from_signals(s['processes'], s['title'])[0]
            if pred not in ('study', 'entertainment', 'idle'):
                abstain += 1
            elif pred == s['label']:
                ok += 1
        n = len(samples)
        results.append({
            'process': wp, 'title': wt, 'min_conf': mc, 'margin': mg,
            'strict_acc': ok / n, 'decided_acc': ok / (n - abstain) if n > abstain else 0.0,
            'abstain': abstain,
        })

    # 排序：严格准确率降序 → 弃权升序（同准确率下少弃权更好）
    results.sort(key=lambda r: (-r['strict_acc'], r['abstain']))

    out = []
    out.append("=" * 78)
    out.append(f"融合参数网格搜索（v1+v2 共 {len(samples)} 样本）")
    out.append("=" * 78)
    out.append(f"{'process':>8} {'title':>7} {'min_conf':>9} {'margin':>7} "
               f"{'严格准确率':>10} {'决策准确率':>10} {'弃权':>5}")
    for r in results[:15]:
        out.append(f"{r['process']:>8} {r['title']:>7} {r['min_conf']:>9} {r['margin']:>7} "
                   f"{r['strict_acc']*100:>9.1f}% {r['decided_acc']*100:>9.1f}% {r['abstain']:>5}")
    out.append("")
    out.append(f"参数组合总数: {len(results)}")
    best = results[0]
    out.append(f"最优: process={best['process']} title={best['title']} "
               f"min_conf={best['min_conf']} margin={best['margin']} "
               f"→ 严格 {best['strict_acc']*100:.1f}% / 弃权 {best['abstain']}/{len(samples)}")
    cur = [r for r in results if r['process'] == 0.45 and r['title'] == 0.30
           and r['min_conf'] == 0.40 and r['margin'] == 0.05][0]
    out.append(f"当前配置(0.45/0.30/0.40/0.05): 严格 {cur['strict_acc']*100:.1f}% / "
               f"弃权 {cur['abstain']}/{len(samples)}（排名 "
               f"{results.index(cur)+1}/{len(results)}）")
    report = "\n".join(out)
    print(report)
    with open(os.path.join(HERE, 'grid_search_report.txt'), 'w', encoding='utf-8') as f:
        f.write(report)


if __name__ == '__main__':
    main()
