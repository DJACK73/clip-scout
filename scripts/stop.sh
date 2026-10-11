#!/usr/bin/env bash
busy=$(pgrep -f "python -m app\.get" | tr '\n' ' ')
[ -n "$busy" ] && echo "téléchargement en cours (PID $busy) : il continue après l'arrêt du dashboard"
pkill -f "streamlit run app/dashboard\.py" && echo "dashboard arrêté" || echo "aucun streamlit"
