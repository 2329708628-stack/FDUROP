# -*- coding: utf-8 -*-
"""参照《预实验/02_史料池/source_pool.json》为对照组每篇生成史料池。

定位策略（逐 text 块，不跨块拼接）：
  对每篇布局 JSON，遍历 preproc_blocks 中 type=='text' 的块，逐个块内搜索脚注圈码，
  取该圈码所在块内的局部文本作为该史料的 text（正文原句定位）。
分组策略：按书名 title 聚合（同书多个脚注合为一个 source，passages 逐条），
          若脚注为现代文献（无《》书名），按 source_full 前缀聚合。
产物：数据集/M全量提取/史料池/<paper>_史料池.json
"""
import json, re
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
IN = LAB / "数据集" / "M全量提取"
OUTDIR = IN / "史料池"
OUTDIR.mkdir(parents=True, exist_ok=True)
CTRL = LAB / "数据集" / "对照组"

RE_DYNASTY = re.compile(r"[（(](唐|宋|元|明|清|汉|晋|南北朝|五代|金)[）)]")
RE_TITLE = re.compile(r"《([^》]{1,60})》")
RE_VOL = re.compile(r"(卷[^，。；,|，、]{0,8})")


def content(b):
    return "".join(s.get("content", "") for L in b.get("lines", []) for s in L.get("spans", []))


def find_layout(pd):
    d = pd / "00_原文"
    if not d.exists():
        return None
    for c in ("原文.json", "湖北茶叶经济.json"):
        if (d / c).exists():
            return d / c
    return None


def tide_textblocks(layout_path):
    """返回 [(page, text)] 逐块，page 为页号字符串，用于页面内圈码定位"""
    d = json.loads(layout_path.read_text(encoding="utf-8"))
    out = []
    for page in d.get("pdf_info", []):
        pn = ""
        for b in page.get("discarded_blocks", []):
            if b.get("type") == "page_number":
                pn = content(b).strip()
        for b in page.get("preproc_blocks", []):
            if b.get("type") == "text":
                t = content(b).strip()
                if t:
                    out.append((pn, t))
    return out


CIRCLED_STR = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def loc_for(m, blocks):
    """提取圈码前引文（"……"① 格式）作为史料 text。

    脚注编号为页内编号（每页从①重新开始），因此必须限定在同一页内搜索圈码，
    否则会错配到其它页的相同圈码。其次取该页内圈码前紧跟的引文片段。
    """
    fn = m.get("footnote_number", "")
    mp = str(m.get("page", "")).strip()
    if not fn:
        return ""
    target = [(pp, t) for (pp, t) in blocks if pp == mp]
    if not target:  # 页号缺失时退回全篇搜索
        target = blocks
    for (pp, t) in target:
        pos = t.find(fn)
        if pos < 0:
            continue
        close = pos
        if close > 0 and t[close - 1] in '”"':
            close -= 1
            oq = max(t.rfind('“', 0, close), t.rfind('"', 0, close))
            s = oq + 1 if oq >= 0 else 0
        else:
            bound = max([t.rfind(ch, 0, pos) for ch in CIRCLED_STR] + [-1])
            s = bound + 1
        seg = t[s:close].strip(" 　，。；：、")
        return seg
    return ""


def parse(text):
    t = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]?\s*", "", text).strip()
    md = RE_DYNASTY.search(t)
    dynasty = md.group(1) if md else ""
    mt = RE_TITLE.search(t)
    title = mt.group(1) if mt else ""
    mv = RE_VOL.search(t)
    volume = mv.group(1) if mv else ""
    return dynasty, title, volume, t


def main():
    for pd in sorted([d for d in CTRL.iterdir() if d.is_dir()], key=lambda x: x.name):
        paper = pd.name
        lp = find_layout(pd)
        mp = IN / f"{paper}_M.json"
        if not lp or not mp.exists():
            continue
        blocks = tide_textblocks(lp)
        mats = json.loads(mp.read_text(encoding="utf-8"))["materials"]

        groups = []
        gindex = {}
        for m in mats:
            dynasty, title, volume, sfull = parse(m["text"])
            key = title if title else sfull[:40]
            loc = loc_for(m, blocks)
            if key not in gindex:
                gindex[key] = len(groups)
                groups.append({"title": title, "dynasty": dynasty, "source_full": sfull,
                               "volume": volume, "passages": []})
            groups[gindex[key]]["passages"].append({
                "passage_id": "", "original_id": m["id"], "text": loc,
                "source_full": sfull, "volume": volume,
            })

        sources = []
        for i, g in enumerate(groups, 1):
            sid = f"SRC_{i:03d}"
            for j, ps in enumerate(g["passages"], 1):
                ps["passage_id"] = f"{sid}_P{j:02d}"
            sources.append({"source_id": sid, "title": g["title"], "dynasty": g["dynasty"],
                            "citation_count": len(g["passages"]), "passages": g["passages"]})

        out = {"metadata": {"version": "2.0", "paper_id": paper,
                            "description": "对照论文全量史料池（含现代文献，未过滤）",
                            "note": "text 为正文引用该史料的原文引文片段（圈码前引文）；source_full 为完整脚注出处"},
               "statistics": {"total_sources": len(sources),
                              "total_passages": sum(len(s["passages"]) for s in sources)},
               "sources": sources}
        (OUTDIR / f"{paper}_史料池.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{paper}: {len(sources)} 源 / {out['statistics']['total_passages']} 条", flush=True)
    print("完成:", OUTDIR, flush=True)


if __name__ == "__main__":
    main()