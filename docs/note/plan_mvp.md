
# MVP 計畫：金融新聞情緒分析 + LLM 報告生成

## 股票池
- 台股大盤
- 2330 台積電
- 2454 聯發科
- 2317 鴻海
- 2882 國泰金
- 3008 大立光

## 新聞來源（MVP）
- Yahoo! 股市新聞 RSS
- 證交所公告 RSS
- 經濟日報 RSS
https://tw.stock.yahoo.com/rss?category=tw-market
https://mopsov.twse.com.tw/nas/rss/mopsrss201002.xml
https://edn.udn.com/rss.jsp
## NLP 情緒分類範圍
- Positive：明顯利多、樂觀訊號
- Negative：明顯利空、悲觀訊號
- Neutral：暫不納入訓練

## 金融驗證指標
- RankIC (秩相關)：新聞情緒 vs. 隔日收益
- 命中率：新聞情緒 vs. 隔日漲跌
- 事件研究：重大新聞後 5–10 日平均報酬

## NLP 模型精度指標
- 宏平均 F1 ≥ 0.80
- AUC ≥ 0.80

## 資料範圍
- 最近 3 個月新聞與股價

## 報告版型（每日產出）
1. 市場總覽：今日情緒指數
2. Top 5 主要新聞（情緒＋來源）
3. 股票情緒曲線（收盤價 vs. 情緒）
4. 熱門產業摘要
5. 引用來源完整列出
