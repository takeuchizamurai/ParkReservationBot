FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 日本語フォントのインストール（スクリーンショットの文字化け防止）
RUN apt-get update && apt-get install -y \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードのコピー
COPY . .

#s		CMD ["python", "main.py"]