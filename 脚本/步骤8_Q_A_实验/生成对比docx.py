# -*- coding: utf-8 -*-
"""生成 DeepSeek vs 人类基准 对比表 docx。

输入：
  1) Q_A_comparison_DS.json  —— 结构 / M 覆盖 / anchor / A·B claim 相似度
  2) Q_A_nli_equivalence.json —— NLI 语义等价判定 + ACI_J
输出：
  A01_湖北茶叶经济/03_实验输出/Q_A_实验/DeepSeek_vs_人类基准_对比表.docx
用法：python 脚本/步骤8_Q_A_实验/生成对比docx.py
"""
import json
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

LAB = Path(r"c:\Users\23297\Downloads\Lab")
QA = LAB / "A01_湖北茶叶经济" / "03_实验输出" / "Q_A_实验"
DS_DIR = QA / "Q_run_DS"

COMP = json.loads((DS_DIR / "Q_A_comparison_DS.json").read_text(encoding="utf-8"))
NLI = json.loads((DS_DIR / "Q_A_nli_equivalence.json").read_text(encoding="utf-8"))
OUT = QA / f"DeepSeek_vs_人类基准_对比表_top{NLI['top_k']}.docx"


def add_table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = str(h)
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = w
    return t


doc = Document()
st = doc.styles["Normal"]
st.font.name = "Microsoft YaHei"
st.font.size = Pt(9)

