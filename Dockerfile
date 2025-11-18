# 使用較小的 Python 基底 image
FROM python:3.11-slim

# 環境變數設定：避免 .pyc、強制 unbuffered log
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 建立工作目錄
WORKDIR /app

# 先安裝系統相依套件（如果你之後需要可再加）
# RUN apt-get update && apt-get install -y build-essential

# 先複製 requirements 再安裝（加快快取）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 再複製專案程式碼
COPY . /app

# 對外開放的 port（FastAPI 預設 8000）
EXPOSE 8000

# 啟動指令
# FastAPI app 在 src/app/api.py，物件名稱是 app
CMD ["uvicorn", "src.app.api:app", "--host", "0.0.0.0", "--port", "8000"]
