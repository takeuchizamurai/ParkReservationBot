#!/bin/bash
set -e

export DISPLAY=:99

Xvfb :99 -screen 0 1600x900x24 &
fluxbox &
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &

sleep 2
python -u main.py