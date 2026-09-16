# -*- coding: utf-8 -*-
"""
原文解析
============
对 原文.json（原 layout.json）中 preproc_blocks 的 type 字段做结构化识别。
"""

import re

# 匹配标题块（论文标题、章节标题）
PATTERN_00_001 = re.compile(r"^title$")
# 用途：匹配 block.type == "title"，识别标题块

# 匹配正文文本块
PATTERN_00_002 = re.compile(r"^text$")
# 用途：匹配 block.type == "text"，识别正文块

# 匹配脚注块（页脚注释）
PATTERN_00_003 = re.compile(r"^page_footnote$")
# 用途：匹配 block.type == "page_footnote"，识别脚注块

# 匹配页码/页眉块
PATTERN_00_004 = re.compile(r"^footer$")
# 用途：匹配 block.type == "footer"，识别页码页眉块
