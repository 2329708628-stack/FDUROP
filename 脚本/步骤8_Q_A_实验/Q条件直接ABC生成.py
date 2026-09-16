# -*- coding: utf-8 -*-
"""Q/A 实验：路线 1——Q 条件下让大模型直接生成 v3.2 schema 的 ABC 论证树。

与路线 2（先生成论文 → 再走 v3.2 抽取）并行对比。
S（史料池）作为唯一外部输入，模型一次调用产出完整 ABC JSON。

由于没有原始论文段落，anchor 字段约定使用 SRC passage_id（即 SRC_xxx_Pyy），
表示该 C 节点的论证依据来自哪条史料段；这与人类基准 A01 用 P 段号做 anchor
在语义上有差异（路线 1 是"史料级锚定"，路线 2/人类基准是"段落级锚定"），
对比时需注意。

用法：
  python 脚本/步骤8_Q_A_实验/Q条件直接ABC生成.py [论文目录(默认 A01_湖北茶叶经济)] [run号(默认 1)] [问题(默认见 DEFAULT_Q)]
产物写入 <论文目录>/03_实验输出/Q_A_实验/Q_direct_run_<n>/：
  输入_prompt.txt     完整 prompt
  生成_ABC.json       模型原始输出（清理后）
  meta.json           模型/温度/时间/输出字符等
"""
import json, os, sys, time, datetime, re
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
_pylibs = str(LAB / ".pylibs")
if _pylibs not in sys.path:
    sys.path.insert(0, _pylibs)
import requests

API_FILE = LAB / "API.txt"
DEFAULT_Q = "北宋时期湖北地区茶叶经济贸易的情况、原因和影响"
MODEL = "GLM-4.5-Flash"
TEMPERATURE = 0.7
MAX_TOKENS = 16384


