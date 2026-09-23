# -*- coding: utf-8 -*-
"""论证树一次性抽取：整篇一次调用 LLM，自下而上提取论证树（只留论点，剔除论据）。

替代 v3.2 五调用抽取 + 逐段论点压缩：一篇论文只调一次 API（deepseek-chat, temp=0）。

层级约定（与 v3.2 一致，供下游 _试点_新管线.py / _批量判定对照.py 复用）：
  A：全文唯一结论节点（结语段归纳），depth=1
  B：章节节点（一、二、三…），depth=2（由 derive_skeleton 确定性推导，id 固定）
  C：段落主张（每正文段至多 1 条，只留作者评价判断，剔除史料/律文/价格/数据）

用法：
  python _论证树一次性抽取.py <run 目录名> [论文目录(默认 A05)] [--overwrite]
    <run 目录> = 数据集/数据清洗后论文/<论文>/03_实验输出/Q_A_实验/<run 目录名>
    默认写出 <run>/run_论证树.json（不覆盖旧 run.json）；加 --overwrite 才写 run.json
"""
import json, os, sys, time, datetime, re, shutil
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
sys.path.insert(0, str(LAB / ".pylibs"))
import requests

sys.path.insert(0, str(LAB / "脚本" / "步骤3_v3.2抽取"))
from 公共库 import load_paper, derive_skeleton, m_key, c_id_for, descendants, union_sources, para_in_span

API_FILE = LAB / "API.txt"
MODEL = "deepseek-chat"
TEMPERATURE = 0.0
MAX_TOKENS = 8192


def read_api():
    lines = [l.strip() for l in API_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines[0], lines[1]


def chat(prompt, max_retries=5):
    key, base = read_api()
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": MODEL, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }
    last = None
    for i in range(max_retries + 1):
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                              json=payload, timeout=900)
        except requests.exceptions.RequestException as e:
            last = e
            time.sleep(10 * (i + 1))
            continue
        if r.status_code == 429:
            time.sleep(30 * (i + 1))
            continue
        if r.status_code != 200:
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            time.sleep(10 * (i + 1))
            continue
        j = r.json()
        txt = j["choices"][0]["message"]["content"]
        return txt, None, j.get("usage") or {}
    return None, str(last), {}


def clean_json(raw):
    s = (raw or "").strip()
    i = s.find("{")
    j = s.rfind("}")
    if i >= 0 and j > i:
        return s[i:j + 1]
    return s


