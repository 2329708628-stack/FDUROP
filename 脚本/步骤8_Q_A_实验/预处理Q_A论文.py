# -*- coding: utf-8 -*-
"""Q_A 实验：把生成论文 .md 转成 v3.2 协议要的 原文_clean.json。

输入：
  <论文目录>/03_实验输出/Q_A_实验/Q_<run_name>/生成_论文.md
输出：
  <论文目录>/03_实验输出/Q_A_实验/Q_<run_name>/00_原文/原文_clean.json
  段落结构：paragraphs (id=P1.., type=title|text, text, material_refs, page)
  史料清单：materials (id=M1..M52, text, source_full) — 来自 02_史料池/source_pool.json
  M 编号按 source_pool.json passages 顺序重排（M1=第1条 passage，M52=第52条），
  把机器产物里的 SRC_xxx_Pyy 也按此顺序映射回 M_i，便于统一对照。

用法：python 脚本/步骤8_Q_A_实验/预处理Q_A论文.py <Q_run 目录> [论文目录(默认 A01_湖北茶叶经济)]
"""
import json, re, sys, shutil
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
sys.path.insert(0, str(LAB / "脚本" / "步骤3_v3.2抽取"))
from 公共库 import CN, RE_H1_NUM, RE_H2, RE_H3, RE_SPECIAL, RE_YEAR


def build_S_index(source_pool):
    """以 original_id 字段为 M 编号（用户人类基准就是按 original_id 标记的）。
    返回 (materials_list, src2m {passage_id -> "M<original_id数字>"})。"""
    materials = []
    src2m = {}
    for s in source_pool["sources"]:
        for p in s["passages"]:
            oid = p.get("original_id", "")
            if not oid.startswith("M"):
                continue
            mid = oid  # 直接用 original_id 作为 M 编号
            materials.append({
                "id": mid,
                "text": p.get("text", ""),
                "source_full": p.get("source_full", ""),
                "footnote_number": int(oid[1:]),
                "src_passage_id": p["passage_id"],
            })
            src2m[p["passage_id"]] = mid
    # 按 M 编号排序
    materials.sort(key=lambda m: int(m["id"][1:]))
    return materials, src2m


def parse_paragraphs(md_text, src2m):
    """把 .md 文本解析成段落列表。
    人类基准已用 original_id (M1..M52) 标记，保留即可；
    机器产物用 SRC_xxx_Pyy，按 src2m 映射回 original_id。"""
    paras = []
    cur_buf = []
    pid = [0]

    def flush(buf):
        if not buf:
            return
        text = "\n".join(buf).strip()
        if not text:
            return
        pid[0] += 1
        p_id = "P%d" % pid[0]
        # 去 markdown 前缀 # 用于检测
        stripped = re.sub(r"^[\s#]+", "", text).strip()
        first_line = stripped.split("\n", 1)[0].strip()

        # 标题检测
        is_title = False
        title_text = None
        if RE_SPECIAL.match(first_line) or RE_H1_NUM.match(first_line):
            is_title = True
            title_text = first_line
        elif RE_H2.match(first_line):
            is_title = True
            title_text = first_line
        elif RE_H3.match(first_line) and not RE_YEAR.match(first_line):
            is_title = True
            title_text = first_line

        if is_title:
            paras.append({
                "id": p_id, "type": "title", "text": title_text,
                "material_refs": [], "page": "1",
            })
        else:
            body = stripped
            # SRC_xxx_Pyy → original_id (M<数字>)
            def repl(m):
                sid = m.group(0)
                return src2m.get(sid, sid)
            body = re.sub(r"SRC_\d+_P\d+", repl, body)
            # 提取 M 引用（按数字大小排序）
            refs = sorted(set(re.findall(r"M\d+", body)), key=lambda x: int(x[1:]))
            paras.append({
                "id": p_id, "type": "text", "text": body,
                "material_refs": refs, "page": "1",
            })

    for line in md_text.split("\n"):
        s = line.rstrip()
        if not s.strip():
            flush(cur_buf)
            cur_buf = []
            continue
        cur_buf.append(s)
    flush(cur_buf)
    return paras


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python 预处理Q_A论文.py <Q_run 目录名> [论文目录]")
    run_name = sys.argv[1]
    paper_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else (LAB / "A01_湖北茶叶经济")
    run_dir = paper_dir / "03_实验输出" / "Q_A_实验" / run_name
    md_path = run_dir / "生成_论文.md"
    if not md_path.exists():
        sys.exit(f"找不到 {md_path}")

    sp_path = paper_dir / "02_史料池" / "source_pool.json"
    source_pool = json.loads(sp_path.read_text(encoding="utf-8"))
    materials, src2m = build_S_index(source_pool)

    md_text = md_path.read_text(encoding="utf-8")
    paragraphs = parse_paragraphs(md_text, src2m)

    # 写出 原文_clean.json
    out_dir = run_dir / "00_原文"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    clean_path = out_dir / "原文_clean.json"
    clean_path.write_text(json.dumps({
        "paragraphs": paragraphs,
        "materials": materials,
        "meta": {"source": run_name, "M_numbering": "original_id (M1..M52)"},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 统计
    n_title = sum(1 for p in paragraphs if p["type"] == "title")
    n_text = sum(1 for p in paragraphs if p["type"] == "text")
    n_with_refs = sum(1 for p in paragraphs if p["type"] == "text" and p["material_refs"])
    all_refs = set()
    for p in paragraphs:
        all_refs |= set(p["material_refs"])
    coverage = len(all_refs) / len(materials)

    print(f"[{run_name}]  段落={len(paragraphs)}  标题段={n_title}  正文段={n_text}  含M引用段={n_with_refs}")
    print(f"  史料覆盖：{len(all_refs)}/{len(materials)} = {coverage*100:.1f}%")
    print(f"  输出：{clean_path}")


if __name__ == "__main__":
    main()
