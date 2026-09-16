# -*- coding: utf-8 -*-
"""人类基准 ABC 一次性抽取（方案 b：跳过 v3.2 五调用，由 LLM 直接读段落生成 claim）。

输入：Q_human_baseline/00_原文/原文_clean.json（= 真·人类原文 full.md 清洗件，
      33 段 / A1-A3+A0 / B 9 个 / 脚注 M1-M63）
输出：Q_human_baseline/run.json            —— 忠实版（sources 使用人类脚注 M 编号）
      Q_human_baseline/run_poolspace.json  —— 池空间视图（sources 折算为史料池 M1-M52，
                                              供与模型侧 run.json 直接对比）
      Q_human_baseline/史料映射报告.json    —— 两侧 M 编号的书目匹配结果
"""
import json, re, sys, difflib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "步骤3_v3.2抽取"))
from 公共库 import load_paper, derive_skeleton, m_key, c_id_for, descendants, union_sources

LAB = Path(r"c:\Users\23297\Downloads\Lab")
RUN_NAME = "Q_human_baseline"
QA = LAB / "A01_湖北茶叶经济" / "03_实验输出" / "Q_A_实验"
RUN_DIR = QA / RUN_NAME
POOL = LAB / "A01_湖北茶叶经济" / "02_史料池" / "source_pool.json"

paras, materials, _ = load_paper(RUN_DIR)
valid_M = {m["id"] for m in materials}
sk = derive_skeleton(paras)
pidx = sk["para_index"]
A_defs = sk["A"]
B_defs = [b for b in sk["B"] if not b["id"].startswith("ORPHAN@")]

