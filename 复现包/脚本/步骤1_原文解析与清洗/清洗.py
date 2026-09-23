# -*- coding: utf-8 -*-
"""
数据清洗脚本（自然段落版）
==========================
1. 用 bbox 垂直间距合并连续 text block → 自然段落
2. 跨页合并：前段未以句号结尾且下段非标题 → 合并
3. 保留 ①②③ 脚注标记在段落原文中
4. 每段记录 material_refs: [M1, M3, ...] 映射（按文本片段来源页码精确匹配）
输出：00_原文/原文_clean.json
"""

import json
import re
import os
import sys

# ---- 路径 ----
# 用法：python 清洗.py [论文目录]  （论文目录需含 layout.json 与 full.md）
# 缺省时用 A01 论文
PAPER_ROOT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\23297\Downloads\Lab\A01_湖北茶叶经济"
PAPER_DIR = os.path.join(PAPER_ROOT, "00_原文")
INPUT_FILE = os.path.join(PAPER_DIR, "原文.json")
OUTPUT_FILE = os.path.join(PAPER_DIR, "原文_clean.json")

# ---- 正则 ----
RE_ABSTRACT    = re.compile(r"^摘要[：:]")
RE_KEYWORDS    = re.compile(r"^关键词[：:]")
RE_AUTHOR      = re.compile(r"^[\u4e00-\u9fff]{2,4}(\s+[\u4e00-\u9fff]{2,4})*\*{0,2}$")
RE_AFFIL       = re.compile(r"^[（(].*?(大学|学院|研究中心|研究所|研究院|实验室|系)")
# 机构续行（如 "2. 四川省社会科学院 哲学研究所，四川 成都，610071）" 为作者机构第二行）
RE_AFFIL_CONT  = re.compile(r"^\d+\.\s*[\u4e00-\u9fff][\u4e00-\u9fff0-9（）()，,、\s]*?(研究所|研究院|学院|大学|中心|系)[\u4e00-\u9fff0-9（）()，,、\s]*?）$")
RE_FUNDED      = re.compile(r"^\*\s*基金项目")
RE_BIO         = re.compile(r"^\*\*作者简介")
RE_DOI         = re.compile(r"^DOI[:：]", re.IGNORECASE)
RE_CNKI        = re.compile(r"^中国知网\s*https?://")
RE_HEADER      = re.compile(r"^■")
RE_SERIES      = re.compile(r"^宋史研究论丛")
RE_PAGENUM     = re.compile(r"^\d{1,4}$")

DELETE_PATTERNS_MAIN = [RE_ABSTRACT, RE_KEYWORDS, RE_AUTHOR, RE_AFFIL, RE_AFFIL_CONT,
                        RE_HEADER, RE_SERIES]
DELETE_PATTERNS_DISCARD = [RE_DOI, RE_CNKI, RE_FUNDED, RE_BIO, RE_PAGENUM, RE_HEADER, RE_SERIES]

RE_HISTORICAL = re.compile(
    r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*(?:[（(](?:唐|宋|元|明|清|汉|晋|南北朝|五代)|《)"
)
RE_CIRCLED = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]")

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

MERGE_GAP = 18

# 块级切分白名单：命中的论文按 MinerU layout 块切段（每个 text 块即一段），
# 不做页内间距合并——中文论文段落多为首行缩进、段间无额外间距（实测页内块间距
# 仅 2~5px，标题才 18~23px），用 MERGE_GAP 合并会把整章正文并成一两段。
# 也可用命令行 --block-level 强制启用。
BLOCK_LEVEL_PAPERS = {"A05", "B05", "C01"}


def use_block_level(paper_root):
    """是否对该论文启用块级切分。"""
    name = os.path.basename(os.path.normpath(paper_root))
    return ("--block-level" in sys.argv) or (name.split("_")[0] in BLOCK_LEVEL_PAPERS)


def get_content(block):
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            return span.get("content", "")
    return ""


def get_bbox(block):
    bbox = block.get("bbox", [0, 0, 0, 0])
    if len(bbox) == 4:
        return bbox[1], bbox[3]
    return 0, 0


def build_material_map(data):
    """构建 (page, footnote_number) → material_id 映射"""
    mat_counter = 0
    mat_map = {}
    materials = []
    for page in data.get("pdf_info", []):
        page_num = ""
        for b in page.get("discarded_blocks", []):
            if b.get("type") == "page_number":
                page_num = get_content(b).strip()
        for block in page.get("discarded_blocks", []):
            content = get_content(block).strip()
            if not content:
                continue
            if any(p.search(content) for p in DELETE_PATTERNS_DISCARD):
                continue
            if RE_HISTORICAL.search(content):
                mat_counter += 1
                mid = "M{}".format(mat_counter)
                fn_num = content[0] if content and content[0] in CIRCLED else ""
                materials.append({
                    "id": mid,
                    "text": content,
                    "page": page_num,
                    "footnote_number": fn_num,
                })
                if fn_num and page_num:
                    mat_map[(page_num, fn_num)] = mid
    return mat_map, materials


