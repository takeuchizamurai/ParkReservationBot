FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 日本語フォント＋gitのインストール
RUN apt-get update && apt-get install -y \
    fonts-noto-cjk \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# git cloneでプログラム取得
RUN git clone https://github.com/takeuchizamurai/ParkReservationBot.git .

# ライブラリのインストール
RUN pip install --no-cache-dir -r requirements.txt

# Playwrightブラウザのインストール
RUN playwright install chromium

# screenshotsフォルダ作成
RUN mkdir -p /app/screenshots

CMD ["python", "-u", "main.py"]