# ============ 手工生成的 C defs（parent, anchor, text, sources）============
# 规则：sources ⊆ anchor 段落的 material_refs；章首总起段（P4/P16/P24）并入 A 级 claim，不切 C。
c_defs = [
    # ---- P2 引言段（front_matter，按语义归入相应 B）----
    {"parent": "B2.1", "anchor": "P2", "text": "饮茶之风兴于唐盛于宋至北宋始为世重", "sources": ["M1"]},
    {"parent": "B2.1", "anchor": "P2", "text": "茶叶已是盖人家每日不可阙者成为日常必需品", "sources": ["M2"]},
    {"parent": "B3.2", "anchor": "P2", "text": "茶盐之法系朝廷利柄自祖宗以来他司不敢侵紊", "sources": ["M3"]},

    # ==== A1 / B1.1 规模化的茶叶供给（P6 P7 P8）====
    {"parent": "B1.1", "anchor": "P6", "text": "以元丰年间所定二十三路为标准考察北宋湖北政区", "sources": ["M4"]},
    {"parent": "B1.1", "anchor": "P6", "text": "今湖北在北宋地跨京西南荆湖北淮南西江南西夔州五路共十八府州军", "sources": ["M5", "M6", "M7", "M8", "M9"]},
    {"parent": "B1.1", "anchor": "P6", "text": "湖北重要产茶区涵盖襄州南漳兴国军阳新通山江陵府鄂州蒲圻崇阳蕲州蕲春黄梅黄州麻城等地", "sources": ["M10", "M11"]},
    {"parent": "B1.1", "anchor": "P6", "text": "湖北产茶区共十府州军在域内府州军总数中占比达百分之五十五", "sources": ["M11"]},
    {"parent": "B1.1", "anchor": "P6", "text": "景祐元年天下户丁三分其一为产茶州军而湖北产茶比例远高于此", "sources": ["M12"]},
    {"parent": "B1.1", "anchor": "P6", "text": "湖北片茶有枕出江陵岳麓草子等散茶有龙溪雨前雨后等品类丰富", "sources": ["M14", "M15"]},
    {"parent": "B1.1", "anchor": "P7", "text": "表一显示鄂州江陵府与蕲州三场茶叶种类较为丰富且质量上乘", "sources": []},
    {"parent": "B1.1", "anchor": "P7", "text": "因地方史料散佚与重量单位屡经更易北宋全国及各路茶叶产额难以确知", "sources": []},
    {"parent": "B1.1", "anchor": "P7", "text": "除夔州路所辖施州外湖北概行榷茶法便于将全域视作一体计算产量", "sources": []},
    {"parent": "B1.1", "anchor": "P8", "text": "据表二北宋官府在湖北地区买茶额为一千零十万二千七百五十三斤", "sources": ["M16"]},
    {"parent": "B1.1", "anchor": "P8", "text": "夔州路自祖宗以来不榷茶始终行赋税折科与住税过税之税茶政策", "sources": ["M16", "M17"]},
    {"parent": "B1.1", "anchor": "P8", "text": "范镇胪列蜀之产茶八处未及施州可推施州即便产茶产量亦极低", "sources": ["M18"]},
    {"parent": "B1.1", "anchor": "P8", "text": "民岁输税愿折茶者谓之折税茶且民茶折税外匿不送官者没入论罪", "sources": ["M19", "M20"]},
    {"parent": "B1.1", "anchor": "P8", "text": "天禧五年全国折税茶较至道年间增百余万斤后天禧末年又降至七十六万斤", "sources": ["M21"]},
    {"parent": "B1.1", "anchor": "P8", "text": "官府要求茶园户承担每百斤二十至三十五斤耗茶湖北耗茶约二百七十七万斤", "sources": ["M22"]},
    {"parent": "B1.1", "anchor": "P8", "text": "任土作贡的贡茶仅涉湖北少数产区江陵府有碧涧茶芽六百斤", "sources": ["M24"]},
    {"parent": "B1.1", "anchor": "P8", "text": "食茶系官府转售民户之茶已计入买茶额故本文不另计", "sources": ["M25", "M26"]},
    {"parent": "B1.1", "anchor": "P8", "text": "荆湖南北产茶州县铺户自造茶货与铺户私相交易致私茶问题严峻", "sources": ["M27", "M13"]},
    {"parent": "B1.1", "anchor": "P8", "text": "宋太宗遣监察御史薛雄诣沿江诸州禁绝私茶反证民间私茶数量之大", "sources": ["M13"]},
    {"parent": "B1.1", "anchor": "P8", "text": "学界估定私茶数量为买茶额半数至持平约五百万至一千万斤", "sources": ["M23"]},
    {"parent": "B1.1", "anchor": "P8", "text": "湖北茶叶总产量保守计为买茶额折税茶纳耗茶与贡茶共约一千二百九十万斤", "sources": ["M16", "M21", "M22", "M24"]},

    # ==== A1 / B1.2 辐射广阔的茶叶市场（P10 P11）====
    {"parent": "B1.2", "anchor": "P10", "text": "北宋商业市场在空间上分为北方东南蜀川与关陇四域", "sources": ["M28"]},
    {"parent": "B1.2", "anchor": "P10", "text": "湖北凭水网交织的交通北通汴京东连江淮南邻荆湖南路西溯汉江抵达关陇", "sources": ["M28"]},
    {"parent": "B1.2", "anchor": "P10", "text": "学界多以官府与市场权利分配划分茶法可归为榷茶与通商两阶段", "sources": ["M29", "M30", "M31"]},
    {"parent": "B1.2", "anchor": "P10", "text": "湖北榷茶始自建隆年间刘湛奉召榷茶于蕲春", "sources": ["M32"]},
    {"parent": "B1.2", "anchor": "P10", "text": "乾德三年宋太祖采苏晓议榷蕲黄舒庐寿五州茶置十四场岁入百余万缗", "sources": ["M33"]},
    {"parent": "B1.2", "anchor": "P10", "text": "十四场分布于蕲州王祺石桥洗马黄州麻城庐州王同舒州太湖罗源寿州霍山麻步开顺光州商城子安光山", "sources": ["M33"]},
    {"parent": "B1.2", "anchor": "P10", "text": "太平兴国二年于江陵府襄复州无为军增置务至淳化四年废建安襄复州务", "sources": ["M34"]},
    {"parent": "B1.2", "anchor": "P10", "text": "雍熙年间令商人输刍粮塞下授以交引至京师给缗钱并移文江淮荆湖给茶盐", "sources": ["M35"]},
    {"parent": "B1.2", "anchor": "P10", "text": "政和二年蔡京主持制定合同场法以长短引从时空维度规制商人茶叶贸易", "sources": ["M29"]},
    {"parent": "B1.2", "anchor": "P10", "text": "短引止于本路限时一季度许民赴场输息于旁近郡县便鬻", "sources": ["M30"]},
    {"parent": "B1.2", "anchor": "P10", "text": "长引允许茶商销茶至他路限时一年沿路登时批发至所指地计税尽输", "sources": ["M31"]},
    {"parent": "B1.2", "anchor": "P10", "text": "天圣元年仁宗采李谘议行贴射法罢官给本钱使商人与园户自相交易官收其息", "sources": ["M29", "M34"]},
    {"parent": "B1.2", "anchor": "P11", "text": "嘉祐四年通商法正式推行园户官收租钱商贾官收征算而尽罢禁榷", "sources": ["M36"]},
    {"parent": "B1.2", "anchor": "P11", "text": "茶法嬗变使采购对象运输路线与销售区域呈现榷货务与茶源地之别", "sources": ["M36"]},

    # ==== A1 / B1.3 丰厚的茶叶利润（P13 P14）====
    {"parent": "B1.3", "anchor": "P13", "text": "凡茶入官以轻估其出以重估县官之利甚博商贾转致西北其利又特厚", "sources": ["M37"]},
    {"parent": "B1.3", "anchor": "P13", "text": "表三辑录北宋湖北部分茶叶官府收购价与本地及外区出售价格", "sources": ["M37"]},
    {"parent": "B1.3", "anchor": "P14", "text": "榷茶阶段湖北茶叶主要销售地仍为本区鲜有远销黄河以北者", "sources": []},
    {"parent": "B1.3", "anchor": "P14", "text": "官府收购价与销售价差距悬殊如兴国军两府号片茶由四十文升至八百文", "sources": []},
    {"parent": "B1.3", "anchor": "P14", "text": "片茶收购与销售价格普遍高于散茶如第一号一百六十五文远高于散茶草子", "sources": []},
    {"parent": "B1.3", "anchor": "P14", "text": "茶叶售价虽受转运道里影响然品质等级实为决定因素", "sources": []},

    # ==== A2 / B2.1 多元需求拉动茶产量攀升（P18）====
    {"parent": "B2.1", "anchor": "P18", "text": "官府对茶利的倚重与民间饮茶风尚共同驱动湖北农民广泛植茶", "sources": ["M38"]},
    {"parent": "B2.1", "anchor": "P18", "text": "鄂州崇阳县多旷土民不务耕织唯以植茶为业", "sources": ["M38"]},
    {"parent": "B2.1", "anchor": "P18", "text": "谏官余靖指天下二税不足供军故茶盐酒税山泽杂产之利尽归于官", "sources": ["M39"]},
    {"parent": "B2.1", "anchor": "P18", "text": "北宋长期保持大量军队官府为保军需持续鼓励民众种植茶叶等高价值作物", "sources": ["M39"]},
    {"parent": "B2.1", "anchor": "P18", "text": "宋徽宗时期湖北恢复榷茶鼓励植茶其意更在满足皇室用度", "sources": ["M38"]},
    {"parent": "B2.1", "anchor": "P18", "text": "蔡條称茶之尚自唐人始至本朝为盛至祐陵时益穷极新出", "sources": ["M40"]},
    {"parent": "B2.1", "anchor": "P18", "text": "江陵鄂州襄阳等城茶坊林立周边草市亦有大量茶坊供百姓饮茶休闲", "sources": ["M40"]},

    # ==== A2 / B2.2 自然环境助推茶叶生产（P20）====
    {"parent": "B2.2", "anchor": "P20", "text": "陆羽与赵佶均论茶树生长环境称上者生烂石且植产之地崖必阳圃必阴", "sources": ["M41"]},
    {"parent": "B2.2", "anchor": "P20", "text": "湖北山地丘陵居多群山既拦截水汽又为茶树提供富含有机质的土壤", "sources": ["M41", "M42"]},
    {"parent": "B2.2", "anchor": "P20", "text": "北宋时期气候整体偏暖较今高零点三至零点五度使湖北温度更宜茶叶生长", "sources": ["M42"]},
    {"parent": "B2.2", "anchor": "P20", "text": "茶树生长最适温度在十九至三十摄氏度今湖北年均气温十五至十七度", "sources": ["M42"]},

    # ==== A2 / B2.3 地理区位促进茶叶运销（P22）====
    {"parent": "B2.3", "anchor": "P22", "text": "北宋承袭前代路网疏浚河道修缮驿道为湖北茶叶经济提供交通保障", "sources": ["M43"]},
    {"parent": "B2.3", "anchor": "P22", "text": "湖北形成以鄂州汉阳军江陵府为多中心的水运网络且水运载量大价廉", "sources": ["M43"]},
    {"parent": "B2.3", "anchor": "P22", "text": "复州北至郢州私路二百五十里官路三百里形成陆运通道", "sources": ["M43"]},
    {"parent": "B2.3", "anchor": "P22", "text": "东西向长江上中游货物经鄂州至淮南由真州向北流入京师", "sources": ["M44"]},
    {"parent": "B2.3", "anchor": "P22", "text": "南北向广南诸州自桂州由湖南北江陵荆门而至汇聚湖北", "sources": ["M44"]},
    {"parent": "B2.3", "anchor": "P22", "text": "江陵府受纳潭鼎澧岳归峡荆南府片散茶共八十七万五千三百五十七斤", "sources": ["M45"]},

    # ==== A3 / B3.1 塑造沿江经济带（P26）====
    {"parent": "B3.1", "anchor": "P26", "text": "乾德二年京师建安汉阳蕲口并置场榷茶并于黄州江陵蕲州襄州复州设场", "sources": ["M46"]},
    {"parent": "B3.1", "anchor": "P26", "text": "官府以行政权力使设榷场的江陵府汉阳蕲口黄州成为茶叶转运与销售核心城市", "sources": ["M46"]},
    {"parent": "B3.1", "anchor": "P26", "text": "大中祥符至天圣七年茶商因泥水阻滞车牛借路取真扬高邮楚泗州只纳旧路庐寿一路税钱", "sources": ["M47"]},
    {"parent": "B3.1", "anchor": "P26", "text": "仁宗令贩卖蕲口太湖洗马石桥无为军五处场务茶货依汉阳榷务茶例上京", "sources": ["M48"]},
    {"parent": "B3.1", "anchor": "P26", "text": "通商阶段江陵府与汉阳军凭榷茶积累与水利条件核心地位有增无减", "sources": ["M47", "M48"]},
    {"parent": "B3.1", "anchor": "P26", "text": "鄂州虽非六榷务十三茶场节点但因产量高种类丰而受官府与商人重视", "sources": ["M49", "M50"]},
    {"parent": "B3.1", "anchor": "P26", "text": "襄州地处湖北北部且郢州至襄阳尽是滩碛水运条件欠佳故降为辅助地位", "sources": ["M49", "M50"]},
    {"parent": "B3.1", "anchor": "P26", "text": "鄂州与汉阳军隔江相望管下舟车辐辏共同构成沿江经济带核心之一", "sources": ["M50"]},
    {"parent": "B3.1", "anchor": "P26", "text": "茶叶贸易促进船运经济并刺激沿江城镇客栈邸舍经济发展", "sources": ["M51"]},
    {"parent": "B3.1", "anchor": "P26", "text": "湖北形成以江陵府为一核心汉阳军与鄂州为另一核心的双核心沿江经济带", "sources": ["M46", "M51"]},

    # ==== A3 / B3.2 提高政府财政收入（P28 P29）====
    {"parent": "B3.2", "anchor": "P28", "text": "官府视茶叶为征榷体制重要一环使茶利成为国家税收重要来源", "sources": []},
    {"parent": "B3.2", "anchor": "P29", "text": "景德年间茶税旧法得五百六十九万贯新法四百一十万贯后降至二百八十五万贯", "sources": ["M52"]},
    {"parent": "B3.2", "anchor": "P29", "text": "天禧末年北宋财政总收入仅二千六百五十余万贯可窥茶利在财政结构中的地位", "sources": ["M53"]},
    {"parent": "B3.2", "anchor": "P29", "text": "北宋府州军监三百余个中产茶府州军九十七处而湖北独占一府九州", "sources": ["M54"]},
    {"parent": "B3.2", "anchor": "P29", "text": "学者估算北宋茶产量至少八千万至九千万斤至多达一亿五千万斤", "sources": ["M55"]},
    {"parent": "B3.2", "anchor": "P29", "text": "通商法时期令园户之种茶者官收租钱故湖北茶利仍保持较高数额", "sources": ["M56"]},
    {"parent": "B3.2", "anchor": "P29", "text": "六路租茶岁计三十三万八千余贯湖北独当十万二千三百余贯鄂州约占三万九千缗", "sources": ["M56"]},
    {"parent": "B3.2", "anchor": "P29", "text": "北宋商税肇自太祖首定商税则例湖北茶相关船运客店茶坊皆纳入商税体系", "sources": ["M56"]},

    # ==== A3 / B3.3 改变地方民生状态（P31）====
    {"parent": "B3.3", "anchor": "P31", "text": "茶叶经济繁盛为民众开辟多元就业途径大量农民转为茶园户", "sources": ["M57"]},
    {"parent": "B3.3", "anchor": "P31", "text": "城镇茶坊林立商业性饮茶场域增加创造大量就业机会", "sources": ["M57"]},
    {"parent": "B3.3", "anchor": "P31", "text": "茶叶经济发展带动茶文化繁荣原盛行闽地的斗茶传入湖北", "sources": ["M58"]},
    {"parent": "B3.3", "anchor": "P31", "text": "江陵汉阳夜间环境改善在文人推广下夜间饮茶习俗迅速发展", "sources": ["M58"]},
    {"parent": "B3.3", "anchor": "P31", "text": "植茶本是贫民取以为利的手段亦是茶商盈利的根本", "sources": ["M59"]},
    {"parent": "B3.3", "anchor": "P31", "text": "官府频更茶法旧纳茶税今变租钱致茶农与茶商生存环境恶化", "sources": ["M59"]},
    {"parent": "B3.3", "anchor": "P31", "text": "通商法时期茶农赋税仍重江南荆湖茶园户破产亡家或举族而逃或自经而死", "sources": ["M60"]},
    {"parent": "B3.3", "anchor": "P31", "text": "大茶园户兼并个体茶户如石桥场祖额一百七万而近岁买纳才得十万", "sources": ["M61"]},
    {"parent": "B3.3", "anchor": "P31", "text": "宋真宗忧佣力贫民被斥去无用或聚为寇盗", "sources": ["M62"]},
    {"parent": "B3.3", "anchor": "P31", "text": "通商法时期出现小商所贩至少大商绝不通行现象", "sources": ["M62"]},
    {"parent": "B3.3", "anchor": "P31", "text": "湖北茶商群聚暴横被籍为兵号曰茶商军后多赖其用", "sources": ["M63"]},
]

