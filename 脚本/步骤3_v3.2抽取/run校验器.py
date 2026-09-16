# -*- coding: utf-8 -*-
"""v3.2 运行结果校验器（通用，论文路径参数化）。
用法：
  python 脚本/步骤3_v3.2抽取/run校验器.py <run.json 路径>
  python 脚本/步骤3_v3.2抽取/run校验器.py <run.json> <论文根目录>   # 自动推断失败时手动指定

校验内容：
  结构层（机械）：A/B 节点集合、id、depth、title_label 逐字、span 与原文标题位置一致、
                  嵌套关系、front_matter；
  论点层：A/B 必有 claim；supported/supported_by 结构合法（语义蕴含需人工/模型，脚本只查结构）；
  C 层：编号连续、anchor 合法且落在父节点 span 内（引言段例外）、按 anchor 页序排列、
        sources 取自 anchor 段 material_refs（漏绑 M 自动识别为例外）、文本长度；
  并集：B=子树 C 并集，A=子树 C 并集，A0=全文 M 并集；
  统计：statistics 各字段与实际一致（含 nodes_by_depth / claims_*）。
输出 ERROR（硬错误，必须修）与 WARNING（需人工确认）。
"""
import json, sys, re
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from 公共库 import (load_paper, derive_skeleton, m_key, c_id_for,
                    descendants, union_sources, para_in_span, find_paper_dir)

run_path = Path(sys.argv[1])
paper_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else find_paper_dir(run_path)

d = json.load(open(run_path, encoding="utf-8"))
ver = d.get("meta", {}).get("version", "?")
paras, materials, clean_path = load_paper(paper_dir)
sk = derive_skeleton(paras)

errs, warns = [], []
valid_M = {m["id"] for m in materials}
valid_P = {p["id"] for p in paras}
text_paras = {p["id"]: p for p in paras if p.get("type") == "text"}
para_refs = {pid: set(p.get("material_refs", [])) for pid, p in text_paras.items()}

A = d["encoding_table"]["A_level"]
B = d["encoding_table"]["B_level"]
C = d["encoding_table"]["C_level"]

# ---------- 0. 版本 ----------
if ver != "3.2":
    warns.append("meta.version='%s'（期望 3.2；v3.1 旧格式请用旧版校验器）" % ver)

# ---------- 1. 骨架机械一致性 ----------
exp_a = {a["id"]: a for a in sk["A"]}
exp_b = {b["id"]: b for b in sk["B"] if not b["id"].startswith("ORPHAN@")}
orphan_b = [b for b in sk["B"] if b["id"].startswith("ORPHAN@")]
for b in orphan_b:
    warns.append("目级标题 '%s'（%s）未找到所属（二）级标题（首章级标题被当主标题跳过所致，front_matter 已收相应段落）"
                 % (b["title_label"], b["title_pid"]))

got_a = {a["id"]: a for a in A}
got_b = {b["id"]: b for b in B}

if set(got_a) != set(exp_a):
    errs.append("A 节点集合不一致：缺少 %s，多出 %s" % (sorted(set(exp_a) - set(got_a)),
                                                          sorted(set(got_a) - set(exp_a))))
if set(got_b) != set(exp_b):
    errs.append("B 节点集合不一致：缺少 %s，多出 %s" % (sorted(set(exp_b) - set(got_b)),
                                                          sorted(set(got_b) - set(exp_b))))

def norm(t):
    t = (t or "").replace("\\*", "").rstrip("*")
    t = t.replace("(", "（").replace(")", "）")  # 半角括号统一为全角（OCR 混用）
    return re.sub(r"\s+", "", t)

for aid, ea in exp_a.items():
    g = got_a.get(aid)
    if not g:
        continue
    if norm(g.get("title_label")) != norm(ea["title_label"]):
        errs.append("%s title_label 与原文不一致：'%s' vs '%s'" % (aid, g.get("title_label"), ea["title_label"]))
    if g.get("depth") != 1:
        errs.append("%s depth 应为 1，实际 %s" % (aid, g.get("depth")))
    if list(g.get("span") or []) != [x for x in ea["span"] if x]:
        # span 允许 None 尾值容错，逐边界比对
        gs = g.get("span") or [None, None]
        if gs[0] != ea["span"][0] or (gs[1] if len(gs) > 1 else gs[0]) != ea["span"][1]:
            errs.append("%s span 应为 %s，实际 %s" % (aid, ea["span"], gs))
