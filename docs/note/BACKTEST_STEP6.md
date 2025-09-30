
# Step 6：金融對齊與回測

這個模組實作了你要的四大塊：**對齊、IC/RankIC、命中率、事件研究**，並提供**穩健性**設計（年度切片、walk-forward）。

## 1. 對齊（避免資訊洩漏）
- 以 `COALESCE(published_at, created_at)` 的時間為準。
- 若 **收盤後**（`--cutoff`，預設 13:30），就將該新聞的影響算到 **下一個交易日 T+1**；收盤前則算到 **當日 T**。
- 交易日以 `dim_trading_calendar` 表為準；若找不到會以 Mon-Fri 近似（請自行補假日）。

### 需要的表
- `news_doc_sentiment(news_id, created_at, doc_score)`
- `news_entity(news_id, matched_json)`（JSON 內含 ticker/inustry）
- `news_raw` 或 `raw_news`（任一）以取得 `published_at`

## 2. 指標
- **IC**：每日以 cross-section 訊號 vs. 未來報酬做皮爾森相關，跨日平均。
- **RankIC**：把兩者都轉成排行（百分位），再做相關。
- **命中率**：`sign(signal) * sign(fwd_return) > 0` 的比例。
- **事件研究**：每日取訊號的極端分位（長端 ≥ p，短端 ≤ 1-p），觀察未來報酬平均（長端直接平均；短端取負號代表做空）。

## 3. 穩健性
- **年度切片**：自動對 start~end 做逐年分段（`Y2024, Y2025, ...`）。
- 後續可擴充：
  - **walk-forward**（訓練/測試分段；本版先做 yearly out-of-sample 檢視）。
  - **牛熊子樣本**：提供 `--market-ticker`，程式會以該 ticker 的價格做市場事件研究；若要嚴格牛/熊切分，可再加一個 `market regime` 函式。

## 4. 執行
```bash
python -m src.backtest.align_and_backtest --start 2024-01-01 --end 2025-09-08       --cutoff 13:30 --tz Asia/Taipei --horizons 1,5,10       --price-table prices_daily --price-col close --market-ticker TAIEX       --percentile 0.95 --chunk-size 2000 --throttle-ms 2 --min-docs 1
```

## 5. 安全性（防閃退）
- **CPU-only**、分批查詢（`--chunk-size`）、可節流（`--throttle-ms`）與記憶體限制（單批上限）。
- 若資料量極大，請降低 `--chunk-size` 與縮短 `--start/--end`。

## 6. 輸出
- SQL：`bt_signal_ic`（IC/RankIC/命中率）、`bt_event_study`（事件研究），還有 `bt_params`（參數快照）。
- CSV：寫到 `out/backtest/metrics_*.csv`、`out/backtest/events_*.csv`。

> 若你要把 **industry 層** 的 IC 做完整，需要行業指數或等權行業回報時間序列；之後可加一張 `industry_returns_daily` 表，再與 `signals_industry_daily` 對齊即可。
