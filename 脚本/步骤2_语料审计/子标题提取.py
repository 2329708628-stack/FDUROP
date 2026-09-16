# -*- coding: utf-8 -*-
"""
提取 20 篇样本全文中的所有小标题。
来源：
  1) markdown 标题行（# / ## / ###，MinerU 转换格式）
  2) 独占一行的裸编号标题：一、 / （一） / 1. 等
层级判定：
  L1 = 一、二、… 或 ## 编号标题（章）
  L2 = （一）（二）… 或 ### 标题（节）
  L3 = 1. 2. … 数字编号（目）
  特殊：结语/结论/余论/小结/引言/绪论 归 L1
可疑项（markdown 标题但无编号、非结语类，可能是误识别的表格/簿书）标 [?]
"""
import re, json
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")

CN_NUM = "一二三四五六七八九十"
SPECIAL_L1 = ["结语", "结论", "余论", "小结", "引言", "绪论", "前言", "问题的提出", "引论"]

RE_MD   = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
RE_L1   = re.compile(rf"^[{CN_NUM}]+\s*[、.．]?\s*\S")
RE_L2   = re.compile(rf"^[（(][{CN_NUM}]+[）)]\s*\S")
RE_L3   = re.compile(r"^\d+\s*[.、．]\s*\S")
RE_SPEC = re.compile(r"^(" + "|".join(SPECIAL_L1) + r")\s*[：:]?\s*$")

def clean(t: str) -> str:
    t = t.strip()
    t = re.sub(r"\\?\*+$", "", t)          # 末尾 * 或 \*
    t = t.replace("\\*", "*").strip()
    return t

def is_body_like(t: str) -> bool:
    """像正文而非标题：过长或以句读结尾"""
    if len(t) > 45:
        return True
    if re.search(r"[。；！？，、]$", t):
        return True
    return False

def extract(md_path: Path):
    out = []  # (level, text, flag)
    seen = set()
    for raw in md_path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s:
            continue
        m = RE_MD.match(s)
        if m:
            hashes, body = m.group(1), clean(m.group(2))
            lvl_md = len(hashes)
            if lvl_md == 1:
                continue  # 文章大标题/副标题
            if not body or body in seen:
                continue
            seen.add(body)
            # 判定层级
            if RE_L2.match(body):
                lvl = 2
            elif RE_L3.match(body):
                lvl = 3
            elif RE_L1.match(body) or RE_SPEC.match(body) or any(k in body for k in SPECIAL_L1):
                lvl = 1
            else:
                lvl = 1 if lvl_md == 2 else 2
                flag = "?"  # 无编号、非结语类，疑似误识别
                out.append((lvl, body, flag))
                continue
            out.append((lvl, body, ""))
            continue
        # 裸标题行（无 markdown 标记）
        body = clean(s)
        if body in seen or is_body_like(body):
            continue
        if RE_L2.match(s):
            seen.add(body); out.append((2, body, ""))
        elif RE_L1.match(s) or RE_SPEC.match(body):
            seen.add(body); out.append((1, body, ""))
        elif RE_L3.match(s) and not re.match(r"^\d{4}", body):
            seen.add(body); out.append((3, body, ""))
    return out

def main():
    lines = []
    data = {}
    for d in sorted(LAB.iterdir()):
        if not (d.is_dir() and d.name.startswith("A") and (d / "00_原文" / "full.md").exists()):
            continue
        heads = extract(d / "00_原文" / "full.md")
        data[d.name] = [{"level": l, "text": t, "flag": f} for l, t, f in heads]
        n1 = sum(1 for l, _, _ in heads if l == 1)
        n2 = sum(1 for l, _, _ in heads if l == 2)
        n3 = sum(1 for l, _, _ in heads if l == 3)
        lines.append(f"\n{'='*64}\n{d.name}   （一级 {n1} / 二级 {n2} / 三级 {n3}）\n{'='*64}")
        for lvl, t, f in heads:
            mark = {"?": "   [?疑似非标题]"}.get(f, "")
            indent = {1: "", 2: "    ", 3: "        "}[lvl]
            lines.append(f"{indent}L{lvl}  {t}{mark}")

    report = "\n".join(lines)
    print(report)
    out_txt = LAB / "脚本" / "步骤2_语料审计" / "子标题清单.txt"
    out_txt.write_text(report, encoding="utf-8")
    (LAB / "脚本" / "步骤2_语料审计" / "子标题清单.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n\n已保存: {out_txt}")

if __name__ == "__main__":
    main()
