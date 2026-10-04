import argparse
import re
from app.agent import process
from app.database import init_db

def video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url) or re.fullmatch(r"([\w-]{11})", url.strip())
    if not m:
        raise SystemExit("id vidéo introuvable")
    return m.group(1)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--category", default="foot")
    ap.add_argument("--subject", default="manual")
    ap.add_argument("--action", default="manual")
    ap.add_argument("--kind", default="raw", choices=["raw", "pack", "edit"])
    a = ap.parse_args()
    a.subject = a.subject.strip().lower()
    a.action = a.action.strip().lower()
    init_db()
    res = process({"video_id": video_id(a.url), "url": a.url}, a.category, a.subject, a.action, a.kind)
    print(res.data or f"{res.status}: {res.reason}")

if __name__ == "__main__":
    main()
