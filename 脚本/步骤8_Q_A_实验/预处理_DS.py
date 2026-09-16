# -*- coding: utf-8 -*-
"""DS.txt（DeepSeek 生成论文）轻量预处理。
DS.txt 是纯文本带 [Mxx] 标记，已直接调用史料池 M1-M52；
[清洗.py] 是为 PDF 解析 JSON 设计的，本脚本专为 DS.txt 格式。

输入：A01_湖北茶叶经济/DS.txt
输出：03_实验输出/Q_A_实验/Q_run_DS/00_原文/原文_clean.json
  - paragraphs: [{id, type, text, material_refs, page}]
  - materials: 直接从 Q_run_2/00_原文/原文_clean.json 复用（同史料池）
"""
import json, re
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
SRC_TXT = LAB / "A01_湖北茶叶经济" / "DS.txt"
MATERIALS_FROM = LAB / "A01_湖北茶叶经济" / "03_实验输出" / "Q_A_实验" / "Q_run_2" / "00_原文" / "原文_clean.json"
OUT_DIR = LAB / "A01_湖北茶叶经济" / "03_实验输出" / "Q_A_实验" / "Q_run_DS" / "00_原文"
OUT = OUT_DIR / "原文_clean.json"

# 标题正则（与 公共库.derive_skeleton 保持一致）
CN = "一二三四五六七八九十"
RE_H1 = re.compile(r"^\s*[" + CN + r"]+\s*[、.．]?\s*\S")
RE_H2 = re.compile(r"^\s*[（(][" + CN + r"]+[）)]")
RE_SPECIAL = re.compile(r"^\s*(结语|余论|结论|小结|引论|绪论)\s*[：:]?\s*$")

# 元信息行（跳过）
RE_META = re.compile(r"^\s*(摘要|关键词|说明)[：:]")


def classify(line):
    """返回 ('title'|'text'|None, level_or_None)"""
    s = line.strip()
    if not s:
        return None, None
    if RE_META.match(s):
        return None, None
    if RE_SPECIAL.match(s) or RE_H1.match(s):
        return "title", 1
    if RE_H2.match(s):
        return "title", 2
    return "text", None


def extract_refs(text):
    """从文本中提取 Mxx 引用标记，按出现顺序去重。
    支持全角（M31）、半角(M31)、[M31] 单 M 形式，
    以及（M41、M43）一个括号内多个 M 用顿号/逗号/空格分隔的形式。"""
    refs, seen = [], set()
    # 先抓括号内整段，再从段内提取所有 M\d+
    for grp in re.findall(r"[（(\[]([^)）\]]*)[)）\]]", text):
        for m in re.findall(r"M(\d+)", grp):
            mid = "M" + m
            if mid not in seen:
                refs.append(mid)
                seen.add(mid)
    return refs


def main():
    text = SRC_TXT.read_text(encoding="utf-8")
    # 按行切分，但相邻正文行需合并为段（DS.txt 段落内不分行，按行即可）
    raw_lines = text.split("\n")

    paragraphs = []
    p_counter = 0
    for line in raw_lines:
        typ, _ = classify(line)
        if typ is None:
            continue
        s = line.strip()
        p_counter += 1
        if typ == "title":
            paragraphs.append({
                "id": "P%d" % p_counter,
                "type": "title",
                "text": s,
                "material_refs": extract_refs(s),
                "page": "1",
            })
        else:
            paragraphs.append({
                "id": "P%d" % p_counter,
                "type": "text",
                "text": s,
                "material_refs": extract_refs(s),
                "page": "1",
            })

    # materials 直接复用 Q_run_2 的史料池
    mat_data = json.load(open(MATERIALS_FROM, encoding="utf-8"))
    materials = mat_data["materials"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {"paragraphs": paragraphs, "materials": materials}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 60)
    print("DS.txt 预处理完成")
    print("=" * 60)
    print("输出: %s" % OUT)
    print("段落数: %d" % len(paragraphs))
    print("史料数: %d（复用 Q_run_2 史料池）" % len(materials))
    print()
    print("--- 标题列表 ---")
    for p in paragraphs:
        if p["type"] == "title":
            print("  %s: %s" % (p["id"], p["text"][:40]))
    print()
    # 验证 M 全覆盖
    all_refs = set()
    for p in paragraphs:
        all_refs.update(p["material_refs"])
    valid_M = {m["id"] for m in materials}
    print("--- M 引用统计 ---")
    print("正文出现 M: %d / %d = %.1f%%" %
          (len(all_refs & valid_M), len(valid_M), len(all_refs & valid_M) / len(valid_M) * 100))
    missing = valid_M - all_refs
    if missing:
        print("未引用 M: %s" % sorted(missing, key=lambda x: int(x[1:])))


if __name__ == "__main__":
    main()
