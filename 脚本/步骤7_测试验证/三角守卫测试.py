# -*- coding: utf-8 -*-
"""
离线验证：严格判定 + 三角形一致性守卫 的聚类效果
规则：合并 x,y 时，若 y 簇中存在与 x 跨轮且已判为非等义(DIFFERENT/ENTAILS/CONTRADICTION/UNCERTAIN)
的成员，则拒绝合并并记录冲突（交人工复核）。
"""
import json, os, re, itertools
from collections import Counter

EQ_DIR = r"c:\Users\23297\Downloads\Lab\A01_湖北茶叶经济\03_实验输出\H1_v3.2\_equivalence"

def run_of(atom):
    return re.match(r"(run_\d+)_", atom).group(1)

def triangle_cluster(detail):
    """带守卫的 union：返回簇列表 + 冲突边列表"""
    labels = {d["pair_id"]: d["label"] for d in detail}
    atoms = set()
    edges = []
    for d in detail:
        a, b = d["pair_id"].split("__")
        atoms.add(a); atoms.add(b)
        edges.append((a, b, d["label"]))

    parent = {x: x for x in atoms}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def members(root):
        return {x for x in atoms if find(x) == root}

    conflicts = []
    # 先合 EQUIV，遇到守卫拒绝则记冲突
    for a, b, lab in edges:
        if lab != "EQUIVALENT":
            continue
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        ma, mb = members(ra), members(rb)
        blocked = False
        for x, y in itertools.chain(itertools.product(ma, mb), itertools.product(mb, ma)):
            if run_of(x) == run_of(y):
                continue  # 同轮未判定，放行
            key = "__".join(sorted([x, y])) if False else None
            # pair_id 顺序按 run 编号，直接两种取法
            lab_xy = labels.get(f"{x}__{y}") or labels.get(f"{y}__{x}")
            if lab_xy and lab_xy != "EQUIVALENT":
                blocked = True
                conflicts.append((a, b, x, y, lab_xy))
                break
        if not blocked:
            parent[rb] = ra

    clusters = {}
    for x in atoms:
        clusters.setdefault(find(x), []).append(x)
    return list(clusters.values()), conflicts

def main():
    for anchor, expect_groups in [("P33", 4), ("P6", 5)]:
        path = os.path.join(EQ_DIR, f"strict_test_{anchor}_GLM_4_Flash.json")
        with open(path, encoding="utf-8") as f:
            detail = json.load(f)
        clusters, conflicts = triangle_cluster(detail)
        print(f"=== {anchor} ===")
        print(f"原子数: {len({d['pair_id'].split('__')[i] for d in detail for i in (0,1)})}")
        print(f"簇数: {len(clusters)} (期望概念组 {expect_groups} + 单成员簇)")
        multi = [c for c in clusters if len(c) > 1]
        print(f"多成员簇: {len(multi)}")
        for c in sorted(multi, key=lambda g: g[0]):
            core = sorted(re.sub(r"^run_\d+_", "", x) for x in c)
            print(f"  size={len(c)}: {sorted(set(core))}")
        print(f"守卫拦截冲突边: {len(conflicts)}")
        for a, b, x, y, lab in conflicts:
            print(f"  拒绝合并 {a}~{b}，因 {x} - {y} 判定为 {lab}")
        print()

if __name__ == "__main__":
    main()
