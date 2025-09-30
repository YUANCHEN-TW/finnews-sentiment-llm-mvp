# Step 5：情緒指標（升級版）— 聚合/去噪/新鮮度/驚奇度

## 新增功能
- **加權聚合**：權重 = 來源權威度 × 新鮮度衰減 `exp(-Δt/τ)`
- **三層輸出**：市場 / 產業 / 個股（個股只聚合有該公司實體的文章）
- **去噪**：Winsorize（預設 5%/95%）+ 3 日中位數濾波
- **驚奇度 Surprise**：相對於同來源的 7 日均值之 Z 分數（`surprise_src7`）

## 依賴資料
- `news_doc_sentiment(news_id, doc_score, created_at)`
- `news_entity(news_id, matched_json)`（ticker/industry）
- （可選）`news_raw` 或 `raw_news`（來源 `source`、發布日 `published_at`）

## 權威度設定
編輯 `data/sources/authority.yaml`，未列到者用 `default` 值。

## 產生指標
```bash
python -m src.signals.build_signals --days 120 --limit 50000 --throttle-ms 5 \\
  --tau-days 30 --winsor-low 0.05 --winsor-high 0.95 --median-window 3 --nan-policy null
```

## 輸出欄位
- 所有層級皆含：`n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7`

## 安全性
- **CPU-only**；有 `--throttle-ms`，避免 DB I/O 尖峰；不會造成閃退關機。
- 大資料量請降低 `--days/--limit` 分批跑。