def read_api():
    lines = [l.strip() for l in API_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines[0], lines[1]


def build_S_block(source_pool):
    """把 source_pool.json 的 passages 平铺成编号文本块。"""
    lines = []
    for src in source_pool["sources"]:
        title = src.get("title", "")
        dynasty = src.get("dynasty", "")
        for p in src["passages"]:
            pid = p["passage_id"]
            mid = p.get("original_id", "")
            text = p.get("text", "").strip()
            cite = p.get("source_full", "")
            vol = p.get("volume", "")
            vol_part = f" 卷{vol}" if vol else ""
            head = f"[{pid}]" + (f"（原 {mid}）" if mid else "")
            lines.append(f"{head} 《{title}》{dynasty}{vol_part}")
            lines.append(f"原文：{text}")
            lines.append(f"出处：{cite}")
            lines.append("")
    return "\n".join(lines)


def build_prompt(S_block, question, all_src_ids):
    """直接 ABC 生成 prompt——v3.2 schema。"""
    src_id_list = ", ".join(all_src_ids)
    return f"""你是一位历史学论文论证结构形式化编码器。请基于以下史料池（S），针对研究问题"{question}"，
直接生成符合 v3.2 协议的论证结构 JSON。不要写论文，只输出结构化论证树。

【v3.2 协议要点】
- 三级节点：A（核心命题）、B（章节命题）、C（具体主张）
- A0 为全文总命题，A1-An 为各章核心命题
- 每个 A 节点：claim（30-80 字命题）+ supported_by（直接子 B 节点 id 列表）
- 每个 B 节点：title_label（章节标题）、claim（30-80 字章节命题）、depth（=2）、
  supported_by（直接子 C 节点 id 列表）
- 每个 C 节点：parent（所属 B id）、anchor（SRC passage_id）、
  text（30-80 字具体主张）、sources（SRC passage_id 列表）
- A0 的 supported_by 列出所有 A_i 节点 id

【输出 JSON schema（严格遵循）】
{{
  "meta": {{
    "version": "3.2",
    "paper_id": "A01_Q_direct",
    "condition": "Q_direct",
    "question": "{question}"
  }},
  "A0": {{"claim": "...", "supported_by": ["A1", "A2", "A3"]}},
  "A": [
    {{"id": "A1", "claim": "...", "supported_by": ["B1.1", "B1.2"]}}
  ],
  "B": [
    {{"id": "B1.1", "title_label": "...", "claim": "...", "depth": 2, "supported_by": ["C1.1.1", "C1.1.2"]}}
  ],
  "C": [
    {{"id": "C1.1.1", "parent": "B1.1", "anchor": "SRC_xxx_Pyy", "text": "...", "sources": ["SRC_xxx_Pyy"]}}
  ]
}}

【硬性要求——必须全部满足】
1. 至少 3 个 A 节点（A1, A2, A3）+ 1 个 A0；至少 6 个 B 节点；至少 20 个 C 节点。
2. 章节结构对应三大部分：A1=情况、A2=原因、A3=影响；其下 B 节点 title_label 必须包含相应的子主题。
3. 每个 C 节点 sources 必须从下方史料池中存在的 SRC 编号中选取，不得虚构。
   可用的 SRC 编号清单：{src_id_list}
4. anchor 字段填该 C 主要依据的 SRC passage_id（与 sources 的第一个元素一致即可）。
5. C 节点 id 按"章节 B 顺序 → 段内顺序"连续编号（C1.1.1, C1.1.2, C1.1.3, ..., C1.2.1, ...）。
6. A/B/C 的 supported_by 必须列出所有直接子节点 id，子节点 id 必须真实存在于对应数组中。
7. 仅输出符合 schema 的纯 JSON，不要任何 markdown 代码块标记、不要说明文字、不要前后缀。

【史料池（S）】
{S_block}

请直接输出 JSON：
"""


def clean_json_output(raw):
    """模型有时仍会包 ```json ... ``` 或前后多余文本，做一次容错清理。"""
    s = raw.strip()
    # 去 markdown 代码块
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    # 截取第一个 { 到最后一个 }
    i = s.find("{")
    j = s.rfind("}")
    if i >= 0 and j > i:
        s = s[i:j + 1]
    return s


def main():
    paper_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else LAB / "A01_湖北茶叶经济"
    run_no = sys.argv[2] if len(sys.argv) > 2 else "1"
    question = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_Q

    sp_path = paper_dir / "02_史料池" / "source_pool.json"
    if not sp_path.exists():
        sys.exit(f"找不到史料池: {sp_path}")
    source_pool = json.loads(sp_path.read_text(encoding="utf-8"))
    S_block = build_S_block(source_pool)
    all_src_ids = [p["passage_id"] for s in source_pool["sources"] for p in s["passages"]]
    prompt = build_prompt(S_block, question, all_src_ids)

    out_dir = paper_dir / "03_实验输出" / "Q_A_实验" / f"Q_direct_run_{run_no}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "输入_prompt.txt").write_text(prompt, encoding="utf-8")

    api_key, base_url = read_api()
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }

    print(f"模型={MODEL}  温度={TEMPERATURE}  最大输出={MAX_TOKENS}")
    print(f"prompt 字符数={len(prompt)}  可用 SRC 编号数={len(all_src_ids)}")
    print(f"输出目录={out_dir}")
    print(f"API={url}")
    print("开始流式生成...")

    t0 = time.time()
    chunks = []
    first_token_t = None
    finish_reason = None
    usage = None
    with requests.post(url, headers=headers, json=payload, stream=True, timeout=600) as r:
        if r.status_code != 200:
            sys.exit(f"HTTP {r.status_code}: {r.text[:500]}")
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
            if usage is None and obj.get("usage"):
                usage = obj["usage"]
            try:
                choice = obj["choices"][0]
            except (KeyError, IndexError):
                continue
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]
            piece = choice.get("delta", {}).get("content", "") or ""
            if piece:
                if first_token_t is None:
                    first_token_t = time.time()
                chunks.append(piece)
                sys.stdout.write(piece)
                sys.stdout.flush()
    elapsed = time.time() - t0
    ttft = (first_token_t - t0) if first_token_t else 0.0
    raw_full = "".join(chunks)
    print()
    print(f"\n[原始输出字符数={len(raw_full)}]  finish={finish_reason}")

    cleaned = clean_json_output(raw_full)
    (out_dir / "生成_ABC_raw.txt").write_text(raw_full, encoding="utf-8")
    parse_ok = False
    parse_err = None
    parsed = None
    try:
        parsed = json.loads(cleaned)
        parse_ok = True
    except Exception as e:
        parse_err = str(e)
    if parse_ok:
        (out_dir / "生成_ABC.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        stats = {
            "A_count": len(parsed.get("A", [])),
            "B_count": len(parsed.get("B", [])),
            "C_count": len(parsed.get("C", [])),
            "src_used": len({sid for c in parsed.get("C", []) for sid in c.get("sources", [])}),
        }
        print(f"[JSON 解析 OK]  A={stats['A_count']}  B={stats['B_count']}  C={stats['C_count']}  使用过的 SRC={stats['src_used']}/{len(all_src_ids)}")
    else:
        print(f"[JSON 解析失败]  {parse_err}")
        (out_dir / "生成_ABC.json").write_text(cleaned, encoding="utf-8")

    meta = {
        "experiment": "Q_A",
        "condition": "Q_direct",
        "route": 1,
        "paper_id": paper_dir.name.split("_")[0],
        "run_no": run_no,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "question": question,
        "prompt_chars": len(prompt),
        "source_pool": {
            "total_sources": source_pool["statistics"]["total_sources"],
            "total_passages": source_pool["statistics"]["total_passages"],
            "S_block_chars": len(S_block),
        },
        "raw_output_chars": len(raw_full),
        "cleaned_output_chars": len(cleaned),
        "json_parsed": parse_ok,
        "parse_error": parse_err,
        "elapsed_sec": round(elapsed, 2),
        "time_to_first_token_sec": round(ttft, 2),
        "finish_reason": finish_reason,
        "usage": usage,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if parse_ok and parsed:
        meta["stats"] = stats
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"meta 已保存: {out_dir / 'meta.json'}")


if __name__ == "__main__":
    main()
