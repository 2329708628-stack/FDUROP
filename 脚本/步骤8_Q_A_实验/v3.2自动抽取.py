# -*- coding: utf-8 -*-
"""v3.2 自动五调用抽取（Q_A 实验用）。

输入：<Q_run 目录>（须已含 00_原文/原文_clean.json）
产物：
  _inputs/skeleton.json       调用①骨架（机械推导，v32_lib.derive_skeleton）
  _intermediate/C_level.json  调用②产物（API）
  _intermediate/B_claims.json 调用③产物（API 批量）
  _intermediate/A_claims.json 调用④产物（API 批量）
  run.json                    最终组装产物（含 statistics）
  meta.json                   模型/温度/各调用耗时

跳过调用⑤（支持核查）—— supported/supported_by 留空 null（用 run校验器.py 检视 WARN）。
批量化策略：调用③④按 depth 分组一次调用，每节点在 prompt 内独立说明，禁止参考其他节点。

用法：python 脚本/步骤8_Q_A_实验/v3.2自动抽取.py <Q_run 目录名> [论文目录(默认 A01_湖北茶叶经济)] [模型(默认 GLM-4.5-Flash)]
"""
import json, os, sys, time, datetime, re, shutil
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
_pylibs = str(LAB / ".pylibs")
if _pylibs not in sys.path:
    sys.path.insert(0, _pylibs)
import requests

sys.path.insert(0, str(LAB / "脚本" / "步骤3_v3.2抽取"))
from 公共库 import load_paper, derive_skeleton, m_key, c_id_for, descendants, union_sources, para_in_span

API_FILE = LAB / "API.txt"
MODEL_DEFAULT = "GLM-4.5-Flash"
TEMPERATURE = 0.7
MAX_TOKENS = 16384


