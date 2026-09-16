# -*- coding: utf-8 -*-
"""探查 RexUniNLU 的 NLI 调用方式与输出结构（是否含概率）"""
import os, sys, json, functools
sys.path.insert(0, r"c:\Users\23297\Downloads\Lab\.pylibs")
os.environ["MODELSCOPE_CACHE"] = r"c:\Users\23297\Downloads\Lab\.ms_cache"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# 兼容旧版远程代码：新版 transformers 移除了若干 API，逐个补桩
import transformers.utils as _tu
if not hasattr(_tu, "cached_property"):
    _tu.cached_property = functools.cached_property
if not hasattr(_tu, "get_full_repo_name"):
    _tu.get_full_repo_name = lambda *a, **k: ""
for _name in ("is_sagemaker_dp_enabled", "is_sagemaker_mp_enabled",
              "is_torch_bf16_available", "is_torch_tf32_available",
              "is_torch_tpu_available"):
    if not hasattr(_tu, _name):
        setattr(_tu, _name, lambda *a, **k: False)

from modelscope.pipelines import pipeline

# 新版 transformers Trainer：tokenizer 参数改名为 processing_class
import transformers
_orig_trainer_init = transformers.Trainer.__init__
def _patched_trainer_init(self, *args, **kwargs):
    if "tokenizer" in kwargs and "processing_class" not in kwargs:
        kwargs["processing_class"] = kwargs.pop("tokenizer")
    return _orig_trainer_init(self, *args, **kwargs)
transformers.Trainer.__init__ = _patched_trainer_init
# prediction_step 访问 self.tokenizer，映射到 processing_class
transformers.Trainer.tokenizer = property(lambda self: self.processing_class)

pipe = pipeline(task='rex-uninlu', model='iic/nlp_deberta_rex-uninlu_chinese-base')

# 新版 slow BertTokenizer 丢失 additional_special_tokens 相关属性，补回
_tok = pipe.trainer.tokenizer
_sp_tokens = ["[PREFIX]", "[TYPE]", "[CLASSIFY]", "[MULTICLASSIFY]"]
if not hasattr(_tok, "additional_special_tokens") or not _tok.additional_special_tokens:
    _tok.additional_special_tokens = _sp_tokens
if not hasattr(_tok, "additional_special_tokens_ids") or not _tok.additional_special_tokens_ids:
    _tok.additional_special_tokens_ids = _tok.convert_tokens_to_ids(_sp_tokens)

prem = "北宋湖北地区茶叶年产量至少逾一千三百余万斤"
hyp_eq = "北宋湖北茶叶年产量至少逾1300万斤"          # 等义
hyp_diff = "茶叶经济增益政府财源并影响地方民生"          # 无关
hyp_contra = "北宋湖北地区茶叶年产量不足一百万斤"        # 矛盾

# 尝试 1：NLI 标准 schema（三分类标签），文本须含 [CLASSIFY] 标记
for schema in [
    {"蕴含": None, "中立": None, "矛盾": None},
]:
    print("=" * 60)
    print("schema =", schema)
    for tag, hyp in [("等义", hyp_eq), ("无关", hyp_diff), ("矛盾", hyp_contra)]:
        try:
            text = f"前提：{prem}[SEP]假设：{hyp}[CLASSIFY]"
            r = pipe(input=text, schema=schema)
            print(f"[{tag}] ->", json.dumps(r, ensure_ascii=False)[:400])
        except Exception as e:
            print(f"[{tag}] ERROR: {e}")

# 尝试 2：句对直接拼接（无"前提/假设"字样）
print("=" * 60)
print("纯句对拼接格式：")
for tag, hyp in [("等义", hyp_eq), ("无关", hyp_diff), ("矛盾", hyp_contra)]:
    try:
        text = f"{prem}[SEP]{hyp}[CLASSIFY]"
        r = pipe(input=text, schema={"蕴含": None, "中立": None, "矛盾": None})
        print(f"[{tag}] ->", json.dumps(r, ensure_ascii=False)[:400])
    except Exception as e:
        print(f"[{tag}] ERROR: {e}")
