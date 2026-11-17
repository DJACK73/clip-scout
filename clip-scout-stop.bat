@echo off
wsl -d Ubuntu -e bash /home/x1_yoga2045/clip-scout/scripts/stop.sh
wsl -d Ubuntu -e bash -c "docker stop -t 2 clip-scout-pot >/dev/null 2>&1"
pause
