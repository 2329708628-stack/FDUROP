# -*- coding: utf-8 -*-
"""导出审阅表：ABC 提取 + 试点新管线（论点压缩/六类判定）+ 旧判定，汇成单个 Excel。

输出：c:\\Users\\23297\\Downloads\\Lab\\实验结果审阅表.xlsx
"""
import json
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

LAB = Path(r"c:\Users\23297\Downloads\Lab")
ROOT = LAB / "数据集/数据清洗后论文"
OUT = LAB / "实验结果审阅表.xlsx"

RUNS = {
    "A05": ["A_human_baseline", "Q_run_1_S", "Q_run_1_M", "Q_run_1_L", "A_run_1_S", "A_run_1_M", "A_run_1_L"],
    "B05": ["A_human_baseline", "Q_run_1", "A_run_1"],
    "C01": ["A_human_baseline", "Q_run_1", "A_run_1"],
}
JUDGE_RUNS = {
    "A05": ["Q_run_1_S", "Q_run_1_M", "Q_run_1_L", "A_run_1_S", "A_run_1_M", "A_run_1_L"],
    "B05": ["Q_run_1", "A_run_1"],
    "C01": ["Q_run_1", "A_run_1"],
}


def qdir(paper):
    return ROOT / paper / "03_实验输出" / "Q_A_实验"


def load_run(paper, run):
    return json.loads((qdir(paper) / run / "run.json").read_text(encoding="utf-8"))


def para_map(d):
    return {p["id"]: (p.get("text") or "").replace("\n", " ") for p in d.get("paragraphs", [])}


def short(t, n=160):
    return (t or "")[:n]


wb = openpyxl.Workbook()
bold = Font(bold=True)

# ---------- Sheet 0: 说明 ----------
ws = wb.active
ws.title = "0_说明"
notes = [
    ["实验结果审阅表", ""],
    ["生成位置", str(OUT)],
    ["数据来源", "数据集/数据清洗后论文/<论文>/03_实验输出/Q_A_实验/<run>/ 下的 run.json（ABC 提取）与 Q_A_llm_judge.json（旧判定）；A05/Q_run_1_S 下的试点_*.json（新管线试点）"],
    ["", ""],
    ["Sheet", "内容"],
    ["1_ABC_A05", "A05 七个 run 的 A/B/C 三层节点（含段号、段落原文节选、sources 数）"],
    ["2_ABC_B05", "B05 三个 run 同上"],
    ["3_ABC_C01", "C01 三个 run 同上"],
    ["4_试点_论点压缩", "新管线试点（A05/Q_run_1_S）：段落→论点压缩结果（人类 76 条 + 模型 44 条），含段落原文"],
    ["5_试点_六类判定", "新管线试点：本轮 685 对候选的六类判定（含判定理由、是否命中宽口径）"],
    ["6_试点_被挤掉的判定", "上一轮候选（更宽 k）中有、本轮 k=8 之外被挤掉的已判对——即召回上限造成的漏检，供审阅"],
    ["7_旧判定_十run", "旧管线（等义/部分重叠/不等义）在十个 run 上的全部判定对，仅作对照"],
    ["", ""],
    ["重要提示", ""],
    ["① 试点数字未冻结", "新管线的覆盖率受召回参数 k 支配（k=8 → 宽口径 4/76；更宽 k → 9/76），召回参数未定前绝对值不可用"],
    ["② 口径三档", "严=仅等义；中=等义+模型⊨人类；宽=等义+双向蕴含。报告中需双口径并列"],
    ["③ A 不进指标", "A 组模型被喂了 A_H，比 A 层是循环；A 仅用于操纵基准/结构呈现/操纵检查"],
    ["④ 旧判定仅对照", "旧判定（1_等义/部分重叠/不等义）为旧管线结果，含已确认的扫射与提示词污染问题，不作为结论依据"],
    ["⑤ B05/C01 结语口径", "B05 人类基准与 C01 模型侧含结语段主张、A05 不含——按新规范应统一排除（分母会变）"],
]
for row in notes:
    ws.append(row)
ws.column_dimensions["A"].width = 22
ws.column_dimensions["B"].width = 110
for r in (1, 5, 14):
    ws.cell(row=r, column=1).font = bold


