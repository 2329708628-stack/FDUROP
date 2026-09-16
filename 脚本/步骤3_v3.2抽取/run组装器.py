# -*- coding: utf-8 -*-
"""v3.2 run 组装器（通用）。
骨架（A/B 节点、depth、title_label、span）由脚本从 paragraphs 机械推导
（即提示词调用①的确定性实现，比模型更可靠）；
论点 claim 与 C 主张由输入文件提供（模型在独立调用②③④中生成）。
本脚本负责：C 编号（父节点内按 anchor 页序连续）、sources 自底向上并集、
statistics 全字段、输出 v3.2 完整 JSON。
注意：supported/supported_by 留空（null）——支持核查须由提示词调用⑤（模型）
完成后回填；可用 run校验器.py 查看待核查 WARN。

用法：
  python 脚本/步骤3_v3.2抽取/run组装器.py <论文根目录> <run号> <输入.json> [输出路径]
输入 JSON 格式：
  {
    "c_defs": [{"parent":"B1.1","anchor":"P6","text":"……","sources":["M4"]}, ...],
    "claims": {"A0":"……","A1":"……","B1.1":"……"},
    "attribution_extra": ["可选：额外归因说明（引言段归属、漏绑补绑理由等）"]
  }
默认输出：<论文根目录>/03_实验输出/H1_v3.2/run_<run号>.json
指定输出路径时直接写到该文件（如 Q_A 实验：Q_run_DS/run.json）
"""
import json, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from 公共库 import load_paper, derive_skeleton, m_key, c_id_for, descendants, union_sources

paper_dir = Path(sys.argv[1])
run_no = int(sys.argv[2])
inp = json.load(open(sys.argv[3], encoding="utf-8"))

paras, materials, _ = load_paper(paper_dir)
valid_M = {m["id"] for m in materials}
valid_P = {p["id"] for p in paras}
sk = derive_skeleton(paras)
pidx = sk["para_index"]

A_defs = sk["A"]
B_defs = [b for b in sk["B"] if not b["id"].startswith("ORPHAN@")]
node_by_id = {n["id"]: n for n in A_defs + B_defs}

# 父节点排序键：标题段在文中的位置（扁平篇 parent=A 同样适用）
parent_order = {n["id"]: pidx[n["title_pid"]] for n in A_defs + B_defs}

claims = inp.get("claims", {})
missing_claim = [nid for nid in node_by_id if nid not in claims]
if missing_claim:
    sys.exit("claims 缺少节点：%s" % missing_claim)

# ---------- 校验并排序 C ----------
c_defs = inp.get("c_defs", [])
enr = []
for i, c in enumerate(c_defs):
    par, anc, txt, srcs = c["parent"], c["anchor"], c["text"], c.get("sources", [])
    if par not in node_by_id:
        sys.exit("C parent 不存在：%s（%s）" % (par, txt[:20]))
    if anc not in valid_P:
        sys.exit("C anchor 非法：%s（%s）" % (anc, txt[:20]))
    for m in srcs:
        if m not in valid_M:
            sys.exit("非法 M %s（%s）" % (m, txt[:20]))
    enr.append((parent_order[par], pidx[anc], i, par, anc, txt, srcs))
enr.sort(key=lambda x: (x[0], x[1], x[2]))

counters, C = {}, []
for _, _, _, par, anc, txt, srcs in enr:
    counters[par] = counters.get(par, 0) + 1
    C.append({"id": c_id_for(par, counters[par]), "anchor": anc,
              "text": txt, "sources": sorted(srcs, key=m_key), "parent": par})

# ---------- 组装 B / A ----------
def span_pair(sp):
    return [sp[0], sp[1] if sp[1] else sp[0]]

B_out = []
for b in sorted(B_defs, key=lambda x: pidx[x["title_pid"]]):
    ms = union_sources(descendants(b["id"], A_defs, B_defs, C))
    B_out.append({"id": b["id"], "depth": b["depth"], "title_label": b["title_label"],
                  "claim": claims[b["id"]], "span": span_pair(b["span"]),
                  "sources": sorted(ms, key=m_key), "source_count": len(ms),
                  "supported": None, "supported_by": [], "parent": b["parent"]})

A_out = []
for a in sorted(A_defs, key=lambda x: (x["id"] != "A0", x["order"])):
    if a["id"] == "A0":
        ms = set(valid_M)
    else:
        ms = union_sources(descendants(a["id"], A_defs, B_defs, C))
    A_out.append({"id": a["id"], "depth": 1, "title_label": a["title_label"],
                  "claim": claims[a["id"]], "span": span_pair(a["span"]),
                  "sources": sorted(ms, key=m_key), "source_count": len(ms),
                  "supported": None, "supported_by": [], "parent": None})

