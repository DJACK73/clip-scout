#!/usr/bin/env bash
cd "$(dirname "$0")/.." && source venv/bin/activate && PYTHONPATH=. exec streamlit run app/dashboard.py --server.headless true --server.address 127.0.0.1
