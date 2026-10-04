#!/usr/bin/env bash
if pgrep -f "app.get" > /dev/null; then echo "app.get en cours, arrêt refusé"; exit 1; fi
pkill -f "streamlit run app/dashboard.py" && echo arrêté || echo "aucun streamlit"