# ============ 手工生成的 B claims ============
b_claims = {
    "B1.1": "湖北茶叶供给呈规模化态势产茶区广品类多官买茶额逾千万斤",
    "B1.2": "湖北茶叶市场随榷茶与通商两阶段茶法嬗变而辐射范围广阔",
    "B1.3": "官府购销价差与片散茶等级差异使湖北茶叶利润丰厚",
    "B2.1": "官府倚重茶利与民间饮茶风尚共同拉动湖北茶产量攀升",
    "B2.2": "湖北群山地形与偏暖气候为茶叶生产提供优渥自然环境",
    "B2.3": "湖北水陆交通枢纽与多中心水运网络促进茶叶运销",
    "B3.1": "榷货务设置与自然区位共同塑造湖北双核心沿江经济带",
    "B3.2": "湖北茶利及茶叶相关商税成为北宋政府财政收入的重要来源",
    "B3.3": "茶叶经济既开辟就业与茶文化又因榷剥致园户破产并催生茶商军",
}

# ============ 手工生成的 A claims ============
a_claims = {
    "A1": "北宋湖北茶叶经济呈现供给规模化市场辐射广利润丰厚的繁盛状貌",
    "A2": "湖北茶叶经济繁盛源于多元需求拉动自然环境适宜与地理区位枢纽三重因素",
    "A3": "湖北茶叶经济繁盛既塑造沿江经济带提高财政收入又改变地方民生状态",
    "A0": "湖北茶叶经济始终与茶法息息相关其繁盛主导权归于中央而非市场规律",
}