for bid, eb in exp_b.items():
    g = got_b.get(bid)
    if not g:
        continue
    if norm(g.get("title_label")) != norm(eb["title_label"]):
        errs.append("%s title_label 与原文不一致：'%s' vs '%s'" % (bid, g.get("title_label"), eb["title_label"]))
    if g.get("depth") != eb["depth"]:
        errs.append("%s depth 应为 %s，实际 %s" % (bid, eb["depth"], g.get("depth")))
    gs = g.get("span") or [None, None]
    if gs[0] != eb["span"][0] or (gs[1] if len(gs) > 1 else gs[0]) != eb["span"][1]:
        errs.append("%s span 应为 %s，实际 %s" % (bid, eb["span"], gs))

# 扁平结构提示
if not exp_b:
    warns.append("本文为扁平结构（无二级标题）：B_level 应为空，C 直接挂 A")

# ---------- 2. parent / 嵌套 ----------
a_ids, b_ids = set(got_a), set(got_b)
for b in B:
    pid = b.get("parent")
    if b.get("depth") == 2:
        if pid not in a_ids:
            errs.append("%s(depth2) parent 应为 A，实际 %s" % (b["id"], pid))
    else:
        if pid not in b_ids or got_b[pid].get("depth") != 2:
            errs.append("%s(depth3) parent 应为 depth2 的 B，实际 %s" % (b["id"], pid))
# span 嵌套
def span_of(node):
    s = node.get("span") or [None, None]
    return s[0], (s[1] if len(s) > 1 and s[1] else s[0])
for b in B:
    if b.get("depth") == 3:
        pb = got_b.get(b["parent"])
        if pb:
            c0, c1 = span_of(b); p0, p1 = span_of(pb)
            if not (c0 and p0 and sk["para_index"].get(c0, -1) >= sk["para_index"].get(p0, 1 << 30)
                    and sk["para_index"].get(c1, 1 << 30) <= sk["para_index"].get(p1, -1)):
                errs.append("%s span %s 超出父 %s span %s" % (b["id"], b.get("span"), b["parent"], pb.get("span")))
for b in B:
    if b.get("depth") == 2:
        pa = got_a.get(b["parent"])
        if pa:
            c0, c1 = span_of(b); p0, p1 = span_of(pa)
            if not (c0 and p0 and sk["para_index"].get(c0, -1) >= sk["para_index"].get(p0, 1 << 30)
                    and sk["para_index"].get(c1, 1 << 30) <= sk["para_index"].get(p1, -1)):
                errs.append("%s span %s 超出父 %s span %s" % (b["id"], b.get("span"), b["parent"], pa.get("span")))

# ---------- 3. claim / supported ----------
claim_nodes = A + B
for n in claim_nodes:
    cl = (n.get("claim") or "").strip()
    if not cl:
        errs.append("%s 缺少 claim" % n["id"])
    elif len(cl) < 12:
        warns.append("%s claim 过短（%d 字）：%s" % (n["id"], len(cl), cl))
    sup = n.get("supported")
    if sup is None:
        warns.append("%s supported 未核查（调用⑤支持核查未做）" % n["id"])
    elif sup:
        sby = n.get("supported_by") or []
        if not sby:
            errs.append("%s supported=true 但 supported_by 为空" % n["id"])
        # supported_by 必须是真实后代
        desc = {x["id"] for x in descendants(n["id"], A, B, C)}
        if n["id"] == "A0":
            desc |= {a["id"] for a in A if a["id"] != "A0"}
        for x in sby:
            if x not in desc and x not in a_ids and x not in b_ids:
                errs.append("%s supported_by 含不存在节点 %s" % (n["id"], x))
            elif x not in desc:
                errs.append("%s supported_by 中 %s 不是其后代节点" % (n["id"], x))

