
# Step 3 — 標註策略（弱監督 + 人工校正）

## 目的
以規則/辭典產生「弱標註」，再抽樣做人工作業校正，建立高品質訓練集。

## 主要輸出
- `labels_sentence_weak`：弱標註結果（`sid`, `label`）
- `labels_sentence_gold`：人工校正後的黃金標註

## 相關程式碼（重點）
- `src/labeling/heuristics.py`：情緒規則、否定詞處理、金融專屬詞彙；
- `src/etl/export_for_annotation.py`：抽樣輸出 CSV/Excel 給標註人員；
- `src/etl/import_annotations.py`：回收標註、與弱標註比對。

## 使用方式（指令）
```bash
# 匯出待標註樣本
python -m src.etl.export_for_annotation --size 300

# 匯入人工標註
python -m src.etl.import_annotations --file data/annotations_YYYYMMDD.csv
```

## 為何需要人工批次？
- 弱標註在諷刺、雙關、金融脈絡（如「利空出盡」）上易誤判；
- 少量高品質標註可顯著提升模型泛化表現與可解釋性。

## 閃退防護
- 匯出/匯入都以分批處理，避免一次載入大量檔案；
- CSV 讀寫加上編碼/欄位檢查。
