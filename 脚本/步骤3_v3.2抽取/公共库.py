# -*- coding: utf-8 -*-
"""v3.2 公共库：骨架机械推导、编号、sources 并集、论文路径解析。
被 run校验器.py / run组装器.py / 三轮锚点对比.py 复用。

数据约定：
  论文目录/00_原文/原文_clean.json  含 paragraphs（id/type/text/material_refs）与 materials（id/...）
  run JSON：v3.2 编码产物（meta.version == "3.2"）
"""
import json, re, sys
from pathlib import Path

CN = "一二三四五六七八九十"
RE_H2 = re.compile(r"^\s*[（(][" + CN + r"]+[）)]")
RE_H3 = re.compile(r"^\s*\d{1,2}\s*[.、．]\s*\S")
RE_H1_NUM = re.compile(r"^\s*[" + CN + r"]+\s*[、.．]?\s*\S")
RE_SPECIAL = re.compile(r"^\s*(结语|余论|结论|小结|引论|绪论)\s*[：:]?\s*$")
RE_YEAR = re.compile(r"^\s*\d{3,4}\s*[.、．]")  # 年份/表号，排除出 H3


def load_paper(paper_dir):
    """返回 (paragraphs_list, materials_list, clean_json_path)。"""
    p = Path(paper_dir)
    clean = p / "00_原文" / "原文_clean.json"
    if not clean.exists():
        sys.exit("找不到 %s —— 该论文尚未完成 01_引用提取/清洗" % clean)
    d = json.load(open(clean, encoding="utf-8"))
    return d["paragraphs"], d["materials"], clean


def derive_skeleton(paragraphs):
    """从 paragraphs 机械推导 v3.2 骨架（即提示词调用①的 Python 实现）。
    返回 dict：
      A: [{id,depth,title_label,span:[start,end|None],parent,order}]  order=正文出现序（A0 为 -1）
      B: [{id,depth,title_label,span,parent,order}]
      front_matter: [P...]  第一个一级标题之前的正文段
      para_index: {Pid: 段落序列位置}
      title_para: {节点id: 标题段Pid}
    """
    paras = paragraphs
    pidx = {p["id"]: i for i, p in enumerate(paras)}
    # 收集标题段（跳过主标题：第一个 type==title）
    heads = []  # (seq_idx, level, text, pid)
    first_title_seen = False
    for i, p in enumerate(paras):
        if p.get("type") != "title":
            continue
        t = (p.get("text") or "").strip()
        if not first_title_seen:
            first_title_seen = True
            continue  # 论文主标题
        if RE_YEAR.match(t):
            continue
        if RE_SPECIAL.match(t) or RE_H1_NUM.match(t):
            lvl = 1
        elif RE_H2.match(t):
            lvl = 2
        elif RE_H3.match(t):
            lvl = 3
        else:
            # 无法识别的标题段（如簿书格式误标）→ 不当结构节点
            continue
        if len(t) > 45:
            continue
        heads.append([i, lvl, t, p["id"]])

    # span：标题 i 之后、第一个 level<=自身 的标题 j 之前的正文段
    def span_of(h_i, level):
        start = end = None
        for k in range(h_i + 1, len(paras)):
            pk = paras[k]
            if pk.get("type") == "title":
                # 该标题段是否为更高级/同级标题
                tk = (pk.get("text") or "").strip()
                lk = None
                if RE_SPECIAL.match(tk) or RE_H1_NUM.match(tk):
                    lk = 1
                elif RE_H2.match(tk):
                    lk = 2
                elif RE_H3.match(tk) and not RE_YEAR.match(tk):
                    lk = 3
                if lk is not None and lk <= level and len(tk) <= 45:
                    break
                continue
            if start is None:
                start = pk["id"]
            end = pk["id"]
        return [start, end]

    A, B = [], []
    cur_a = cur_b = None
    a_n = 0
    b2_n = {}   # A序号 -> depth2 计数
    b3_n = {}   # (A序, b2序) -> depth3 计数
    first_h1_idx = None
    for h_i, level, text, pid in heads:
        if level == 1:
            is_concl = bool(RE_SPECIAL.match(text))
            if is_concl:
                aid = "A0"
                order = -1
            else:
                a_n += 1
                aid = "A%d" % a_n
                order = a_n
            if first_h1_idx is None and not is_concl:
                first_h1_idx = h_i
            A.append({"id": aid, "depth": 1, "title_label": text,
                      "span": span_of(h_i, 1), "parent": None, "order": order,
                      "title_pid": pid})
            cur_a = aid
            cur_b = None
        elif level == 2:
            if cur_a is None:
                continue
            a_seq = int(cur_a[1:])
            b2_n[a_seq] = b2_n.get(a_seq, 0) + 1
            bid = "B%d.%d" % (a_seq, b2_n[a_seq])
            B.append({"id": bid, "depth": 2, "title_label": text,
                      "span": span_of(h_i, 2), "parent": cur_a,
                      "title_pid": pid})
            cur_b = bid
        else:  # level 3
            if cur_b is None:
                # 目级标题出现在无（二）级位置：挂当前 A，按 depth2 处理仍不合规——跳过并提示
                B.append({"id": "ORPHAN@%s" % pid, "depth": 3, "title_label": text,
                          "span": span_of(h_i, 3), "parent": cur_a,
                          "title_pid": pid})
                continue
            a_seq = int(cur_a[1:])
            b2_seq = int(cur_b.split(".")[1])
            key = (a_seq, b2_seq)
            b3_n[key] = b3_n.get(key, 0) + 1
            bid = "B%d.%d.%d" % (a_seq, b2_seq, b3_n[key])
            B.append({"id": bid, "depth": 3, "title_label": text,
                      "span": span_of(h_i, 3), "parent": cur_b,
                      "title_pid": pid})

    # front_matter：第一个一级标题前的正文段
    front = []
    if first_h1_idx is not None:
        for k in range(first_h1_idx):
            if paras[k].get("type") == "text":
                front.append(paras[k]["id"])
    return {"A": A, "B": B, "front_matter": front, "para_index": pidx,
            "paragraphs": paras}


