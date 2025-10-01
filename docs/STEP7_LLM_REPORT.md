
# Step 7 — LLM 報告生成（RAG + Guardrails）

## 目的
以「當日 Top-K 新聞」與信號生成市場/產業/個股日報，固定段落順序、必列引用、拒絕臆測。

## 排序與模板
- 檢索排序：`|情緒| × 新鮮度衰減 × 來源權威`
- Prompt 模板段落：市場總結 → 產業 → 個股 → 風險
- 若無資料：必輸出「無足夠信息」

## 相關程式碼（重點）
- `src/llm/prompt_templates.py`：報告模板（固定段落、必列引用、缺資料→「無足夠信息」）
- `src/llm/guardrails.py`：Guardrails：防幻覺/缺段落補救
- `src/llm/rag_report_gemini.py`：RAG 主流程（Top-K 檢索→模板→Gemini 生成）
- `src/app/report_strict_gemini.py`：/report API（Strict 版：未載入 Transformer → 503）

## 使用方式（指令）

# 1) 用 Gemini 取代 OpenAI：免費方案與安裝

**免費 API Key**
到官方 **Google AI Studio** 取得，支援免費開發用額度（有速率與日用量限制；細節因模型而異）

**安裝 SDK**
```bash
pip install -U google-genai
```

**設定金鑰（Windows PowerShell 範例）：**
```powershell
setx GEMINI_API_KEY "<你的_ApiKey>"
```

（或在 `.env` 內設 `GEMINI_API_KEY=...`）

---

# 2) 兩組完整程式

### A. `src/llm/*`（RAG + Guardrails）

* `rag_report_gemini.py`：

  * 從 DB 取 **當日 Top-K** 新聞：依「**來源權威 × 新鮮度衰減 × 情緒強度**」排序

    * 新鮮度：`exp(-Δt/72hr)`
    * 情緒強度：`abs(doc_score)`
    * 來源權威：若無對照表則預設 1
  * 把 **檢索片段與日級情緒指標** 餵到模板
  * 呼叫 **Gemini** 產生報告（預設 `gemini-1.5-flash`；可改 `GEMINI_MODEL` 環境變數）
  * **防爆衝/防閃退**：

    * `--Top-K` 有上限（預設 12）、prompt token 上限（預設 1200）
    * DB 連線池限制（小池，避免同時太多連線）
    * **超時**＋**重試**＋重試間隔，避免高頻錯誤造成 CPU/散熱尖峰
    * 檢索與 signals 都只抓**當日**必要資料，避免讀爆記憶體
* `prompt_templates.py`：固定段落（市場→產業→個股→風險），**必列引用**，缺資料要寫「**無足夠信息**」。
* `guardrails.py`：

  * 若出現數字卻無引用，附上警告
  * 自動補上遺失段落或空段標示「無足夠信息」

### B. `src/app/report_strict_gemini.py`

* **Strict 規則**：若偵測不到 Transformer 分類器 → 直接回 **503**：「模型未載入」。

  * 透過 `TRANSFORMER_READY=1` 或 `src.models.runtime.is_ready()` 來認定載入狀態。
* 成功時才會呼叫 `generate_daily_report()`。
* FastAPI 介面。

**啟動（範例）**

```bash
# 先啟用 Transformer（或暫時用環境變數告知就緒）
setx TRANSFORMER_READY 1

# 啟動 FastAPI（取決於專案啟動方式）
uvicorn src.app.report_strict_gemini:app --host 0.0.0.0 --port 8000
```

呼叫：

```
GET /report?date_str=2025-09-08&top_k=8
```

## 快速驗收（有 Transformer 時會生成）

```bash
# 產出報告（例如 2025-09-08，符合資料集）
curl "http://127.0.0.1:8000/report?date_str=2025-09-08&top_k=8"
```

---

## 使用與整合說明

1. **資料對齊**

   * 會用 `news_doc_sentiment.created_at` 與 `news.published_at`（若有）組合計算新鮮度；前面第 6 步已經做了 T/T+1 對齊與信號，這裡只取**同日**的 Top-K 呈現敘述。
2. **引用**

   * RAG context 會列：`標題 | 來源 (時間) <連結> | 情緒強度:x.xx`
   * 模板輸出最後 **# 來源** 區塊逐條列引用，滿足“必列出引用”的要求。
3. **防幻覺**

   * 模板明確限制：**數字必來自檢索或我們指標**
   * Guardrails：若檢測到數字卻沒引用/或有「推測」詞彙，會加上審閱警告
   * 若缺資料→各段落輸出「無足夠信息」

---

## 可能的故障點與**防閃退/防暴衝**提醒（已內建防護）

* **大 K 值或大量新聞** → prompt 爆大、CPU/記憶體飆：

  * 已內建 `Top-K 上限 (12)`、signals 只取 Top N（預設 20）
  * 若機器偏弱，建議把 `RAG_TOPK_MAX=8`、`RAG_MAX_TOKENS=900` 設小一點。
* **LLM 超時/Rate Limit**：

  * 已加 `TIMEOUT_S`（預設 60s）與**重試**（預設 2 次）＋退避睡眠
  * 遇到429/timeout時不會瘋狂重試導致功耗尖峰
* **DB 大量掃描**：

  * 查詢限定 `CAST(created_at AS DATE) = :d`，只抓**當日**
  * 連線池縮小（pool_size=3, max_overflow=2），避免超多併發
* **Transformer 未載入**：

  * 嚴格模式下 `/report` 直接 503，不會 fallback，避免誤用/幻覺

---
