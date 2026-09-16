# -*- coding: utf-8 -*-
"""
NLI 工具验证（金标准：P33 48对 + P6 85对 = 133对人工标定）
=================================================================
对每对命题双向推理（A→B, B→A），得到蕴含/中立/矛盾概率。
等义判定：双向蕴含概率都高。
  - score_min = min(e_ab, e_ba)      （严格：两个方向都必须高）
  - score_avg = (e_ab + e_ba) / 2    （方案口径：算术平均）
扫阈值 θ∈[0.50, 0.95]，与金标准比对，输出 P/R/F1。
P6 另查 4 对"拆合"案例：应表现为单向蕴含（一个方向高、另一个低）。

模型：
  1. MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7  多语言
  2. IDEA-CCNL/Erlangshen-MegatronBert-1.3B-NLI                  中文原生
"""
import json, os, re, sys, time
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

EQ_DIR = r"c:\Users\23297\Downloads\Lab\A01_湖北茶叶经济\03_实验输出\H1_v3.2\_equivalence"

# P6 金标准（与 严格判定测试.py 一致）
GOLD_EQ_P6 = {
    "run_1_C1.1.1__run_2_C1.1.1", "run_1_C1.1.1__run_3_C1.1.1", "run_2_C1.1.1__run_3_C1.1.1",
    "run_1_C1.1.4__run_2_C1.1.3", "run_1_C1.1.4__run_3_C1.1.3", "run_2_C1.1.3__run_3_C1.1.3",
    "run_1_C1.1.5__run_2_C1.1.4", "run_1_C1.1.5__run_3_C1.1.4", "run_2_C1.1.4__run_3_C1.1.4",
    "run_1_C1.1.6__run_2_C1.1.5", "run_1_C1.1.6__run_3_C1.1.5", "run_2_C1.1.5__run_3_C1.1.5",
}
GOLD_ENTAIL_P6 = {
    "run_1_C1.1.2__run_2_C1.1.2", "run_1_C1.1.3__run_2_C1.1.2",
    "run_1_C1.1.2__run_3_C1.1.2", "run_1_C1.1.3__run_3_C1.1.2",
}

MODELS = {
    "mdeberta": "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
    "erlangshen": "IDEA-CCNL/Erlangshen-MegatronBert-1.3B-NLI",
}


def load_pairs():
    pairs = []
    for anchor, fname in [("P33", "strict_test_P33_GLM_4_Flash.json"),
                          ("P6", "strict_test_P6_GLM_4_Flash.json")]:
        data = json.load(open(os.path.join(EQ_DIR, fname), encoding="utf-8"))
        for d in data:
            pairs.append({"anchor": anchor, "pair_id": d["pair_id"],
                          "A": d["A"], "B": d["B"]})
    return pairs


def gold_label(p):
    """返回 'eq'（等义）/ 'entail'（单向蕴含）/ 'diff'（不等义）"""
    pid = p["pair_id"]
    if p["anchor"] == "P33":
        left, right = pid.split("__")
        node = lambda k: re.sub(r"^run_\d+_", "", k)
        return "eq" if node(left) == node(right) else "diff"
    if pid in GOLD_EQ_P6:
        return "eq"
    if pid in GOLD_ENTAIL_P6:
        return "entail"
    return "diff"


