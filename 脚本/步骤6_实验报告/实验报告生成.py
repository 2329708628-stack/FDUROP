# -*- coding: utf-8 -*-
"""
生成 A01 等义判定预实验报告（docx）
"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import json, os, datetime

RUN_DIR = r"c:\Users\23297\Downloads\Lab\A01_湖北茶叶经济\03_实验输出\H1_v3.2"
EQ_DIR = os.path.join(RUN_DIR, "_equivalence")
OUT_PATH = r"c:\Users\23297\Downloads\Lab\实验方案\A01_等义判定预实验报告.docx"

def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    return h

def add_para(doc, text, bold=False, size=11):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.font.size = Pt(size)
    return p

def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for run in hdr[i].paragraphs[0].runs:
            run.bold = True
    for ri, row in enumerate(rows):
        cells = table.rows[ri + 1].cells
        for ci, val in enumerate(row):
            cells[ci].text = str(val)
    return table

# 加载真实数据
aci_result_path = os.path.join(EQ_DIR, "aci_result.json")
aci = json.load(open(aci_result_path, encoding="utf-8"))

judgments = json.load(open(os.path.join(EQ_DIR, "judgments.json"), encoding="utf-8"))
from collections import Counter
label_dist = Counter(j["label"] for j in judgments)

clusters = json.load(open(os.path.join(EQ_DIR, "clusters.json"), encoding="utf-8"))
cluster_sizes = Counter(c["size"] for c in clusters)

# 严格判定结果
strict_p33 = json.load(open(os.path.join(EQ_DIR, "strict_test_P33_GLM_4_Flash.json"), encoding="utf-8"))
strict_p6 = json.load(open(os.path.join(EQ_DIR, "strict_test_P6_GLM_4_Flash.json"), encoding="utf-8"))

doc = Document()

# 标题
title = doc.add_heading("A01 等义判定预实验报告", 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
add_para(doc, f"生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", size=10)

# 一、实验背景与目标
add_heading(doc, "一、实验背景与目标", 1)
add_para(doc,
    "本预实验是新实验方案（《Exploring The Boundaries of Reproducibility in Humanistic Argumentation》）"
    "第四、五步的可行性验证。方案规定：对模型多轮输出的论证命题，经原子化拆分后，由盲态 LLM "
    "进行六类语义关系判定（EQUIVALENT / A_ENTAILS_B / B_ENTAILS_A / CONTRADICTION / DIFFERENT / "
    "UNCERTAIN），再归一化为统一 concept_id 集合，输入 aci_reference.py 计算 ACI_J（节点收敛度）。")
add_para(doc, "本预实验聚焦回答以下问题：", bold=True)
add_para(doc, "1. 等义判定的核心困难在哪里？")
add_para(doc, "2. 单纯依赖 LLM 批量判定是否可靠？")
add_para(doc, "3. 需要哪些机制保证判定质量？")

# 二、实验数据
add_heading(doc, "二、实验数据", 1)
add_para(doc, "使用 A01《北宋时期湖北地区茶叶经济繁盛的状貌、缘由及影响》的 v3.2 三轮论证提取结果作为输入：")
add_table(doc, ["轮次", "A 级节点", "B 级节点", "C 级节点（叶子主张）"],
          [["run_1", "4", "9", "78"],
           ["run_2", "4", "9", "67"],
           ["run_3", "4", "9", "67"]])
add_para(doc, f"总计 212 个 C 级主张，按段落 anchor（P2–P33）分 16 组。"
              f"跨轮两两配对总数：{len(judgments)} 对。")
add_para(doc, "工具：组员提交的语义归一化实施包（normalization_prompts.json、aci_reference.py），"
              "API 中转站 model=GLM-4-Flash，temperature=0。", size=10)

# 三、第一遍：宽松批量判定
add_heading(doc, "三、第一遍：宽松批量判定（12 对/批）", 1)
add_para(doc, "采用自定义批量 prompt，每批 12 对命题，要求 LLM 输出 JSON 数组。全量 1159 对一次跑完。")
add_para(doc, "标签分布：", bold=True)
add_table(doc, ["标签", "数量", "占比"],
          [[k, v, f"{v/len(judgments)*100:.1f}%"] for k, v in sorted(label_dist.items())])
add_para(doc, "ACI_J 计算结果：", bold=True)
g = aci["groups"]["single"]["analysis"]
add_table(doc, ["指标", "值"],
          [["ACI_J（节点收敛度）", f"{g['aci_j']:.4f}"],
           ["unique concepts", g["counts"]["U_unique_concepts"]],
           ["每轮概念数", g["per_run_concept_counts"]],
           ["固定归一化声明", "False（预实验，不声明）"]])
add_para(doc, "表面结论：ACI_J=0.0693 很低，似乎收敛度极高。但进一步检查簇结构发现严重问题。", bold=True)

# 簇结构问题
add_heading(doc, "簇结构异常", 2)
add_table(doc, ["簇大小", "簇数"],
          [[s, cluster_sizes[s]] for s in sorted(cluster_sizes, reverse=True)])
add_para(doc, "出现 16、14、13、12 成员的巨型簇。但同段落 anchor 内每个概念最多应有 3 个成员"
              "（每轮一个对应节点），超过 3 必然是把不同概念合并了。")
add_para(doc, "典型错误（P33 结语段，4 个本应独立的结论）：", bold=True)
for c in clusters:
    if c["size"] >= 12:
        add_para(doc, f"概念 c{c['concept_id'].strip('c')}（{c['size']} 成员）合并了：")
        for m in c["members"]:
            add_para(doc, f"  · {m['atom']}: {m['text']}", size=10)
        break

add_para(doc, "根因：LLM 在批量模式下产生随机假阳性 EQUIVALENT 判定，经 Union-Find 传递性桥接，"
              "把 4 个不同结论焊成一个簇。这正是组员方案第五步第 3 点警告的'语义非传递冲突'。")

# 四、第二遍：严格判定
add_heading(doc, "四、第二遍：严格判定（组员原始 prompt + 5 对/批）", 1)
add_para(doc, "改用组员 normalization_prompts.json 中的 pair_decision system prompt，要求：")
add_para(doc, "· 逐项检查主体、关系、对象、时空范围、肯否、数量程度、状态或变化、因果方向、条件、认识强度")
add_para(doc, "· 只有双向蕴含且关键限定完全一致才判 EQUIVALENT")
add_para(doc, "· 输出 a_entails_b、b_entails_a 布尔字段")
add_para(doc, "· 批次缩小到 5 对，批次内用短序号 q1..q5 防止长 ID 被模型改写")

add_para(doc, "在 P33（4 结论）和 P6（含拆合节点）上建立手工金标准评估：", bold=True)
add_table(doc, ["段落", "精确率", "召回率", "主要错误类型"],
          [["P33（4 结论）", "91.7%", "91.7%",
            "1 条离奇假阳性（产量↔政策结果）、1 条降级为蕴含"],
           ["P6（含拆合）", "84.6%", "91.7%",
            "错误全部集中在复合节点（run2/run3 把'18府州+10产茶区'合并成一条）"]])

add_para(doc, "结论：严格 prompt + 小批量显著降低假阳性，但仍有残余错误，且无法处理'拆合'——"
              "run1 拆成两条、run2/run3 合成一条，比较错位。")

# 五、第三遍：三角形一致性守卫
add_heading(doc, "五、第三遍：三角形一致性守卫（离线验证）", 1)
add_para(doc, "实现方案第五步第 3 点的'簇内两两校验'：合并 x~y 时，若目标簇中存在与 x 跨轮、"
              "且已被判为非等义（DIFFERENT/ENTAILS/CONTRADICTION/UNCERTAIN）的成员，"
              "则拒绝合并并记录冲突交人工复核。")
add_para(doc, "在严格判定结果上离线运行守卫（无需再调 API）：", bold=True)
add_table(doc, ["段落", "守卫效果"],
          [["P33", "完美恢复 4 个概念组（C0.1/C0.2/C0.3 各 3 成员）；"
                    "离奇假阳性被自动拦截，run3_C0.4 进入人工复核队列"],
           ["P6", "残余混乱全部源于复合节点（拆合问题），守卫只能拦截不能解决"]])
add_para(doc, "守卫拦截的冲突示例：")
add_para(doc, "  · 拒绝合并 run_1_C0.1 ~ run_3_C0.4，因 run_2_C0.1 - run_3_C0.4 已判 DIFFERENT")
add_para(doc, "  · 拒绝合并 run_2_C0.4 ~ run_3_C0.4，因 run_1_C0.4 - run_3_C0.4 已判 A_ENTAILS_B")

# 六、核心发现
add_heading(doc, "六、核心发现", 1)
add_para(doc, "1. 等义判定的最大风险是'传递性桥接'：少量假阳性 EQUIVALENT 经 Union-Find 扩散，"
              "产生巨型错误簇，使 ACI 表面值严重失真。", bold=True)
add_para(doc, "2. 三道防线缺一不可：", bold=True)
add_para(doc, "   ① 先原子化——复合句（'A，且B'）必须拆成独立命题，否则比较从根上错位；")
add_para(doc, "   ② 双向蕴含 + 关键限定逐项核对——同主题、同数字都不算（'维持高位'≠'拉动攀升'）；")
add_para(doc, "   ③ 簇内两两一致性校验——LLM 残余随机假阳性由传递性守卫自动捕获进人工复核。")
add_para(doc, "3. GLM-4-Flash 在严格 prompt + 小批量下精确率约 85–92%，残余错误需人工裁决；"
              "正式实验应考虑更强模型（如 GLM-4.5）或双人独立标注。", bold=True)

# 七、产出文件
add_heading(doc, "七、产出文件", 1)
add_table(doc, ["文件", "说明"],
          [["脚本/步骤7_测试验证/equivalence_judge.py", "第一遍宽松批量判定 + ACI 计算（待编写）"],
           ["脚本/步骤7_测试验证/严格判定测试.py", "第二遍严格判定 + 金标准评估"],
           ["脚本/步骤7_测试验证/三角守卫测试.py", "第三遍三角形守卫离线验证"],
           ["A01/.../_equivalence/judgments.json", "第一遍 1159 对判定记录"],
           ["A01/.../_equivalence/clusters.json", "第一遍簇结构（含巨型错误簇）"],
           ["A01/.../_equivalence/aci_result.json", "第一遍 ACI_J=0.0693 结果"],
           ["A01/.../_equivalence/strict_test_*.json", "P33/P6 严格判定明细"]])

# 八、下一步
add_heading(doc, "八、下一步计划", 1)
add_para(doc, "1. 实现原子化步骤：对 212 个 C 节点调用组员 atomization prompt，拆为最小可独立判断命题；")
add_para(doc, "2. 用'严格判定 + 三角形守卫'重跑全量，输出最终 ACI；")
add_para(doc, "3. 评估更强模型（GLM-4.5）的判定精度；")
add_para(doc, "4. 按方案要求建立开发集/冻结测试集，完成双人标注与 κ 系数验证。")

# 保存（带时间戳避免占用冲突）
base, ext = os.path.splitext(OUT_PATH)
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
final_path = f"{base}_{ts}{ext}"
doc.save(final_path)
print(f"报告已生成: {final_path}")
