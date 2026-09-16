# -*- coding: utf-8 -*-
"""Q_A 实验跨论文对比器（人类基准 vs 模型生成）。
输入：两个 run.json 路径（第一个为 gold 人类基准，第二个为模型生成）。
用法：
  python 脚本/步骤8_Q_A_实验/Q_A对比.py <gold_run.json> <model_run.json> [报告输出路径]

输出指标：
  1) 结构对比：A/B/C 节点数、深度分布、平均每节点字数
  2) 史料覆盖对比：M 使用集合、覆盖率、Precision/Recall/F1（gold 为基准）
  3) 锚点段对比：anchor P 集合、Jaccard、覆盖率
  4) claim 文本相似度：按 title_label 模糊匹配的 A/B 节点对做 difflib 相似度
  5) 综合差距评分：M_F1、anchor_Jaccard、claim_平均相似度 的几何平均
"""
import json, sys, difflib, re
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "步骤3_v3.2抽取"))
from 公共库 import m_key

gold_path = Path(sys.argv[1])
model_path = Path(sys.argv[2])
out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else model_path.parent / "Q_A_comparison_report.json"

gold = json.load(open(gold_path, encoding="utf-8"))
model = json.load(open(model_path, encoding="utf-8"))

def summarize(d):
    A = d["encoding_table"]["A_level"]
    B = d["encoding_table"]["B_level"]
    C = d["encoding_table"]["C_level"]
    M = d["encoding_table"]["M_level"]
    used_M = set()
    for c in C:
        used_M |= set(c.get("sources", []))
    anchors = {c["anchor"] for c in C}
    all_claims = [n.get("claim", "") for n in A + B if n.get("claim")] + [c.get("text", "") for c in C]
    return {
        "A": A, "B": B, "C": C, "M_total": M,
        "used_M": used_M, "anchors": anchors,
        "depth_dist": {
            "A": len(A),
            "B_depth2": len([b for b in B if b.get("depth") == 2]),
            "B_depth3": len([b for b in B if b.get("depth") == 3]),
            "C": len(C),
        },
        "claim_text_length_sum": sum(len(x) for x in all_claims),
        "claim_text_count": len(all_claims),
    }

g = summarize(gold)
m = summarize(model)

# ---------- 1. 结构对比 ----------
print("=" * 78)
print("一、结构对比（节点数 / 深度分布）")
print("=" * 78)
print(f"{'指标':<24}{'人类基准':>14}{'模型生成':>14}{'差值':>12}{'比值%':>10}")
print("-" * 78)
for k, label in [("A", "A 节点"), ("B_depth2", "B depth=2"), ("B_depth3", "B depth=3"),
                 ("C", "C 节点")]:
    gv = g["depth_dist"][k]
    mv = m["depth_dist"][k]
    diff = mv - gv
    ratio = (mv / gv * 100) if gv else float("inf")
    print(f"{label:<22}{gv:>14}{mv:>14}{diff:>+12}{ratio:>9.1f}%")
print("-" * 78)
total_g = sum(g["depth_dist"].values())
total_m = sum(m["depth_dist"].values())
print(f"{'节点总数':<22}{total_g:>14}{total_m:>14}{total_m - total_g:>+12}{(total_m/total_g*100 if total_g else 0):>9.1f}%")
print(f"{'平均 claim 字数':<22}"
      f"{g['claim_text_length_sum']/max(g['claim_text_count'],1):>14.1f}"
      f"{m['claim_text_length_sum']/max(m['claim_text_count'],1):>14.1f}")

# ---------- 2. 史料覆盖对比 ----------
print("=" * 78)
print("二、史料（M）覆盖对比")
print("=" * 78)
total_M = len(g["M_total"]) or len(m["M_total"])
g_M, m_M = g["used_M"], m["used_M"]
print(f"史料池大小: {total_M}")
print(f"人类基准使用 M: {len(g_M)}/{total_M} = {len(g_M)/total_M*100:.1f}%")
print(f"模型生成使用 M: {len(m_M)}/{total_M} = {len(m_M)/total_M*100:.1f}%")
print(f"  交集: {len(g_M & m_M)}  仅基准: {len(g_M - m_M)}  仅模型: {len(m_M - g_M)}")
# 以 gold 为基准的 P/R/F1
tp = len(g_M & m_M)
fp = len(m_M - g_M)
fn = len(g_M - m_M)
P = tp / (tp + fp) if (tp + fp) else 0
R = tp / (tp + fn) if (tp + fn) else 0
F1 = 2*P*R / (P+R) if (P+R) else 0
print(f"  Precision={P:.3f}  Recall={R:.3f}  F1={F1:.3f}")
print(f"  模型漏用 M: {sorted(g_M - m_M, key=m_key)}")
print(f"  模型多用 M（不应存在，因 gold 为全集基准）: {sorted(m_M - g_M, key=m_key)}")