def run_model(model_key, pairs):
    name = MODELS[model_key]
    print(f"\n=== 加载模型: {name} ===", flush=True)
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForSequenceClassification.from_pretrained(name)
    model.eval()

    # 统一标签映射：找到 entailment/neutral/contradiction 的列号
    id2label = {int(k): v.lower() for k, v in model.config.id2label.items()}
    print("标签映射:", id2label, flush=True)
    col = {lab: i for i, lab in id2label.items()}
    ie, ic = col.get("entailment", 0), col.get("contradiction", 2)

    results = []
    t0 = time.time()
    with torch.no_grad():
        for k, p in enumerate(pairs):
            # 双向推理
            probs = {}
            for direction, (prem, hyp) in {"ab": (p["A"], p["B"]),
                                           "ba": (p["B"], p["A"])}.items():
                enc = tok(prem, hyp, return_tensors="pt", truncation=True, max_length=256)
                logits = model(**enc).logits[0]
                pr = torch.softmax(logits, dim=-1)
                probs[direction] = {"entail": float(pr[ie]),
                                    "contradict": float(pr[ic]),
                                    "neutral": float(pr[col.get("neutral", 1)])}
            e_ab, e_ba = probs["ab"]["entail"], probs["ba"]["entail"]
            results.append({
                "anchor": p["anchor"], "pair_id": p["pair_id"],
                "gold": gold_label(p), "A": p["A"], "B": p["B"],
                "e_ab": round(e_ab, 4), "e_ba": round(e_ba, 4),
                "c_ab": round(probs["ab"]["contradict"], 4),
                "c_ba": round(probs["ba"]["contradict"], 4),
                "score_min": round(min(e_ab, e_ba), 4),
                "score_avg": round((e_ab + e_ba) / 2, 4),
            })
            if (k + 1) % 20 == 0:
                print(f"  {k+1}/{len(pairs)}  用时 {time.time()-t0:.0f}s", flush=True)
    print(f"推理完成，用时 {time.time()-t0:.0f}s", flush=True)
    return results


def sweep(results, score_key):
    """扫阈值，等义二分类评估（gold eq=正例，其余=负例）"""
    rows = []
    for theta in [x / 100 for x in range(50, 96, 5)]:
        tp = fp = tn = fn = 0
        for r in results:
            pred_eq = r[score_key] >= theta
            gold_eq = r["gold"] == "eq"
            if pred_eq and gold_eq: tp += 1
            elif pred_eq and not gold_eq: fp += 1
            elif not pred_eq and not gold_eq: tn += 1
            else: fn += 1
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        rows.append((theta, tp, fp, tn, fn, prec, rec, f1))
    return rows


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "mdeberta"
    pairs = load_pairs()
    gold_counts = {}
    for p in pairs:
        gold_counts[gold_label(p)] = gold_counts.get(gold_label(p), 0) + 1
    print(f"金标准分布: {gold_counts}（共 {len(pairs)} 对）")

    results = run_model(which, pairs)
    out = os.path.join(EQ_DIR, f"nli_{which}_results.json")
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 阈值扫描
    for key in ["score_min", "score_avg"]:
        print(f"\n--- 等义判定阈值扫描（{key}）---")
        print(f"{'θ':>5} {'TP':>3} {'FP':>3} {'TN':>3} {'FN':>3} {'精确率':>7} {'召回率':>7} {'F1':>6}")
        for theta, tp, fp, tn, fn, prec, rec, f1 in sweep(results, key):
            print(f"{theta:5.2f} {tp:3d} {fp:3d} {tn:3d} {fn:3d} {prec:7.1%} {rec:7.1%} {f1:6.3f}")

    # 拆合案例（单向蕴含）：应 e 单向高
    print("\n--- P6 拆合案例（金标准：单向蕴含）---")
    print(f"{'pair_id':<40} {'e_ab':>6} {'e_ba':>6} {'min':>6}")
    for r in results:
        if r["gold"] == "entail":
            print(f"{r['pair_id']:<40} {r['e_ab']:6.2f} {r['e_ba']:6.2f} {r['score_min']:6.2f}")

    # 假阳性明细（θ=0.85, min 口径）
    print("\n--- θ=0.85/min 口径下的错误案例 ---")
    for r in results:
        pred = r["score_min"] >= 0.85
        if pred != (r["gold"] == "eq"):
            kind = "FP" if pred else "FN"
            print(f"[{kind}] {r['pair_id']}  min={r['score_min']:.2f} avg={r['score_avg']:.2f}  gold={r['gold']}")
            print(f"     A: {r['A'][:45]}")
            print(f"     B: {r['B'][:45]}")

    print(f"\n明细已保存: {out}")


if __name__ == "__main__":
    main()
