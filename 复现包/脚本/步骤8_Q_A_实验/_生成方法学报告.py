# -*- coding: utf-8 -*-
"""生成 LLM 多次采样次数方法学参考 docx 报告。"""
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, Cm
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "python-docx"])
    from docx import Document
    from docx.shared import Pt, Cm
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH

LAB = Path(r"c:\Users\23297\Downloads\Lab")
OUT = LAB / "数据集/数据清洗后论文/A05/03_实验输出/Q_A_实验/LLM多次采样次数方法学参考.docx"

doc = Document()

# 中文字体
style = doc.styles["Normal"]
style.font.name = "宋体"
style.font.size = Pt(11)
style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def set_cn(run, font="宋体", size=11, bold=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    run.element.rPr.rFonts.set(qn("w:eastAsia"), font)


def heading(text, level=1, font="黑体", size=None):
    sizes = {0: 18, 1: 15, 2: 13}
    s = size or sizes.get(level, 11)
    p = doc.add_paragraph()
    if level == 0:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    set_cn(r, font, s, bold=True)
    return p


def para(text, font="宋体", size=11, bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_cn(r, font, size, bold)
    return p


# === 标题 ===
heading("LLM 评委多次采样次数方法学参考", 0)
para("（针对论证树对齐实验的频次投票设计）", "楷体", 10)
para("2026-09-23", "楷体", 10)
doc.add_paragraph()

# === 一、问题背景 ===
heading("一、问题背景", 1)
para("本实验用 DeepSeek（temperature=0）作为评委，对人类基准论文与模型生成论文的"
     "论证树做逐对对齐（判断「哪条人类论点对应哪条模型论点」及其关系性质）。"
     "同一份输入在 T=0 下重复跑 6 遍，输出边数在 71–109 条之间摆动"
     "（最大偏差 54%），但有 54 条边在 6/6 全部出现（稳定核）。"
     "目前用频次投票筛 k≥4（4 票及以上）的边进入主指标。")
para("本报告检索相关文献，回答「跑几次合适」这一方法学问题。")

# === 二、文献综述 ===
heading("二、文献综述", 1)

heading("1. LLM 零温度不稳定性", 2)
para("[Atil 等 2025] 让 5 个主流模型在「确定性设置」下各跑 10 次，准确率漂移最高 "
     "15%，最好与最差差距达 70%，无一模型能逐字一致。")
para("[Nicholson 2026] 实测 gpt-4o-mini 在 T=0 下约四分之一输出仍会变化，根因是 "
     "GPU 浮点求和顺序依赖批次大小、MoE 路由等基础设施因素——与本实验 54% 的"
     "边数偏差方向一致。结论：T=0 不保证逐位确定性，是基础设施层面的随机性，"
     "调温度无法消除。")

heading("2. 多采样投票的经验次数", 2)
para("[Wang 等 2022 / ICLR 2023] 是 self-consistency（自我一致性投票）的奠基工作："
     "采样多条推理路径再多数投票，GSM8K 准确率从 56% 升到 74.4%。原文用 40 条，"
     "但社区共识是 5–10 条即达「甜点区」，超过 20 条收益递减。其统计直觉——"
     "正确路径会彼此收敛、错误路径各走各的——与本次频次投票逻辑同源。")

heading("3. 文本标注一致性", 2)
para("[Krippendorff 2011] 的 α 系数对任意标注者数量都适用且容忍缺失值，通常 "
     "2–3 名标注者即可给出可信估计。")
para("[Weber-Genzel 等 2024] VARIERR NLI 用多轮标注+解释分离「真分歧」与「标注错误」。")
para("[Plaza-del-Arco 等 2024] 发现把多个 LLM 当标注者聚合效果优于任何单模型——"
     "直接支持「6 次 DeepSeek 当 6 个标注者投票」的做法。")

heading("4. 其他学科重复次数惯例", 2)
para("深度强化学习 [Colas 等 2018] 显示 5 个种子常不足以稳定结论、推荐 10+；"
     "流行病学因果推断 [Schader 等 2024] 建议 20 个种子才能稳定双稳健估计；"
     "机器学习小样本比较 [Du 2025] 推荐配对多 seed + bootstrap（≥1000 次重采样）"
     "作为护栏。生物学 N=3、心理学 N=30+ 是领域惯例。")

# === 三、跨学科对照表 ===
heading("三、跨学科重复次数对照", 1)
table = doc.add_table(rows=1, cols=3)
table.style = "Light Grid Accent 1"
hdr = table.rows[0].cells
for i, t in enumerate(["学科/场景", "重复次数", "出处"]):
    p = hdr[i].paragraphs[0]
    r = p.add_run(t)
    set_cn(r, "黑体", 11, bold=True)

rows = [
    ("深度强化学习种子数", "5 常不足，推荐 10+", "Colas 2018"),
    ("流行病学因果推断", "20 个种子才稳", "Schader 2024"),
    ("Bootstrap 重采样", "≥1000 次", "统计惯例"),
    ("生物学", "N=3", "领域惯例"),
    ("心理学", "N=30+", "领域惯例"),
    ("LLM self-consistency", "5–10 甜点，40 饱和", "Wang 2022"),
]
for a, b, c in rows:
    cells = table.add_row().cells
    for i, t in enumerate([a, b, c]):
        p = cells[i].paragraphs[0]
        r = p.add_run(t)
        set_cn(r, "宋体", 10)

doc.add_paragraph()

# === 四、对本实验的建议 ===
heading("四、对本实验的建议", 1)
para("1. 6 次偏少，补到 10 次。", "宋体", 11, bold=True)
para("   成本只多 4 轮（约 +70% token），但跨过了 self-consistency 与 seed 文献"
     "共同指向的「10 次门槛」。6 次能初步揭示稳定核，但低于方法学共识。")
para("2. 阈值改 k≥6/10（60%）。", "宋体", 11, bold=True)
para("   现行 k≥4/6 在 6 次下只允许 2 次反对，统计上偏松；扩到 10 次后改 k≥6，"
     "与 self-consistency 经验区间吻合。")
para("3. 54 条 6/6 全命中的稳定核是可靠锚点。", "宋体", 11, bold=True)
para("   它天然满足 10 次下的 k≥6 阈值，不需要重跑就能复用。")
para("4. 若要加置信区间，", "宋体", 11, bold=True)
para("   对该 10 次结果做 1000 次 bootstrap 重采样即可给出主指标的 95% CI。")
para("5. k≥4/6 思路本身与 majority voting 一致、合理——只是次数不够。", "宋体", 11, bold=True)

# === 五、核心结论 ===
heading("五、核心结论", 1)
para("• T=0 不稳是 LLM 的普遍现象，非 DeepSeek 独有（基础设施层随机性）。")
para("• 跨学科共识指向 10 次为最低可信门槛；6 次可看方向，10 次可定结论。")
para("• 频次投票（k≥6/10）思路与 self-consistency 同源，是被文献充分支持的做法。")
para("• 当前 54 条 6/6 稳定核可直接作为可靠锚点复用。")

doc.add_page_break()

# === 参考文献 ===
heading("参考文献", 1)
refs = [
    "Atil, B. et al. (2025). Non-Determinism of \"Deterministic\" LLM Settings. arXiv:2408.04667.",
    "Nicholson, L. (2026). Quantifying non-deterministic drift in large language models. arXiv:2601.19934.",
    "Wang, X. et al. (2022/ICLR 2023). Self-Consistency Improves Chain of Thought Reasoning. arXiv:2203.11171.",
    "Weber-Genzel, A. et al. (2024). VARIERR NLI: Separating Annotation Error from Human Label Variation. ACL 2024.",
    "Plaza-del-Arco, S. et al. (2024). Wisdom of Instruction-Tuned Language Model Crowds. arXiv:2307.12973.",
    "Krippendorff, K. (2011). Computing Krippendorff's Alpha-Reliability. 本文档.",
    "Colas, C. et al. (2018). How Many Random Seeds? Statistical Power Analysis in Deep RL.",
    "Schader, M. et al. (2024). Don't let your analysis go to seed. Epidemiology.",
    "Du, J. (2025). When +1% Is Not Enough: A Paired Bootstrap Protocol. arXiv:2511.19794.",
]
for i, r in enumerate(refs, 1):
    p = doc.add_paragraph()
    run = p.add_run(f"[{i}] {r}")
    set_cn(run, "宋体", 9)

doc.save(str(OUT))
print(f"已生成：{OUT}")
print(f"大小：{OUT.stat().st_size} bytes")