title = doc.add_heading("DeepSeek vs 人类基准 对比表", level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run(
    "对象：A01 湖北茶叶经济（人类原文《北宋时期湖北地区茶叶经济繁盛的状貌、缘由及影响》"
    " vs DeepSeek 生成论文）\n"
    f"人类基准：Q_human_baseline/run_poolspace.json（史料已折算到史料池 M 空间）　　"
    f"模型：Q_run_DS/run.json（DeepSeek）\n"
    f"NLI：{NLI['model']}　θ={NLI['theta']}　{NLI['metric']}　召回 top_k={NLI['top_k']}"
).italic = True

# ============ 一、结构对比 ============
doc.add_heading("一、结构对比", level=1)
s = COMP["structure"]
g, m = s["gold"], s["model"]
add_table(
    doc,
    ["指标", "人类基准", "DeepSeek", "差值", "比值"],
    [
        ["A 节点（章级）", g["A"], m["A"], m["A"] - g["A"],
         f"{m['A']/g['A']*100:.1f}%"],
        ["B depth=2（节级）", g["B_depth2"], m["B_depth2"], m["B_depth2"] - g["B_depth2"],
         f"{m['B_depth2']/g['B_depth2']*100:.1f}%"],
        ["B depth=3（目级）", g["B_depth3"], m["B_depth3"], m["B_depth3"] - g["B_depth3"], "—"],
        ["C 节点（具体主张）", COMP["metrics"]["C_count_gold"], COMP["metrics"]["C_count_model"],
         COMP["metrics"]["C_count_model"] - COMP["metrics"]["C_count_gold"],
         f"{COMP['metrics']['C_ratio_percent']}%"],
        ["节点总数", s["gold_total"], s["model_total"], s["model_total"] - s["gold_total"],
         f"{COMP['metrics']['nodes_ratio_percent']}%"],
    ],
)

# ============ 二、史料（M）覆盖 ============
doc.add_heading("二、史料（M）覆盖对比", level=1)
mc = COMP["material_coverage"]
add_table(
    doc,
    ["指标", "值"],
    [
        ["史料池大小", mc["total_M"]],
        ["人类基准使用 M", f"{mc['gold_used']} / {mc['total_M']} = {mc['gold_coverage_pct']}%"],
        ["DeepSeek 使用 M", f"{mc['model_used']} / {mc['total_M']} = {mc['model_coverage_pct']}%"],
        ["两者交集", mc["gold_used"] - len(mc["gold_only"])],
        ["仅人类基准", len(mc["gold_only"])],
        ["仅 DeepSeek", len(mc["model_only"])],
        ["Precision", mc["Precision"]],
        ["Recall", mc["Recall"]],
        ["F1", mc["F1"]],
    ],
)
doc.add_paragraph(f"仅人类基准使用的 M：{', '.join(mc['gold_only']) if mc['gold_only'] else '（无）'}")
doc.add_paragraph(f"仅 DeepSeek 使用的 M：{', '.join(mc['model_only']) if mc['model_only'] else '（无）'}")

# ============ 三、锚点段覆盖 ============
doc.add_heading("三、锚点段（anchor P）覆盖对比", level=1)
ac = COMP["anchor_coverage"]
add_table(
    doc,
    ["指标", "值"],
    [
        ["人类基准 anchor 段数", len(ac["gold_anchors"])],
        ["DeepSeek anchor 段数", len(ac["model_anchors"])],
        ["交集段数", len(ac["intersection"])],
        ["并集段数", len(set(ac["gold_anchors"]) | set(ac["model_anchors"]))],
        ["Jaccard", ac["Jaccard"]],
    ],
)
doc.add_paragraph(f"人类基准锚点：{', '.join(ac['gold_anchors'])}")
doc.add_paragraph(f"DeepSeek 锚点：{', '.join(ac['model_anchors'])}")
doc.add_paragraph(f"共同锚点：{', '.join(ac['intersection']) if ac['intersection'] else '（无）'}")

# ============ 四、A/B claim 文本相似度 ============
doc.add_heading("四、A/B claim 文本相似度（按 title_label 匹配）", level=1)
rows = []
for c in COMP["claim_comparison"]:
    rows.append([
        c["gold_id"], c["model_id"], c["sim"],
        c.get("title_label", ""),
        c["gold_claim"], c["model_claim"],
    ])
add_table(doc, ["基准 ID", "模型 ID", "相似度", "对应标题", "人类基准 claim", "DeepSeek claim"], rows)
mt = COMP["metrics"]
doc.add_paragraph(
    f"匹配对数：{mt['matched_claim_pairs']}　相似度均值：{mt['claim_sim_mean']}　"
    f"最低：{mt['claim_sim_min']}"
)

# ============ 五、NLI 语义等价判定 ============
doc.add_heading("五、NLI 语义等价判定结果（ACI_J）", level=1)
add_table(
    doc,
    ["指标", "值", "说明"],
    [
        ["输入 claim 数", f"human {NLI['n_human']} + model {NLI['n_model']} = {NLI['n_human']+NLI['n_model']}", "C 级主张"],
        ["候选对", f"{NLI['candidate_pairs']}（{NLI['candidate_pct']}%）", f"句向量余弦 top-{NLI['top_k']} 双向召回"],
        ["等义边", NLI["eq_edges"], f"score_avg ≥ {NLI['theta']}"],
        ["概念总数", NLI["n_concepts"], "等义关系连通分量"],
        ["人类基准概念数", NLI["human_concepts"], ""],
        ["DeepSeek 概念数", NLI["model_concepts"], ""],
        ["共享概念", NLI["shared_concepts"], "两篇共有"],
        ["仅人类概念", NLI["human_only_concepts"], ""],
        ["仅模型概念", NLI["model_only_concepts"], ""],
        ["Jaccard", NLI["jaccard"], "交集 / 并集"],
        ["ACI_J", NLI["aci_j"], "1 − Jaccard（越低越收敛）"],
    ],
)

doc.add_heading(f"5.1 共享概念明细（{NLI['shared_concepts']} 个，全部列出）", level=2)
shared_rows = []
for c in NLI["concepts"]:
    hs = [x for x in c["members"] if x["run"] == "human"]
    ms = [x for x in c["members"] if x["run"] == "model"]
    if hs and ms:
        shared_rows.append([
            c["concept_id"],
            " / ".join(x["node_id"] for x in hs),
            " / ".join(x["node_id"] for x in ms),
            " ｜ ".join(x["text"] for x in hs),
            " ｜ ".join(x["text"] for x in ms),
        ])
add_table(doc, ["概念", "基准 C 节点", "DS C 节点", "人类基准 claim", "DeepSeek claim"], shared_rows)

doc.add_heading("5.2 仅人类基准持有的概念（示例前 10）", level=2)
onlyH = []
for c in NLI["concepts"]:
    hs = [x for x in c["members"] if x["run"] == "human"]
    ms = [x for x in c["members"] if x["run"] == "model"]
    if hs and not ms:
        onlyH.append([c["concept_id"], " / ".join(x["node_id"] for x in hs),
                      " ｜ ".join(x["text"] for x in hs)])
add_table(doc, ["概念", "基准 C 节点", "人类基准 claim"], onlyH[:10])
doc.add_paragraph(f"仅人类概念共 {len(onlyH)} 个。")

doc.add_heading("5.3 仅 DeepSeek 持有的概念（示例前 10）", level=2)
onlyM = []
for c in NLI["concepts"]:
    hs = [x for x in c["members"] if x["run"] == "human"]
    ms = [x for x in c["members"] if x["run"] == "model"]
    if ms and not hs:
        onlyM.append([c["concept_id"], " / ".join(x["node_id"] for x in ms),
                      " ｜ ".join(x["text"] for x in ms)])
add_table(doc, ["概念", "DS C 节点", "DeepSeek claim"], onlyM[:10])
doc.add_paragraph(f"仅模型概念共 {len(onlyM)} 个。")

# ============ 说明 ============
doc.add_heading("六、结果解读与注意事项", level=1)
mtr = COMP["metrics"]
gst, mst = COMP["structure"]["gold"], COMP["structure"]["model"]
_lines = [
    "1. 结构：人类基准 %dA/%dB/%dC（共 %d 节点），DeepSeek %dA/%dB/%dC（共 %d 节点），"
    "A 级完全对齐（均 %d 个），C 级论证密度为基准的 %.1f%%。"
    % (gst["A"], gst["B_depth2"] + gst["B_depth3"], mtr["C_count_gold"], COMP["structure"]["gold_total"],
       mst["A"], mst["B_depth2"] + mst["B_depth3"], mtr["C_count_model"], COMP["structure"]["model_total"],
       gst["A"], mtr["C_ratio_percent"]),
    "2. 史料覆盖（统一折算到史料池 M1-M%d）：人类基准使用 %d 条（%.1f%%），DeepSeek 使用 %d 条（%.1f%%）；"
    "以人类基准为参照 Precision=%.3f、Recall=%.3f、F1=%.3f。"
    "注意：人类基准有 14 条脚注无法在史料池中找到对应书目（池外的独立引用），"
    "故其池内覆盖率天然低于模型，该指标受史料池构建口径影响。"
    % (mc["total_M"], mc["gold_used"], mc["gold_coverage_pct"],
       mc["model_used"], mc["model_coverage_pct"], mc["Precision"], mc["Recall"], mc["F1"]),
    "3. 锚点段：Jaccard=%.3f（共同锚点 %d 段）。两侧 P 编号体系不同（各自按自己论文的段落编排），"
    "段级差异不直接表征语义差距，只反映'段落颗粒度'策略差异。"
    % (ac["Jaccard"], len(ac["intersection"])),
    "4. A/B claim 文本相似度：匹配 %d 对，均值 %.3f（最低 %.3f）。"
    "本轮 DeepSeek 的 ABC 由 LLM 独立抽取（未接触人类基准原文），相似度低属预期——"
    "标题层级可机械对齐，但同一层级上模型的概括措辞与人类作者并不趋同。"
    % (mtr["matched_claim_pairs"], mtr["claim_sim_mean"], mtr["claim_sim_min"]),
    "5. 语义等价率以 NLI 结果为准（第五节）：ACI_J = %.4f，C 级概念共享 %d 个（占 %.1f%%）。"
    "该指标基于 C 级主张文本独立判定，是本次实验的核心可比指标。"
    % (NLI["aci_j"], NLI["shared_concepts"],
       NLI["shared_concepts"] / NLI["n_concepts"] * 100),
    "6. 召回口径：本次 NLI 采用 top_k=%d 双向召回（候选对 %d，占全量 %.1f%%），"
    "召回率低于大 top-k 口径，等义边数量偏保守（可能漏判），ACI_J 为偏悲观估计。"
    % (NLI["top_k"], NLI["candidate_pairs"], NLI["candidate_pct"]),
]
for line in _lines:
    doc.add_paragraph(line)

doc.save(OUT)
print(f"已生成：{OUT}")