# ============ 组装 ============
node_by_id = {n["id"]: n for n in A_defs + B_defs}
parent_order = {n["id"]: pidx[n["title_pid"]] for n in A_defs + B_defs}

enr = []
for i, c in enumerate(c_defs):
    par, anc, txt, srcs = c["parent"], c["anchor"], c["text"], c.get("sources", [])
    if par not in node_by_id:
        print("跳过 C：parent 不存在 %s  text=%s" % (par, txt[:30]))
        continue
    if anc not in {p["id"] for p in paras}:
        print("跳过 C：anchor 非法 %s  text=%s" % (anc, txt[:30]))
        continue
    bad = [m for m in srcs if m not in valid_M]
    if bad:
        print("跳过非法 M %s @%s" % (bad, txt[:20]))
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
        "attribution_method": "引言段 P2 的三条 C 按语义归入 B2.1/B3.2；章首总起段 P4/P16/P24 并入 A 级 claim；"
                              "M13/M23 为 01_引用提取漏绑，按语义补绑至 P8",
        "source_universe": "人类原文脚注 M1-M63",
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
        "M_used_by_C": len(all_used_M),
        "M_unused_by_C": sorted(valid_M - all_used_M, key=m_key),
    },
}
run_path = RUN_DIR / "run.json"
run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
print("[人类基准 run.json 已保存] %s" % run_path)
print("  A=%d  B=%d  C=%d" % (len(A_out), len(B_out), len(C)))
print("  M 使用: %d/%d = %.1f%%" % (len(all_used_M), len(materials), len(all_used_M) / len(materials) * 100))
print("  未使用 M: %s" % sorted(valid_M - all_used_M, key=m_key))
print("  C 分布: %s" % {b["id"]: sum(1 for c in C if c["parent"] == b["id"]) for b in B_out})