# ---------- 4. C 层 ----------
all_parents = a_ids | b_ids
by_parent = defaultdict(list)
all_ms = set()
rebound_ms = valid_M - set().union(*para_refs.values()) if para_refs else set(valid_M)
front = set(sk["front_matter"])
for c in C:
    pid = c.get("parent")
    if pid not in all_parents:
        errs.append("%s parent 不存在：%s" % (c["id"], pid))
    by_parent[pid].append(c)
    for m in c.get("sources", []):
        all_ms.add(m)
        if m not in valid_M:
            errs.append("%s 引用非法 M：%s" % (c["id"], m))
    srcs = c.get("sources", [])
    if len(srcs) != len(set(srcs)):
        errs.append("%s sources 重复" % c["id"])
    anc = c.get("anchor")
    if anc not in valid_P:
        errs.append("%s anchor 非法：%s" % (c["id"], anc))
        continue
    # anchor 须落在父节点 span 内（front_matter 引言段为例外）
    par = got_b.get(pid) or got_a.get(pid)
    if par is not None and anc not in front:
        if not para_in_span(anc, par.get("span"), sk["para_index"]):
            errs.append("%s anchor %s 不在父节点 %s span %s 内" % (c["id"], anc, pid, par.get("span")))
    if anc in front:
        warns.append("%s anchor %s 为引言段（front_matter），归属 %s 需在 attribution_method 说明"
                     % (c["id"], anc, pid))
    # sources 取自 anchor 段 refs（漏绑 M 例外）
    allowed = para_refs.get(anc, set())
    for m in srcs:
        if m not in allowed and m not in rebound_ms:
            errs.append("%s 的 M %s 不在 anchor %s 的 material_refs 中（且非漏绑补绑 M）"
                        % (c["id"], m, anc))
    L = len(c.get("text", ""))
    if not (25 <= L <= 95):
        warns.append("%s 文本长度 %d 字（建议 30~80）" % (c["id"], L))

# C 编号连续 + 同父内 anchor 页序非递减
for pid, cs in by_parent.items():
    nums = []
    for c in cs:
        tail = c["id"].split(".")[-1]
        expect_prefix = "C" + pid[1:] + "."
        if not c["id"].startswith(expect_prefix):
            errs.append("%s 编号前缀应为 %s…（父 %s）" % (c["id"], expect_prefix, pid))
        nums.append(int(tail) if tail.isdigit() else -1)
    if sorted(nums) != list(range(1, len(cs) + 1)):
        errs.append("父 %s 下 C 序号不连续：%s" % (pid, sorted(nums)))
    order = [sk["para_index"].get(c["anchor"], -1) for c in cs]
    if order != sorted(order):
        errs.append("父 %s 下 C 未按 anchor 页序排列：%s"
                    % (pid, [c["id"] + "@" + str(c["anchor"]) for c in cs]))

# ---------- 5. sources 并集 ----------
for b in B:
    want = union_sources(descendants(b["id"], A, B, C))
    if set(b.get("sources", [])) != want:
        errs.append("%s sources 与子树 C 并集不符：差集 %s"
                    % (b["id"], sorted(want ^ set(b.get("sources", [])), key=m_key)))
for a in A:
    if a["id"] == "A0":
        want = set(valid_M)
    else:
        want = union_sources(descendants(a["id"], A, B, C))
    if set(a.get("sources", [])) != want:
        errs.append("%s sources 与子树并集不符：差集 %s"
                    % (a["id"], sorted(want ^ set(a.get("sources", [])), key=m_key)))
for n in A + B:
    sc = n.get("source_count")
    if sc is not None and sc != len(set(n.get("sources", []))):
        errs.append("%s source_count=%s 与实际 %s 不符" % (n["id"], sc, len(set(n.get("sources", [])))))

# ---------- 6. 段落覆盖 ----------
anchored = {c["anchor"] for c in C}
spanned = set()
for n in A + B:
    s = n.get("span") or [None, None]
    lo, hi = s[0], (s[1] if len(s) > 1 and s[1] else s[0])
    if lo is None:
        continue
    for pid, i in sk["para_index"].items():
        if pid in text_paras and sk["para_index"][lo] <= i <= sk["para_index"][hi]:
            spanned.add(pid)