def m_key(m):
    """M 编号排序键：M13 -> 13。"""
    return int(re.sub(r"\D", "", m))


def c_id_for(parent_id, n):
    """C 编号 = C + 父节点数字路径 + .序号。
    B1.1->C1.1.n ; B2.3.1->C2.3.1.n ; A1->C1.n（扁平篇）。"""
    return "C" + parent_id[1:] + ".%d" % n


def descendants(parent_id, A, B, C):
    """返回某节点整棵子树内的 C 节点列表。"""
    b_ids = {b["id"] for b in B}
    a_ids = {a["id"] for a in A}
    # 子 B
    child_b = set()
    stack = [parent_id] if parent_id in b_ids or parent_id in a_ids else []
    while stack:
        cur = stack.pop()
        for b in B:
            if b["parent"] == cur:
                child_b.add(b["id"])
                stack.append(b["id"])
    targets = child_b | ({parent_id} if parent_id in b_ids or parent_id in a_ids else set())
    return [c for c in C if c["parent"] in targets]


def union_sources(nodes):
    s = set()
    for n in nodes:
        s |= set(n.get("sources", []))
    return s


def para_in_span(pid, span, para_index):
    """段落 P 是否落在 span 闭区间内（按段落序列位置）。"""
    if not span or span[0] is None:
        return False
    i = para_index.get(pid)
    lo = para_index.get(span[0])
    hi = para_index.get(span[1]) if span[1] else lo
    return i is not None and lo is not None and hi is not None and lo <= i <= hi


def find_paper_dir(start):
    """从 run 文件路径或论文目录路径推断论文根目录（含 00_原文 的最近祖先）。"""
    p = Path(start)
    if p.is_file():
        p = p.parent
    for q in [p] + list(p.parents):
        if (q / "00_原文").exists():
            return q
    return p