def collect_blocks(data):
    """收集所有页面的 block，按原文顺序排列"""
    all_blocks = []  # [(page_num, block, content, y0, y1)]
    for page in data.get("pdf_info", []):
        page_num = ""
        for b in page.get("discarded_blocks", []):
            if b.get("type") == "page_number":
                page_num = get_content(b).strip()
        for block in page.get("preproc_blocks", []):
            content = get_content(block).strip()
            if not content:
                continue
            btype = block.get("type", "text")
            # title 块不执行删除检查（避免"结语"等被误删）
            if btype != "title" and any(p.search(content) for p in DELETE_PATTERNS_MAIN):
                continue
            y0, y1 = get_bbox(block)
            all_blocks.append((page_num, block, content, y0, y1))
    return all_blocks


def merge_paragraphs(data, mat_map, block_level=False):
    """合并连续 text block 为自然段落（含跨页），提取脚注引用

    block_level=True 时：每个 text 块独立成段，仅保留跨页续段合并（分页截断）。
    """
    all_blocks = collect_blocks(data)
    para_counter = 0
    paragraphs = []

    i = 0
    while i < len(all_blocks):
        page_num, block, content, _, y1 = all_blocks[i]
        btype = block.get("type", "text")

        # title 单独成段
        if btype == "title":
            para_counter += 1
            refs = extract_refs(content, page_num, mat_map)
            paragraphs.append({
                "id": "P{}".format(para_counter),
                "type": "title",
                "text": content,
                "page": page_num,
                "material_refs": refs,
            })
            i += 1
            continue

        # text 块：向后续 block 合并
        # segments: [(page_num, text)]，用于精确提取脚注引用
        segments = [(page_num, content)]
        merged_text = content
        prev_y1 = y1
        prev_page = page_num
        j = i + 1
        while j < len(all_blocks):
            next_page, next_block, next_content, next_y0, next_y1 = all_blocks[j]
            next_type = next_block.get("type", "text")

            if not next_content:
                break
            if any(p.search(next_content) for p in DELETE_PATTERNS_MAIN):
                break
            # 遇到标题块 → 停止合并
            if next_type == "title":
                break

            if next_page == prev_page:
                if block_level:
                    break  # 块级切分：每块一段，不做页内间距合并
                gap = next_y0 - prev_y1
                if gap >= MERGE_GAP:
                    break
            else:
                # 跨页：仅当前段以非标点汉字结尾（被分页截断）才合并
                if next_type == "title":
                    break
                if not merged_text:
                    break
                last_char = merged_text[-1]
                # 只允许以纯汉字结尾时跨页合并（排除所有标点）
                if not ("\u4e00" <= last_char <= "\u9fff"):
                    break

            merged_text += next_content
            segments.append((next_page, next_content))
            prev_y1 = next_y1
            prev_page = next_page
            j += 1

        para_counter += 1
        refs = extract_refs_from_segments(segments, mat_map)
        paragraphs.append({
            "id": "P{}".format(para_counter),
            "type": "text",
            "text": merged_text,
            "page": page_num,
            "material_refs": refs,
        })
        i = j

    return paragraphs


def extract_refs(text, page_num, mat_map):
    """从文本中提取 ①②③，用指定页码映射到 M-id"""
    refs = []
    seen = set()
    for ch in RE_CIRCLED.findall(text):
        mid = mat_map.get((page_num, ch))
        if mid and mid not in seen:
            refs.append(mid)
            seen.add(mid)
    return refs


def extract_refs_from_segments(segments, mat_map):
    """从合并段落的各片段分别提取引用，保持顺序"""
    refs = []
    seen = set()
    for page_num, seg_text in segments:
        for ch in RE_CIRCLED.findall(seg_text):
            mid = mat_map.get((page_num, ch))
            if mid and mid not in seen:
                refs.append(mid)
                seen.add(mid)
    return refs


def merge_subtitles(paragraphs):
    """将以 —— 开头的副标题并入前一个标题（如主标题+破折号副标题）"""
    out = []
    for p in paragraphs:
        if (p["type"] == "text" and p["text"].startswith("——") and out
                and out[-1]["type"] == "title"):
            out[-1]["text"] = out[-1]["text"] + p["text"]
            continue
        out.append(p)
    return out


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    mat_map, materials = build_material_map(data)
    block_level = use_block_level(PAPER_ROOT)
    paragraphs = merge_paragraphs(data, mat_map, block_level=block_level)
    paragraphs = merge_subtitles(paragraphs)

    output = {
        "paragraphs": paragraphs,
        "materials": materials,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 50)
    print("数据清洗完成（自然段落版{}）".format("，块级切分" if block_level else ""))
    print("输出: {}".format(OUTPUT_FILE))
    print("=" * 50)
    print("段落数: {} 条".format(len(paragraphs)))
    print("史料数: {} 条".format(len(materials)))

    print("\n--- 标题列表 ---")
    for p in paragraphs:
        if p["type"] == "title":
            print("  {} (p.{}): {}".format(p["id"], p["page"], p["text"][:40]))

    print("\n--- 含史料引用的段落示例 ---")
    count = 0
    for p in paragraphs:
        if p["type"] == "text" and p["material_refs"]:
            print("  {} (p.{}) refs={}: {}...".format(
                p["id"], p["page"], p["material_refs"], p["text"][:80]))
            count += 1
            if count >= 5:
                break


if __name__ == "__main__":
    main()
