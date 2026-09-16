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

# ---- 路径 ----
PAPER_DIR = r"C:\Users\23297\Downloads\Lab\A01_湖北茶叶经济\00_原文"
INPUT_FILE = os.path.join(PAPER_DIR, "原文.json")
OUTPUT_FILE = os.path.join(PAPER_DIR, "原文_clean.json")

# ---- 正则 ----
RE_ABSTRACT    = re.compile(r"^摘要[：:]")
RE_KEYWORDS    = re.compile(r"^关键词[：:]")
RE_AUTHOR      = re.compile(r"^[\u4e00-\u9fff]{2,4}(\s+[\u4e00-\u9fff]{2,4})*\*{0,2}$")
RE_AFFIL       = re.compile(r"^[（(].*?(大学|学院|研究中心|研究所|研究院|实验室|系)")
RE_FUNDED      = re.compile(r"^\*\s*基金项目")
RE_BIO         = re.compile(r"^\*\*作者简介")
RE_DOI         = re.compile(r"^DOI[:：]", re.IGNORECASE)
RE_CNKI        = re.compile(r"^中国知网\s*https?://")
RE_HEADER      = re.compile(r"^■")
RE_SERIES      = re.compile(r"^宋史研究论丛")
RE_PAGENUM     = re.compile(r"^\d{1,4}$")

DELETE_PATTERNS_MAIN = [RE_ABSTRACT, RE_KEYWORDS, RE_AUTHOR, RE_AFFIL, RE_HEADER, RE_SERIES]
DELETE_PATTERNS_DISCARD = [RE_DOI, RE_CNKI, RE_FUNDED, RE_BIO, RE_PAGENUM, RE_HEADER, RE_SERIES]

RE_HISTORICAL = re.compile(
    r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]\s*(?:[（(](?:唐|宋|元|明|清|汉|晋|南北朝|五代)|《)"
)
RE_CIRCLED = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]")

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

MERGE_GAP = 18


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


def merge_paragraphs(data, mat_map):
    """合并连续 text block 为自然段落（含跨页），提取脚注引用"""
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


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    mat_map, materials = build_material_map(data)
    paragraphs = merge_paragraphs(data, mat_map)

    output = {
        "paragraphs": paragraphs,
        "materials": materials,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 50)
    print("数据清洗完成（自然段落版）")
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
