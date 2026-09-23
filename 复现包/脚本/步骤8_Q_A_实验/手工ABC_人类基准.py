# -*- coding: utf-8 -*-
"""人类基准 ABC 手工抽取（一次性，跳过 v3.2 五调用）。
由 LLM 在对话里直接读段落生成 C/B/A claim，脚本组装 run.json。

用法：python 手工ABC_人类基准.py <论文目录> [run名，默认 Q_human_baseline]
论断来源：优先 <RUN_DIR>/claims.json；不存在时回落到脚本内联的 A01 论断。
适用扁平结构论文：正文只有「一、二、三」而无小标题时，B 层即一级标题。
产物写入 <RUN_DIR>/run.json。
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, r"c:\Users\23297\Downloads\Lab\脚本\步骤3_v3.2抽取")
from 公共库 import load_paper, derive_skeleton, m_key, c_id_for, descendants, union_sources

LAB = Path(r"c:\Users\23297\Downloads\Lab")

if len(sys.argv) < 2:
    sys.exit("用法：python 手工ABC_人类基准.py <论文目录> [run名，默认 Q_human_baseline]")
PAPER_DIR = Path(sys.argv[1])
RUN_NAME = sys.argv[2] if len(sys.argv) > 2 else "Q_human_baseline"
RUN_DIR = PAPER_DIR / "03_实验输出" / "Q_A_实验" / RUN_NAME
CLAIMS_FILE = RUN_DIR / "claims.json"

paras, materials, _ = load_paper(RUN_DIR)
valid_M = {m["id"] for m in materials}
sk = derive_skeleton(paras)
pidx = sk["para_index"]
A_defs = sk["A"]
B_defs = [b for b in sk["B"] if not b["id"].startswith("ORPHAN@")]

# ============ 手工生成的 C defs（parent, anchor, text, sources）============
c_defs = [
    # P9 引言段（front_matter，按语义归入成因章各 B）
    {"parent": "B2.2", "anchor": "P9", "text": "北宋军费浩繁迫使朝廷将茶盐酒税山泽之利尽归于官以济用度", "sources": ["M31"]},
    {"parent": "B2.2", "anchor": "P9", "text": "茶盐之法被宋人视为朝廷利柄自祖宗以来他司不敢侵紊", "sources": ["M3"]},
    {"parent": "B2.3", "anchor": "P9", "text": "茶饮自唐兴起至北宋而极盛已成为人家每日不可阙之必需品", "sources": ["M1", "M2", "M32"]},
    {"parent": "B2.1", "anchor": "P9", "text": "宋太祖首定商税则例累朝守为家法奠定茶法制度基础", "sources": ["M46"]},
    # P12 (一)产茶区域与品类
    {"parent": "B1.1", "anchor": "P12", "text": "蜀地八处产茶虽非湖北却反映全国产茶之盛", "sources": ["M11"]},
    {"parent": "B1.1", "anchor": "P12", "text": "荆湖地区出产龙溪雨前雨后等十一等散茶品类丰富", "sources": ["M7", "M6"]},
    {"parent": "B1.1", "anchor": "P12", "text": "鄂州崇阳民不务耕织唯以植茶为业显示茶叶种植专业化", "sources": ["M30"]},
    {"parent": "B1.1", "anchor": "P12", "text": "茶树种植讲究崖阳圃阴且以上者生烂石为珍", "sources": ["M33", "M34"]},
    {"parent": "B1.1", "anchor": "P12", "text": "碧涧茶芽六百斤反映湖北地方贡茶或茶额之规模", "sources": ["M15"]},
    {"parent": "B1.1", "anchor": "P12", "text": "景祐元年天下户丁三分之一为产茶州军产茶区域甚广", "sources": ["M5"]},
    {"parent": "B1.1", "anchor": "P12", "text": "元丰二十三路包含荆湖南北淮南东西湖北居其间", "sources": ["M4"]},
    # P14 (二)榷茶机构与山场布局
    {"parent": "B1.2", "anchor": "P14", "text": "宋初奉召榷茶于蕲春开启湖北榷茶之始", "sources": ["M19"]},
    {"parent": "B1.2", "anchor": "P14", "text": "朝廷榷蕲黄舒庐寿五州茶置十四场岁入百余万缗", "sources": ["M20"]},
    {"parent": "B1.2", "anchor": "P14", "text": "蕲州王祺石桥洗马与黄州麻城为湖北境内核心山场", "sources": ["M21"]},
    {"parent": "B1.2", "anchor": "P14", "text": "京师建安汉阳蕲口并置场榷茶构成全国榷务骨架", "sources": ["M38"]},
    {"parent": "B1.2", "anchor": "P14", "text": "江陵府襄复州无为军增置务端拱二年又于海州置务", "sources": ["M22"]},
    {"parent": "B1.2", "anchor": "P14", "text": "荆南府务受纳潭鼎澧岳归峡片散茶共八十七万五千余斤", "sources": ["M37"]},
    # P16 (三)贸易网络与运输路线
    {"parent": "B1.3", "anchor": "P16", "text": "北至郢州私路二百五十里官路三百里显示湖北陆路要冲", "sources": ["M35"]},
    {"parent": "B1.3", "anchor": "P16", "text": "广南诸州自桂州经湖南北江陵荆门而至汇聚于湖北", "sources": ["M36"]},
    {"parent": "B1.3", "anchor": "P16", "text": "商贩蕲口洗马石桥茶货因泥水阻车改由江船借路东行", "sources": ["M39"]},
    {"parent": "B1.3", "anchor": "P16", "text": "蕲口太湖洗马石桥无为军五处茶货取东路真扬高邮楚泗州上京", "sources": ["M40"]},
    {"parent": "B1.3", "anchor": "P16", "text": "荆湖为浮江下黔蜀陆驿往京师之咽喉", "sources": ["M41"]},
    {"parent": "B1.3", "anchor": "P16", "text": "郢州至襄阳尽是滩碛反映水运局部阻碍", "sources": ["M42"]},
    {"parent": "B1.3", "anchor": "P16", "text": "管下舟车辐辏显示商贸繁盛", "sources": ["M43"]},
    {"parent": "B1.3", "anchor": "P16", "text": "住税每斤六文过税每斤二文构成湖北茶货过境税制", "sources": ["M10"]},
    # P18 (四)税课规模与流通实态
    {"parent": "B1.4", "anchor": "P18", "text": "茶法变动使岁入自五百六十九万贯降至二百八十五万贯", "sources": ["M44"]},
    {"parent": "B1.4", "anchor": "P18", "text": "湖北一路茶课独当十万二千三百三十一贯有畸", "sources": ["M45"]},
    {"parent": "B1.4", "anchor": "P18", "text": "石桥场祖额一百七万近岁买纳才得十万反映榷茶亏额", "sources": ["M49"]},
    {"parent": "B1.4", "anchor": "P18", "text": "诸州军每岁捕私茶三二万斤送食茶务补充官茶来源", "sources": ["M16"]},
    {"parent": "B1.4", "anchor": "P18", "text": "产茶州县铺户自造私茶相兼转般入城与铺户私相交易", "sources": ["M17"]},
    {"parent": "B1.4", "anchor": "P18", "text": "朝廷遣监察御史薛雄诣沿江诸州禁绝私茶", "sources": ["M18"]},
    # P21 (一)地理交通与区域格局
    {"parent": "B2.1", "anchor": "P21", "text": "湖北地跨荆湖北路京西南路淮南西路元丰二十三路交汇", "sources": ["M4"]},
    {"parent": "B2.1", "anchor": "P21", "text": "景祐产茶州军占天下户丁三分之一说明产茶区域广大", "sources": ["M5"]},
    {"parent": "B2.1", "anchor": "P21", "text": "荆南鄂州汉阳蕲口皆为长江汉水水陆枢纽", "sources": ["M41", "M43"]},
    {"parent": "B2.1", "anchor": "P21", "text": "郢州至襄阳滩碛之险迫使茶货改道借路东行", "sources": ["M42", "M39", "M40"]},
    {"parent": "B2.1", "anchor": "P21", "text": "湖北崖阳圃阴烂石之地理条件适宜茶树生长", "sources": ["M33", "M34"]},
    {"parent": "B2.1", "anchor": "P21", "text": "鄂州崇阳民以植茶为业反映地理优势转化为产业", "sources": ["M30"]},
    # P23 (二)榷茶制度的设计与调适
    {"parent": "B2.2", "anchor": "P23", "text": "北宋行交引法令商人输刍粮塞下授以要券至京师给缗钱", "sources": ["M23"]},
    {"parent": "B2.2", "anchor": "P23", "text": "产茶州军许民赴场输息给短便于旁近郡县便鬻", "sources": ["M25"]},
    {"parent": "B2.2", "anchor": "P23", "text": "商人自场给长引沿路批发至所指地然后计税尽输", "sources": ["M26"]},
    {"parent": "B2.2", "anchor": "P23", "text": "罢官给本钱使商人与园户自相交易一切定为中估官收其息", "sources": ["M27"]},
    {"parent": "B2.2", "anchor": "P23", "text": "一度园户收租钱商贾收征算尽罢禁榷", "sources": ["M28"]},
    {"parent": "B2.2", "anchor": "P23", "text": "官府以轻估入重估出茶利甚博且西北转致利又特厚", "sources": ["M29"]},
    {"parent": "B2.2", "anchor": "P23", "text": "赋税一例折科役钱一例均出构成园户双重负担", "sources": ["M9"]},
    {"parent": "B2.2", "anchor": "P23", "text": "民岁输税愿折茶者谓之折税茶形成茶税折纳惯例", "sources": ["M12"]},
    {"parent": "B2.2", "anchor": "P23", "text": "私贩鬻茶者没入计直论罪反映禁榷刑罚", "sources": ["M13"]},
    {"parent": "B2.2", "anchor": "P23", "text": "每百斤纳耗二十至三十五斤加重园户负担", "sources": ["M14"]},
    {"parent": "B2.2", "anchor": "P23", "text": "欧阳修言旧纳茶税今变租钱民不堪命", "sources": ["M47"]},
    {"parent": "B2.2", "anchor": "P23", "text": "园户破产亡家怨嗟愁苦或举族而逃或自经而死", "sources": ["M48"]},
    {"parent": "B2.2", "anchor": "P23", "text": "小商贩至少大商绝不通行反映榷法之弊", "sources": ["M51"]},
    {"parent": "B2.2", "anchor": "P23", "text": "佣力贫民被斥去无用官员忧其聚为寇盗", "sources": ["M50"]},
    # P25 (三)消费市场与边地需求
    {"parent": "B2.3", "anchor": "P25", "text": "茶为日常必需盖人家每日不可阙者", "sources": ["M2"]},
    {"parent": "B2.3", "anchor": "P25", "text": "茶之尚兴于唐盛于宋至本朝祐陵时益穷极新出", "sources": ["M1", "M32"]},
    {"parent": "B2.3", "anchor": "P25", "text": "商人转致茶于西北利尝至数倍拉动湖北茶货北输", "sources": ["M24"]},
    {"parent": "B2.3", "anchor": "P25", "text": "夔路自祖宗不榷茶政和中议卖引以民夷不便罢之反衬湖北榷利", "sources": ["M8"]},
    {"parent": "B2.3", "anchor": "P25", "text": "商人输刍粮塞下得交引移文江淮荆湖给茶拉动湖北茶货", "sources": ["M23"]},
    # P28 (一)国家财政的支撑
    {"parent": "B3.1", "anchor": "P28", "text": "蕲黄等五州榷茶岁入百余万缗支撑国家财政", "sources": ["M20"]},
    {"parent": "B3.1", "anchor": "P28", "text": "湖北一路茶课独当十万二千三百三十一贯有畸", "sources": ["M45"]},
    {"parent": "B3.1", "anchor": "P28", "text": "荆南府务受纳片散茶八十七万余斤构成财政实物支柱", "sources": ["M37"]},
    {"parent": "B3.1", "anchor": "P28", "text": "碧涧茶芽等地方茶额亦入贡或榷卖补充财政", "sources": ["M15"]},
    {"parent": "B3.1", "anchor": "P28", "text": "私茶每岁三二万斤送食茶务出卖补充官茶来源", "sources": ["M16"]},
    {"parent": "B3.1", "anchor": "P28", "text": "茶法收入波动反映其为财政重要变量", "sources": ["M44"]},
    {"parent": "B3.1", "anchor": "P28", "text": "朝廷视茶盐为利柄太祖定商税则例奠定体制", "sources": ["M3", "M46"]},
    # P30 (二)沿江经济带的发育
    {"parent": "B3.2", "anchor": "P30", "text": "鄂州崇阳以茶为业带动地方产业专门化", "sources": ["M30"]},
    {"parent": "B3.2", "anchor": "P30", "text": "荆南鄂州汉阳蕲口舟车辐辏形成沿江商贸节点", "sources": ["M43"]},
    {"parent": "B3.2", "anchor": "P30", "text": "荆湖为咽喉广南湖南北江陵荆门商路汇聚", "sources": ["M41", "M36"]},
    {"parent": "B3.2", "anchor": "P30", "text": "蕲口等五处茶货水路转江取东路上京支撑区域市场", "sources": ["M40", "M39"]},
    {"parent": "B3.2", "anchor": "P30", "text": "郢州襄阳虽有滩碛但整体交通网络支撑区域市场发育", "sources": ["M42"]},
    # P32 (三)社会矛盾与茶商军
    {"parent": "B3.3", "anchor": "P32", "text": "园户破产或举族而逃或自经而死反映榷剥之酷", "sources": ["M48"]},
    {"parent": "B3.3", "anchor": "P32", "text": "小商贩至少大商绝不通行挤压中小茶商生存空间", "sources": ["M51"]},
    {"parent": "B3.3", "anchor": "P32", "text": "佣力贫民被斥官员忧其聚为寇盗", "sources": ["M50"]},
    {"parent": "B3.3", "anchor": "P32", "text": "铺户更无引目收私茶相兼私相交易形成地下茶市", "sources": ["M17"]},
    {"parent": "B3.3", "anchor": "P32", "text": "朝廷遣薛雄禁绝私茶收效有限", "sources": ["M18"]},
    {"parent": "B3.3", "anchor": "P32", "text": "湖北茶商群聚暴横籍为兵号茶商军后多赖其用", "sources": ["M52"]},
    # P34 结语（A0 的 span 段，按规则 A0 claim 直接概括，不切 C）
]

# ============ 手工生成的 B claims（id -> claim）============
b_claims = {
    "B1.1": "湖北及周边产茶区域广大品类繁多崇阳等地已以植茶为业",
    "B1.2": "宋初在湖北设蕲黄等州山场并置汉阳蕲口榷货务构成榷茶骨架",
    "B1.3": "湖北地处水陆要冲形成借路改道与沿江转贩的茶叶运输网络",
    "B1.4": "湖北茶课岁入可观但祖额亏额与私茶盛行并存",
    "B2.1": "湖北地跨多路兼有长江汉水之便与滩碛之险地理条件适宜茶植",
    "B2.2": "北宋榷茶制度经交引短长引罢官本收中估等多次调适但仍致园户破产",
    "B2.3": "茶饮普及与西北边地需求共同拉动湖北茶叶生产扩张",
    "B3.1": "湖北茶利在国家财政中举足轻重岁入与盐课共为朝廷利柄",
    "B3.2": "茶叶贸易带动鄂州汉阳蕲口等沿江城镇繁荣形成区域经济带",
    "B3.3": "榷剥激化社会矛盾最终孕育出茶商军这一特殊军事力量",
}

# ============ 手工生成的 A claims ============
a_claims = {
    "A1": "北宋湖北茶叶经济繁盛呈现产茶广品类多榷务密税课巨的状貌",
    "A2": "湖北茶叶繁盛源于地理枢纽榷法调适与消费需求三重力量交汇",
    "A3": "湖北茶利支撑国家财政拉动沿江经济带同时催生茶商军等社会矛盾",
    "A4": "北宋湖北茶叶经济贸易在国家茶法体系与区域地理优势的交汇中走向繁盛榷茶机构水陆网络引法制度共同塑造湖北作为长江中游茶叶集散中心的地位",
    "A0": "湖北茶利既是北宋财政体系的支撑点也是社会矛盾的滋生地其双重性构成理解北宋区域经济与制度运行关系的重要切面",
}

# ============ 外部论断覆盖 ============
# A01 的论断内联在上方作为默认值；其他论文把论断写到 <RUN_DIR>/claims.json：
#   {"c": [{"parent","anchor","text","sources"}...], "b": {"B1": "..."}, "a": {"A1": "..."}}
# 扁平结构的论文（正文只有「一、二、三」而无小标题）B 层即由 derive_skeleton 给出的一级标题，
# c 的 parent 直接指向这些 B，不需要更深层级。
if CLAIMS_FILE.exists():
    cf = json.loads(CLAIMS_FILE.read_text(encoding="utf-8"))
    c_defs = cf.get("c", c_defs)
    b_claims = cf.get("b", b_claims)
    a_claims = cf.get("a", a_claims)
    print(f"已载入外部论断 {CLAIMS_FILE}：C={len(c_defs)}  B={len(b_claims)}  A={len(a_claims)}")
    print(f"  骨架：A={[a['id'] for a in A_defs]}  B={[b['id'] for b in B_defs]}")
else:
    print(f"未找到 {CLAIMS_FILE}，使用脚本内联的 A01 论断")

# ============ 组装 ============
node_by_id = {n["id"]: n for n in A_defs + B_defs}
parent_order = {n["id"]: pidx[n["title_pid"]] for n in A_defs + B_defs}

# 校验并排序 C
enr = []
for i, c in enumerate(c_defs):
    par, anc, txt, srcs = c["parent"], c["anchor"], c["text"], c.get("sources", [])
    if par not in node_by_id:
        print(f"跳过 C: parent 不存在 {par}  text={txt[:30]}")
        continue
    if anc not in {p["id"] for p in paras}:
        print(f"跳过 C: anchor 非法 {anc}  text={txt[:30]}")
        continue
    srcs = [m for m in srcs if m in valid_M]
    enr.append((parent_order[par], pidx[anc], i, par, anc, txt, srcs))
enr.sort(key=lambda x: (x[0], x[1], x[2]))

chapter_count = max([int(m.group(1)) for m in
                     (re.match(r"B(\d+)", b["id"]) for b in B_defs) if m] or [0])
counters, C = {}, []
for _, _, _, par, anc, txt, srcs in enr:
    counters[par] = counters.get(par, 0) + 1
    C.append({"id": c_id_for(par, counters[par], chapter_count), "anchor": anc,
              "text": txt, "sources": sorted(srcs, key=m_key), "parent": par})

def span_pair(sp):
    return [sp[0], sp[1] if sp and len(sp) > 1 and sp[1] else sp[0]] if sp and sp[0] else [None, None]

B_out = []
for b in sorted(B_defs, key=lambda x: pidx[x["title_pid"]]):
    ms = union_sources(descendants(b["id"], A_defs, B_defs, C))
    B_out.append({"id": b["id"], "depth": b["depth"], "title_label": b["title_label"],
                  "claim": b_claims.get(b["id"], ""), "span": span_pair(b["span"]),
                  "sources": sorted(ms, key=m_key), "source_count": len(ms),
                  "supported": None, "supported_by": [], "parent": b.get("parent")})

A_out = []
for a in sorted(A_defs, key=lambda x: (x["order"] if x["order"] is not None else -1)):
    ms = union_sources(descendants(a["id"], A_defs, B_defs, C))
    if a["id"] == "A0":
        ms = set(valid_M)
    A_out.append({"id": a["id"], "depth": a["depth"], "title_label": a["title_label"],
                  "claim": a_claims.get(a["id"], ""), "span": span_pair(a["span"]),
                  "sources": sorted(ms, key=m_key), "source_count": len(ms),
                  "supported": None, "supported_by": [], "parent": None})

paragraphs_out = [{"id": p["id"], "type": p["type"], "text": p["text"],
                   "material_refs": p.get("material_refs", []), "page": p.get("page", "1")} for p in paras]
materials_out = [{"id": m["id"], "text": m.get("text", ""),
                  "footnote_number": m.get("footnote_number"),
                  "source_full": m.get("source_full", "")} for m in materials]

all_used_M = set()
for c in C:
    all_used_M |= set(c["sources"])

run = {
    "meta": {
        "paper_title": paras[0]["text"] if paras and paras[0].get("type") == "title" else RUN_NAME,
        "encoding_scheme": "A-B-C-M hierarchical encoding",
        "version": "3.2",
        "run_name": RUN_NAME,
        "extraction_method": "LLM one-shot in chat (option b, skips v3.2 5-call protocol)",
        "timestamp": "2026-09-16",
    },
    "encoding_table": {
        "A_level": A_out,
        "B_level": B_out,
        "C_level": C,
        "M_level": materials_out,
    },
    "paragraphs": paragraphs_out,
    "front_matter": sk["front_matter"],
    "statistics": {
        "total_A_nodes": len(A_out),
        "total_B_nodes": len(B_out),
        "total_C_nodes": len(C),
        "total_unique_M": len(valid_M),
        "nodes_by_depth": {"1": len(A_out), "2": len(B_out), "3": 0},
        "source_count_by_A": {a["id"]: a["source_count"] for a in A_out},
        "source_count_by_B": {b["id"]: b["source_count"] for b in B_out},
        "C_nodes_without_sources": sum(1 for c in C if not c["sources"]),
        "claims_total": len(A_out) + len(B_out),
        "claims_supported": 0,
        "claims_unsupported": 0,
        # 额外字段（报告用）
        "M_used_by_C": len(all_used_M),
        "M_unused_by_C": sorted(valid_M - all_used_M, key=m_key),
    },
}
run_path = RUN_DIR / "run.json"
run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[人类基准 run.json 已保存] {run_path}")
print(f"  A={len(A_out)} (含A0=A0)  B={len(B_out)}  C={len(C)}")
print(f"  M 使用: {len(all_used_M)}/{len(materials)} = {len(all_used_M)/len(materials)*100:.1f}%")
print(f"  未使用 M: {sorted(valid_M - all_used_M, key=m_key)}")
