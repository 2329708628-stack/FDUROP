# 论证结构可复现性实验

检验**论证结构可复现性**：在同一切分工具（大模型）下，不同生成条件（人类写作 / 不同模型 / Q 组与 A 组前置指令）产出的论文，其论点层级树（A–B–C–M）能否被另一篇忠实复现。

> 本项目是**实验代码与管线**，不含任何第三方模型权重、不含 API 密钥。语料与产物（可选）单独存放。

---

## 目录结构

```
Lab/
├── 脚本/
│   ├── 步骤1_原文解析与清洗/     # MinerU 原文 → 原文_clean.json（段落 P / 史料 M 绑定）
│   ├── 步骤2_语料审计/           # 入样条件核查（一手史料引用、多级标题）
│   ├── 步骤3_v3.2抽取/           # v3.2 论证树（A-B-C-M）抽取的确定性实现与校验
│   │   ├── 公共库.py             # 骨架机械推导、编号、sources 并集、论文路径
│   │   ├── run组装器.py          # 输入 C 主张 + claims → 组装完整 run.json
│   │   ├── run校验器.py          # ERROR/WARN 校验（骨架/title/span/sources/编号/并集）
│   │   └── 三轮锚点对比.py       # 多轮重复抽取的骨架/claim/锚点一致性
│   ├── 步骤4_NLI判定/            # NLI 工具评估与选型（mDeBERTa 定阈）
│   ├── 步骤5_稳定性分析/         # 抽取结果跨轮稳定性
│   ├── 步骤6_实验报告/           # docx 报告生成
│   ├── 步骤7_测试验证/           # 边角/负向注入测试
│   └── 步骤8_Q_A_实验/           # 核心：Q vs A 前置指令对照
│       ├── Q_A_NLI判定.py        # 【NLI】两级流水线：句向量余弦召回 → 双向 NLI 判定
│       ├── Q_A对比.py            # 结构/M覆盖/锚点/claim 相似度汇总
│       ├── v3.2自动抽取.py       # 同工具自动抽取（A-B-C 调用 ②③④）
│       ├── 生成对比docx.py       # 对比结果 → docx 表
│       └── ...
├── A01_湖北茶叶经济/            # 案例语料 + 实验输出（产物）
├── requirements.txt
└── README.md
```

## 核心概念：v3.2 论证树

```
A0 全文结论（结语）
 ├─ A1 ── B1.x ── C1.x.y ── sources: [M…]（史料）
 ├─ A2 ── B2.x ── C2.x.y ── sources: [M…]
 └─ …
```
- **A**：章级命题；**B**：节级命题（扁平结构可无）；**C**：段级主张（*叶子节点，一段一论点*，带史料锚点）
- **M**：史料池条目；每条 C 的 `sources` 取自其 anchor 段落引用（自底向上并集）
- `null` 骨架由 `公共库.derive_skeleton` 从标题机械推导，保证跨轮一致
- 结语 STATUS 有两种口径：特殊节点 A0（全文 M 并集）或普通章节点 A4（本项目统一为 A4）

## 安装

```bash
pip install -r requirements.txt
```

NLI 使用的多语言模型：
```
MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
```
首次运行自动下载；离线环境可将 `HF_HOME`/`TRANSFORMERS_OFFLINE=1` 指向本地缓存。

## 快速开始

1. **原文清洗**：`步骤1` 脚本把 MinerU 输出（`00_原文/`）处理为 `原文_clean.json`
2. **骨架 + 组装**：`步骤3` 的 `run组装器.py` 由 C 主张组装完整 v3.2 run
3. **校验**：`run校验器.py <run.json>`（`ERRORS: NONE` 为通过）
4. **语义等价（NLI）**：
   ```bash
   python 脚本/步骤8_Q_A_实验/Q_A_NLI判定.py <gold_run.json> <model_run.json> <out.json> [top_k]
   ```
   Stage1 mDeBERTa 句向量余弦召回（top_k）→ Stage2 双向 NLI，`ACI_J = 1 − Jaccard(概念)`。
5. **对比表**：`生成对比docx.py <comparison> <nli> <输出.docx> <模型标签>`

## Q/A 实验设计

唯一自变量是**前置指令**：
- **Q 组**：*"基于以下史料，分析 X 与 Y 的关系"*
- **A 组**：*"论证以下观点，使用给定史料支撑"*

因变量 = 论证结构的复现度（节点数、史料覆盖 F1、锚点段 Jaccard、C 级 ACI_J）。

## 开源声明
- **不含**：`API.txt`（密钥）、AI 模型权重、Python 依赖包、大体积实验原始产物
- 语料版权归原论文作者，仅作学术研究用途；如需发布语料请自行评估