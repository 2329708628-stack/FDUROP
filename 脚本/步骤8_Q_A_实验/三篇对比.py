# -*- coding: utf-8 -*-
"""Q/A 实验：三篇（四产物）对比脚本。

对比对象：
  1. Q_run_1/生成_论文.md        — GLM-4-Flash 弱 prompt（v1，5 SRC 引用，1154 字）
  2. Q_run_2/生成_论文.md        — GLM-4.5-Flash 强 prompt（v2，6016 字）
  3. Q_human_baseline/生成_论文.md — 用户手工撰写的人类基准（M1—M52，全部调用）
  4. Q_direct_run_1/生成_ABC.json  — GLM-4.5-Flash 直接生成 v3.2 ABC（路线 1）

映射口径：
  - 人类基准用 M1—M52 标记，按 source_pool.json 的 passages 顺序对应（M1=第1条 passage，
    M2=第2条…）；这与 source_pool.json 自身的 original_id 字段是两套体系，
    本脚本明确使用 passage 顺序索引（positional index）做统一口径。
  - 机器产物用 SRC_xxx_Pyy 标记，直接对应 source_pool.json 的 passage_id 字段。
  - 两套口径统一映射到 0-51 的 passage 顺序索引，再算覆盖率。

用法：python 脚本/步骤8_Q_A_实验/三篇对比.py
"""
import json, re
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
EXP = LAB / "A01_湖北茶叶经济" / "03_实验输出" / "Q_A_实验"


def load_source_pool():
    sp = json.loads((LAB / "A01_湖北茶叶经济" / "02_史料池" / "source_pool.json").read_text(encoding="utf-8"))
    passages = []  # 顺序列表
    pid2idx = {}
    for s in sp["sources"]:
        for p in s["passages"]:
            idx = len(passages)  # 0-based
            pid = p["passage_id"]
            passages.append({"idx": idx, "pid": pid, "src_title": s.get("title", ""),
                              "text": p.get("text", ""), "original_id": p.get("original_id", "")})
            pid2idx[pid] = idx
    return sp, passages, pid2idx


def extract_m_refs(text):
    """提取 M\d+ 引用（人类基准用 M1—M52，按 passage 顺序对应）。"""
    refs = re.findall(r"M(\d+)", text)
    return sorted({int(r) for r in refs})


def extract_src_refs(text):
    """提取 SRC_xxx_Pyy 引用（机器产物用 passage_id）。"""
    refs = re.findall(r"SRC_\d+_P\d+", text)
    return sorted(set(refs))


def extract_section_headings(text):
    """提取一/二/三级标题计数（允许 markdown 的 # 前缀）。"""
    h1 = len(re.findall(r"(?m)^[\s#]*[一二三四五]、", text))
    h2 = len(re.findall(r"(?m)^[\s#]*[（(][一二三四五六七八九十]+[）)]", text))
    h3 = len(re.findall(r"(?m)^[\s#]*\d+[.、]", text))
    return h1, h2, h3


def char_count(text):
    # 去掉 markdown 标记后的字符数
    cleaned = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)  # 去标题行
    cleaned = re.sub(r"\s", "", cleaned)
    return len(cleaned)


def analyze_paper(name, path):
    text = Path(path).read_text(encoding="utf-8")
    h1, h2, h3 = extract_section_headings(text)
    m_refs = extract_m_refs(text)
    src_refs = extract_src_refs(text)
    return {
        "name": name,
        "path": str(path),
        "total_chars": len(text),
        "body_chars": char_count(text),
        "h1": h1, "h2": h2, "h3": h3,
        "m_refs": m_refs,
        "m_count": len(m_refs),
        "src_refs": src_refs,
        "src_count": len(src_refs),
    }


def analyze_abc(name, path):
    """对路线 1 直接 ABC 的产物做单独分析。"""
    j = json.loads(Path(path).read_text(encoding="utf-8"))
    A = j.get("A", [])
    B = j.get("B", [])
    C = j.get("C", [])
    src_used = set()
    for c in C:
        for s in c.get("sources", []):
            src_used.add(s)
    return {
        "name": name,
        "path": str(path),
        "A_count": len(A) + 1,  # +1 for A0
        "B_count": len(B),
        "C_count": len(C),
        "src_used": sorted(src_used),
        "src_count": len(src_used),
    }


def map_m_to_pid(m_set, passages):
    """M1—M52 → passage_id 列表（M_i 对应 passages[i-1].pid）。"""
    return [passages[m - 1]["pid"] for m in m_set if 1 <= m <= len(passages)]


