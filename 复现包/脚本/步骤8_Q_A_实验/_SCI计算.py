# -*- coding: utf-8 -*-
"""
_SCI计算.py —— SCI（边收敛度）与结构收敛分析（方案 v4 §2.2 定稿口径）

口径：
- 结构边 = 祖先节点到 M 的边（C→M、B→M，排除 A→M 与 M→A）
- 归一化：模型节点经整树对齐 k≥4 边映射到人类节点，边变为 (人类节点, M)
- SCI = 归一化后与人类基准重合的结构边数 ÷ 人类结构边总数，越高越收敛
- 全池绑定节点（单节点 sources 数 > 阈值）剔除，防交集虚高
- 两模型 run 之间：M 收敛（同一人类节点上两组共同指向同一 M）、B 收敛（共同指向同一章节，宽/严两口径）

用法：
    python _SCI计算.py --run-dir Q_run_2_S --other-run-dir A_run_2_S [--human-dir A_human_baseline] [--k 4]

输出：<run-dir>/SCI计算.json + 控制台摘要
"""
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

LAB = Path(r"c:\Users\23297\Downloads\Lab")
BASE = LAB / "数据集" / "数据清洗后论文" / "A05" / "03_实验输出" / "Q_A_实验"
MAX_SOURCES = 15  # 全池绑定阈值：单节点 sources 超过此数视为 anchor 大段误并，剔除

M_RE_NUM = lambda s: int("".join(ch for ch in s.split(".")[0] if ch.isdigit()) or 0)


def load_sources(run_dir: Path) -> dict:
    """读 run.json 的 encoding_table，返回 {节点id: set(M编号)}（A/B/C 全层）。"""
    d = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    et = d["encoding_table"]
    src = {}
    for lvl in ("A_level", "B_level", "C_level"):
        for n in et[lvl]:
            src[n["id"]] = set(n.get("sources") or [])
    return src


def load_k4_edges(run_dir: Path, k: int):
    """读频次聚合.json，返回 [(human, model)]（freq≥k）。"""
    fq = json.loads((run_dir / "频次聚合.json").read_text(encoding="utf-8"))
    return [(e["human"], e["model"]) for e in fq["edges_k_ge_4"] if e["freq"] >= k]


def structure_edges(src: dict) -> set:
    """结构边集合 {(节点id, M)}：C→M、B→M；A 层与全池绑定节点排除。"""
    return {(nid, m) for nid, ms in src.items()
            if not nid.startswith("A") and len(ms) <= MAX_SOURCES
            for m in ms}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="模型 run 目录名（如 Q_run_2_S）")
    ap.add_argument("--other-run-dir", default=None, help="第二模型 run 目录名（可选，用于组间 M/B 收敛）")
    ap.add_argument("--human-dir", default="A_human_baseline")
    ap.add_argument("--k", type=int, default=4)
    args = ap.parse_args()

    run_dir = BASE / args.run_dir
    human_dir = BASE / args.human_dir
    h_src = load_sources(human_dir)
    m_src = load_sources(run_dir)

    h_edges = structure_edges(h_src)
    # 全池绑定节点记录（质控）
    polluted = {nid: len(ms) for nid, ms in {**h_src, **m_src}.items() if len(ms) > MAX_SOURCES}

    # 归一化：模型 C →（k≥4 对齐边）→ 人类节点，结构边变为 (人类节点, M)
    norm_edges = set()
    for h, m in load_k4_edges(run_dir, args.k):
        for mm in m_src.get(m, set()):
            norm_edges.add((h, mm))

    sci = len(h_edges & norm_edges) / len(h_edges) if h_edges else 0.0

    out = {
        "run": args.run_dir,
        "human_dir": args.human_dir,
        "k_threshold": args.k,
        "max_sources_threshold": MAX_SOURCES,
        "human_structure_edges": len(h_edges),
        "model_normalized_edges": len(norm_edges),
        "overlap_edges": len(h_edges & norm_edges),
        "SCI": round(sci, 4),
        "polluted_nodes": polluted,
    }

    # 组间收敛（两个模型 run 归一化到同一人类节点后比较 M/B 指向）
    if args.other_run_dir:
        other_dir = BASE / args.other_run_dir
        o_src = load_sources(other_dir)
        h2m = defaultdict(list)
        for h, m in load_k4_edges(run_dir, args.k):
            h2m[h].append(m)
        h2o = defaultdict(list)
        for h, m in load_k4_edges(other_dir, args.k):
            h2o[h].append(m)

        common_h = sorted(set(h2m) & set(h2o))
        m_conv, detail = 0, []
        for h in common_h:
            ms = set().union(*[m_src.get(x, set()) for x in h2m[h]])
            os_ = set().union(*[o_src.get(x, set()) for x in h2o[h]])
            inter = ms & os_
            if inter:
                m_conv += 1
            detail.append({"human": h, "Q": sorted(ms), "other": sorted(os_),
                           "common_M": sorted(inter)})

        chap = lambda ids: {"".join(ch for ch in i.split(".")[0] if ch.isdigit()) for i in ids}
        b_strict = b_loose = 0
        for h in common_h:
            sq, so, sh = chap(h2m[h]), chap(h2o[h]), chap([h])
            if sq & so:
                b_loose += 1
                if sq & so & sh:
                    b_strict += 1

        out["between_runs"] = {
            "other_run": args.other_run_dir,
            "common_aligned_nodes": len(common_h),
            "M_converged_nodes": m_conv,
            "B_converged_loose": b_loose,
            "B_converged_strict": b_strict,
            "detail": detail,
        }

    dest = run_dir / "SCI计算.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== SCI 计算：{args.run_dir}（k≥{args.k}，全池阈值 {MAX_SOURCES}） ===")
    print(f"人类结构边 {len(h_edges)} | 归一化模型边 {len(norm_edges)} | 重合 {len(h_edges & norm_edges)}")
    print(f"SCI = {sci:.4f}")
    if polluted:
        print(f"全池绑定剔除节点: { {k: v for k, v in polluted.items()} }")
    if args.other_run_dir:
        b = out["between_runs"]
        print(f"组间（{args.run_dir} vs {args.other_run_dir}）：共同对齐 {b['common_aligned_nodes']} 节点 | "
              f"M 收敛 {b['M_converged_nodes']} | B 收敛 宽{b['B_converged_loose']}/严{b['B_converged_strict']}")
    print(f"已写入 {dest}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
