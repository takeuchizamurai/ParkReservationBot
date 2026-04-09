#!/bin/bash
set -e

export DISPLAY=:99

Xvfb :99 -screen 0 1600x900x24 &
sleep 1
fluxbox &
sleep 1

# x11vncを起動してポート5900が開くまで待つ
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &
echo "x11vnc起動待ち..."
for i in $(seq 1 30); do
    if nc -z localhost 5900 2>/dev/null; then
        echo "x11vnc 起動確認 (${i}秒)"
        break
    fi
    sleep 1
done

websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
sleep 1

python -u main.py