# -*- coding: utf-8 -*-
"""v3.2 跨轮对比器（通用）。
对齐点：标题节点按 (id/span) 机械对齐，C 按 anchor 段落对齐。
输出三层信度：
  1) 骨架一致性：各轮 A/B 节点集合（id, depth, title_label, span）是否完全一致（应 100%）；
  2) 论点层：同一 A/B 节点各轮 claim 文本对照 + difflib 两两相似度（语义等价率供人工/模型判定）；
  3) C 层：各锚点段各轮 C 条数、史料绑定集合一致性；C 总数 CV（H0 阈值 <15%）；锚点覆盖。
用法：
  python 脚本/步骤3_v3.2抽取/三轮锚点对比.py <论文根目录> [run目录名(默认 03_实验输出/H1_v3.2)]
报告同时保存到 <run目录>/comparison_report.json。
"""
import json, glob, os, sys, difflib
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from 公共库 import load_paper, derive_skeleton, m_key

paper_dir = Path(sys.argv[1])
run_dir = paper_dir / (sys.argv[2] if len(sys.argv) > 2 else os.path.join("03_实验输出", "H1_v3.2"))

paras, materials, _ = load_paper(paper_dir)
sk = derive_skeleton(paras)
text_paras = [p["id"] for p in paras if p.get("type") == "text"]
para = {p["id"]: p for p in paras}

files = sorted(f for f in glob.glob(str(run_dir / "run_*.json"))
               if os.path.basename(f)[4:5].isdigit())
if not files:
    sys.exit("找不到 %s 下的 run_*.json" % run_dir)
runs = {}
for f in files:
    runs[int(os.path.basename(f).split("_")[1].split(".")[0])] = json.load(open(f, encoding="utf-8"))
run_ids = sorted(runs)
report = {"paper": paper_dir.name, "run_dir": str(run_dir), "runs": run_ids}

def sim(a, b):
    return difflib.SequenceMatcher(None, a or "", b or "").ratio()

# ---------- 1. 骨架一致性 ----------
print("=" * 78)
print("一、骨架（空间层）一致性")
print("=" * 78)
skeleton_mismatch = []
ref = runs[run_ids[0]]
ref_nodes = {n["id"]: n for n in ref["encoding_table"]["A_level"] + ref["encoding_table"]["B_level"]}
for rid in run_ids[1:]:
    cur = {n["id"]: n for n in runs[rid]["encoding_table"]["A_level"] + runs[rid]["encoding_table"]["B_level"]}
    if set(cur) != set(ref_nodes):
        skeleton_mismatch.append((rid, "节点集合差异: 缺%s 多%s" %
                                  (sorted(set(ref_nodes) - set(cur)), sorted(set(cur) - set(ref_nodes)))))
        continue
    for nid, n in cur.items():
        r = ref_nodes[nid]
        for fld in ("depth", "title_label", "span", "parent"):
            if n.get(fld) != r.get(fld):
                skeleton_mismatch.append((rid, "%s 字段 %s 不一致：%s vs %s"
                                          % (nid, fld, r.get(fld), n.get(fld))))
if skeleton_mismatch:
    for rid, msg in skeleton_mismatch:
        print("  run%d: %s" % (rid, msg))
else:
    print("  %d 轮 A/B 节点集合、depth、title_label、span、parent 完全一致（机械层 100%% 可复现）" % len(run_ids))

# ---------- 2. 论点层 claim 对照 ----------
print("=" * 78)
print("二、A/B 论点（claim）跨轮对照与文本相似度")
print("=" * 78)
claim_tbl = defaultdict(dict)
for rid in run_ids:
    for n in runs[rid]["encoding_table"]["A_level"] + runs[rid]["encoding_table"]["B_level"]:
        claim_tbl[n["id"]][rid] = n.get("claim", "")
claim_rows = []
order = sorted(ref_nodes, key=lambda x: (ref_nodes[x].get("depth", 1),
                                         sk["para_index"].get(ref_nodes[x].get("span", [None])[0], 9999)))
for nid in order:
    if nid not in claim_tbl:
        continue
    claims_by_run = claim_tbl[nid]
    texts = [claims_by_run.get(r, "") for r in run_ids]
    sims = [sim(texts[0], texts[i]) for i in range(1, len(texts))]
    min_s = min(sims) if sims else 1.0
    node = ref_nodes[nid]
    claim_rows.append({"id": nid, "depth": node.get("depth"),
                       "title_label": node.get("title_label"),
                       "claims": {str(r): claims_by_run.get(r, "") for r in run_ids},
                       "min_pairwise_sim": round(min_s, 3)})
    flag = "OK " if min_s >= 0.75 else "LOW"
    print("[%s] %s (depth%s) %s" % (flag, nid, node.get("depth"),
                                    (node.get("title_label") or "")[:24]))
    for r in run_ids:
        print("     run%d: %s" % (r, claims_by_run.get(r, "（缺失）")))
    if sims:
        print("     两两最小相似度: %.2f" % min_s)
