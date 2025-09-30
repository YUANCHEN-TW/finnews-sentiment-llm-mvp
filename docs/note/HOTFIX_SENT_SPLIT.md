# Hotfix: 中文句子切分正則

修正 `src/nlp/sent_tokenize.py` 內使用「變長 lookbehind」導致：
```
re.error: look-behind requires fixed-width pattern
```
改用 `re.findall` 句子抽取，避免 lookbehind：
- 正則：`[^。！？；…\n]+[。！？；…]+|[^。！？；…\n]+$`
- 執行前先把 `...` 視為 `…`，提升切分穩定度。