for pid, p in text_paras.items():
    if pid in front:
        continue
    if pid not in spanned:
        warns.append("段落 %s 不在任何 span 内（标题识别遗漏？）" % pid)
    refs = set(p.get("material_refs", []))
    if refs and pid not in anchored:
        warns.append("段落 %s 含 %d 条 material_refs 但无 C 锚定" % (pid, len(refs)))
unbound = set()
for pid, refs in para_refs.items():
    unbound |= refs - all_ms
unbound -= rebound_ms  # 漏绑 M 本就不在段落 refs 里
used_rebound = all_ms & rebound_ms
if used_rebound:
    warns.append("漏绑补绑 M 已使用 %s（需在 attribution_method 逐条说明 M→anchor→理由）"
                 % sorted(used_rebound, key=m_key))

# ---------- 7. statistics ----------
st = d.get("statistics", {})
checks = [
    ("total_A_nodes", len(A)), ("total_B_nodes", len(B)), ("total_C_nodes", len(C)),
    ("total_unique_M", len(valid_M)),
]
for k, v in checks:
    if st.get(k) != v:
        errs.append("statistics.%s=%s，实际 %s" % (k, st.get(k), v))
nbd = {1: 0, 2: 0, 3: 0}
for b in B:
    nbd[b.get("depth")] = nbd.get(b.get("depth"), 0) + 1
nbd[1] = len(A)
if st.get("nodes_by_depth") != {"1": nbd[1], "2": nbd[2], "3": nbd[3]}:
    errs.append("statistics.nodes_by_depth=%s，实际 %s"
                % (st.get("nodes_by_depth"), {"1": nbd[1], "2": nbd[2], "3": nbd[3]}))
for a in A:
    if st.get("source_count_by_A", {}).get(a["id"]) != len(set(a.get("sources", []))):
        errs.append("statistics.source_count_by_A.%s 不符" % a["id"])
for b in B:
    if st.get("source_count_by_B", {}).get(b["id"]) != len(set(b.get("sources", []))):
        errs.append("statistics.source_count_by_B.%s 不符" % b["id"])
n_no_src = sum(1 for c in C if not c.get("sources"))
if st.get("C_nodes_without_sources") != n_no_src:
    errs.append("statistics.C_nodes_without_sources=%s，实际 %s"
                % (st.get("C_nodes_without_sources"), n_no_src))
ct = len(claim_nodes)
cs = sum(1 for n in claim_nodes if n.get("supported") is True)
cu = sum(1 for n in claim_nodes if n.get("supported") is False)
if st.get("claims_total") != ct:
    errs.append("statistics.claims_total=%s，实际 %s" % (st.get("claims_total"), ct))
if st.get("claims_supported") != cs:
    errs.append("statistics.claims_supported=%s，实际 %s" % (st.get("claims_supported"), cs))
if st.get("claims_unsupported") != cu:
    errs.append("statistics.claims_unsupported=%s，实际 %s" % (st.get("claims_unsupported"), cu))

# ---------- 报告 ----------
print("论文: %s" % paper_dir.name)
print("run : %s  (meta.version=%s)" % (run_path.name, ver))
print("骨架: A=%d  B(depth2)=%d  B(depth3)=%d  front_matter=%s"
      % (len(exp_a), nbd[2], nbd[3], sk["front_matter"]))
print("产物: A=%d  B=%d  C=%d  含史料C=%d  无史料C=%d"
      % (len(A), len(B), len(C), len(C) - n_no_src, n_no_src))
print("A:", [(a["id"], len(set(a.get("sources", [])))) for a in A])
print("B:", [(b["id"], b.get("depth"), len(set(b.get("sources", [])))) for b in B])
print("C 分布:", {k: len(v) for k, v in sorted(by_parent.items())})
if rebound_ms:
    print("漏绑 M（不在任何段落 refs）:", sorted(rebound_ms, key=m_key))
print("-" * 70)
for w in warns:
    print("WARN  ", w)
print("-" * 70)
if errs:
    for e in errs:
        print("ERROR ", e)
    print("\n共 %d 个 ERROR，%d 个 WARN" % (len(errs), len(warns)))
    sys.exit(1)
print("ERRORS: NONE（%d 个 WARN 需人工确认）" % len(warns))
