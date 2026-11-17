@echo off
wsl -d Ubuntu -e bash /home/x1_yoga2045/clip-scout/scripts/ensure_pot.sh
start "clip-scout" /min wsl -d Ubuntu -e bash /home/x1_yoga2045/clip-scout/scripts/start-fg.sh
timeout /t 8 /nobreak >nul
start http://127.0.0.1:8501