# ========================================================================
# 池空间视图：把人类脚注 M 编号折算为史料池 M 编号
# ========================================================================
FN = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def norm_cite(s):
    s = re.sub(r"^[" + FN + r"]+", "", (s or "").strip())
    s = re.sub(r"[\s。，,、．.；;：:·]+", "", s)
    return s.replace("(", "（").replace(")", "）")


pool = json.loads(POOL.read_text(encoding="utf-8"))
pool_pas = [dict(p, src_title=s["title"]) for s in pool["sources"] for p in s["passages"]]
hm = {m["id"]: norm_cite(m.get("text")) for m in materials}
pm = {p["original_id"]: norm_cite(p.get("source_full")) for p in pool_pas}

cand = []
for hid, hk in hm.items():
    for pid, pk in pm.items():
        r = 1.0 if (hk and hk == pk) else difflib.SequenceMatcher(None, hk, pk).ratio()
        cand.append((r, hid, pid))
cand.sort(reverse=True)
h2p, p2h = {}, {}
for r, hid, pid in cand:
    if r < 0.95:
        break
    if hid in h2p:
        continue
    h2p[hid] = pid
    p2h.setdefault(pid, hid)

human_only = sorted(set(hm) - set(h2p), key=m_key)
pool_only = sorted(set(pm) - set(p2h), key=m_key)
print("\n[史料映射] 人类脚注 %d 条，其中 %d 条与史料池条目书目一致" % (len(hm), len(h2p)))
print("  池中无对应的人类脚注 %s" % human_only)
print("  人类脚注无对应的池条目 %s" % pool_only)

