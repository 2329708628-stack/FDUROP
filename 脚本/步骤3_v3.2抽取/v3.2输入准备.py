# -*- coding: utf-8 -*-
"""为 A01 生成 v3.2 五调用实验输入数据包。
产物写入 A01/03_实验输出/H1_v3.2/_inputs/：
  skeleton.json       ——调用①骨架（脚本确定性推导，可直接作为产物①，无需模型）
  call2_C_input.json   ——调用②输入：paragraphs+materials（完整）
  call3_B_inputs/      ——调用③输入：每个 B 节点单独一份（title_label+span 段落原文）
  call4_A_inputs/      ——调用④输入：每个 A 节点单独一份
  call5_inputs.json    ——调用⑤输入：骨架+段落+材料清单（综合时使用）
  执行说明.txt        ——本地窗口 5 调用执行步骤
用法：python 脚本/步骤3_v3.2抽取/v3.2输入准备.py [论文目录(默认A01)]
"""
import json, os, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from 公共库 import load_paper, derive_skeleton, para_in_span

paper_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"c:\Users\23297\Downloads\Lab\A01_湖北茶叶经济")
paras, materials, clean_path = load_paper(paper_dir)
sk = derive_skeleton(paras)
pidx = sk["para_index"]
text_paras = {p["id"]: p for p in paras if p.get("type") == "text"}

outdir = paper_dir / "03_实验输出" / "H1_v3.2" / "_inputs"
if outdir.exists():
    shutil.rmtree(outdir)
outdir.mkdir(parents=True)
(outdir / "call3_B_inputs").mkdir()
(outdir / "call4_A_inputs").mkdir()


def span_paras(span):
    """返回 span 闭区间内的正文段（按原文序）。"""
    if not span or span[0] is None:
        return []
    lo, hi = pidx[span[0]], pidx[span[1] if span[1] else span[0]]
    return [p for p in paras if p.get("type") == "text"
            and lo <= pidx[p["id"]] <= hi]


def slim_para(p):
    """段落精简版：去 page 字段减小体积（模型上下文更省）。"""
    return {"id": p["id"], "type": p["type"], "text": p["text"],
            "material_refs": p.get("material_refs", [])}


