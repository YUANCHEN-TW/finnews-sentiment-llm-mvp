
# Step 6 — 金融對齊與回測

## 目的
以新聞**發布時間**對齊至交易日（T/T+1），避免收盤後新聞造成的資訊洩漏，並評估信號有效性。

### 功能
* **對齊**：用 `COALESCE(published_at, created_at)` 決定落在 **T** 或 **T+1**（收盤後 → 下一交易日），用 `dim_trading_calendar` 判斷交易日（若沒有就先以 Mon-Fri 近似；你之後可把假日補進表裡）。
* **指標**：IC、RankIC、命中率、事件研究（長端 ≥ p、短端 ≤ 1-p），支援多期（例：1、5、10 日）。
* **穩健性**：年度切片（`Y2024/2025/...`）自動輸出；之後要 walk-forward 或牛熊 regime 再加參數即可。
* **輸出**：寫入 SQL（`bt_signal_ic`、`bt_event_study`、`bt_params`），並輸出 CSV 到 `out/backtest/`。


## 相關程式碼（重點）
- `src/backtest/align_and_backtest.py`：對齊 + IC/RankIC + 命中率 + 事件研究 + 年度分段
  
## 使用方式（指令）
```bash
python -m src.backtest.align_and_backtest --start 2025-09-01 --end 2025-09-30 \
  --cutoff 13:30 --horizons 1,5,10 \
  --price-table prices_daily --ticker-col ticker --date-col ds --price-col close \
  --sig-table news_doc_sentiment --sig-time-col created_at \
  --chunk-size 1000 --throttle-ms 5
```

* 找不到表時 → 自動列出候選:會掃 INFORMATION_SCHEMA，列出像 ticker/symbol/code、ds/date/tradeDate、close/price/px/last 這些欄位跡象的表，幫你快速挑對資料表。
* 可以顯式指定 sig_time_col 為 created_at 或 published_at 看哪個是想要的對齊邏輯

### 風險 & 防護

* **CPU-only**、**分批查詢**（`--chunk-size`）、**節流**（`--throttle-ms`）與**單批上限**，避免功耗/溫度尖峰導致閃退關機。
* 價格表需要你提供：預設 `prices_daily(ticker, ds, close)`，可改 `--price-table/--price-col`。
* 若 `news_raw/news` 都缺，會直接報錯。
* 行業層做完整 IC 需要「行業回報」時間序列；目前程式先提示並跳過（不做錯誤回退）。
* 若資料量大，先縮小 --start/--end 測通，或把 --chunk-size 調小、--throttle-ms 調高。