def build_prompt(paras, A_defs, B_defs, front_matter, pidx):
    # 段落分组：按最深层 B 归属，把章节标题与正文段组织成树
    text_paras = [p for p in paras if p.get("type") == "text"]

    b_lines = []
    for b in B_defs:
        b_lines.append(f"{b['id']} [锚点：{b['title_label']}] depth={b['depth']} parent={b.get('parent')}")

    a_lines = []
    for a in A_defs:
        a_lines.append(f"{a['id']} [锚点：{a['title_label']}] span={a.get('span')}")

    p_lines = []
    for p in text_paras:
        pm = ",".join(p.get("material_refs", []))
        p_lines.append(f"{p['id']}（refs:{pm or '无'}）: {p['text']}")

    return f"""你是历史学论文论证结构形式化编码器。请对全文一次性提取论证树：自下而上归纳，只保留「论点」，剔除一切「论据」。

【核心原则】
1. 小标题只作结构锚点，用于固定层级，不直接当论点。
2. 每个结构单元（各节、各正文段）都要另行归纳一句「该单元论点」。
3. 归纳路径自下而上：先概括每个正文段的核心论点(C)；将同一节内各段论点归纳为该节论点(B)；将各节论点归纳为全文核心结论(A/总论点)。
4. 纯论据/史料/律文/数据/过渡段不单独成节点，其内容归入支撑它的上级论点。

【论据剔除——绝对禁止写进论点】
例子、案例、事件、数字、价格、数量、统计、引文、诗文、书名、篇名、人物、地名、官职、朝代年号、法律条文原文，以及"如/例如/据统计/记载/XX云/XX曰"引导的内容，一律剔除。
特别强调：
- 法律条文的照抄或复述（如"笞三十""杖一百""立市券""价定立券""听悔"等）是史料(M)，不是论点，禁止写进 C。
- 价格数字（如"每匹二十贯""一头5贯""每斤百三十文""十二贯""三点九贯"）是史料(M)，不是论点，禁止写进 C。
- 只有作者自己的评价判断（如"…有利于规范市场""…反映官府管理成熟""…价格浮动较大""…推动贸易繁荣"）才是论点。

【层级与编号约束】
- C = 段落主张：每个正文段至多 1 条；若该段纯为论据/史料/律文/价格罗列/过渡，则不产出 C（跳过该段，不出 anchor）。
- B = 章节论点：对每个给出的 B 节点归纳恰好 1 条，id 必须与输入 B 节点 id 逐字一致。
- A = 全文核心结论：由结语段（及全文）归纳，id = A1。

【写法要求】
- 论点须是可独立判断的陈述句，20~60 字，主谓宾完整。
- 直接写论点，不用"作者认为""本文指出"开头；不照抄小标题；不解释、不评价、不添加原文没有的观点。
- C 的 text 只保留作者判断，删掉该段内的数字、价格、律文、引文、例证。

【输入：层级锚点】
A 节点：
{chr(10).join(a_lines) if a_lines else '（无）'}

B 节点：
{chr(10).join(b_lines) if b_lines else '（无）'}

前置段 front_matter（不属于任何 B），可跳过或按语义归入首章：
{", ".join(front_matter) if front_matter else "（无）"}

【输入：正文段】
{chr(10).join(p_lines)}

【输出 JSON（只输出一个 JSON 对象，不要 markdown 代码块、不要说明文字）】
{{
  "A_claim": "全文核心结论",
  "B_claims": [{{"id": "B1", "claim": "..."}}, ...],
  "C_claims": [{{"anchor": "P6", "text": "..."}}, ...]
}}
规则：B_claims 覆盖输入的全部 B 节点（id 原样）；C_claims 只列出确有论点的段落（anchor 用 P 编号，text 只留论点）。
"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("用法：python _论证树一次性抽取.py <run 目录名> [论文目录(默认 A05)] [--overwrite]")
    run_name = args[0]
    paper_dir = Path(args[1]) if len(args) > 1 else (LAB / "数据集/数据清洗后论文/A05")
    overwrite = "--overwrite" in sys.argv
    run_dir = paper_dir / "03_实验输出" / "Q_A_实验" / run_name

    paras, materials, _ = load_paper(run_dir)
    valid_M = {m["id"] for m in materials}
    sk = derive_skeleton(paras)
    pidx = sk["para_index"]
    A_defs = sk["A"]
    B_defs = sk["B"]
    front = sk["front_matter"]

    print(f"[{run_name}] 段落={len(paras)}  M={len(materials)}  A={len(A_defs)}  B={len(B_defs)}  front={front}", flush=True)

    prompt = build_prompt(paras, A_defs, B_defs, front, pidx)
    prompt_path = run_dir / "_论证树_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"  prompt 字符数={len(prompt)}", flush=True)

    raw, err, usage = chat(prompt)
    if err:
        print(f"  API 失败：{err}", flush=True)
        return
    raw_path = run_dir / "_论证树_raw.txt"
    raw_path.write_text(raw, encoding="utf-8")
    print(f"  原始输出字符={len(raw)}  usage={usage}", flush=True)

    cleaned = clean_json(raw)
    try:
        obj = json.loads(cleaned)
    except Exception as e:
        print(f"  JSON 解析失败：{e}", flush=True)
        print(f"  （原始已存 {raw_path}）", flush=True)
        return

    a_claim = obj.get("A_claim", "")
    b_map = {it["id"]: it.get("claim", "") for it in obj.get("B_claims", [])}
    c_list = obj.get("C_claims", [])

    # ---- 组装 C 节点：parent 确定性指派 + 编号 ----
    valid_P = {p["id"] for p in paras}
    concl_pid = None
    for a in A_defs:
        if a.get("derived_from_para"):
            concl_pid = a["derived_from_para"]
        elif a.get("span") and a["span"][0]:
            concl_pid = a["span"][0]

    def assign_parent(anchor):
        for a in A_defs:
            if para_in_span(anchor, a.get("span"), pidx):
                return a["id"]
        best = None
        for b in B_defs:
            if para_in_span(anchor, b.get("span"), pidx):
                if best is None or b["depth"] > best["depth"]:
                    best = b
        if best:
            return best["id"]
        if anchor in front:
            return B_defs[0]["id"] if B_defs else (A_defs[0]["id"] if A_defs else None)
        return None

    seen = set()
    C = []
    for c in c_list:
        anc = c.get("anchor")
        txt = (c.get("text") or "").strip()
        if not anc or anc not in valid_P or not txt:
            continue
        if anc in seen:
            print(f"  跳过重复 anchor：{anc}", flush=True)
            continue
        seen.add(anc)
        par = assign_parent(anc)
        if par is None:
            print(f"  跳过 C：无法归属 {anc}  text={txt[:30]}", flush=True)
            continue
        srcs = [m for m in paras[pidx[anc]].get("material_refs", []) if m in valid_M]
        C.append({"anchor": anc, "text": txt, "parent": par, "sources": srcs})

    # 编号（按 parent 标题位置 + anchor 页序）
    def node_pos(nid):
        for n in A_defs + B_defs:
            if n["id"] == nid:
                if n.get("title_pid"):
                    return pidx[n["title_pid"]]
                if n.get("derived_from_para"):
                    return pidx[n["derived_from_para"]]
        if nid in front:
            return pidx.get(nid, 1 << 30)
        return 1 << 30

    C.sort(key=lambda x: (node_pos(x["parent"]), pidx[x["anchor"]]))
    chapter_count = max([int(m.group(1)) for m in
                         (re.match(r"B(\d+)", b["id"]) for b in B_defs) if m] or [0])
    counters = {}
    C_out = []
    for c in C:
        counters[c["parent"]] = counters.get(c["parent"], 0) + 1
        C_out.append({"id": c_id_for(c["parent"], counters[c["parent"]], chapter_count),
                      "anchor": c["anchor"], "text": c["text"],
                      "sources": sorted(c["sources"], key=m_key), "parent": c["parent"]})

    def span_pair(sp):
        return [sp[0], sp[1] if sp and len(sp) > 1 and sp[1] else sp[0]] if sp and sp[0] else [None, None]

    B_out = []
    for b in sorted(B_defs, key=lambda x: pidx[x["title_pid"]]):
        ms = union_sources(descendants(b["id"], A_defs, B_defs, C_out))
        B_out.append({
            "id": b["id"], "depth": b["depth"], "title_label": b["title_label"],
            "claim": b_map.get(b["id"], ""), "span": span_pair(b["span"]),
            "sources": sorted(ms, key=m_key), "source_count": len(ms),
            "supported": None, "supported_by": [], "parent": b.get("parent"),
        })

    A_out = []
    for a in sorted(A_defs, key=lambda x: (x["order"] if x["order"] is not None else -1)):
        if len(A_defs) == 1:
            ms = set(valid_M)
        else:
            ms = union_sources(descendants(a["id"], A_defs, B_defs, C_out))
        A_out.append({
            "id": a["id"], "depth": a["depth"], "title_label": a["title_label"],
            "claim": a_claim, "span": span_pair(a["span"]),
            "sources": sorted(ms, key=m_key), "source_count": len(ms),
            "supported": None, "supported_by": [], "parent": None,
        })

    all_used_M = set()
    for c in C_out:
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
            "version": "3.2-once",
            "run_name": run_name, "model": MODEL,
            "temperature": TEMPERATURE,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "论证树一次性抽取（整篇一次调用，只留论点剔除论据；sources 由 anchor 段 material_refs 确定性绑定）",
        },
        "encoding_table": {
            "A_level": A_out,
            "B_level": B_out,
            "C_level": C_out,
            "M_level": materials_out,
        },
        "paragraphs": paragraphs_out,
        "front_matter": front,
        "statistics": {
            "total_A_nodes": len(A_out),
            "total_B_nodes": len(B_out),
            "total_C_nodes": len(C_out),
            "total_unique_M": len(materials),
            "nodes_by_depth": {str(d): (
                len(A_out) if d == 1 else sum(1 for b in B_out if b["depth"] == d))
                for d in range(1, max([1] + [b["depth"] for b in B_out]) + 1)},
            "source_count_by_A": {a["id"]: a["source_count"] for a in A_out},
            "source_count_by_B": {b["id"]: b["source_count"] for b in B_out},
            "C_nodes_without_sources": sum(1 for c in C_out if not c["sources"]),
            "claims_total": len(A_out) + len(B_out),
            "M": {"total": len(materials), "used": len(all_used_M),
                  "unused": sorted(valid_M - all_used_M, key=m_key)},
        },
    }

    out_path = run_dir / ("run.json" if overwrite else "run_论证树.json")
    if overwrite and out_path.exists():
        bak = run_dir / "run_v3.2_backup.json"
        shutil.copyfile(out_path, bak)
        print(f"  已备份旧 run.json → {bak}", flush=True)
    out_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[完成] {run_name}  A={len(A_out)}  B={len(B_out)}  C={len(C_out)}", flush=True)
    print(f"  M 使用: {len(all_used_M)}/{len(materials)} = {len(all_used_M)/len(materials)*100:.1f}%", flush=True)
    print(f"  输出: {out_path}", flush=True)
    print(f"  已跳过段落（纯论据/无论点）：{[p for p in valid_P if p not in seen and p not in {concl_pid or ''} and p != 'P3']}", flush=True)


if __name__ == "__main__":
    main()