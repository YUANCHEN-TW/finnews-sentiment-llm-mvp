# Step 4：句級分類模型（Transformer）

## 先決條件
- 已完成 Step 3，並在 `data/processed/dataset_v1/` 有 `train.csv/val.csv/test.csv`。

## 安裝補充依賴
把 `requirements.txt.append` 的三行加入 `requirements.txt`，然後：
```
pip install -r requirements.txt
```

## 訓練
```
python -m src.models.train_transformer --model_name hfl/chinese-bert-wwm-ext --epochs 3 --batch_size 16 --fp16
```

## 推論
```
python -m src.models.infer_transformer --model_dir models/bert_sentence_cls --text "台積電法說會釋出利多，訂單上修"
```
或：
```
python -m src.models.infer_transformer --model_dir models/bert_sentence_cls --file samples.txt
```

> 標籤對應：0=neg, 1=neu, 2=pos（已寫入 label_mapping.txt）
