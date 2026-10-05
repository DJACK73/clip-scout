# clip-scout

Sourcing et validation de rushs vidéo bruts (yt-dlp + FFprobe), sans montage.

## Lancer / arrêter (Windows)
- `clip-scout-start.bat` : démarre le dashboard (fenêtre `clip-scout` à laisser ouverte) puis ouvre http://127.0.0.1:8501
- `clip-scout-stop.bat` : arrêt propre, refusé si un téléchargement est en cours

## Installation
    sudo apt install -y ffmpeg
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp config/.env.example config/.env

## Vérifications
    PYTHONPATH=. python scripts/check_rules.py
    python -m app.cleanup