# ---------- 3. 锚点段对比 ----------
print("=" * 78)
print("三、锚点段（anchor P）覆盖对比")
print("=" * 78)
g_A, m_A = g["anchors"], m["anchors"]
print(f"人类基准 anchor 段: {len(g_A)} 段  {sorted(g_A)}")
print(f"模型生成 anchor 段: {len(m_A)} 段  {sorted(m_A)}")
inter = g_A & m_A
union = g_A | m_A
print(f"  交集: {len(inter)}  并集: {len(union)}  Jaccard: {len(inter)/len(union):.3f}")
# 每段 C 条数对比
print("-" * 78)
print(f"{'anchor':<10}{'基准C条数':>12}{'模型C条数':>12}{'基准M集':>12}{'模型M集':>12}{'M_Jaccard':>12}")
g_by_p = defaultdict(list)
m_by_p = defaultdict(list)
for c in g["C"]:
    g_by_p[c["anchor"]].append(c)
for c in m["C"]:
    m_by_p[c["anchor"]].append(c)
all_p = sorted(g_A | m_A, key=lambda x: int(x[1:]) if x[1:].isdigit() else 9999)
anchor_rows = []
for p_ in all_p:
    gc = g_by_p.get(p_, [])
    mc = m_by_p.get(p_, [])
    gms = set().union(*[set(c.get("sources", [])) for c in gc]) if gc else set()
    mms = set().union(*[set(c.get("sources", [])) for c in mc]) if mc else set()
    j = len(gms & mms) / len(gms | mms) if (gms | mms) else 1.0
    anchor_rows.append({"anchor": p_, "gold_C": len(gc), "model_C": len(mc),
                        "gold_M": len(gms), "model_M": len(mms),
                        "M_Jaccard": round(j, 3)})
    print(f"{p_:<10}{len(gc):>12}{len(mc):>12}{len(gms):>12}{len(mms):>12}{j:>12.3f}")

# ---------- 4. claim 文本相似度（按 title_label 模糊匹配） ----------
print("=" * 78)
print("四、A/B claim 文本相似度（按 title_label 模糊匹配）")
print("=" * 78)
def norm(t):
    return re.sub(r"\s+", "", (t or "")).replace("(", "（").replace(")", "）")

g_nodes = [{"id": n["id"], "title_label": n.get("title_label", ""),
            "claim": n.get("claim", ""), "depth": n.get("depth")}
           for n in g["A"] + g["B"]]
m_nodes = [{"id": n["id"], "title_label": n.get("title_label", ""),
            "claim": n.get("claim", ""), "depth": n.get("depth")}
           for n in m["A"] + m["B"]]

# 先尝试精确 title_label 匹配，再 difflib 模糊匹配
g_by_title = defaultdict(list)
for n in g_nodes:
    g_by_title[norm(n["title_label"])].append(n)
m_by_title = defaultdict(list)
for n in m_nodes:
    m_by_title[norm(n["title_label"])].append(n)

claim_pairs = []
matched_g, matched_m = set(), set()
# 精确匹配
for t, gs in g_by_title.items():
    if t in m_by_title:
        for gi, gn in enumerate(gs):
            for mi, mn in enumerate(m_by_title[t]):
                if gn["id"] in matched_g or mn["id"] in matched_m:
                    continue
                s = difflib.SequenceMatcher(None, gn["claim"], mn["claim"]).ratio()
                claim_pairs.append({"gold_id": gn["id"], "model_id": mn["id"],
                                    "title_label": gn["title_label"],
                                    "gold_claim": gn["claim"], "model_claim": mn["claim"],
                                    "sim": round(s, 3)})
                matched_g.add(gn["id"])
                matched_m.add(mn["id"])