# ---------- 调用①骨架（脚本确定性产出） ----------
skeleton = {
    "A_skeleton": [{"id": a["id"], "depth": a["depth"],
                    "title_label": a["title_label"], "span": a["span"],
                    "parent": a["parent"]} for a in sk["A"]],
    "B_skeleton": [{"id": b["id"], "depth": b["depth"],
                    "title_label": b["title_label"], "span": b["span"],
                    "parent": b["parent"]}
                   for b in sk["B"] if not b["id"].startswith("ORPHAN@")],
    "front_matter": sk["front_matter"],
}
json.dump(skeleton, open(outdir / "skeleton.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

# ---------- 调用②输入：paragraphs+materials ----------
call2 = {"paragraphs": [slim_para(p) for p in paras],
         "materials": [{"id": m["id"], "text": m.get("text", ""),
                        "footnote_number": m.get("footnote_number")}
                       for m in materials],
         "skeleton_for_reference": skeleton}
json.dump(call2, open(outdir / "call2_C_input.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

# ---------- 调用③输入：每个 B 节点一份 ----------
for b in sk["B"]:
    if b["id"].startswith("ORPHAN@"):
        continue
    doc = {"node_id": b["id"], "depth": b["depth"],
           "title_label": b["title_label"], "span": b["span"],
           "parent": b["parent"],
           "paragraphs_in_span": [slim_para(p) for p in span_paras(b["span"])],
           "rule": "只依据 title_label 与 span 段落生成 1 条 claim（20-60字命题，主谓宾完整）；禁止参考任何 C 级主张或其他节点。"}
    json.dump(doc, open(outdir / "call3_B_inputs" / (b["id"] + ".json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=2)

# ---------- 调用④输入：每个 A 节点一份 ----------
for a in sk["A"]:
    doc = {"node_id": a["id"], "depth": a["depth"],
           "title_label": a["title_label"], "span": a["span"],
           "parent": a["parent"],
           "paragraphs_in_span": [slim_para(p) for p in span_paras(a["span"])],
           "rule": "只依据 title_label 与 span 段落生成 1 条 claim；A0 从结语段概括全文核心结论；禁止参考 B/C 的任何输出。"}
    json.dump(doc, open(outdir / "call4_A_inputs" / (a["id"] + ".json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=2)

# ---------- 调用⑤输入：骨架+段落+材料清单 ----------
call5 = {"skeleton": skeleton,
         "all_paragraphs": [slim_para(p) for p in paras],
         "all_materials": [{"id": m["id"]} for m in materials],
         "rule": "综合调用②③④的产物：做支持核查（claim 须被后代蕴含，不过仅可收窄改写）→ 自底向上算 sources → 输出 v3.2 完整 JSON。"}
json.dump(call5, open(outdir / "call5_inputs.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

# ---------- README ----------
n_b = len(skeleton["B_skeleton"])
n_a = len(skeleton["A_skeleton"])
readme = """A01 v3.2 五调用实验输入（脚本自动生成）

【骨架】A={n_a}  B={n_b}  front_matter={fm}
  扁平结构（B 为空）的论文：调用③跳过，C 直接挂 A。

【执行步骤——本地窗口手动操作】
1. 新开空白对话窗口（独立会话）。
2. 粘贴 提示词/提示词_H1_v3.2.txt 的【提示词正文】（从"你是历史学论文论证结构形式化编码器"到末尾），等模型确认理解。
3. 调用①：骨架已由脚本确定性产出（skeleton.json），无需让模型再跑；
   实验时把 skeleton.json 内容贴给模型，声明"调用①产物如下，直接使用"。
4. 调用②：把 call2_C_input.json 全文贴给模型，要求产出 C_level 数组。
   保存模型输出为 C_level.json。
5. 调用③：把 call3_B_inputs/ 下每个 .json 逐个贴给模型，要求产出
   该节点 1 条 claim。所有节点合起来保存为 B_claims.json：
   [{{"id":"B1.1","claim":"…"}}, …]
   重要：每个节点的输入只含该节点 title_label+span 段落，禁止让模型看到
   其他节点或 C 级输出。
6. 调用④：把 call4_A_inputs/ 下每个 .json 逐个贴给模型，产出 A_claims.json：
   [{{"id":"A1","claim":"…"}}, …，{{"id":"A0","claim":"…"}}]
7. 调用⑤：新开窗口，贴提示词正文 + skeleton.json + C_level.json +
   B_claims.json + A_claims.json + call5_inputs.json（含段落和材料清单），
   要求模型做支持核查并输出最终一份 JSON。
8. 最终 JSON 保存为 run_1.json，用 run校验器.py 校验：
   python 脚本/步骤3_v3.2抽取/run校验器.py A01_湖北茶叶经济/03_实验输出/H1_v3.2/run_1.json
9. 重复步骤 1-8 共 5 轮（每轮独立会话），最后跑：
   python 脚本/步骤3_v3.2抽取/三轮锚点对比.py A01_湖北茶叶经济

【简化路径——单窗口顺序执行（预实验可用）】
同一窗口按①→②→③→④→⑤顺序执行，但执行③④时严格遵守"只看本节点 span 段落"
的规则，假定未见过②③的论点文本。

【文件清单】
_inputs/skeleton.json          调用①产物（脚本产出）
_inputs/call2_C_input.json     调用②输入
_inputs/call3_B_inputs/*.json  调用③输入（每节点 1 个）
_inputs/call4_A_inputs/*.json  调用④输入（每节点 1 个）
_inputs/call5_inputs.json      调用⑤输入
""".format(n_a=n_a, n_b=n_b, fm=sk["front_matter"])
open(outdir / "执行说明.txt", "w", encoding="utf-8").write(readme)

print("written:", outdir)
print("A=%d B=%d  front_matter=%s" % (n_a, n_b, sk["front_matter"]))
print("call3 文件数:", len(list((outdir / "call3_B_inputs").glob("*.json"))))
print("call4 文件数:", len(list((outdir / "call4_A_inputs").glob("*.json"))))
