# -*- coding: utf-8 -*-
"""Q_A 实验：把对比结果 + NLI 结果生成 docx 对比表（6 节 8 表，与 DeepSeek 版同版式）。

用法：
  python 脚本/步骤8_Q_A_实验/生成对比docx.py <comparison.json> <nli.json> <输出.docx> <模型标签> [人类标签]

示例：
  python 脚本/步骤8_Q_A_实验/生成对比docx.py \
    "A01_湖北茶叶经济/03_实验输出/Q_A_实验/Q_run_DSA/Q_A_comparison_DSA.json" \
    "A01_湖北茶叶经济/03_实验输出/Q_A_实验/Q_run_DSA/Q_A_nli_equivalence_top3.json" \
    "A01_湖北茶叶经济/03_实验输出/Q_A_实验/DSA_vs_人类基准_对比表_top3.docx" DSA
"""
import json, sys
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
sys.path.insert(0, str(LAB / ".pylibs"))
from docx import Document
from docx.shared import Pt

cmp_path, nli_path, out_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
model_label = sys.argv[4]
gold_label = sys.argv[5] if len(sys.argv) > 5 else "人类基准"

C = json.load(open(cmp_path, encoding="utf-8"))
N = json.load(open(nli_path, encoding="utf-8"))
st, mc, ac = C["structure"], C["material_coverage"], C["anchor_coverage"]
mt = C["metrics"]
gd, md = st["gold"], st["model"]

doc = Document()
doc.styles["Normal"].font.name = "Microsoft YaHei"
doc.styles["Normal"].font.size = Pt(10)


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = str(h)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = str(v)
    return t


def pct(a, b):
    return "%.1f%%" % (a / b * 100) if b else "-"


doc.add_heading(f"{model_label} vs {gold_label} 对比表", level=0)
doc.add_paragraph(
    f"对象：A01 湖北茶叶经济（{gold_label}原文《北宋时期湖北地区茶叶经济繁盛的状貌、缘由及影响》 vs "
    f"{model_label} 论文）\n"
    f"{gold_label}：{C['gold_run']}\n"
    f"{model_label}：{C['model_run']}\n"
    f"NLI：{N['model']}（theta={N['theta']}，metric={N['metric']}，top_k={N['top_k']} 双向召回）"
)

# ---------- 一、结构对比 ----------
doc.add_heading("一、结构对比", level=1)
table(["指标", gold_label, model_label, "差值", "比值"], [
    ["A 节点（章级）", gd["A"], md["A"], md["A"] - gd["A"], pct(md["A"], gd["A"])],
    ["B 节点（depth=2）", gd["B_depth2"], md["B_depth2"], md["B_depth2"] - gd["B_depth2"], pct(md["B_depth2"], gd["B_depth2"])],
    ["B 节点（depth=3）", gd["B_depth3"], md["B_depth3"], md["B_depth3"] - gd["B_depth3"], pct(md["B_depth3"], gd["B_depth3"])],
    ["C 节点（叶子）", gd["C"], md["C"], md["C"] - gd["C"], pct(md["C"], gd["C"])],
    ["节点总数", st["gold_total"], st["model_total"], st["model_total"] - st["gold_total"],
     pct(st["model_total"], st["gold_total"])],
])

# ---------- 二、史料覆盖 ----------
doc.add_heading("二、史料（M）覆盖对比", level=1)
table(["指标", "值"], [
    ["史料池大小", mc["total_M"]],
    [f"{gold_label}使用 M", f"{mc['gold_used']}/{mc['total_M']} = {mc['gold_coverage_pct']}%"],
    [f"{model_label}使用 M", f"{mc['model_used']}/{mc['total_M']} = {mc['model_coverage_pct']}%"],
    ["共同使用 M", mc["gold_used"] + mc["model_used"] - len(mc["gold_only"]) - len(mc["model_only"])],
    ["Precision / Recall / F1", f"{mc['Precision']} / {mc['Recall']} / {mc['F1']}"],
])
doc.add_paragraph(f"仅{gold_label}使用的 M：" + (", ".join(mc["gold_only"]) or "（无）"))
doc.add_paragraph(f"仅{model_label}使用的 M：" + (", ".join(mc["model_only"]) or "（无）"))

# ---------- 三、锚点段覆盖 ----------
doc.add_heading("三、锚点段（anchor P）覆盖对比", level=1)
table(["指标", "值"], [
    [f"{gold_label} anchor 段数", len(ac["gold_anchors"])],
    [f"{model_label} anchor 段数", len(ac["model_anchors"])],
    ["共同 anchor 段数", len(ac["intersection"])],
    ["Jaccard", ac["Jaccard"]],
])
doc.add_paragraph(f"{gold_label}锚点：" + ", ".join(ac["gold_anchors"]))
doc.add_paragraph(f"{model_label}锚点：" + ", ".join(ac["model_anchors"]))
doc.add_paragraph("共同锚点：" + (", ".join(ac["intersection"]) or "（无）"))

# ---------- 四、A/B claim 相似度 ----------
doc.add_heading("四、A/B claim 文本相似度（按 title_label 匹配）", level=1)
cc = C["claim_comparison"]
if cc:
    doc.add_paragraph(f"匹配对数：{mt['matched_claim_pairs']}　相似度均值：{mt['claim_sim_mean']}　最低：{mt['claim_sim_min']}")
    table(["基准 ID", "模型 ID", "相似度", "对应标题", f"{gold_label} claim", f"{model_label} claim"],
          [[r.get("gold_id", ""), r.get("model_id", ""), r.get("sim", ""), r.get("title_pair", ""),
            r.get("gold_claim", ""), r.get("model_claim", "")] for r in cc])
