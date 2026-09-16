# -*- coding: utf-8 -*-
"""Q_run_2 ABC 手工抽取（一次性）。
基于 Q_run_2/00_原文/原文_clean.json 的段落内容生成 ABC。
front_matter 段（P5/P7/P10/P12/P14）按语义归入最相关的 B。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, r"c:\Users\23297\Downloads\Lab\脚本\步骤3_v3.2抽取")
from 公共库 import load_paper, derive_skeleton, m_key, c_id_for, descendants, union_sources

LAB = Path(r"c:\Users\23297\Downloads\Lab")
RUN_NAME = "Q_run_2"
RUN_DIR = LAB / "A01_湖北茶叶经济" / "03_实验输出" / "Q_A_实验" / RUN_NAME

paras, materials, _ = load_paper(RUN_DIR)
valid_M = {m["id"] for m in materials}
sk = derive_skeleton(paras)
pidx = sk["para_index"]
A_defs = sk["A"]
B_defs = [b for b in sk["B"] if not b["id"].startswith("ORPHAN@")]

# ============ 手工 C defs（按段落 anchor 排列）============
c_defs = [
    # === front_matter P5 (产茶区域) → 归入 B1.1.1 产量与税收 ===
    {"parent": "B1.1.1", "anchor": "P5", "text": "蕲州王祺石桥洗麻与黄州麻城为湖北核心产茶地", "sources": ["M21"]},
    {"parent": "B1.1.1", "anchor": "P5", "text": "鄂州崇阳民不务耕织唯以植茶为业显示专业化", "sources": ["M30"]},
    {"parent": "B1.1.1", "anchor": "P5", "text": "荆湖南北出产龙溪雨前雨后等十一等散茶品类丰富", "sources": ["M7", "M6"]},
    # === front_matter P7 (种植特点) → 归入 B1.2.1 自然地理 ===
    {"parent": "B1.2.1", "anchor": "P7", "text": "茶经载上者生烂石反映北宋对茶树生长环境的科学认识", "sources": ["M33"]},
    {"parent": "B1.2.1", "anchor": "P7", "text": "茶录言植产之地崖必阳圃必阴显示光照要求", "sources": ["M34"]},
    {"parent": "B1.2.1", "anchor": "P7", "text": "碧涧茶芽六百斤反映湖北茶产规模化商品化", "sources": ["M15"]},
    # === front_matter P10 (官榷) → 归入 B1.2.2 政策支持 ===
    {"parent": "B1.2.2", "anchor": "P10", "text": "茶盐之法被宋人视为朝廷利柄他司不敢侵紊", "sources": ["M3"]},
    {"parent": "B1.2.2", "anchor": "P10", "text": "蕲口洗马石桥太湖场务承担湖北茶货收购管理销售", "sources": ["M39", "M40"]},
    {"parent": "B1.2.2", "anchor": "P10", "text": "北宋榷蕲黄舒庐寿五州茶置十四场岁入百余万缗", "sources": ["M20"]},
    {"parent": "B1.2.2", "anchor": "P10", "text": "商人自场给长引沿路批发至所指地然后计税尽输", "sources": ["M26"]},
    # === front_matter P12 (私茶) → 归入 B1.3.2 私茶冲击 ===
    {"parent": "B1.3.2", "anchor": "P12", "text": "诸州军每岁捕私茶三二万斤送食茶务出卖显示规模", "sources": ["M16"]},
    {"parent": "B1.3.2", "anchor": "P12", "text": "铺户居民在城外种茶自造私茶相兼转般入城私相交易", "sources": ["M17"]},
    {"parent": "B1.3.2", "anchor": "P12", "text": "朝廷遣监察御史薛雄诣沿江诸州禁绝私茶", "sources": ["M18"]},
    {"parent": "B1.3.2", "anchor": "P12", "text": "商人转致茶于西北利尝至数倍吸引私贩", "sources": ["M24"]},
    # === front_matter P14 (运输网络) → 归入 B1.2.3 交通便利 ===
    {"parent": "B1.2.3", "anchor": "P14", "text": "广南诸州自桂州经湖南北江陵荆门汇聚于湖北", "sources": ["M36"]},
    {"parent": "B1.2.3", "anchor": "P14", "text": "荆湖为浮江下黔蜀陆驿往京师之咽喉", "sources": ["M41"]},
    {"parent": "B1.2.3", "anchor": "P14", "text": "管下舟车辐辏反映商贸繁盛", "sources": ["M43"]},
    {"parent": "B1.2.3", "anchor": "P14", "text": "商贩蕲口等场务茶货因泥水阻车改由江船借路东行", "sources": ["M39"]},
    {"parent": "B1.2.3", "anchor": "P14", "text": "郢州至襄阳尽是滩碛反映水运局部阻碍", "sources": ["M42"]},

    # === A1 B1.1 (一)表现 ===
    # P18 → B1.1.1 产量与税收
    {"parent": "B1.1.1", "anchor": "P18", "text": "石桥场祖额一百七万近岁买纳才得十万反映亏额", "sources": ["M49"]},
    {"parent": "B1.1.1", "anchor": "P18", "text": "湖北一路茶课独当十万二千三百三十一贯有畸", "sources": ["M45"]},
    # P20 → B1.1.2 贸易规模
    {"parent": "B1.1.2", "anchor": "P20", "text": "京师建安汉阳蕲口均设茶叶场务构成全国贸易网络", "sources": ["M38"]},
    {"parent": "B1.1.2", "anchor": "P20", "text": "荆南府务受纳潭鼎澧岳归峡片散茶八十七万五千余斤", "sources": ["M37"]},
    {"parent": "B1.1.2", "anchor": "P20", "text": "荆湖出产龙溪雨前雨后等茶叶品种多样", "sources": ["M7"]},

    # === A1 B1.2 (二)原因 ===
    # P23 → B1.2.1 自然地理
    {"parent": "B1.2.1", "anchor": "P23", "text": "茶经上者生烂石之土壤条件湖北恰好符合", "sources": ["M33"]},
    {"parent": "B1.2.1", "anchor": "P23", "text": "鄂州崇阳多旷土民不务耕织唯以植茶为业", "sources": ["M30"]},
    # P25 → B1.2.2 政策支持
    {"parent": "B1.2.2", "anchor": "P25", "text": "宋初奉召榷茶于蕲春开启湖北榷茶", "sources": ["M19"]},
    {"parent": "B1.2.2", "anchor": "P25", "text": "榷蕲黄舒庐寿五州茶置十四场笼其利岁入百余万缗", "sources": ["M20"]},
    {"parent": "B1.2.2", "anchor": "P25", "text": "交引法令商人输刍粮至京师给缗钱移文江淮荆湖给茶", "sources": ["M23"]},
    {"parent": "B1.2.2", "anchor": "P25", "text": "产茶州军许民赴场输息给短便于旁近郡县便鬻", "sources": ["M25"]},
    # P27 → B1.2.3 交通便利
    {"parent": "B1.2.3", "anchor": "P27", "text": "荆湖为咽喉连接南北商路", "sources": ["M41"]},
    {"parent": "B1.2.3", "anchor": "P27", "text": "管下舟车辐辏显示商贸繁忙", "sources": ["M43"]},
    {"parent": "B1.2.3", "anchor": "P27", "text": "郢州至襄阳滩碛之险反映局部运输困难", "sources": ["M42"]},
    {"parent": "B1.2.3", "anchor": "P27", "text": "商贩借路取真扬高邮楚泗州只纳旧路税钱", "sources": ["M39"]},

    # === A1 B1.3 (三)挑战 ===
    # P30 → B1.3.1 官榷弊端
    {"parent": "B1.3.1", "anchor": "P30", "text": "旧纳茶税今变租钱加重茶农茶商负担", "sources": ["M47"]},
    {"parent": "B1.3.1", "anchor": "P30", "text": "园户破产亡家怨嗟愁苦或举族而逃或自经而死", "sources": ["M48"]},
    {"parent": "B1.3.1", "anchor": "P30", "text": "小商贩至少大商绝不通行挤压中小茶商生存空间", "sources": ["M51"]},
    # P32 → B1.3.2 私茶冲击
    {"parent": "B1.3.2", "anchor": "P32", "text": "诸州军每岁捕私茶三二万斤显示规模持续", "sources": ["M16"]},
    {"parent": "B1.3.2", "anchor": "P32", "text": "朝廷遣薛雄禁绝私茶收效有限", "sources": ["M18"]},
    {"parent": "B1.3.2", "anchor": "P32", "text": "商人转致茶于西北利尝至数倍吸引私贩", "sources": ["M24"]},

    # === A2 B2.1 (一)对湖北经济影响 ===
    # P36 → B2.1.1 财政贡献
    {"parent": "B2.1.1", "anchor": "P36", "text": "湖北茶课独当十万二千三百三十一贯有畸支撑财政", "sources": ["M45"]},
    {"parent": "B2.1.1", "anchor": "P36", "text": "管下舟车辐辏显示商贸繁荣带动相关产业", "sources": ["M43"]},
    # P38 → B2.1.2 产业结构调整
    {"parent": "B2.1.2", "anchor": "P38", "text": "鄂州崇阳以植茶为业形成茶叶种植主导产业结构", "sources": ["M30"]},

    # === A2 B2.2 (二)对社会影响 ===
    # P41 → B2.2.1 民生影响
    {"parent": "B2.2.1", "anchor": "P41", "text": "佣力者众皆是贫民茶叶种植吸纳大量劳动力", "sources": ["M50"]},
    {"parent": "B2.2.1", "anchor": "P41", "text": "官榷弊端致园户破产亡家或举族而逃或自经而死", "sources": ["M48"]},
    # P43 → B2.2.2 茶商群体形成
    {"parent": "B2.2.2", "anchor": "P43", "text": "湖北茶商群聚暴横籍为兵号曰茶商军后多赖其用", "sources": ["M52"]},
    {"parent": "B2.2.2", "anchor": "P43", "text": "商人转致茶于西北利尝至数倍吸引茶商群体", "sources": ["M24"]},

    # === A2 B2.3 (三)对国家战略影响 ===
    # P46 → B2.3.1 茶盐互市政策
    {"parent": "B2.3.1", "anchor": "P46", "text": "交引法以茶与盐互市是北宋重要经济政策", "sources": ["M23"]},
    # P48 → B2.3.2 茶商军作用
    {"parent": "B2.3.2", "anchor": "P48", "text": "湖北茶商籍为兵号茶商军成为北宋军队重要补充", "sources": ["M52"]},
    # P49 (结语段, no refs) → 不切 C，归入 A0 claim
]

# ============ B claims ============
b_claims = {
    "B1.1": "湖北茶叶经济呈现产茶广产量巨品种多的繁荣表现",
    "B1.1.1": "湖北茶叶产量与税收在国家财政中占有重要地位但祖额亏额", 
    "B1.1.2": "湖北茶叶贸易规模庞大形成多场务多品种的网络",
    "B1.2": "湖北茶叶经济发展得益于自然地理政策支持与交通便利三重原因",
    "B1.2.1": "湖北自然地理条件适宜茶树生长构成经济基础",
    "B1.2.2": "北宋榷茶制度与交引短长引政策支持湖北茶业发展",
    "B1.2.3": "湖北水陆交通便利降低贸易成本保障茶叶运输",
    "B1.3": "官榷制度弊端与私茶贸易冲击构成湖北茶叶经济的挑战",
    "B1.3.1": "官榷制度加重园户负担导致破产亡家与小商衰落",
    "B1.3.2": "私茶贸易持续存在冲击官榷制度秩序",
    "B2.1": "茶叶经济促进湖北产业结构调整与财政贡献",
    "B2.1.1": "湖北茶课支撑北宋财政并带动相关产业发展",
    "B2.1.2": "鄂州崇阳等地形成茶叶种植主导的产业结构",
    "B2.2": "茶叶经济深刻影响湖北民生与茶商群体形成",
    "B2.2.1": "茶叶经济既提供就业又因官榷弊端加剧民生痛苦",
    "B2.2.2": "湖北茶商群体壮大最终被籍为茶商军成为特殊社会力量",
    "B2.3": "湖北茶叶经济影响北宋茶盐互市与军事战略",
    "B2.3.1": "湖北茶叶成为北宋茶盐互市政策的重要物资",
    "B2.3.2": "茶商军成为北宋军事战略的重要补充力量",
}

# ============ A claims ============
a_claims = {
    "A1": "北宋湖北茶叶经济在产量税收贸易规模上呈现繁荣同时面临官榷弊端与私茶冲击的挑战",
    "A2": "湖北茶叶经济对区域产业结构财政民生社会群体及国家茶盐军略均产生深远影响",
    "A0": "综上所述北宋湖北茶叶经济呈现繁荣发展态势得益于地理政策交通三重原因对经济社会国家战略产生深远影响但官榷弊端与私茶冲击带来挑战",
}

# ============ 组装 ============
node_by_id = {n["id"]: n for n in A_defs + B_defs}
parent_order = {n["id"]: pidx[n["title_pid"]] for n in A_defs + B_defs}

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

counters, C = {}, []
for _, _, _, par, anc, txt, srcs in enr:
    counters[par] = counters.get(par, 0) + 1
    C.append({"id": c_id_for(par, counters[par]), "anchor": anc,
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
        ms = set(valid_M)  # A0 = 全文 M 并集（v3.2 规则）
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

# 注意：A0 sources 是全文 M 并集（v3.2 规则），但实际 C 层只用了部分 M。
# 我们报告两个数字：C 层实际用到的 M vs A0 应有的全集 M。
c_used_M = all_used_M.copy()
all_used_M |= set(valid_M)  # 加上 A0 的全集

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
        "nodes_by_depth": {
            "1": len(A_out),
            "2": len([b for b in B_out if b["depth"] == 2]),
            "3": len([b for b in B_out if b["depth"] == 3]),
        },
        "source_count_by_A": {a["id"]: a["source_count"] for a in A_out},
        "source_count_by_B": {b["id"]: b["source_count"] for b in B_out},
        "C_nodes_without_sources": sum(1 for c in C if not c["sources"]),
        "claims_total": len(A_out) + len(B_out),
        "claims_supported": 0,
        "claims_unsupported": 0,
        # 额外字段（报告用）
        "M_used_by_C": len(c_used_M),
        "M_used_including_A0": len(all_used_M),
        "M_unused_by_C": sorted(valid_M - c_used_M, key=m_key),
    },
}
run_path = RUN_DIR / "run.json"
run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[Q_run_2 run.json 已保存] {run_path}")
print(f"  A={len(A_out)} (含A0)  B={len(B_out)} (depth2={len([b for b in B_defs if b['depth']==2])}, depth3={len([b for b in B_defs if b['depth']==3])})  C={len(C)}")
print(f"  C 层 M 使用: {len(c_used_M)}/{len(materials)} = {len(c_used_M)/len(materials)*100:.1f}%")
print(f"  C 层未使用 M: {sorted(valid_M - c_used_M, key=m_key)}")
