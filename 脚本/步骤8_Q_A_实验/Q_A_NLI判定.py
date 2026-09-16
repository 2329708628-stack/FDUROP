# -*- coding: utf-8 -*-
"""Q_A 实验：C 层 claim 语义等价判定与 ACI_J（两级流水线优化版）。

两级流水线（项目既定方案）：
  Stage 1 召回：用 mDeBERTa <[BOS_never_used_51bce0c785ca2f68081bfa7d91973934]> 句向量 + 余弦相似度，每篇取 top-K 候选
  Stage 2 精判：仅对候选对做双向 NLI，score_avg=(e_ab+e_ba)/2 >= 0.50 判等义
  聚类：等义关系连通分量 = 概念
  ACI_J = 1 - Jaccard(human_concepts, model_concepts)
用法：python 脚本/步骤8_Q_A_实验/Q_A_NLI判定.py [top_k]
"""
import json, sys, time, os
from pathlib import Path

LAB = Path(r"c:\Users\23297\Downloads\Lab")
os.environ["HF_HOME"] = str(LAB / ".hf_cache")
os.environ["TRANSFORMERS_OFFLINE"] = "1"
sys.path.insert(0, str(LAB / ".pylibs"))
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

MODEL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
THETA = 0.50

QA_DIR = LAB / "A01_湖北茶叶经济" / "03_实验输出" / "Q_A_实验"
# 默认值（向后兼容）：python Q_A_NLI判定.py [top_k]
# 命令行参数：python Q_A_NLI判定.py <gold_run.json> <model_run.json> <out.json> [top_k]
if len(sys.argv) >= 4 and sys.argv[1].endswith(".json"):
    GOLD = Path(sys.argv[1])
    MODEL_RUN = Path(sys.argv[2])
    OUT = Path(sys.argv[3])
    TOP_K = int(sys.argv[4]) if len(sys.argv) > 4 else 15
else:
    GOLD = QA_DIR / "Q_human_baseline" / "run.json"
    MODEL_RUN = QA_DIR / "Q_run_2" / "run.json"
    OUT = QA_DIR / "Q_run_2" / "Q_A_nli_equivalence.json"
    TOP_K = int(sys.argv[1]) if len(sys.argv) > 1 else 15


def load_claims(run_path, run_label):
    d = json.load(open(run_path, encoding="utf-8"))
    return [{"atom": f"{run_label}_{c['id']}", "run": run_label,
             "node_id": c["id"], "text": c["text"], "sources": c.get("sources", [])}
            for c in d["encoding_table"]["C_level"]]


@torch.no_grad()
def encode(tok, mdl, texts, batch=64, max_len=64):
    embs = []
    for s in range(0, len(texts), batch):
        bt = texts[s:s + batch]
        enc = tok(bt, return_tensors="pt", truncation=True, max_length=max_len, padding=True)
        out = mdl(**enc)
        # <[BOS_never_used_51bce0c785ca2f68081bfa7d91973934]> 向量作句向量
        cls = out.last_hidden_state[:, 0, :].cpu().numpy()
        embs.append(cls)
    return np.concatenate(embs, axis=0)


def cosine_matrix(A, B):
    An = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
    Bn = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-9)
    return An @ Bn.T