# 派生池空间 run.json
pool_M = [{"id": p["original_id"], "text": p.get("text", ""),
           "source_full": p.get("source_full", ""), "title": p.get("src_title", "")}
          for p in sorted(pool_pas, key=lambda x: m_key(x["original_id"]))]

run_p = json.loads(json.dumps(run))
run_p["meta"]["source_universe"] = "史料池 M1-M52（人类脚注经书目匹配折算）"
run_p["meta"]["material_map_note"] = "人类脚注→史料池 M 的折算见 史料映射报告.json"
run_p["encoding_table"]["M_level"] = pool_M
for c in run_p["encoding_table"]["C_level"]:
    c["sources_human"] = list(c["sources"])
    c["sources"] = sorted({h2p[m] for m in c["sources"] if m in h2p}, key=m_key)
for b in run_p["encoding_table"]["B_level"]:
    ms = union_sources(descendants(b["id"], A_defs, B_defs, run_p["encoding_table"]["C_level"]))
    b["sources"], b["source_count"] = sorted(ms, key=m_key), len(ms)
for a in run_p["encoding_table"]["A_level"]:
    if a["id"] == "A0":
        ms = {m["id"] for m in pool_M}
    else:
        ms = union_sources(descendants(a["id"], A_defs, B_defs, run_p["encoding_table"]["C_level"]))
    a["sources"], a["source_count"] = sorted(ms, key=m_key), len(ms)
