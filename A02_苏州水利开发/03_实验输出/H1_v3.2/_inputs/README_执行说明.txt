A01 v3.2 五调用实验输入（脚本自动生成）

【骨架】A=3  B=7  front_matter=['P2']
  扁平结构（B 为空）的论文：调用③跳过，C 直接挂 A。

【执行步骤——本地窗口手动操作】
1. 新开空白对话窗口（独立会话）。
2. 粘贴 提示词_H1_v3.2.txt 的【提示词正文】（从"你是历史学论文论证结构形式化编码器"到末尾），等模型确认理解。
3. 调用①：骨架已由脚本确定性产出（skeleton.json），无需让模型再跑；
   实验时把 skeleton.json 内容贴给模型，声明"调用①产物如下，直接使用"。
4. 调用②：把 call2_C_input.json 全文贴给模型，要求产出 C_level 数组。
   保存模型输出为 C_level.json。
5. 调用③：把 call3_B_inputs/ 下每个 .json 逐个贴给模型，要求产出
   该节点 1 条 claim。所有节点合起来保存为 B_claims.json：
   [{"id":"B1.1","claim":"…"}, …]
   重要：每个节点的输入只含该节点 title_label+span 段落，禁止让模型看到
   其他节点或 C 级输出。
6. 调用④：把 call4_A_inputs/ 下每个 .json 逐个贴给模型，产出 A_claims.json：
   [{"id":"A1","claim":"…"}, …，{"id":"A0","claim":"…"}]
7. 调用⑤：新开窗口，贴提示词正文 + skeleton.json + C_level.json +
   B_claims.json + A_claims.json + call5_inputs.json（含段落和材料清单），
   要求模型做支持核查并输出最终一份 JSON。
8. 最终 JSON 保存为 run_1.json，用 check_run.py 校验：
   python 脚本/check_run.py A01_湖北茶叶经济/03_实验输出/H1_v3.2/run_1.json
9. 重复步骤 1-8 共 5 轮（每轮独立会话），最后跑：
   python 脚本/compare_anchors.py A01_湖北茶叶经济

【简化路径——单窗口顺序执行（预实验可用）】
同一窗口按①→②→③→④→⑤顺序执行，但执行③④时严格遵守"只看本节点 span 段落"
的规则，假定未见过②③的论点文本。

【文件清单】
_inputs/skeleton.json          调用①产物（脚本产出）
_inputs/call2_C_input.json     调用②输入
_inputs/call3_B_inputs/*.json  调用③输入（每节点 1 个）
_inputs/call4_A_inputs/*.json  调用④输入（每节点 1 个）
_inputs/call5_inputs.json      调用⑤输入