# 模糊匹配（剩余节点）
for gn in g_nodes:
    if gn["id"] in matched_g:
        continue
    best = None
    for mn in m_nodes:
        if mn["id"] in matched_m:
            continue
        # title_label 相似度
        ts = difflib.SequenceMatcher(None, norm(gn["title_label"]), norm(mn["title_label"])).ratio()
        if ts < 0.5:
            continue
        cs = difflib.SequenceMatcher(None, gn["claim"], mn["claim"]).ratio()
        score = ts * 0.5 + cs * 0.5
        if best is None or score > best[0]:
            best = (score, ts, cs, mn)
    if best:
        mn = best[3]
        claim_pairs.append({"gold_id": gn["id"], "model_id": mn["id"],
                            "title_label": gn["title_label"] + " ≈ " + mn["title_label"],
                            "gold_claim": gn["claim"], "model_claim": mn["claim"],
                            "sim": round(best[2], 3),
                            "title_sim": round(best[1], 3)})
        matched_g.add(gn["id"])
        matched_m.add(mn["id"])

claim_pairs.sort(key=lambda x: x["sim"])
print(f"匹配上的 A/B 节点对: {len(claim_pairs)} 对  "
      f"(gold {len(g_nodes)} 个, model {len(m_nodes)} 个)")
if claim_pairs:
    sims = [p["sim"] for p in claim_pairs]
    print(f"claim 文本相似度: 均值 {sum(sims)/len(sims):.3f}  最低 {min(sims):.3f}  最高 {max(sims):.3f}")
    print(f"  相似度 <0.3 的对: {sum(1 for s in sims if s < 0.3)}")
    print(f"  相似度 ≥0.5 的对: {sum(1 for s in sims if s >= 0.5)}")
print("-" * 78)
print(f"{'gold_id':<10}{'model_id':<14}{'sim':>8}  {'title_label':<40}")
for p in claim_pairs:
    print(f"{p['gold_id']:<10}{p['model_id']:<14}{p['sim']:>8.3f}  {p['title_label'][:38]:<40}")
# 显示低相似度的几对详细文本
low_pairs = [p for p in claim_pairs if p["sim"] < 0.5][:5]
if low_pairs:
    print("-" * 78)
    print("低相似度对（<0.5）示例：")
    for p in low_pairs:
        print(f"  [{p['gold_id']} vs {p['model_id']}] {p['title_label'][:30]}")
        print(f"    gold:  {p['gold_claim'][:80]}")
        print(f"    model: {p['model_claim'][:80]}")

# ---------- 5. 综合差距评分 ----------
print("=" * 78)
print("五、综合对比指标汇总")
print("=" * 78)
metrics = {
    "M_coverage_gold": round(len(g_M)/total_M*100, 1),
    "M_coverage_model": round(len(m_M)/total_M*100, 1),
    "M_Precision": round(P, 3),
    "M_Recall": round(R, 3),
    "M_F1": round(F1, 3),
    "anchor_Jaccard": round(len(inter)/len(union) if union else 1, 3),
    "nodes_total_gold": total_g,
    "nodes_total_model": total_m,
    "nodes_ratio_percent": round(total_m/total_g*100 if total_g else 0, 1),
    "C_count_gold": len(g["C"]),
    "C_count_model": len(m["C"]),
    "C_ratio_percent": round(len(m["C"])/len(g["C"])*100 if g["C"] else 0, 1),
    "matched_claim_pairs": len(claim_pairs),
    "claim_sim_mean": round(sum(p["sim"] for p in claim_pairs)/len(claim_pairs), 3) if claim_pairs else 0,
    "claim_sim_min": round(min(p["sim"] for p in claim_pairs), 3) if claim_pairs else 0,
}
for k, v in metrics.items():
    print(f"  {k:<28} {v}")

# 保存报告
report = {
    "gold_run": str(gold_path),
    "model_run": str(model_path),
    "structure": {
        "gold": g["depth_dist"], "model": m["depth_dist"],
        "gold_total": total_g, "model_total": total_m,
    },
    "material_coverage": {
        "total_M": total_M,
        "gold_used": len(g_M), "model_used": len(m_M),
        "gold_coverage_pct": round(len(g_M)/total_M*100, 1),
        "model_coverage_pct": round(len(m_M)/total_M*100, 1),
        "gold_only": sorted(g_M - m_M, key=m_key),
        "model_only": sorted(m_M - g_M, key=m_key),
        "Precision": round(P, 3), "Recall": round(R, 3), "F1": round(F1, 3),
    },
    "anchor_coverage": {
        "gold_anchors": sorted(g_A), "model_anchors": sorted(m_A),
        "intersection": sorted(inter), "Jaccard": metrics["anchor_Jaccard"],
        "per_anchor": anchor_rows,
    },
    "claim_comparison": claim_pairs,
    "metrics": metrics,
}
out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n报告已保存: {out_path}")