used_p = set()
for c in run_p["encoding_table"]["C_level"]:
    used_p |= set(c["sources"])
all_pool = {m["id"] for m in pool_M}
run_p["statistics"]["total_unique_M"] = len(all_pool)
run_p["statistics"]["source_count_by_A"] = {a["id"]: a["source_count"] for a in run_p["encoding_table"]["A_level"]}
run_p["statistics"]["source_count_by_B"] = {b["id"]: b["source_count"] for b in run_p["encoding_table"]["B_level"]}
run_p["statistics"]["C_nodes_without_sources"] = sum(1 for c in run_p["encoding_table"]["C_level"] if not c["sources"])
run_p["statistics"]["M_used_by_C_poolspace"] = len(used_p)
run_p["statistics"]["M_unused_by_C_poolspace"] = sorted(all_pool - used_p, key=m_key)
(RUN_DIR / "run_poolspace.json").write_text(json.dumps(run_p, ensure_ascii=False, indent=2), encoding="utf-8")
print("[池空间视图已保存] %s" % (RUN_DIR / "run_poolspace.json"))
print("  池空间 M 使用: %d/%d = %.1f%%" % (len(used_p), len(all_pool), len(used_p) / len(all_pool) * 100))

# 史料映射报告（含双向覆盖指标）
model = json.loads((QA / "Q_run_DS" / "run.json").read_text(encoding="utf-8"))
model_M = {m["id"] for m in model["encoding_table"]["M_level"]}
model_used = set()
for c in model["encoding_table"]["C_level"]:
    model_used |= set(c.get("sources", []))
model_in_human = {p2h[m] for m in model_used if m in p2h}
tp = len(model_in_human)
P = tp / len(model_used) if model_used else 0
R = tp / len(hm) if hm else 0
report = {
    "人类脚注总数": len(hm), "史料池条目总数": len(pm),
    "书目一一对应": len(h2p),
    "人类脚注无池对应": human_only,
    "池条目无人类对应": pool_only,
    "人类脚注→池M": h2p,
    "池M→人类脚注": p2h,
    "池空间": {"人类使用": sorted(used_p, key=m_key), "人类未用": sorted(all_pool - used_p, key=m_key),
               "覆盖率%": round(len(used_p) / len(all_pool) * 100, 1),
               "模型使用": sorted(model_used, key=m_key), "模型覆盖率%": round(len(model_used) / len(all_pool) * 100, 1)},
    "内容空间": {"共同史料": sorted(model_in_human, key=m_key), "模型未覆盖的人类史料": sorted(set(hm) - model_in_human, key=m_key),
                 "模型独有（池外折算）": sorted(model_used - set(p2h), key=m_key),
                 "Precision": round(P, 3), "Recall": round(R, 3),
                 "F1": round(2 * P * R / (P + R), 3) if (P + R) else 0},
}
(RUN_DIR / "史料映射报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("[史料映射报告已保存] %s" % (RUN_DIR / "史料映射报告.json"))
print("  内容空间：共同 %d 条  Precision=%.3f Recall=%.3f F1=%.3f"
      % (tp, P, R, report["内容空间"]["F1"]))
