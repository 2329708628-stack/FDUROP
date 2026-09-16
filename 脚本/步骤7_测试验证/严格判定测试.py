# -*- coding: utf-8 -*-
"""
严格判定小测试：在 P33/P6 上对比不同模型/批量大小/提示词的判定质量
"""
import json, os, sys, time, itertools
sys.path.insert(0, r"c:\Users\23297\Downloads\Lab\脚本\步骤3_v3.2抽取")

LAB_DIR = r"c:\Users\23297\Downloads\Lab"
RUN_DIR = os.path.join(LAB_DIR, "A01_湖北茶叶经济", "03_实验输出", "H1_v3.2")
NORM_DIR = os.path.join(LAB_DIR, "语义归一化脚本", "语义归一化实施包")
API_FILE = os.path.join(LAB_DIR, "API.txt")

with open(API_FILE, encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]
API_KEY, BASE_URL = lines[0], lines[1]

for d in os.listdir(NORM_DIR):
    full = os.path.join(NORM_DIR, d)
    if os.path.isdir(full) and "MACOSX" not in d:
        NORM_SUB = full
        break

with open(os.path.join(NORM_SUB, "normalization_prompts.json"), encoding="utf-8") as f:
    PROMPTS = json.load(f)

from openai import OpenAI
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def llm_chat(model, system_prompt, user_msg, temperature=0.0):
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_msg}],
        temperature=temperature, stream=True)
    return "".join(c.choices[0].delta.content for c in stream if c.choices and c.choices[0].delta.content)

def llm_json(model, system_prompt, user_msg, retries=3):
    for attempt in range(retries):
        try:
            text = llm_chat(model, system_prompt, user_msg).strip()
            if text.startswith("```"):
                text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("```"))
            return json.loads(text)
        except Exception as e:
            print(f"    retry {attempt+1}: {e}")
            time.sleep(3)
    return None

# 组员原始严谨单对 system prompt（要求双向蕴含）
STRICT_SYSTEM = PROMPTS["pair_decision"]["system"]

def strict_batch(model, pairs_data, batch_size):
    """小批量严格判定，要求每对输出双向蕴含字段；批次内用短序号防 ID 改写"""
    all_results = []
    for s in range(0, len(pairs_data), batch_size):
        batch = pairs_data[s:s+batch_size]
        items = [{"pair_id": f"q{k+1}",
                  "A": p["A"]["text"], "B": p["B"]["text"]}
                 for k, p in enumerate(batch)]
        user = ("逐对判定下列命题。仅当双向互相蕴含且关键限定（主体/时空/数量/肯否/"
                "因果方向/状态或变化/认识强度）完全一致才判EQUIVALENT。"
                "同主题或同含数字不等于等义。输出JSON数组，每元素含 "
                "pair_id, label(EQUIVALENT/A_ENTAILS_B/B_ENTAILS_A/CONTRADICTION/DIFFERENT/UNCERTAIN),"
                "a_entails_b, b_entails_a, reason：\n"
                + json.dumps(items, ensure_ascii=False, indent=1))
        r = llm_json(model, STRICT_SYSTEM, user)
        if isinstance(r, dict):
            r = [r]
        if r:
            # 短序号映射回全局 pair_id
            id_map = {f"q{k+1}": p["pair_id"] for k, p in enumerate(batch)}
            for item in r:
                if isinstance(item, dict):
                    short = item.get("pair_id", "")
                    item["pair_id"] = id_map.get(short, short)
            all_results.extend(r)
        time.sleep(0.5)
    return all_results

def load_pairs(anchor):
    """加载指定 anchor 的跨轮配对（使用原始 run 数据）"""
    runs = {}
    for i in range(1, 4):
        with open(os.path.join(RUN_DIR, f"run_{i}.json"), encoding="utf-8") as f:
            data = json.load(f)
        runs[f"run_{i}"] = [c for c in data["encoding_table"]["C_level"] if c.get("anchor") == anchor]
    pairs = []
    for ri, rj in itertools.combinations(["run_1","run_2","run_3"], 2):
        for ci in runs[ri]:
            for cj in runs[rj]:
                pairs.append({"pair_id": f"{ri}_{ci['id']}__{rj}_{cj['id']}",
                              "ri_rj": f"{ri}x{rj}",
                              "A": {"text": ci["text"]}, "B": {"text": cj["text"]}})
    return pairs

