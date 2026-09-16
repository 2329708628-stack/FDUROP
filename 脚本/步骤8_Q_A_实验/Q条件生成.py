# -*- coding: utf-8 -*-
"""Q/A 实验：Q 条件——基于史料（S）由大模型生成论文。

Q/A 实验条件的唯一差异为前置指令：
  Q 组：基于以下史料，分析 X 与 Y 的关系
  A 组：论证以下观点，使用给定史料支撑
本脚本为 Q 组：把 source_pool.json 的全部 passages 喂给模型，
让其围绕指定问题（默认 A01 的"北宋湖北茶叶经济贸易的情况、原因和影响"）生成论文。

用法：
  python 脚本/步骤8_Q_A_实验/Q条件生成.py [论文目录(默认 A01_湖北茶叶经济)] [run号(默认 1)] [问题(默认见 DEFAULT_Q)]
产物写入 <论文目录>/03_实验输出/Q_A_实验/Q_run_<n>/：
  输入_prompt.txt    完整 prompt
  生成_论文.md       模型输出
  meta.json          模型/温度/时间/token 等
"""
import json, os, sys, time, datetime
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
# .venv 是空的，但 .pylibs 提供了 requests；统一加进 sys.path
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


def build_prompt(S_block, question):
    """Q 条件 prompt：分析 X 与 Y 的关系。强化版——强制多级标题、字数下限、SRC 引用下限。"""
    # 把 question 切成三部分供章节标题使用
    parts = question.replace("的情况", "/情况").replace("的原因", "/原因").replace("和影响", "/影响").split("/")
    sec1 = parts[0] if len(parts) > 0 else "情况"
    sec2 = parts[1] if len(parts) > 1 else "原因"
    sec3 = parts[2] if len(parts) > 2 else "影响"
    return f"""你是一位宋代经济史学者，请基于以下史料池，分析{question}。

【硬性要求——必须全部满足】
1. 严格依据所给史料展开论证，不得引入额外史料或现代学术观点；若史料不足以下结论，请显式说明"史料不足，难以判断"。
2. 论文必须采用三级标题结构（用于后续结构化抽取）：
   - 一级标题形如：一、xxxx；二、xxxx；三、xxxx（共三大部分，如下）
   - 每个一级标题下必须有 2-4 个二级标题，形如：(一)、(二)、(三)……
   - 每个二级标题下可有 1-3 个三级标题，形如：1.、2.、3.……
   - 章节固定为：一、{sec1}；二、{sec2}；三、{sec3}
3. 必须引用至少 15 条不同的 SRC 史料编号（形如 [SRC_001_P01]、[SRC_002_P01] 等），且每条引用与论点直接相关；不得集中堆在同一段。
4. 正文字数不少于 4000 字（中文），不含标题与编号标记；目标 5000 字。
5. 输出格式：纯文本（不要 markdown 代码块标记 ```），章节标题独占一行。
6. 不要在论文之外输出任何说明、注释、meta 信息或重述提示词。

【史料池（S）】
{S_block}

请直接从论文标题（独占一行，不含"标题:"前缀）开始撰写。
"""


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


def main():
    paper_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else LAB / "A01_湖北茶叶经济"
    run_no = sys.argv[2] if len(sys.argv) > 2 else "1"
    question = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_Q

    sp_path = paper_dir / "02_史料池" / "source_pool.json"
    if not sp_path.exists():
        sys.exit(f"找不到史料池: {sp_path}")
    source_pool = json.loads(sp_path.read_text(encoding="utf-8"))
    S_block = build_S_block(source_pool)
    prompt = build_prompt(S_block, question)

    out_dir = paper_dir / "03_实验输出" / "Q_A_实验" / f"Q_run_{run_no}"
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
    print(f"prompt 字符数={len(prompt)}  史料源数={len(source_pool['sources'])}  passages={source_pool['statistics']['total_passages']}")
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
            if not raw:
                continue
            if not raw.startswith("data:"):
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
    full = "".join(chunks)
    print()
    print(f"\n[完成] 用时={elapsed:.1f}s  首token={ttft:.2f}s  输出字符={len(full)}  finish={finish_reason}")

    (out_dir / "生成_论文.md").write_text(full, encoding="utf-8")

    meta = {
        "experiment": "Q_A",
        "condition": "Q",
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
        "output_chars": len(full),
        "elapsed_sec": round(elapsed, 2),
        "time_to_first_token_sec": round(ttft, 2),
        "finish_reason": finish_reason,
        "usage": usage,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"meta 已保存: {out_dir / 'meta.json'}")


if __name__ == "__main__":
    main()