def main():
    human = load_claims(GOLD, "human")
    model = load_claims(MODEL_RUN, "model")
    all_claims = human + model
    n_h, n_m = len(human), len(model)
    print(f"载入 claim：human={n_h}  model={n_m}  total={n_h+n_m}", flush=True)

    print(f"加载模型 {MODEL} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL)
    mdl = AutoModel.from_pretrained(MODEL)
    mdl.eval()

    # Stage 1: 句向量召回
    print("Stage 1: 句向量编码 ...", flush=True)
    t0 = time.time()
    h_texts = [c["text"] for c in human]
    m_texts = [c["text"] for c in model]
    h_emb = encode(tok, mdl, h_texts)
    m_emb = encode(tok, mdl, m_texts)
    print(f"  编码完成 {time.time()-t0:.0f}s  h_emb={h_emb.shape} m_emb={m_emb.shape}", flush=True)

    sim = cosine_matrix(h_emb, m_emb)  # (n_h, n_m)
    # 每个 human claim 取 top-K model claim；每个 model claim 取 top-K human claim（双向召回，防漏）
    candidates = set()
    for i in range(n_h):
        top = np.argsort(sim[i])[::-1][:TOP_K]
        for j in top:
            candidates.add((i, j))
    for j in range(n_m):
        top = np.argsort(sim[:, j])[::-1][:TOP_K]
        for i in top:
            candidates.add((i, j))
    print(f"  候选对: {len(candidates)}（全量 {n_h*n_m}，压缩至 {len(candidates)/(n_h*n_m)*100:.1f}%）", flush=True)

    # Stage 2: 双向 NLI 精判
    # 复用 mDeBERTa 做 NLI：需加载分类头。重新加载为 SequenceClassification。
    print("Stage 2: 加载 NLI 分类头 ...", flush=True)
    from transformers import AutoModelForSequenceClassification
    mdl_nli = AutoModelForSequenceClassification.from_pretrained(MODEL)
    mdl_nli.eval()
    id2label = {int(k): v.lower() for k, v in mdl_nli.config.id2label.items()}
    col = {lab: i for i, lab in id2label.items()}
    ie = col.get("entailment", 0)

    cand_list = sorted(candidates)
    print(f"  双向 NLI 推理 {len(cand_list)*2} 次 ...", flush=True)
    t0 = time.time()

    def run_nli(prem_texts, hyp_texts):
        probs = []
        BATCH = 64
        for s in range(0, len(prem_texts), BATCH):
            enc = tok(prem_texts[s:s + BATCH], hyp_texts[s:s + BATCH],
                      return_tensors="pt", truncation=True, max_length=128, padding=True)
            with torch.no_grad():
                logits = mdl_nli(**enc).logits
            pr = torch.softmax(logits, dim=-1)
            probs.extend(pr[:, ie].tolist())
        return probs

    prems_ab = [human[i]["text"] for i, j in cand_list]
    hyps_ab = [model[j]["text"] for i, j in cand_list]
    prems_ba = [model[j]["text"] for i, j in cand_list]
    hyps_ba = [human[i]["text"] for i, j in cand_list]
    e_ab = run_nli(prems_ab, hyps_ab)
    print(f"  dir ab 完成 {time.time()-t0:.0f}s", flush=True)
    e_ba = run_nli(prems_ba, hyps_ba)
    print(f"  dir ba 完成 {time.time()-t0:.0f}s", flush=True)

    # 等义判定 + 连通分量
    results = {}
    parent = list(range(n_h + n_m))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    eq_edges = 0
    for k, (i, j) in enumerate(cand_list):
        sa = (e_ab[k] + e_ba[k]) / 2
        results[(i, j)] = {"e_ab": round(e_ab[k], 4), "e_ba": round(e_ba[k], 4),
                           "score_avg": round(sa, 4), "equivalent": sa >= THETA}
        if sa >= THETA:
            union(i, n_h + j)
            eq_edges += 1
    print(f"等义边: {eq_edges}", flush=True)

    comps = {}
    for i in range(n_h + n_m):
        comps.setdefault(find(i), []).append(i)
    concepts = []
    for idx, members in enumerate(sorted(comps.values(), key=lambda x: -len(x)), 1):
        concepts.append({"concept_id": f"c{idx}",
                         "members": [all_claims[m] for m in members]})

    atom2c = {}
    for c in concepts:
        for m in c["members"]:
            atom2c[m["atom"]] = c["concept_id"]
    hc = set(atom2c[a["atom"]] for a in human)
    mc = set(atom2c[a["atom"]] for a in model)
    inter = hc & mc
    union_s = hc | mc
    jaccard = len(inter) / len(union_s) if union_s else 1.0
    aci_j = 1 - jaccard

    print("=" * 60)
    print(f"概念总数: {len(concepts)}")
    print(f"人类基准概念: {len(hc)}  模型概念: {len(mc)}")
    print(f"交集 {len(inter)} / 并集 {len(union_s)}")
    print(f"Jaccard = {jaccard:.4f}")
    print(f"ACI_J   = {aci_j:.4f}  (越低越收敛)")
    print("=" * 60)

    shared = [c for c in concepts if c["concept_id"] in inter]
    print(f"共享概念: {len(shared)}  仅人类: {len(hc)-len(inter)}  仅模型: {len(mc)-len(inter)}")
    print("\n共享概念示例（前10）:")
    for c in shared[:10]:
        mems = c["members"]
        print(f"  {c['concept_id']} (size={len(mems)}): {mems[0]['text'][:30]} ...")

    report = {
        "model": MODEL, "theta": THETA, "metric": "score_avg",
        "top_k": TOP_K,
        "n_human": n_h, "n_model": n_m,
        "candidate_pairs": len(cand_list), "candidate_pct": round(len(cand_list)/(n_h*n_m)*100, 1),
        "eq_edges": eq_edges, "n_concepts": len(concepts),
        "human_concepts": len(hc), "model_concepts": len(mc),
        "intersection": len(inter), "union": len(union_s),
        "jaccard": round(jaccard, 4), "aci_j": round(aci_j, 4),
        "shared_concepts": len(shared),
        "human_only_concepts": len(hc) - len(inter),
        "model_only_concepts": len(mc) - len(inter),
        "concepts": concepts,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已保存: {OUT}")


if __name__ == "__main__":
    main()
