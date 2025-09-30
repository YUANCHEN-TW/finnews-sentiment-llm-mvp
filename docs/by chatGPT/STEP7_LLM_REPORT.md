
# Step 7 — LLM 報告生成（RAG + Guardrails）

## 目的
以「當日 Top-K 新聞」與信號生成市場/產業/個股日報，固定段落順序、必列引用、拒絕臆測。

## 排序與模板
- 檢索排序：`|情緒| × 新鮮度衰減 × 來源權威`
- Prompt 模板段落：市場總結 → 產業 → 個股 → 風險
- 若無資料：必輸出「無足夠信息」

## 相關程式碼（重點）
- `src/llm/rag_report_gemini.py`（v1.4）：
  - 自動偵測 `news_doc_sentiment/news` 欄位（可用環境變數覆寫）；
  - 兼容 `google-genai` 與 `google-generativeai` 兩種 SDK，不同簽名都能用；
  - 軟性 timeout + 重試 + 退避，避免卡死；
  - **嚴格模式**：服務端若 Transformer 未載入，外層 API 直接 503。

## 使用方式（指令）
```bash
# 需先設定
setx GEMINI_API_KEY "<你的_key>"

# （內部函式被 API 使用；亦可在 REPL 測試）
python - << 'PY'
from src.llm.rag_report_gemini import generate_daily_report
print(generate_daily_report("2024-09-08", top_k=8))
PY
```

## 閃退防護
- Top-K 上限、token 上限；
- 以 ThreadPoolExecutor 包裝 timeout；
- DB 小連線池、僅拉取當日資料。