def main():
    sp, passages, pid2idx = load_source_pool()
    total_passages = len(passages)
    print(f"source_pool: {sp['statistics']['total_sources']} sources, {total_passages} passages")
    print(f"人类基准的 M_i 顺序对应：M1={passages[0]['pid']}（原 original_id={passages[0]['original_id']}），"
          f"M2={passages[1]['pid']}（原 {passages[1]['original_id']}），...，"
          f"M52={passages[-1]['pid']}（原 {passages[-1]['original_id']}）")
    print()

    # 1) 三篇论文对比
    papers = [
        analyze_paper("Q_run_1 (GLM-4-Flash, 弱)", EXP / "Q_run_1" / "生成_论文.md"),
        analyze_paper("Q_run_2 (GLM-4.5-Flash, 强)", EXP / "Q_run_2" / "生成_论文.md"),
        analyze_paper("Q_human_baseline (人类手工)", EXP / "Q_human_baseline" / "生成_论文.md"),
    ]
    # 把所有引用都映射到 passage 顺序索引（0-51）
    for p in papers:
        idx_set = set()
        # 人类基准：M_i → idx i-1
        for m in p["m_refs"]:
            if 1 <= m <= total_passages:
                idx_set.add(m - 1)
        # 机器：SRC_xxx_Pyy → idx
        for s in p["src_refs"]:
            if s in pid2idx:
                idx_set.add(pid2idx[s])
        p["covered_idx"] = sorted(idx_set)
        p["coverage"] = len(idx_set) / total_passages

    print("=" * 100)
    print(f"{'论文':<32}{'字数(含空格)':>12}{'正文字':>8}{'一/二/三级标题':>18}{'引用数':>8}{'覆盖':>10}")
    print("-" * 100)
    for p in papers:
        title_str = f"{p['h1']}/{p['h2']}/{p['h3']}"
        ref_str = f"M={p['m_count']}  SRC={p['src_count']}"
        cov_str = f"{len(p['covered_idx'])}/{total_passages}={p['coverage']*100:.1f}%"
        print(f"{p['name']:<32}{p['total_chars']:>12}{p['body_chars']:>8}{title_str:>18}{ref_str:>18}{cov_str:>14}")
    print()

    # 2) 路线 1 直接 ABC 对比
    abc = analyze_abc("Q_direct_run_1 (GLM-4.5-Flash 直接 ABC)", EXP / "Q_direct_run_1" / "生成_ABC.json")
    abc_idx = set()
    for s in abc["src_used"]:
        if s in pid2idx:
            abc_idx.add(pid2idx[s])
    abc["covered_idx"] = sorted(abc_idx)
    abc["coverage"] = len(abc_idx) / total_passages

    print("=" * 100)
    print("路线 1（直接 ABC 生成）")
    print("-" * 100)
    print(f"  A={abc['A_count']}  B={abc['B_count']}  C={abc['C_count']}  使用 SRC={abc['src_count']}/{total_passages}  覆盖率={abc['coverage']*100:.1f}%")
    print()

    # 3) 三篇论文+直接 ABC 共同未覆盖的 passage
    all_covered = set()
    for p in papers:
        all_covered |= set(p["covered_idx"])
    all_covered |= set(abc["covered_idx"])
    never_covered = [i for i in range(total_passages) if i not in all_covered]
    print("=" * 100)
    print("四产物共同未覆盖的 passage（即没有任何产物引用过的史料段）")
    print("-" * 100)
    if not never_covered:
        print("  无——所有 52 条 passages 都被至少一个产物引用过")
    else:
        for idx in never_covered:
            psg = passages[idx]
            print(f"  M{idx+1}={psg['pid']}  原 {psg['original_id']}  《{psg['src_title']}》")
            print(f"     原文: {psg['text'][:80]}{'...' if len(psg['text']) > 80 else ''}")
    print()

    # 4) 人类基准独占覆盖（只有人类基准引用、机器产物都没引用的）
    human_only = set(papers[2]["covered_idx"]) - set(papers[0]["covered_idx"]) - set(papers[1]["covered_idx"]) - set(abc["covered_idx"])
    print("=" * 100)
    print("人类基准独占引用（机器产物 0 命中）")
    print("-" * 100)
    print(f"  共 {len(human_only)} 条")
    for idx in sorted(human_only)[:10]:  # 只列前 10 条
        psg = passages[idx]
        print(f"  M{idx+1}={psg['pid']}  原 {psg['original_id']}  《{psg['src_title']}》")
        print(f"     原文: {psg['text'][:80]}{'...' if len(psg['text']) > 80 else ''}")
    if len(human_only) > 10:
        print(f"  ...（剩余 {len(human_only) - 10} 条略）")

    # 5) 报告写入文件
    report = {
        "source_pool": {"total_sources": sp["statistics"]["total_sources"], "total_passages": sp["statistics"]["total_passages"]},
        "papers": [
            {
                "name": p["name"],
                "total_chars": p["total_chars"],
                "body_chars": p["body_chars"],
                "h1_h2_h3": [p["h1"], p["h2"], p["h3"]],
                "m_refs": p["m_refs"],
                "src_refs": p["src_refs"],
                "covered_idx_count": len(p["covered_idx"]),
                "coverage": round(p["coverage"], 4),
            } for p in papers
        ],
        "direct_abc": {
            "name": abc["name"],
            "A": abc["A_count"], "B": abc["B_count"], "C": abc["C_count"],
            "src_count": abc["src_count"],
            "coverage": round(abc["coverage"], 4),
            "src_used": abc["src_used"],
        },
        "never_covered_idx": never_covered,
        "human_only_idx": sorted(human_only),
    }
    out = EXP / "三篇对比_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[report 已保存] {out}")


if __name__ == "__main__":
    main()
