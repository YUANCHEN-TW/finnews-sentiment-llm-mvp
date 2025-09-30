
# Step 6 — 金融對齊與回測

## 目的
以新聞**發布時間**對齊至交易日（T/T+1），避免收盤後新聞造成的資訊洩漏，並評估信號有效性。

## 指標
- IC / RankIC（信號 vs 未來報酬）
- 命中率（多空方向）
- 事件研究（公告/大利空/大利多）
- 穩健性：walk-forward、分年度/牛熊、p-value 與效果量

## 相關程式碼（重點）
- `src/backtest/align_and_backtest.py`：
  - 以 `prices_daily`（`ticker`, `ds`, `[close]`）載入價格；
  - 將 `signals_entity_daily` 對齊交易日，計算未來 k 日報酬；
  - 以分塊（TOP+OFFSET）模式讀取，兼容 SQL Server 語法；
  - 算出 IC/RankIC、命中率與事件研究結果。

## 使用方式（指令）
```bash
# 例：回測 2024-01-01 ~ 2025-01-01，對齊到 T+1，視窗 [1,3,5] 日
python -m src.backtest.align_and_backtest --start 2024-01-01 --end 2025-01-01   --cutoff "16:00" --tz "Asia/Taipei" --horizons 1 3 5 --chunk-size 2000 --top 2000
```

## 閃退防護
- SQL 查詢改用 `TOP + WHERE > last_id` 避免 `TOP 與 OFFSET` 衝突；
- 表名/欄位名使用方括號；
- 設上限（chunk-size、top）避免一次拉取過大。
