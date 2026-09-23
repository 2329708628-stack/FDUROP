# -*- coding: utf-8 -*-
"""全量提取对照组全部论文的所有脚注(记为 M)，含现代学者引用，分篇+汇总总表。
用户要求：不问是不是史料，全部取，后续再人工排除。
每篇从 00_原文/ 下的布局 JSON（原文.json 或 *经济.json）读 discarded_blocks 中
type=='page_footnote' 的块，剔除页眉/页脚/页码，编号 M1..Mn。
输出：数据集/M全量提取/<篇号>_M.json + M全量总表.json/.csv
"""
import json, re, sys
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
CTRL = LAB / "数据集" / "对照组"
OUT = LAB / "数据集" / "M全量提取"
PAGE_NUM = re.compile(r"^\d{1,4}$")
# 页眉/页脚/非脚注已知噪声（DOI、知网页脚、基金、作者简介、栏目头）
NOISE = re.compile(r"^(DOI[:：]?|中国知网|www\.|http|\*\s*基金项目|\*\*\s*作者简介|作者简介|宋史研究论丛)"
                   , re.IGNORECASE)
CIRCLED_FN = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]")


def content(block):
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            return span.get("content", "")
    return ""


def find_layout(paper_dir):
    d = paper_dir / "00_原文"
    if not d.exists():
        return None
    for cand in ("原文.json", "湖北茶叶经济.json"):
        p = d / cand
        if p.exists():
            return p
    return None


def extract_materials(layout_path):
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    mats = []
    for page in data.get("pdf_info", []):
        page_num = ""
        for b in page.get("discarded_blocks", []):
            if b.get("type") == "page_number":
                page_num = content(b).strip()
        for b in page.get("discarded_blocks", []):
            txt = content(b).strip()
            if not txt or b.get("type") != "page_footnote":
                continue
            if PAGE_NUM.match(txt) or NOISE.search(txt):
                continue
            fn = txt[0] if CIRCLED_FN.match(txt) else ""
            mats.append({"text": txt, "page": page_num, "footnote_number": fn})
    # 编号
    out = []
    for i, m in enumerate(mats, 1):
        m = dict(m); m["id"] = f"M{i}"; out.append(m)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total = []
    papers = sorted([d for d in CTRL.iterdir() if d.is_dir()], key=lambda x: x.name)
    for p in papers:
        lp = find_layout(p)
        if not lp:
            print(f"{p.name}: 无布局JSON，跳过", flush=True)
            continue
        try:
            mats = extract_materials(lp)
        except Exception as e:
            print(f"{p.name}: 错误 {e}", flush=True)
            continue
        rec = {"paper": p.name, "n_materials": len(mats), "materials": mats}
        (OUT / f"{p.name}_M.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        for m in mats:
            total.append({"paper": p.name, "m_id": m["id"], "text": m["text"],
                          "page": m["page"], "footnote_number": m["footnote_number"]})
        print(f"{p.name}: {len(mats)} 条脚注", flush=True)

    # 汇总
    summary = {"n_papers": len(papers), "n_total_materials": len(total),
               "all": total}
    (OUT / "M全量总表.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    import csv
    with open(OUT / "M全量总表.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["paper", "m_id", "footnote_number", "page", "text"])
        for t in total:
            w.writerow([t["paper"], t["m_id"], t["footnote_number"], t["page"], t["text"]])
    print(f"\n总篇数: {summary['n_papers']}  总脚注数: {summary['n_total_materials']}", flush=True)
    print(f"输出: {OUT}", flush=True)


if __name__ == "__main__":
    main()