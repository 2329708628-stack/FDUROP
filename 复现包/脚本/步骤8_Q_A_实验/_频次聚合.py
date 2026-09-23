# -*- coding: utf-8 -*-
"""频次聚合：把多轮整树对齐的边按出现频次筛主指标。

读取 整树_LLM对齐.json（r0 pairs + extra_repeats），统计每条 (human,model) 边
在 N 轮中的出现次数与标签分布，按阈值 k 筛边（多数票标签），复用 aggregate 算指标。

用法：python _频次聚合.py [run_dir]
"""
import json, sys, importlib.util
from pathlib import Path
from collections import defaultdict, Counter

LAB = Path(r"c:\Users\23297\Downloads\Lab")
PAPER_ROOT = LAB / "数据集/数据清洗后论文"


def load_align_module():
    spec = importlib.util.spec_from_file_location(
        "align", str(LAB / "脚本/步骤8_Q_A_实验/_整树LLM对齐.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        PAPER_ROOT / "A05/03_实验输出/Q_A_实验/Q_run_2_S")
    paper = "A05"
    base = PAPER_ROOT / paper / "03_实验输出" / "Q_A_实验"
    run_name = run_dir.name

    align = load_align_module()
    nodes_h = align.load_tree(base / "A_human_baseline")
    nodes_m = align.load_tree(run_dir)
    print(f"人类 {len(nodes_h)} 节点 / 模型 {len(nodes_m)} 节点", flush=True)

    d = json.loads((run_dir / "整树_LLM对齐.json").read_text(encoding="utf-8"))
    rounds = [d["pairs"]] + [er["pairs"] for er in d["extra_repeats"]]
    n_rounds = len(rounds)

    # 边频次 + 标签分布（同轮内同边只计一次，取该轮标签）
    edge_labels = defaultdict(list)
    for ps in rounds:
        seen = {}
        for p in ps:
            key = (p["human"], p["model"])
            if key not in seen:
                seen[key] = p["label"]
        for k, lab in seen.items():
            edge_labels[k].append(lab)

    freq_dist = Counter(len(v) for v in edge_labels.values())
    print(f"\n=== 频次分布（{n_rounds} 轮，共 {len(edge_labels)} 条不同边）===")
    for k in range(n_rounds, 0, -1):
        print(f"  出现 {k}/{n_rounds} 轮：{freq_dist.get(k, 0)} 条")

    # 标签一致性
    consistent = sum(1 for v in edge_labels.values() if len(set(v)) == 1)
    print(f"\n=== 标签一致性 ===")
    print(f"  标签全部一致：{consistent}/{len(edge_labels)} = {round(consistent/len(edge_labels), 4)}")

    # 阈值扫描
    print(f"\n=== 阈值扫描（多数票标签）===")
    print(f"{'k>=':<6}{'边数':<8}{'H覆盖加权':<12}{'H覆盖二值':<12}{'M精度加权':<12}{'M精度二值':<12}")
    for k in range(n_rounds, 0, -1):
        pairs = []
        for (h, m), labels in edge_labels.items():
            if len(labels) >= k:
                top = Counter(labels).most_common(1)[0][0]
                pairs.append({"human": h, "model": m, "label": top, "reason": ""})
        if not pairs:
            print(f"{k:<6}{0:<8}{'-':<12}{'-':<12}{'-':<12}{'-':<12}")
            continue
        agg = align.aggregate(nodes_h, nodes_m, pairs)
        o = agg["overall"]
        print(f"{k:<6}{len(pairs):<8}{o['human_coverage_weighted']:<12}{o['human_coverage_binary']:<12}{o['model_precision_weighted']:<12}{o['model_precision_binary']:<12}")

    # k>=4 主聚合（按记忆约定 k>=4 进主指标）
    print(f"\n=== k>=4 主聚合详情 ===")
    pairs_main = []
    for (h, m), labels in edge_labels.items():
        if len(labels) >= 4:
            c = Counter(labels)
            top, cnt = c.most_common(1)[0]
            pairs_main.append({
                "human": h, "model": m, "label": top,
                "freq": len(labels), "label_split": dict(c),
            })
    print(f"  共 {len(pairs_main)} 条边")
    # 按层统计
    by_lv = defaultdict(lambda: {"h": set(), "m": set()})
    for p in pairs_main:
        # 从节点 level 推断
        pass

    # 写产物
    out = run_dir / "频次聚合.json"
    out.write_text(json.dumps({
        "run": run_name, "n_rounds": n_rounds,
        "total_unique_edges": len(edge_labels),
        "freq_distribution": {str(k): freq_dist.get(k, 0) for k in range(n_rounds, 0, -1)},
        "label_consistent_edges": consistent,
        "edges_k_ge_4": pairs_main,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n产物：{out}")


if __name__ == "__main__":
    main()
