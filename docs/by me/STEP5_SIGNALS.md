
# Step 5 — 情緒指標建構（Signal Engineering）

## 目的
把句/文級分數整合成：市場/產業/個股層級的每日信號，並加入去噪、衰減與驚奇度。

## 聚合與計算
* **聚合（全都有）：**

  * 市場層：用 **權威度×新鮮度** 的加權平均（新鮮度 = `exp(-Δt/τ)`，預設 τ=30 天）。
  * 產業層：依 `news_entity` 的 `industry` 匯總，同樣用加權。
  * 個股層：**只聚合含該公司實體**的文章，同樣用加權。
* **去噪：**

  * Winsorize（預設 5%/95%）+ **3 日中位數濾波**（可調）。
* **新鮮度衰減：**

  * 參數 `--tau-days`（預設 30），越小越重視新新聞。
* **驚奇度 Surprise：**

  * `surprise_src7`：對（**同來源**，例如 Reuters）且同公司/產業/市場的 **7 日均值**做 **Z-score**。
    用處：突出相對來源常態的異常波動。

## 相關程式碼（重點）
- `src/signals/build_signals.py`：生成 Entity/Industry/Market 三類日度情緒指標（CPU、節流、批次寫入）
- `src/app/main_strict.py`：新增 /signals 端點（嚴格：未載入 Transformer 就 503）
- `src/dashboard/signals_strict.py`：Signals 檢視頁（Streamlit）
- `data/sources/authority.yaml`：來源權威度表（可自行調整；未列到者用 default）

## 使用方式（指令）

### 1) 產生日度 Signals（CPU、資源友善）

```
python -m src.signals.build_signals --days 120 --limit 50000 --throttle-ms 5 --nan-policy null
```

```bash
python -m src.signals.build_signals --days 120 --limit 50000 --throttle-ms 5 \
  --tau-days 30 --winsor-low 0.05 --winsor-high 0.95 --median-window 3 --nan-policy null
```
會建立/更新三張表：

* `signals_entity_daily`（公司）：每日平均分數、EWMA(20)、Z-score(30)、30日累積
* `signals_industry_daily`（產業）
* `signals_market_daily`（市場整體）

🛡️安全：全程 **CPU**；可用 `--throttle-ms` 降低資料庫尖峰負載。若資料量很大，請縮小 `--days/--limit` 分批執行。


## 指標定義（簡版）

* `mean_score`：該日所有新聞的文級情緒平均（-1~1）
* `ewma_20`：20日指數移動平均（平滑趨勢）
* `zscore_30`：30日窗口的標準化指標（偵測偏離常態）
* `cum30`：近 30 日累積情緒（衡量情緒慣性）

> 資料來源：
> `news_doc_sentiment`（文級分數） × `news_entity.matched_json`（展開新聞對象 → company/industry）

---

## 風險提醒

* Signals 計算是 **CPU + Pandas + 分批寫入**，風險遠低於 GPU；但如果 DB 很忙，仍建議調大 `--throttle-ms` 或分段執行，以免 I/O 尖峰。
* 若 `news_entity` 的 `matched_json` 很大，單次解析會吃 RAM；程式會分批寫入、但仍建議用 `--days/--limit` 控量。

### 其他說明

* 權威度表在 `data/sources/authority.yaml`，可以把常見媒體補進去；沒列到的用 `default`。
* 新鮮度用 `published_at`（若找不到 `news_raw`/`raw_news` 表，會自動回退只用權威度或全 1 權重）。
* `NaN/inf`（常見於樣本少或標準差為 0 的 Z-score）已統一依 `--nan-policy` 轉為 `NULL`（建議）或 `0.0`。
