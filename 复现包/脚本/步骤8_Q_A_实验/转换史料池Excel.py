# -*- coding: utf-8 -*-
"""把人工校订的史料上下文 Excel（A05.xlsx / B05.xlsx）转换为 source_pool.json，
落到论文目录的 02_史料池/source_pool.json，供 Q/A 模型实验使用。

映射规则（Excel「史料上下文」sheet -> source_pool passages）：
  original_id  = 编号列（如 M7 / B05 M6，统一为 M<数字>，保留 A05-S01 等特殊编号原样）
  title        = 核心引文所在篇章 中 《书名》 部分（缺书名时用定位/出处推断）
  volume       = 篇章中的 卷X / 卷X·篇 部分
  dynasty      = 优先「原表数据」sheet 的 时代 列；缺省按书名常见朝代表推断
  text         = 校订后核心引文（空则用 论文对应引文/陈述）
  source_full  = 论文原脚注（空则用 核心出处及扩充段定位）
  context      = 原书连续上下文（400汉字），保留备查

聚合：按 title 聚合为 source（同书多 passage），citation_count = passages 数。
用法：python 转换史料池Excel.py <A05.xlsx|B05.xlsx> <论文目录>
"""
import json, re, sys, io
from pathlib import Path
import openpyxl

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

CN = "一二三四五六七八九十"
RE_TITLE = re.compile(r"《([^》]{1,60})》")
RE_VOL = re.compile(r"(卷[0-9零一二三四五六七八九十]{1,4})(?:[·.．、]|$)")
RE_SPECIAL_ID = re.compile(r"^[A-Z]+\d*-\S+$")  # A05-S01 这类

# 常用古籍朝代表（无时代列时按书名推断）
BOOK_ERA = {
    "宋史": "元", "续资治通鉴长编": "宋", "文献通考": "元",
    "宋会要辑稿": "清", "东京梦华录": "宋", "夷坚志": "宋",
    "东轩笔录": "宋", "二程文集": "宋", "作邑自箴": "宋",
    "参天台五台山记": "日", "天一阁藏明钞本天圣令校证": "唐",
    "宋文鉴": "宋", "宛陵集": "宋", "建炎以来系年要录": "宋",
    "彭城集": "宋", "拙堂文话": "日", "杨文公谈苑": "宋",
    "欧阳修集": "宋", "范太史集": "宋", "通俗编": "清",
    "鸡肋编": "宋", "麈史": "宋", "乌青镇志": "清",
    "事物纪原": "宋", "澉水志": "宋", "淳熙三山志": "宋",
    "吴郡志": "宋", "宝庆四明志": "宋", "嘉泰会稽志": "宋",
    "咸淳临安志": "宋", "梦粱录": "宋", "都城纪胜": "宋",
    "西湖老人繁胜录": "宋", "武林旧事": "宋", "建炎以来朝野杂记": "宋",
    "宋名臣言行录": "宋", "朱子语类": "宋", "西山先生真文忠公文集": "宋",
    "续古今考": "元", "芝园集": "明", "皇宋中兴两朝圣政": "宋",
    "宋大诏令集": "宋", "挥麈录": "宋", "老学庵笔记": "宋",
    "容斋随笔": "宋", "鹤林玉露": "宋", "癸辛杂识": "宋",
    "齐东野语": "宋", "玉照新志": "宋", "投辖录": "宋",
    "云麓漫钞": "宋", "宾退录": "宋", "独醒杂志": "宋",
    "四朝闻见录": "宋", "朝野类要": "宋", "鼠璞": "宋",
    "却扫编": "宋", "曲洧旧闻": "宋", "铁围山丛谈": "宋",
    "墨庄漫录": "宋", "过庭录": "宋", "萍洲可谈": "宋",
    "春渚纪闻": "宋", "浩然斋雅谈": "宋", "吹剑录外集": "宋",
    "贵耳集": "宋", "识小录": "宋", "三朝北盟会编": "宋",
    "宋会要": "清", "皇宋通鉴长编纪事本末": "宋",
    "宋稗类钞": "清", "分门古今类事": "宋", "夷坚志全集": "宋",
}


def clean_code(raw):
    """M7 / B05 M6 / A05-S01 / M77-b -> 统一 original_id"""
    s = str(raw).strip()
    m = re.search(r"(M\d+)", s)
    if m and not RE_SPECIAL_ID.match(s):
        return m.group(1)  # 提取 M<数字>
    return s  # 特殊编号原样


def parse_chapter(chap):
    """《东京梦华录》卷一·河道 -> (title, volume)"""
    title = ""
    mt = RE_TITLE.search(chap or "")
    if mt:
        title = mt.group(1)
    vol = ""
    mv = RE_VOL.search(chap or "")
    if mv:
        vol = mv.group(1)
    return title, vol


def infer_title_from_loc(loc):
    """定位串《东京梦华录》卷一·河道 -> 书名"""
    mt = RE_TITLE.search(loc or "")
    return mt.group(1) if mt else ""