def abc_sheet(paper):
    ws = wb.create_sheet(f"ABC_{paper}")
    ws.append(["run", "层级", "id", "深度", "parent", "段号/span", "标题或主张", "段落原文（节选）", "sources数"])
    for run in RUNS[paper]:
        d = load_run(paper, run)
        pm = para_map(d)
        et = d["encoding_table"]
        for a in et.get("A_level", []):
            span = a.get("span") or [None, None]
            ws.append([run, "A", a["id"], 1, a.get("parent"), span[0],
                       short(a.get("title_label") or a.get("claim")), "", len(a.get("sources", []))])
        for b in et.get("B_level", []):
            span = b.get("span") or [None, None]
            ws.append([run, "B", b["id"], b.get("depth"), b.get("parent"), span[0],
                       short(b.get("title_label")), "", len(b.get("sources", []))])
        for c in et.get("C_level", []):
            ws.append([run, "C", c["id"], None, c.get("parent"), c.get("anchor"),
                       short(c.get("text")), short(pm.get(c.get("anchor"), ""), 120),
                       len(c.get("sources", []))])
    for i, w in enumerate([18, 6, 10, 6, 8, 10, 60, 60, 8], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


for p in RUNS:
    abc_sheet(p)

# ---------- 试点：论点压缩 ----------
d5 = qdir("A05") / "Q_run_1_S"
comp = json.loads((d5 / "试点_论点压缩.json").read_text(encoding="utf-8"))
hrun = load_run("A05", "A_human_baseline")
mrun = load_run("A05", "Q_run_1_S")
hpm, mpm = para_map(hrun), para_map(mrun)

ws = wb.create_sheet("4_试点_论点压缩")
ws.append(["侧", "编号", "段落", "章节", "类型", "论点文本", "段落原文"])
for c in comp["human_claims"]:
    ws.append(["人类", c["id"], c["p_id"], c.get("chapter"), c.get("type"), c["text"], short(hpm.get(c["p_id"], ""), 300)])
for c in comp["model_claims"]:
    ws.append(["模型", c["id"], c["p_id"], c.get("chapter"), c.get("type"), c["text"], short(mpm.get(c["p_id"], ""), 300)])
for i, w in enumerate([6, 10, 8, 8, 8, 60, 60], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A2"

# ---------- 试点：六类判定 ----------
pilot = json.loads((d5 / "试点_新管线.json").read_text(encoding="utf-8"))
H = {c["id"]: c for c in pilot["human_claims"]}
M = {c["id"]: c for c in pilot["model_claims"]}
HIT = {"EQUIVALENT", "A_ENTAILS_B", "B_ENTAILS_A"}

ws = wb.create_sheet("5_试点_六类判定")
ws.append(["人类论点id", "人类论点", "人类段落原文", "模型论点id", "模型论点", "模型段落原文", "标签", "是否命中(宽)", "理由"])
for x in pilot["pairs"]:
    hc, mc = H.get(x["human"], {}), M.get(x["model"], {})
    ws.append([x["human"], hc.get("text", ""), short(hpm.get(hc.get("p_id", ""), ""), 150),
               x["model"], mc.get("text", ""), short(mpm.get(mc.get("p_id", ""), ""), 150),
               x.get("label"), "是" if x.get("label") in HIT else "", short(x.get("reason", ""), 120)])
for i, w in enumerate([12, 55, 50, 12, 55, 50, 14, 10, 55], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A2"

# ---------- 试点：被挤掉的判定（上一轮候选） ----------
prog = json.loads((d5 / "试点_判定进度.json").read_text(encoding="utf-8"))
cur = {x["human"] + "|" + x["model"] for x in pilot["pairs"]}
ws = wb.create_sheet("6_试点_被挤掉的判定")
ws.append(["人类论点id", "人类论点", "模型论点id", "模型论点", "标签", "理由"])
n_extra = 0
for k, v in prog.items():
    if k in cur:
        continue
    hc, mc = H.get(v["human"], {}), M.get(v["model"], {})
    ws.append([v["human"], hc.get("text", ""), v["model"], mc.get("text", ""),
               v.get("label"), short(v.get("reason", ""), 120)])
    n_extra += 1
for i, w in enumerate([12, 60, 12, 60, 14, 60], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A2"

# ---------- 旧判定（十 run） ----------
ws = wb.create_sheet("7_旧判定_十run")
ws.append(["论文", "run", "人类主张id", "人类主张", "模型主张id", "模型主张", "标签"])
for paper, runs in JUDGE_RUNS.items():
    for run in runs:
        d = load_run(paper, run)
        j = json.loads((qdir(paper) / run / "Q_A_llm_judge.json").read_text(encoding="utf-8"))
        C = {c["id"]: c for c in d["encoding_table"]["C_level"]}
        for x in j["judgments"]:
            ws.append([paper, run, x["human"], C.get(x["human"], {}).get("text", ""),
                       x["model"], C.get(x["model"], {}).get("text", ""), x.get("label")])
for i, w in enumerate([6, 13, 12, 60, 12, 60, 12], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A2"

wb.save(OUT)
print("已生成：", OUT)
print("sheets：", wb.sheetnames)
print("被挤掉的判定行数：", n_extra)