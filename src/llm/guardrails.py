# -*- coding: utf-8 -*-
"""
Guardrails：輸出安全檢查與補強
"""
import re
from typing import List, Dict

def append_hallucination_warning_if_needed(report: str, allowed_urls: List[str]) -> str:
    # 粗略檢查：有數字但來源區塊沒有任何引用時，提醒人工檢查
    has_number = re.search(r"\d+(\.\d+)?", report) is not None
    has_sources = ("# 來源" in report) and ("<" in report and ">" in report)
    if has_number and not has_sources:
        report += "\n\n[警告] 報告包含數字但未列出引用，請人工審閱。"
    # 若出現「可能」「猜測」等詞，提醒
    if re.search(r"猜測|臆測|推測|大概|也許", report):
        report += "\n\n[警告] 報告可能包含不確定描述，請人工審閱。"
    return report

def ensure_missing_section_mark(report: str) -> str:
    required = ["# 市場總結", "# 產業", "# 個股", "# 風險提示"]
    for sec in required:
        if sec not in report:
            report += f"\n\n{sec}\n無足夠信息\n"
    # 若段落存在但內容全空，補上無足夠信息
    report = re.sub(r"(# (市場總結|產業|個股|風險提示)\s*)(?=\n#|\Z)", r"\1\n無足夠信息\n", report, flags=re.M)
    return report