def load_dynasty_map(xlsx):
    """从「原表数据」sheet 读 校订文献名->时代。"""
    dm = {}
    try:
        wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
        if "原表数据" in wb.sheetnames:
            ws = wb["原表数据"]
            rows = list(ws.iter_rows(values_only=True))
            hdr = [str(h) if h else "" for h in rows[0]]
            if "校订文献名" in hdr and "时代" in hdr:
                i_n = hdr.index("校订文献名")
                i_e = hdr.index("时代")
                for r in rows[1:]:
                    if r and r[i_n]:
                        dm[str(r[i_n]).strip()] = str(r[i_e]).strip() if r[i_e] else ""
        wb.close()
    except Exception as e:
        print("  读时代列失败:", e)
    return dm


def convert(xlsx, paper_dir):
    xlsx = Path(xlsx)
    paper_dir = Path(paper_dir)
    dyn_map = load_dynasty_map(xlsx)

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb["史料上下文"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(h) if h else "" for h in rows[0]]

    def col(name, alias=()):
        for i, h in enumerate(hdr):
            if h == name or h in alias:
                return i
        return None

    i_code = col("编号")
    i_chap = col("核心引文所在篇章")
    i_ctx = col("原书连续上下文（400汉字）")
    i_quote = col("论文对应引文／陈述（照录）")
    i_loc = col("核心出处及扩充段定位")
    i_link = col("原典链接")
    i_corr = col("校订后核心引文")
    i_fn = col("论文原脚注（照录）")
    i_ver = col("汉字数")

    groups = {}  # title -> list[passage]
    order = []
    special = []  # 特殊编号（无书名归属）单列 source
    for r in rows[1:]:
        if not r or not r[i_code]:
            continue
        oid = clean_code(r[i_code])
        chap = str(r[i_chap]).strip() if i_chap is not None and r[i_chap] else ""
        title, vol = parse_chapter(chap)
        corr = str(r[i_corr]).strip() if i_corr is not None and r[i_corr] else ""
        quote = str(r[i_quote]).strip() if i_quote is not None and r[i_quote] else ""
        loc = str(r[i_loc]).strip() if i_loc is not None and r[i_loc] else ""
        fn = str(r[i_fn]).strip() if i_fn is not None and r[i_fn] else ""
        ctx = str(r[i_ctx]).strip() if i_ctx is not None and r[i_ctx] else ""
        link = str(r[i_link]).strip() if i_link is not None and r[i_link] else ""

        text = corr or quote
        source_full = fn or loc
        if not title:
            title = infer_title_from_loc(loc)
        if not title:
            title = quote[:20]  # 兜底
        dynasty = dyn_map.get(title, "") or BOOK_ERA.get(title, "")

        ps = {
            "original_id": oid,
            "text": text,
            "source_full": source_full,
            "volume": vol,
            "context": ctx,
            "link": link,
            "_quote": quote,      # 论文对应引文，保留供核
            "_loc": loc,
        }
        key = (title, dynasty)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(ps)

    sources = []
    for k, (title, dynasty) in enumerate(order, 1):
        g = groups[(title, dynasty)]
        sid = "SRC_%03d" % k
        passages = []
        for j, ps in enumerate(g, 1):
            passages.append({
                "passage_id": f"{sid}_P{j:02d}",
                "original_id": ps["original_id"],
                "text": ps["text"],
                "source_full": ps["source_full"],
                "volume": ps["volume"],
                "context": ps["context"],
                "link": ps["link"],
            })
        sources.append({
            "source_id": sid, "title": title, "dynasty": dynasty,
            "citation_count": len(passages), "passages": passages,
        })

    out = {
        "metadata": {
            "version": "2.0",
            "paper_id": paper_dir.name,
            "description": "人工校订史料池（原书上下文400字 + 校订引文）",
            "note": "来源：人工校订 Excel；text 为校订后核心引文（缺省用论文引文）；context 为原书连续上下文（400字）；source_full 为完整出处",
        },
        "statistics": {"total_sources": len(sources),
                       "total_passages": sum(len(s["passages"]) for s in sources)},
        "sources": sources,
    }

    sp_dir = paper_dir / "02_史料池"
    sp_dir.mkdir(parents=True, exist_ok=True)
    out_path = sp_dir / "source_pool.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 统计
    n_empty_text = sum(1 for s in sources for p in s["passages"] if not p["text"])
    n_ctx = sum(1 for s in sources for p in s["passages"] if p.get("context"))
    print(f"[{paper_dir.name}] 源={len(sources)} 条={out['statistics']['total_passages']} "
          f"text空={n_empty_text} 有上下文={n_ctx}")
    print(f"  输出: {out_path}")
    return out


if __name__ == "__main__":
    xlsx = sys.argv[1]
    paper = sys.argv[2]
    convert(xlsx, paper)
