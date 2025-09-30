
# Step 5 — 情緒指標建構（Signal Engineering）

## 目的
把句/文級分數整合成：市場/產業/個股層級的每日信號，並加入去噪、衰減與驚奇度。

## 主要輸出表
- `signals_entity_daily`：個股層信號（`ticker`, `ds`, `n_docs`, `mean_score`, `weighted_mean`, `ewma_20`, `zscore_30`, `cum30`, `surprise_src7`）

## 聚合與計算
- 聚合：
  - 市場層：全市場加權平均（權重=來源權威度×新鮮度）
  - 產業層：依產業字典匯總
  - 個股層：僅聚合**含該公司實體**的句子/文章
- 去噪：Winsorize/中位數濾波；新鮮度衰減 `exp(-Δt/τ)`
- 驚奇度（Surprise）：來源/公司近 7 日均值差異的 Z-score

## 相關程式碼（重點）
- `src/signals/build_signals.py`：讀取 `news_doc_sentiment` + `news_entity`，計算後 `MERGE` 寫回 `signals_entity_daily`
  - 已修復：SQL Server 不接受 `NaN`；新增欄位 `weighted_mean/surprise_src7`；
  - 兼容 SQL Server 的 `GETDATE()`（避免 `GETUTCDATETIME` 不存在）；
  - 修正 `GROUPBY.apply` 未來警告。

## 使用方式（指令）
```bash
python -m src.signals.build_signals --days 120 --limit 50000 --throttle-ms 5
```

## 閃退防護
- 嚴格處理 `NaN/None` → 以 `NULL` 或數值替代；
- 以 `--limit` + 分批 `MERGE`；
- 表不存在則自動建立索引與必要欄位。