else:
    doc.add_paragraph("匹配上的 A/B 节点对：0 对。两侧标题体系无法机械对齐（层级数量或标题措辞不同），"
                      "本项不参与语义比较，语义等价以第五节 NLI 结果为准。")

# ---------- 五、NLI ----------
doc.add_heading("五、NLI 语义等价判定结果（ACI_J）", level=1)
table(["指标", "值", "说明"], [
    ["输入 claim 数", f"human {N['n_human']} + model {N['n_model']} = {N['n_human'] + N['n_model']}", "C 级主张"],
    ["候选对", f"{N['candidate_pairs']}（占全量 {N['candidate_pct']}%）", f"top_k={N['top_k']} 双向余弦召回"],
    ["等义边", N["eq_edges"], f"score_avg >= {N['theta']}"],
    ["概念数", N["n_concepts"], f"{gold_label} {N['human_concepts']} / {model_label} {N['model_concepts']}"],
    ["共享概念", N["shared_concepts"], f"占并集 {N['jaccard']}"],
    ["ACI_J", N["aci_j"], "1 − Jaccard，越低越收敛"],
])

shared = [c for c in N["concepts"] if len({m["run"] for m in c["members"]}) > 1]
h_only = [c for c in N["concepts"] if {m["run"] for m in c["members"]} == {"human"}]
m_only = [c for c in N["concepts"] if {m["run"] for m in c["members"]} == {"model"}]


def row_for(c):
    h = [m for m in c["members"] if m["run"] == "human"]
    m = [m for m in c["members"] if m["run"] == "model"]
    return [c["concept_id"],
            " / ".join(x["node_id"] for x in h),
            " / ".join(x["node_id"] for x in m),
            " / ".join(x["text"] for x in h),
            " / ".join(x["text"] for x in m)]


doc.add_heading(f"5.1 共享概念明细（{len(shared)} 个，全部列出）", level=2)
if shared:
    table(["概念", f"{gold_label} C 节点", f"{model_label} C 节点", f"{gold_label} claim", f"{model_label} claim"],
          [row_for(c) for c in shared])
else:
    doc.add_paragraph("无共享概念。")

doc.add_heading(f"5.2 仅{gold_label}持有的概念（示例前 10）", level=2)
doc.add_paragraph(f"仅{gold_label}概念共 {len(h_only)} 个。")
table(["概念", "C 节点", "claim"], [[c["concept_id"], m["node_id"], m["text"]] for c in h_only[:10] for m in c["members"]])

doc.add_heading(f"5.3 仅{model_label}持有的概念（示例前 10）", level=2)
doc.add_paragraph(f"仅{model_label}概念共 {len(m_only)} 个。")
table(["概念", "C 节点", "claim"], [[c["concept_id"], m["node_id"], m["text"]] for c in m_only[:10] for m in c["members"]])

# ---------- 六、解读 ----------
doc.add_heading("六、结果解读与注意事项", level=1)
flat = md["B_depth2"] == 0
notes = [
    f"1. 结构：{gold_label} {gd['A']}A/{gd['B_depth2']}B/{gd['C']}C（共 {st['gold_total']} 节点），"
    f"{model_label} {md['A']}A/{md['B_depth2']}B/{md['C']}C（共 {st['model_total']} 节点），"
    f"节点总数为基准的 {mt['nodes_ratio_percent']}%，C 级论证密度为基准的 {mt['C_ratio_percent']}%。",
    f"2. 史料覆盖（统一折算到史料池 M1-M{mc['total_M']}）："
    f"{gold_label}使用 {mc['gold_used']} 条（{mc['gold_coverage_pct']}%），"
    f"{model_label}使用 {mc['model_used']} 条（{mc['model_coverage_pct']}%）；"
    f"以{gold_label}为参照 Precision={mc['Precision']}、Recall={mc['Recall']}、F1={mc['F1']}。",
    f"3. 锚点段：Jaccard={ac['Jaccard']}（共同锚点 {len(ac['intersection'])} 段）。"
    f"两侧 P 编号体系不同（各自按自己论文的段落编排），段级差异不直接表征语义差距，只反映段落颗粒度策略差异。",
    ("4. A/B claim 文本相似度：无法机械匹配到对照节点对，本项缺失。"
     if not cc else
     f"4. A/B claim 文本相似度：匹配 {mt['matched_claim_pairs']} 对，均值 {mt['claim_sim_mean']}"
     f"（最低 {mt['claim_sim_min']}）。"),
    f"5. 语义等价率以 NLI 结果为准（第五节）：ACI_J = {N['aci_j']}，C 级共享概念 {N['shared_concepts']} 个"
    f"（占并集 {N['jaccard']}）。该指标基于 C 级主张文本独立判定，是本次实验的核心可比指标。",
    f"6. 召回口径：本次 NLI 采用 top_k={N['top_k']} 双向召回（候选对 {N['candidate_pairs']}，占全量 {N['candidate_pct']}%），"
    f"召回率低于大 top-k 口径，等义边数量偏保守（可能漏判），ACI_J 为偏悲观估计。",
]
if flat:
    notes.append(
        f"7. 结构警告：{model_label} 为扁平结构（无（二）级标题，B_level 为空），而{gold_label}有 {gd['B_depth2']} 个 B 节点；"
        f"节点数差与 A/B 层级无法对齐主要由结构层级缺失造成，不应读作概括能力差异。"
    )
for n in notes:
    doc.add_paragraph(n)

out_path.parent.mkdir(parents=True, exist_ok=True)
doc.save(out_path)
print(f"已生成：{out_path}")
print(f"  共享概念 {len(shared)} / 仅{gold_label} {len(h_only)} / 仅{model_label} {len(m_only)}  ACI_J={N['aci_j']}")
