# -*- coding: utf-8 -*-
"""检查 A01 三轮 v3.2 提取稳定性"""
import json, statistics, difflib
from collections import Counter

RUN_DIR = r"c:\Users\23297\Downloads\Lab\A01_湖北茶叶经济\03_实验输出\H1_v3.2"
runs = {f"run{i}": json.load(open(f"{RUN_DIR}/run_{i}.json", encoding="utf-8")) for i in range(1, 4)}

print("=== 节点数统计 ===")
for name, r in runs.items():
    et = r["encoding_table"]
    print(f"{name}: A={len(et['A_level'])} B={len(et['B_level'])} C={len(et['C_level'])}  M={r['statistics']['total_unique_M']}")

# C 级 anchor 分布
def c_list(r):
    return r["encoding_table"]["C_level"]

print("\n=== C 级 anchor 分布 ===")
anchors = sorted(set(n.get("anchor", "?") for n in c_list(runs["run1"])))
cv_list = []
for a in anchors:
    counts = []
    for i in range(1, 4):
        cl = c_list(runs[f"run{i}"])
        counts.append(sum(1 for n in cl if n.get("anchor") == a))
    cv = statistics.stdev(counts) / statistics.mean(counts) * 100 if statistics.mean(counts) > 0 else 0
    cv_list.append(cv)
    flag = "  ⚠" if len(set(counts)) > 1 else ""
    print(f"  {a}: {counts}  CV={cv:.1f}%{flag}")
print(f"  平均 CV = {statistics.mean(cv_list):.1f}%")

# 骨架一致性
print("\n=== 骨架一致性（A/B 标题集合）===")
def skeleton(r):
    et = r["encoding_table"]
    titles = []
    for level in ("A_level", "B_level"):
        for n in et[level]:
            titles.append(n.get("title_label", n.get("claim", "")))
    return sorted(titles)
s1, s2, s3 = skeleton(runs["run1"]), skeleton(runs["run2"]), skeleton(runs["run3"])
print(f"run1∩run2: {len(set(s1)&set(s2))}/{len(set(s1))}")
print(f"三者交集: {len(set(s1)&set(s2)&set(s3))}")
print(f"骨架完全一致: {s1 == s2 == s3}")

# sources 一致性
print("\n=== sources 一致性（同 anchor 下 C 节点绑定的 M 并集）===")
def anchor_sources(r, a):
    return set().union(*[set(n.get("sources", [])) for n in c_list(r) if n.get("anchor") == a] or [set()])
match = 0
for a in anchors:
    s = [anchor_sources(runs[f"run{i}"], a) for i in range(1, 4)]
    if s[0] == s[1] == s[2]:
        match += 1
print(f"  三轮 sources 完全一致: {match}/{len(anchors)} ({match/len(anchors)*100:.1f}%)")

# C 级 claim 文本相似度
print("\n=== C 级 claim 文本相似度（同 anchor 第一条 claim 跨轮）===")
def first_claim(r, a):
    cl = [n.get("text", "") for n in c_list(r) if n.get("anchor") == a]
    return cl[0] if cl else ""
sims = []
for a in anchors:
    c = [first_claim(runs[f"run{i}"], a) for i in range(1, 4)]
    for i in range(3):
        for j in range(i+1, 3):
            if c[i] and c[j]:
                sims.append(difflib.SequenceMatcher(None, c[i], c[j]).ratio())
print(f"  n={len(sims)}  均值={sum(sims)/len(sims):.3f}  最小={min(sims):.3f}  最大={max(sims):.3f}")
print(f"  ≥0.80 占比: {sum(1 for s in sims if s>=0.80)/len(sims)*100:.1f}%")
print(f"  ≥0.60 占比: {sum(1 for s in sims if s>=0.60)/len(sims)*100:.1f}%")

# A/B claim 相似度
print("\n=== A 级 claim 跨轮相似度 ===")
def a_claims(r):
    return [n.get("text", "") for n in r["encoding_table"]["A_level"]]
ac = [a_claims(runs[f"run{i}"]) for i in range(1, 4)]
for idx in range(len(ac[0])):
    sims_a = []
    for i in range(3):
        for j in range(i+1, 3):
            if len(ac[i]) > idx and len(ac[j]) > idx:
                sims_a.append(difflib.SequenceMatcher(None, ac[i][idx], ac[j][idx]).ratio())
    if sims_a:
        print(f"  A{idx}: 均值={sum(sims_a)/len(sims_a):.3f}")
