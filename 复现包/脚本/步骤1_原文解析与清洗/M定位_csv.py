# -*- coding: utf-8 -*-
"""给 M 全量总表补"正文定位"，输出 Excel 可直接打开的 CSV（UTF-8 带 BOM）。

定位逻辑：
  对每篇，读 00_原文/ 布局 JSON（原文.json / 湖北茶叶经济.json），把正文 preproc_blocks 中
  type=='text' 的块按阅读顺序编号为段落,记 {page, para_index, text}。
  每条 M 有 footnote_number（圈码）+ page，在所属页的正文段落里找含该圈码的段落，
  取整段文本与该圈码在段内位置，作为该 M 的定位字段。
用法：python 脚本/步骤1_原文解析与清洗/M定位_csv.py [对照目录]
输出：数据集/M全量提取/M全量总表_定位.csv
"""
import csv, json, sys
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
CTRL = Path(sys.argv[1]) if len(sys.argv) > 1 else LAB / "数据集" / "对照组"
IN = LAB / "数据集" / "M全量提取"
OUT = IN / "M全量总表_定位.csv"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
CIRCLED_RE = None


def content(b):
    return "".join(s.get("content", "") for L in b.get("lines", []) for s in L.get("spans", []))


def all_text_blocks(layout_path):
    """返回 [(page, para_index, text)] 按阅读顺序"""
    d = json.loads(layout_path.read_text(encoding="utf-8"))
    paras = []
    pi = 0
    texts = []  # 收集连续 text 块，段落可能跨多块
    for page in d.get("pdf_info", []):
        pn = ""
        for b in page.get("discarded_blocks", []):
            if b.get("type") == "page_number":
                pn = content(b).strip()
        for b in page.get("preproc_blocks", []):
            t = b.get("type")
            txt = content(b).strip()
            if not txt:
                continue
            if t == "text":
                texts.append((pn, txt))
            elif t in ("title", "image", "table") and texts:
                # 遇到标题/表图，把已缓冲的 text 块合成一个段落提交
                paras.append((texts[0][0], pi, "".join(x for _, x in texts)))
                pi += 1
                texts = []
                paras.append((pn, pi, txt)) if t == "title" else None
                if t == "title":
                    pi += 1
    if texts:
        paras.append((texts[0][0], pi, "".join(x for _, x in texts)))
    return paras


def find_layout(pd):
    d = pd / "00_原文"
    if not d.exists():
        return None
    for c in ("原文.json", "湖北茶叶经济.json"):
        if (d / c).exists():
            return d / c
    return None


def main():
    rows = []
    total = 0
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["paper", "m_id", "footnote_number", "page", "para_index",
                    "正文位置片段", "脚注原文"])
        for pd in sorted([d for d in CTRL.iterdir() if d.is_dir()], key=lambda x: x.name):
            lp = find_layout(pd)
            mp = IN / f"{pd.name}_M.json"
            if not lp or not mp.exists():
                continue
            paras = all_text_blocks(lp)
            mats = json.loads(mp.read_text(encoding="utf-8"))["materials"]
            for m in mats:
                fn = m.get("footnote_number", "")
                loc_seg = ""
                target_para = ""
                if fn and fn in CIRCLED:
                    page = m.get("page", "")
                    for (ppg, pidx, ptext) in paras:
                        if page and ppg != page:
                            continue
                        pos = ptext.find(fn)
                        if pos >= 0:
                            start = max(0, pos - 60)
                            loc_seg = ptext[start:pos + len(fn) + 60]
                            target_para = f"P{pidx + 1}"
                            break
                w.writerow([pd.name, m["id"], fn, m.get("page", ""), target_para,
                            loc_seg, m["text"]])
                total += 1
    print(f"写入 {OUT}\n总行数: {total}")


if __name__ == "__main__":
    main()