low_claim = [r_ for r_ in claim_rows if r_["min_pairwise_sim"] < 0.75]
print("-" * 78)
print("claim 节点数 %d；文本相似度 <0.75 的节点 %d 个（需人工判定语义等价性）：%s"
      % (len(claim_rows), len(low_claim), [r_["id"] for r_ in low_claim] or "无"))

# ---------- 3. C 层锚点对比 ----------
print("=" * 78)
print("三、C 层锚点对比（anchor 段落对齐）")
print("=" * 78)
per_run = {}
for rid in run_ids:
    tab = defaultdict(list)
    for c in runs[rid]["encoding_table"]["C_level"]:
        tab[c["anchor"]].append(c)
    per_run[rid] = tab

# 段落顺序：以所有轮出现过的 anchor + 正文段并集，按原文页序
anchors_all = set()
for rid in run_ids:
    anchors_all |= set(per_run[rid])
para_seq = [p for p in text_paras if p in anchors_all]

mismatch_points, missing_cov, rows = [], [], []
for p_ in para_seq:
    counts = [len(per_run[r].get(p_, [])) for r in run_ids]
    msets = [set().union(*[set(c["sources"]) for c in per_run[r].get(p_, [])])
             if per_run[r].get(p_) else set() for r in run_ids]
    same = all(msets[0] == m for m in msets[1:])
    parents = [per_run[r].get(p_, [{}])[0].get("parent", "?") for r in run_ids]
    nrefs = len(para[p_].get("material_refs", []))
    if not same:
        mismatch_points.append(p_)
    for r in run_ids:
        if not per_run[r].get(p_):
            missing_cov.append((p_, r))
    rows.append({"anchor": p_, "counts": dict(zip(run_ids, counts)),
                 "parents": dict(zip(run_ids, parents)), "nrefs": nrefs,
                 "sources_same": same,
                 "sources": {str(r): sorted(msets[i], key=m_key) for i, r in enumerate(run_ids)}})
    print("%5s | refs=%2d | 各轮C条数 %s | parent %s | 史料集 %s"
          % (p_, nrefs, counts, parents[0], "OK" if same else "DIFF"))
    if not same:
        for i, r in enumerate(run_ids):
            extra = msets[i] - msets[0]
            miss = msets[0] - msets[i]
            if extra or miss:
                print("        run%d: %s%s" %
                      (r, ("多出" + str(sorted(extra, key=m_key))) if extra else "",
                       (" 缺少" + str(sorted(miss, key=m_key))) if miss else ""))

# ---------- 4. 汇总统计 ----------
print("=" * 78)
print("四、汇总")
print("=" * 78)
tot = {r: len(runs[r]["encoding_table"]["C_level"]) for r in run_ids}
mean = sum(tot.values()) / len(tot)
var = sum((x - mean) ** 2 for x in tot.values()) / (len(tot) - 1) if len(tot) > 1 else 0
cv = (var ** 0.5) / mean * 100 if mean else 0
print("各轮 C 总数: %s" % tot)
print("C 节点总数 CV = %.1f%%（H0 判定阈值 < 15%%）" % cv)
print("骨架不一致项: %s" % (skeleton_mismatch and "有，见上" or "无"))
print("史料绑定集合不一致锚点: %s" % (mismatch_points or "无——全部锚点史料集一致"))
print("锚点覆盖缺失: %s" % (missing_cov or "无——所有产出锚点各轮均被 C 覆盖"))
claim_sims = [r_["min_pairwise_sim"] for r_ in claim_rows]
if claim_sims:
    print("claim 两两最小相似度：均值 %.2f，最低 %.2f（%s）"
          % (sum(claim_sims) / len(claim_sims), min(claim_sims),
             next(r_["id"] for r_ in claim_rows if r_["min_pairwise_sim"] == min(claim_sims))))

report.update({
    "skeleton_mismatch": [{"run": rid, "msg": msg} for rid, msg in skeleton_mismatch],
    "claim_comparison": claim_rows,
    "anchor_comparison": rows,
    "C_counts": tot,
    "C_CV_percent": round(cv, 2),
    "source_mismatch_anchors": mismatch_points,
    "coverage_missing": [{"anchor": a, "run": r} for a, r in missing_cov],
})
out = run_dir / "comparison_report.json"
json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("报告已保存: %s" % out)
