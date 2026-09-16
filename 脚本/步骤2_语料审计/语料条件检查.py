# -*- coding: utf-8 -*-
"""
检查 20 篇样本是否满足两个入样条件：
  条件1：多级标题结构清晰（至少 2 级标题，如 一/（一）；且一级标题 >=2 个）
  条件2：段落内含一手史料引用标记（圈码脚注 ①-⑳ 等 + 《》史料名 + 直接引语）
输出：每篇的标题层级、标题列表、引用标记密度
"""
import re, json, sys
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")

# 圈码：①-⑳ (U+2460-2473)，以及 latex 风格 $^{①}$
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵"
CIRCLED_RE = re.compile("[" + CIRCLED + "]")
LATEX_FN_RE = re.compile(r"\$\^?\{?[" + CIRCLED + r"]+\}?\$")

# 中文标题模式
H1_RE = re.compile(r"^\s*(?:#{1,6}\s*)?([一二三四五六七八九十]+)\s*[、.．]?\s*\S")   # 一、 / 一
H2_RE = re.compile(r"^\s*(?:#{1,6}\s*)?[（(]([一二三四五六七八九十]+)[）)]\s*\S")     # （一）
H3_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(\d+)[.、．]\s*\S")                          # 1. / 1、

# 一手史料书名号（排除现代作者论文名较难，先统计总数 + 常见史料关键词命中）
SHILIAO_KEYS = ["宋会要", "续资治通鉴长编", "长编", "宋史", "建炎以来系年要录", "系年要录",
                "文献通考", "通考", "玉海", "诸蕃志", "救荒活民书", "名公书判清明集",
                "清明集", "作邑自箴", "州县提纲", "元丰九域志", "太平寰宇记", "舆地纪胜",
                "方舆胜览", "咸淳临安志", "淳熙三山志", "嘉定赤城志", "宝庆四明志",
                "攻媿集", "朱文公文集", "晦庵集", "诚斋集", "剑南诗稿", "欧阳修",
                "司马公文集", "宋刑统", "庆元条法事类", "吏部条法", "武经总要",
                "宣和奉使", "岭外代答", "容斋随笔", "老学庵笔记", "东京梦华录",
                "梦粱录", "武林旧事", "都城纪胜", "东坡志林", "萍洲可谈", "桯史",
                "建炎以来朝野杂记", "朝野杂记", "宋大诏令集", "大诏令集", "历代名臣奏议",
                "宋名臣奏议", "朱子语类", "朱子全书", "黄氏日抄", "西山读书记",
                "册府元龟", "太平御览", "文苑英华", "全宋文", "宋会要辑稿",
                "三司条例司", "中书备对", "会计录", "中书典故"]

def analyze(paper_dir: Path):
    md = paper_dir / "00_原文" / "full.md"
    text = md.read_text(encoding="utf-8")
    lines = text.splitlines()

    # ---- 标题识别 ----
    h1, h2, h3 = [], [], []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m_md = re.match(r"^(#{1,6})\s+(.*)$", s)
        body = m_md.group(2) if m_md else s
        # 跳过作者、单位、摘要关键词行
        if re.match(r"^(摘要|关键词|作者简介|基金项目|中图分类号|收稿日期)", body):
            continue
        if H2_RE.match(s):
            h2.append(body)
        elif H1_RE.match(s) and len(body) <= 40:
            h1.append(body)
        elif H3_RE.match(s) and len(body) <= 40 and not re.match(r"^\d{4}", body):
            h3.append(body)

    # ---- 段落与引用标记 ----
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body_paras = []
    for p in paras:
        head = p.lstrip("# ").strip()
        if re.match(r"^(摘要|关键词|作者简介|基金项目|参考文献|注释|#?\s*[一二三四五六七八九十]+\s*[、.．]?\s*$)", head):
            continue
        if re.match(r"^[（(]?[一二三四五六七八九十]+[）)]?\s*$", head):
            continue
        body_paras.append(p)

    n_para = len(body_paras)
    n_fn_para = 0      # 含圈码/latex脚注的段落
    fn_total = 0
    n_quote_para = 0   # 含中文引号直接引语的段落
    n_book_para = 0    # 含《》的段落
    book_titles = set()
    shiliao_hits = set()

    for p in body_paras:
        plain = re.sub(r"^#+\s*", "", p, flags=re.M)
        marks = CIRCLED_RE.findall(plain)
        marks += LATEX_FN_RE.findall(plain)  # latex 形式
        if marks:
            n_fn_para += 1
            fn_total += len(marks)
        if ("“" in plain and "”" in plain) or ("「" in plain and "」" in plain):
            n_quote_para += 1
        books = re.findall(r"《([^》]{2,30})》", plain)
        if books:
            n_book_para += 1
            for b in books:
                book_titles.add(b)
                for k in SHILIAO_KEYS:
                    if k in b:
                        shiliao_hits.add(k)

    return {
        "paper": paper_dir.name,
        "n_h1": len(h1), "n_h2": len(h2), "n_h3": len(h3),
        "h1_titles": h1[:12],
        "h2_sample": h2[:8],
        "n_body_para": n_para,
        "n_fn_para": n_fn_para,
        "fn_total": fn_total,
        "fn_para_ratio": round(n_fn_para / n_para, 2) if n_para else 0,
        "n_quote_para": n_quote_para,
        "n_book_para": n_book_para,
        "n_book_titles": len(book_titles),
        "n_shiliao_types": len(shiliao_hits),
        "shiliao_sample": sorted(shiliao_hits)[:10],
    }

def main():
    rows = []
    for d in sorted(LAB.iterdir()):
        if d.is_dir() and d.name.startswith("A") and (d / "00_原文" / "full.md").exists():
            rows.append(analyze(d))

    print(f"{'编号':<22}{'一级':>4}{'二级':>4}{'三级':>4}{'正文段':>6}{'含注段':>6}{'注均':>6}{'引语段':>6}{'《》段':>6}{'史料类':>6}")
    print("-" * 90)
    for r in rows:
        avg = round(r["fn_total"] / r["n_fn_para"], 1) if r["n_fn_para"] else 0
        print(f"{r['paper']:<22}{r['n_h1']:>4}{r['n_h2']:>4}{r['n_h3']:>4}"
              f"{r['n_body_para']:>6}{r['n_fn_para']:>6}{avg:>6}{r['n_quote_para']:>6}"
              f"{r['n_book_para']:>6}{r['n_shiliao_types']:>6}")

    print("\n===== 条件判定 =====")
    for r in rows:
        cond1 = "✔" if (r["n_h1"] >= 2 and r["n_h2"] >= 2) else ("△" if r["n_h1"] >= 2 else "✘")
        cond2 = "✔" if (r["fn_para_ratio"] >= 0.3 and r["n_shiliao_types"] >= 2) else "✘"
        print(f"{r['paper']:<22} 多级标题[{cond1}]  一手史料标记[{cond2}]  "
              f"(H1={r['n_h1']},H2={r['n_h2']},H3={r['n_h3']}; 含注段占比={r['fn_para_ratio']},史料种类={r['n_shiliao_types']})")

    out = LAB / "脚本" / "步骤2_语料审计" / "语料审计报告.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细已写入: {out}")

if __name__ == "__main__":
    main()