paper_title = next((p["text"] for p in paras if p.get("type") == "title"), "")
attr = [
    "每条 C 带 anchor（来源段落 P 编号）；跨轮比较以 span（标题节点）与 anchor（C）为客观对齐点。",
    "标题节点严格机械映射作者显式标题：一级→A(depth1)，（一）→B(depth2)，1.→B(depth3)；扁平结构无 B 层，C 直接挂 A。",
    "A/B 的 claim 由模型在独立调用中仅依据 title_label+span 段落生成（B 不见 C、A 不见 B/C）；supported 字段待调用⑤支持核查回填。",
    "sources 自底向上取并集：B=子树 C 并集，A=子树 C 并集，A0=全文 M 并集；推导性主张 sources 留空 []。",
] + inp.get("attribution_extra", [])

nbd = {1: len(A_out), 2: sum(1 for b in B_out if b["depth"] == 2),
       3: sum(1 for b in B_out if b["depth"] == 3)}
doc = {
    "meta": {
        "paper_title": paper_title,
        "encoding_scheme": "A-B-C-M hierarchical encoding",
        "version": "3.2",
        "node_roles": {
            "A0": "结论节点（结语/余论/结论），claim 为全文核心命题，sources 为全文 M 并集",
            "A1_An": "正文一级章节节点，depth=1，title_label 为原标题、claim 为独立生成的命题",
            "B": "二级（一）/三级（1.）标题节点，depth=2 或 3；扁平结构论文 B_level 为空数组",
            "C": "段落级单一可检验事实主张（叶子节点），anchor 为来源段落 P 编号，直接绑定 M",
            "M": "原始史料（脚注）编号，只能取输入 materials 中存在的编号",
        },
    },
    "encoding_rules": {
        "depth_policy": "标题层机械映射作者显式标题：一级→A(depth1)，（一）→B(depth2)，1.→B(depth3)；无该级标题则该层为空，禁止推断性补层；span 为所辖正文段 P 编号闭区间",
        "A": "一级标题节点；title_label 保原文，claim 由调用④独立生成；sources 为子树并集，A0 为全文 M 并集",
        "B": "节/目节点；title_label 保原文，claim 由调用③独立生成；sources 为下属并集",
        "C": "段落级事实主张，按父节点内 anchor 页序→段内切分序连续编号；anchor 为来源段 P 编号；sources 只取 anchor 段 material_refs 中支撑该条的 M，推导性主张留空 []",
        "M": "史料编号，仅能使用输入 materials 中存在的编号，不得虚构",
        "path_separator": "-",
        "independent_generation": [
            "调用①骨架：标题→节点+span，机械映射零概括（本 run 骨架由脚本确定性推导）",
            "调用②C 级：仅见 paragraphs+materials",
            "调用③B 级：每节点仅见自身 title_label+span 段落，不见 C",
            "调用④A 级：每节点仅见自身 title_label+span 段落，不见 B/C",
            "调用⑤核查综合：支持核查通过后回填 supported/supported_by",
        ],
        "attribution_method": attr,
        "support_check": ["待调用⑤回填：节点id | 首查是否通过 | 改写后 claim（若有）| supported_by"],
    },
    "encoding_table": {"A_level": A_out, "B_level": B_out, "C_level": C,
                       "M_level": [{"id": m["id"], "text": m.get("text", ""),
                                    "footnote_number": m.get("footnote_number"),
                                    "source_full": m.get("source_full", "")} for m in materials]},
    "statistics": {
        "total_A_nodes": len(A_out),
        "total_B_nodes": len(B_out),
        "total_C_nodes": len(C),
        "total_unique_M": len(valid_M),
        "nodes_by_depth": {"1": nbd[1], "2": nbd[2], "3": nbd[3]},
        "source_count_by_A": {a["id"]: a["source_count"] for a in A_out},
        "source_count_by_B": {b["id"]: b["source_count"] for b in B_out},
        "C_nodes_without_sources": sum(1 for c in C if not c["sources"]),
        "claims_total": len(A_out) + len(B_out),
        "claims_supported": 0,
        "claims_unsupported": 0,
        "claims_revised": 0,
    },
}

if len(sys.argv) > 4:
    out = Path(sys.argv[4])
    out.parent.mkdir(parents=True, exist_ok=True)
else:
    outdir = paper_dir / "03_实验输出" / "H1_v3.2"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / ("run_%d.json" % run_no)
json.dump(doc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("written %s" % out)
print("A=%d (depth1)  B=%d (depth2=%d/depth3=%d)  C=%d" %
      (len(A_out), len(B_out), nbd[2], nbd[3], len(C)))
print("注意：supported 全部为 null，需经调用⑤支持核查后回填，再用 脚本/步骤3_v3.2抽取/run校验器.py 复验。")
