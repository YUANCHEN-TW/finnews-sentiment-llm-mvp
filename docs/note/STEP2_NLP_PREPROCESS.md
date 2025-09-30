# Step 2. NLP 前處理

## 目的
- 將新聞標題、內文進行斷句與清理。

## 核心檔案
- `src/etl/preprocess_news.py`
- `src/nlp/preprocess.py`
- `src/nlp/sent_tokenize.py`

## 注意事項
- 修正 regex lookbehind（固定長度限制）。
- 清理符號、空白、HTML 標籤。
- 嚴格模式：必要欄位缺失則報錯。防止閃退：try/except 包裹。