def evaluate(anchor, model, batch_size):
    pairs = load_pairs(anchor)
    print(f"\n{'='*70}\n{anchor} | model={model} | batch={batch_size} | pairs={len(pairs)}", flush=True)
    results = strict_batch(model, pairs, batch_size)
    print(f"返回结果条数: {len(results)} (期望 {len(pairs)})", flush=True)
    # 调试：检查 pair_id 覆盖
    returned_ids = {x.get("pair_id") for x in results if isinstance(x, dict)}
    missing = [p["pair_id"] for p in pairs if p["pair_id"] not in returned_ids]
    if missing:
        print(f"未覆盖 pair_id {len(missing)} 条，示例: {missing[:3]}", flush=True)
    rmap = {x.get("pair_id"): x for x in results if isinstance(x, dict)}

    labels = {}
    for p in pairs:
        r = rmap.get(p["pair_id"], {})
        lab = (r.get("label") or "UNCERTAIN").upper()
        labels[p["pair_id"]] = lab

    # 手工金标准集合（pair_id 集合）
    GOLD = {
        "P33": None,  # 用位置规则
        "P6": {
            # 23路行政区划
            "run_1_C1.1.1__run_2_C1.1.1", "run_1_C1.1.1__run_3_C1.1.1", "run_2_C1.1.1__run_3_C1.1.1",
            # 蕲州三场十三山场
            "run_1_C1.1.4__run_2_C1.1.3", "run_1_C1.1.4__run_3_C1.1.3", "run_2_C1.1.3__run_3_C1.1.3",
            # 景祐三分之一
            "run_1_C1.1.5__run_2_C1.1.4", "run_1_C1.1.5__run_3_C1.1.4", "run_2_C1.1.4__run_3_C1.1.4",
            # 片茶散茶品种
            "run_1_C1.1.6__run_2_C1.1.5", "run_1_C1.1.6__run_3_C1.1.5", "run_2_C1.1.5__run_3_C1.1.5",
            # 注意：r1.C1.1.2(18府州)、r1.C1.1.3(10产茶55%) 与 r2/r3.C1.1.2(合并条)
            # 是单向蕴含，非 EQUIVALENT —— 故意不放入金标准
        },
    }
    # 单向蕴含金标准（P6 拆合案例）
    GOLD_ENTAIL = {
        "P6": {
            "run_1_C1.1.2__run_2_C1.1.2", "run_1_C1.1.3__run_2_C1.1.2",
            "run_1_C1.1.2__run_3_C1.1.2", "run_1_C1.1.3__run_3_C1.1.2",
        }
    }

    import re
    def node_of(key):
        return re.sub(r"^run_\d+_", "", key)

    if anchor == "P33":
        tp=fp=tn=fn=0
        fps=[]
        for p in pairs:
            left, right = p["pair_id"].split("__")
            gold_eq = (node_of(left) == node_of(right))
            pred_eq = labels[p["pair_id"]] == "EQUIVALENT"
            if gold_eq and pred_eq: tp+=1
            elif not gold_eq and pred_eq:
                fp+=1
                fps.append((p["pair_id"], p["A"]["text"][:20], p["B"]["text"][:20]))
            elif not gold_eq and not pred_eq: tn+=1
            else: fn+=1
        print(f"金标准评估: TP={tp} FP={fp} TN={tn} FN={fn}", flush=True)
        print(f"精确率={tp/(tp+fp) if tp+fp else 0:.2%} 召回率={tp/(tp+fn) if tp+fn else 0:.2%}", flush=True)
        if fps:
            print("假阳性案例:", flush=True)
            for x in fps: print("  FP:", x, flush=True)

    if anchor == "P6":
        gold_eq_set = GOLD["P6"]
        gold_ent_set = GOLD_ENTAIL["P6"]
        tp=fp=tn=fn=0
        fps=[]
        ent_ok=ent_bad=0
        for p in pairs:
            pid = p["pair_id"]
            gold_eq = pid in gold_eq_set
            pred = labels[pid]
            pred_eq = pred == "EQUIVALENT"
            if gold_eq and pred_eq: tp+=1
            elif not gold_eq and pred_eq:
                fp+=1
                fps.append((pid, p["A"]["text"][:22], p["B"]["text"][:22]))
            elif not gold_eq and not pred_eq: tn+=1
            else: fn+=1
            if pid in gold_ent_set:
                if "ENTAILS" in pred: ent_ok+=1
                else:
                    ent_bad+=1
                    print(f"  拆合案未判蕴含: {pid} -> {pred}", flush=True)
        print(f"等义金标准: TP={tp} FP={fp} TN={tn} FN={fn}", flush=True)
        print(f"精确率={tp/(tp+fp) if tp+fp else 0:.2%} 召回率={tp/(tp+fn) if tp+fn else 0:.2%}", flush=True)
        print(f"拆合案单向蕴含识别: {ent_ok}/{ent_ok+ent_bad}", flush=True)
        if fps:
            print("假阳性案例:", flush=True)
            for x in fps: print("  FP:", x, flush=True)

    # 保存完整结果
    out_path = os.path.join(RUN_DIR, "_equivalence", f"strict_test_{anchor}_{model.replace('-','_')}.json")
    detail = [{"pair_id": p["pair_id"], "label": labels[p["pair_id"]],
               "A": p["A"]["text"], "B": p["B"]["text"],
               "raw": rmap.get(p["pair_id"], {})} for p in pairs]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2)
    print(f"明细已存: {out_path}", flush=True)

    # 标签分布
    from collections import Counter
    print("标签分布:", Counter(labels.values()), flush=True)
    return labels

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "GLM-4-Flash"
    anchors = sys.argv[2].split(",") if len(sys.argv) > 2 else ["P33"]
    for a in anchors:
        evaluate(a.strip(), model, 5)
