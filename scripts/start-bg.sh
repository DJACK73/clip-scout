#!/usr/bin/env bash
cd "$(dirname "$0")/.." || exit 1
pgrep -f "streamlit run app/[d]ashboard.py" >/dev/null && exit 0
mkdir -p logs
setsid nohup scripts/start.sh >logs/streamlit.log 2>&1 </dev/null &