def read_api():
    lines = [l.strip() for l in API_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines[0], lines[1]


def clean_json_output(raw):
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    i = s.find("[")
    j = s.rfind("]")
    if i < 0 or j < i:
        i = s.find("{")
        j = s.rfind("}")
    if i >= 0 and j > i:
        s = s[i:j + 1]
    return s


def call_api(prompt, model, api_key, base_url, max_retries=5):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }
    last_err = None
    for attempt in range(max_retries + 1):
        chunks = []
        t0 = time.time()
        first_t = None
        finish = None
        try:
            with requests.post(url, headers=headers, json=payload, stream=True, timeout=900) as r:
                if r.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"    [429 限流] 第 {attempt+1}/{max_retries} 次，等 {wait}s 后重试...")
                    time.sleep(wait)
                    continue
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
                for raw in r.iter_lines(decode_unicode=True):
                    if not raw or not raw.startswith("data:"):
                        continue
                    data = raw[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    try:
                        ch = obj["choices"][0]
                    except (KeyError, IndexError):
                        continue
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
                    piece = ch.get("delta", {}).get("content", "") or ""
                    if piece:
                        if first_t is None:
                            first_t = time.time()
                        chunks.append(piece)
            elapsed = time.time() - t0
            return "".join(chunks), elapsed, (first_t - t0 if first_t else 0.0), finish
        except requests.exceptions.RequestException as e:
            last_err = e
            wait = 15 * (attempt + 1)
            print(f"    [网络异常] {e}  第 {attempt+1}/{max_retries} 次，等 {wait}s 后重试...")
            time.sleep(wait)
    raise RuntimeError(f"API 调用 {max_retries} 次重试后仍失败: {last_err}")


# ---------- 调用② prompt ----------
def build_call2_prompt(paras, materials, skeleton):
    paras_json = json.dumps([
        {"id": p["id"], "type": p["type"], "text": p["text"],
         "material_refs": p.get("material_refs", [])}
        for p in paras
    ], ensure_ascii=False, indent=1)
    mats_json = json.dumps([
        {"id": m["id"], "text": m.get("text", "")}
        for m in materials
    ], ensure_ascii=False, indent=1)
    sk_json = json.dumps(skeleton, ensure_ascii=False, indent=1)
    return f"""你是历史学论文论证结构形式化编码器。任务：把一篇历史学论文编码为 A-B-C-M 层级路径的 JSON。

【v3.2 C 级论点独立生成——调用②】
规则：
1. 逐段阅读每个正文段（type=="text"），将其切分为 1~6 条单一、可检验的事实主张；每条为 30~80 字一行式短句，不照抄原文长句。
2. 每条 C 必须带 "anchor"：来源段落的 P 编号。一条 C 只锚定一个段落；跨两段的内容拆成两条 C 分别锚定。
3. sources 绑定：C 的 sources 只取其 anchor 段 material_refs 中、且确实支撑该主张的 M 编号；推导性主张 sources 用空数组 []。
4. 段落归属：正文段归入其空间所在的最低级标题（depth=3 之下归 depth=3，无 depth=3 归 depth=2；扁平结构直接归 A）。front_matter 段（含 material_refs 的）按语义归入最相关的 B，anchor 仍为其原 P 编号。
5. 纯总起/过渡段（无 material_refs 且仅承上启下、无事实主张）不切 C。
6. 编号与排序：C 的 id = "C" + 父节点数字路径 + "." + 序号（父为 B1.1 → C1.1.1、C1.1.2…；扁平篇父为 A1 → C1.1、C1.2…）；同一父节点内按 anchor 段页序→段内切分顺序连续编号。

【输入 1: skeleton】
{sk_json}

【输入 2: paragraphs】
{paras_json}

【输入 3: materials】
{mats_json}

请只输出 C_level JSON 数组，形如：
[{{"id":"C1.1.1","anchor":"P6","text":"……事实主张……","sources":["M4"],"parent":"B1.1"}}]

不要输出 markdown 代码块标记、不要说明文字、不要前后缀。直接以 [ 开头。
"""


# ---------- 调用③ prompt (B 批量) ----------
def build_call3_prompt(b_nodes, paras, pidx):
    """b_nodes: list of {id, depth, title_label, span, parent}"""
    items = []
    for b in b_nodes:
        span = b["span"]
        lo = pidx[span[0]] if span and span[0] else None
        hi = pidx[span[1] if span and len(span) > 1 and span[1] else span[0]] if span and span[0] else None
        ps = []
        if lo is not None and hi is not None:
            for p in paras:
                if p.get("type") == "text":
                    pi = pidx[p["id"]]
                    if lo <= pi <= hi:
                        ps.append({"id": p["id"], "text": p["text"]})
        items.append({
            "id": b["id"], "depth": b["depth"], "title_label": b["title_label"],
            "span": span, "parent": b["parent"],
            "paragraphs_in_span": ps,
        })
    items_json = json.dumps(items, ensure_ascii=False, indent=1)
    return f"""你是历史学论文论证结构形式化编码器。任务：v3.2 调用③【B 级论点独立生成】。

【规则】
对下列每个 B 节点，你只被允许看到该节点的 title_label 与其 span 区间内的段落原文。
禁止参考任何 C 级主张、其他 B 或 A 节点内容。
为该节点生成恰好 1 条 claim（20~60 字命题式陈述句）：
1. 必须是一个可判真假的命题：主谓宾完整的陈述句，20~60 字；禁止名词短语、话题罗列、禁止"本文/笔者认为"等元话语。
2. 以 title_label 为话题约束：title_label 是判断性短语则补全主语成句；title_label 是名词标签则从 span 段落概括出该节论证的结论性命题。
3. 只能使用 span 内段落出现的信息，不得引入 span 外内容；若 span 内论点不止一个，claim 写为能统摄全节的总命题。

【输入：B 节点列表（每个含 title_label + span 段落原文）】
{items_json}

【输出格式：JSON 数组】
[{{"id":"B1.1","claim":"……命题……"}}, …]

只输出 JSON 数组，不要 markdown 代码块标记、不要说明文字。直接以 [ 开头。
"""


# ---------- 调用④ prompt (A 批量) ----------
def build_call4_prompt(a_nodes, paras, pidx):
    items = []
    for a in a_nodes:
        span = a["span"]
        lo = pidx[span[0]] if span and span[0] else None
        hi = pidx[span[1] if span and len(span) > 1 and span[1] else span[0]] if span and span[0] else None
        ps = []
        if lo is not None and hi is not None:
            for p in paras:
                if p.get("type") == "text":
                    pi = pidx[p["id"]]
                    if lo <= pi <= hi:
                        ps.append({"id": p["id"], "text": p["text"]})
        items.append({
            "id": a["id"], "depth": a["depth"], "title_label": a["title_label"],
            "span": span, "parent": a["parent"],
            "paragraphs_in_span": ps,
        })
    items_json = json.dumps(items, ensure_ascii=False, indent=1)
    return f"""你是历史学论文论证结构形式化编码器。任务：v3.2 调用④【A 级论点独立生成】。

【规则】
对下列每个 A 节点（含 A0=结语），你只被允许看到该节点的 title_label 与其 span 区间内段落的原文。
禁止参考调用②③的任何输出。
为该节点生成恰好 1 条 claim（20~60 字、主谓宾完整的命题）：
- A1…An 的 claim 从其 span 段落概括该章核心论点；
- A0 的 claim 从结语段概括全文核心结论。
不得引入 span 外内容。

【输入：A 节点列表（每个含 title_label + span 段落原文）】
{items_json}

【输出格式：JSON 数组】
[{{"id":"A1","claim":"……命题……"}}, …，{{"id":"A0","claim":"……核心结论……"}}]

只输出 JSON 数组，不要 markdown 代码块标记、不要说明文字。直接以 [ 开头。
"""


def slim_para(p):
    return {"id": p["id"], "type": p["type"], "text": p["text"],
            "material_refs": p.get("material_refs", [])}


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python v3.2自动抽取.py <Q_run 目录名> [论文目录] [模型]")
    run_name = sys.argv[1]
    paper_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else (LAB / "A01_湖北茶叶经济")
    model = sys.argv[3] if len(sys.argv) > 3 else MODEL_DEFAULT
    run_dir = paper_dir / "03_实验输出" / "Q_A_实验" / run_name

    paras, materials, _ = load_paper(run_dir)
    valid_M = {m["id"] for m in materials}
    valid_P = {p["id"] for p in paras}
    sk = derive_skeleton(paras)
    pidx = sk["para_index"]

    A_defs = sk["A"]
    B_defs_all = [b for b in sk["B"] if not b["id"].startswith("ORPHAN@")]
    B_depth2 = [b for b in B_defs_all if b["depth"] == 2]
    B_depth3 = [b for b in B_defs_all if b["depth"] == 3]

    skeleton_out = {
        "A_skeleton": [{"id": a["id"], "depth": a["depth"], "title_label": a["title_label"],
                        "span": a["span"], "parent": a.get("parent")} for a in A_defs],
        "B_skeleton": [{"id": b["id"], "depth": b["depth"], "title_label": b["title_label"],
                        "span": b["span"], "parent": b.get("parent")} for b in B_defs_all],
        "front_matter": sk["front_matter"],
    }

    inputs_dir = run_dir / "_inputs"
    inter_dir = run_dir / "_intermediate"
    for d in (inputs_dir, inter_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    (inputs_dir / "skeleton.json").write_text(
        json.dumps(skeleton_out, ensure_ascii=False, indent=2), encoding="utf-8")

    api_key, base_url = read_api()
    print(f"[{run_name}] 模型={model}  段落={len(paras)}  M={len(materials)}  A={len(A_defs)}  B(d2/d3)={len(B_depth2)}/{len(B_depth3)}")
    print(f"  骨架：A={','.join(a['id'] for a in A_defs)}  B={','.join(b['id'] for b in B_defs_all)}")

    meta = {
        "run_name": run_name, "model": model, "temperature": TEMPERATURE,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "skeleton": {"A_count": len(A_defs), "B_count": len(B_defs_all),
                     "B_depth2": len(B_depth2), "B_depth3": len(B_depth3),
                     "front_matter": sk["front_matter"]},
        "calls": {},
    }

    # -------- 调用②：C 级 --------
    print("  [调用② C 级] 生成 prompt...")
    p2 = build_call2_prompt(paras, materials, skeleton_out)
    (inputs_dir / "call2_prompt.txt").write_text(p2, encoding="utf-8")
    print(f"    prompt 字符数={len(p2)}  开始 API 调用...")
    raw2, t2, ttft2, fin2 = call_api(p2, model, api_key, base_url)
    print(f"    用时={t2:.1f}s  首token={ttft2:.2f}s  原始字符={len(raw2)}  finish={fin2}")
    cleaned2 = clean_json_output(raw2)
    (inter_dir / "C_level_raw.txt").write_text(raw2, encoding="utf-8")
    try:
        c_level = json.loads(cleaned2)
        (inter_dir / "C_level.json").write_text(
            json.dumps(c_level, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    C 解析 OK  条数={len(c_level)}")
        parse2_ok = True
    except Exception as e:
        print(f"    C 解析失败: {e}")
        (inter_dir / "C_level.json").write_text(cleaned2, encoding="utf-8")
        c_level = []
        parse2_ok = False
    meta["calls"]["call2_C"] = {
        "elapsed_sec": round(t2, 2), "ttft_sec": round(ttft2, 2),
        "raw_chars": len(raw2), "parsed": parse2_ok, "c_count": len(c_level),
        "finish_reason": fin2,
    }

    # -------- 调用③：B 级 --------
    b_claims = {}
    for depth_label, b_list in (("depth2", B_depth2), ("depth3", B_depth3)):
        if not b_list:
            continue
        print(f"  [调用③ B 级 {depth_label}] 节点数={len(b_list)}")
        p3 = build_call3_prompt(b_list, paras, pidx)
        (inputs_dir / f"call3_{depth_label}_prompt.txt").write_text(p3, encoding="utf-8")
        raw3, t3, ttft3, fin3 = call_api(p3, model, api_key, base_url)
        cleaned3 = clean_json_output(raw3)
        (inter_dir / f"B_{depth_label}_raw.txt").write_text(raw3, encoding="utf-8")
        try:
            arr = json.loads(cleaned3)
            for it in arr:
                b_claims[it["id"]] = it["claim"]
            (inter_dir / f"B_{depth_label}_claims.json").write_text(
                json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    {depth_label} OK  解析={len(arr)} 条  用时={t3:.1f}s")
            ok3 = True
        except Exception as e:
            print(f"    {depth_label} 解析失败: {e}")
            (inter_dir / f"B_{depth_label}_claims.json").write_text(cleaned3, encoding="utf-8")
            ok3 = False
        meta["calls"][f"call3_B_{depth_label}"] = {
            "elapsed_sec": round(t3, 2), "ttft_sec": round(ttft3, 2),
            "raw_chars": len(raw3), "parsed": ok3,
            "node_count": len(b_list), "finish_reason": fin3,
        }
    (inter_dir / "B_claims.json").write_text(
        json.dumps([{"id": k, "claim": v} for k, v in b_claims.items()], ensure_ascii=False, indent=2),
        encoding="utf-8")

    # -------- 调用④：A 级 --------
    print(f"  [调用④ A 级] 节点数={len(A_defs)}")
    p4 = build_call4_prompt(A_defs, paras, pidx)
    (inputs_dir / "call4_prompt.txt").write_text(p4, encoding="utf-8")
    raw4, t4, ttft4, fin4 = call_api(p4, model, api_key, base_url)
    cleaned4 = clean_json_output(raw4)
    (inter_dir / "A_claims_raw.txt").write_text(raw4, encoding="utf-8")
    a_claims = {}
    try:
        arr4 = json.loads(cleaned4)
        for it in arr4:
            a_claims[it["id"]] = it["claim"]
        (inter_dir / "A_claims.json").write_text(
            json.dumps(arr4, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    A 解析 OK  条数={len(arr4)}  用时={t4:.1f}s")
        ok4 = True
    except Exception as e:
        print(f"    A 解析失败: {e}")
        (inter_dir / "A_claims.json").write_text(cleaned4, encoding="utf-8")
        ok4 = False
    meta["calls"]["call4_A"] = {
        "elapsed_sec": round(t4, 2), "ttft_sec": round(ttft4, 2),
        "raw_chars": len(raw4), "parsed": ok4,
        "node_count": len(A_defs), "finish_reason": fin4,
    }

    # -------- 组装 run.json --------
    print("  [组装 run.json]")
    # 校验并排序 C
    enr = []
    for i, c in enumerate(c_level):
        par, anc, txt, srcs = c.get("parent"), c.get("anchor"), c.get("text", ""), c.get("sources", [])
        if par not in {n["id"] for n in A_defs + B_defs_all}:
            print(f"    跳过 C: parent 不存在 {par}  text={txt[:30]}")
            continue
        if anc not in valid_P:
            print(f"    跳过 C: anchor 非法 {anc}  text={txt[:30]}")
            continue
        srcs = [m for m in srcs if m in valid_M]
        enr.append((pidx[par], pidx[anc], i, par, anc, txt, srcs))
    enr.sort(key=lambda x: (x[0], x[1], x[2]))

    parent_order = {n["id"]: pidx[n["title_pid"]] for n in A_defs + B_defs_all}
    counters, C = {}, []
    for _, _, _, par, anc, txt, srcs in enr:
        counters[par] = counters.get(par, 0) + 1
        C.append({"id": c_id_for(par, counters[par]), "anchor": anc,
                  "text": txt, "sources": sorted(srcs, key=m_key), "parent": par})

    def span_pair(sp):
        return [sp[0], sp[1] if sp and len(sp) > 1 and sp[1] else sp[0]] if sp and sp[0] else [None, None]

    B_out = []
    for b in sorted(B_defs_all, key=lambda x: pidx[x["title_pid"]]):
        ms = union_sources(descendants(b["id"], A_defs, B_defs_all, C))
        B_out.append({
            "id": b["id"], "depth": b["depth"], "title_label": b["title_label"],
            "claim": b_claims.get(b["id"], ""), "span": span_pair(b["span"]),
            "sources": sorted(ms, key=m_key), "source_count": len(ms),
            "supported": None, "supported_by": [], "parent": b.get("parent"),
        })

    A_out = []
    for a in sorted(A_defs, key=lambda x: (x["order"] if x["order"] is not None else -1)):
        ms = union_sources(descendants(a["id"], A_defs, B_defs_all, C))
        is_a0 = a["id"] == "A0"
        if is_a0:
            ms = set(valid_M)  # A0 = 全文 M 并集
        A_out.append({
            "id": a["id"], "depth": a["depth"], "title_label": a["title_label"],
            "claim": a_claims.get(a["id"], ""), "span": span_pair(a["span"]),
            "sources": sorted(ms, key=m_key), "source_count": len(ms),
            "supported": None, "supported_by": [], "parent": None,
        })

    # 段落清单
    all_used_M = set()
    for c in C:
        all_used_M |= set(c["sources"])
    paragraphs_out = [{
        "id": p["id"], "type": p["type"], "text": p["text"],
        "material_refs": p.get("material_refs", []), "page": p.get("page", "1"),
    } for p in paras]
    materials_out = [{"id": m["id"], "text": m.get("text", ""),
                      "footnote_number": m.get("footnote_number"),
                      "source_full": m.get("source_full", "")} for m in materials]

    run = {
        "meta": {
            "paper_title": paras[0]["text"] if paras and paras[0].get("type") == "title" else run_name,
            "encoding_scheme": "A-B-C-M hierarchical encoding",
            "version": "3.2",
            "run_name": run_name, "model": model,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Q_A 实验：v3.2 自动五调用抽取（跳过⑤支持核查，supported 留 null）",
        },
        "encoding_table": {
            "A_level": A_out,  # 含 A0 在内
            "B_level": B_out,
            "C_level": C,
            "M_level": materials_out,
        },
        "paragraphs": paragraphs_out,
        "front_matter": sk["front_matter"],
        "statistics": {
            "nodes_by_depth": {
                "A0": 1, "A": len(A_out) - (1 if any(a["id"] == "A0" for a in A_out) else 0),
                "B": len(B_out), "B_depth2": len(B_depth2), "B_depth3": len(B_depth3),
                "C": len(C),
            },
            "total_nodes": 1 + len(A_out) + len(B_out) + len(C),
            "claims": {"A_count": len(A_out), "B_count": len(B_out), "C_count": len(C),
                       "claims_with_text": sum(1 for a in A_out if a["claim"]) +
                       sum(1 for b in B_out if b["claim"]) + len(C)},
            "M": {"total": len(materials), "used": len(all_used_M),
                  "unused": sorted(valid_M - all_used_M, key=m_key)},
        },
    }
    run_path = run_dir / "run.json"
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[完成] {run_name}")
    print(f"  A={len(A_out)} (含A0)  B={len(B_out)}  C={len(C)}")
    print(f"  M 使用: {len(all_used_M)}/{len(materials)} = {len(all_used_M)/len(materials)*100:.1f}%")
    print(f"  run.json: {run_path}")
    print(f"  meta.json: {run_dir / 'meta.json'}")


if __name__ == "__main__":
    main()
