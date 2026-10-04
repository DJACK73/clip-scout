cd ~/clip-scout
cat > scripts/scout.py << 'EOF'
import argparse
import subprocess
import sys
from pathlib import Path

from app.database import get_connection, init_db
from app.scout_router import find_candidates_ex

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("category")
    ap.add_argument("subject")
    ap.add_argument("action")
    ap.add_argument("--kind", default="raw")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--download", type=int, default=0)
    a = ap.parse_args()
    init_db()
    items, _ = find_candidates_ex(a.category, a.subject, a.action, a.limit, a.kind)
    seen = {r["video_id"]: r["status"] for r in get_connection().execute("select video_id, status from downloads")}
    for i, c in enumerate(items, 1):
        print(f"{i}. {c['video_id']} {c['title'][:70]} [{seen.get(c['video_id'], 'new')}]")
    todo = [c for c in items if seen.get(c["video_id"]) in (None, "failed")]
    for c in todo[: a.download]:
        url = c.get("url") or f"https://www.youtube.com/watch?v={c['video_id']}"
        cmd = [sys.executable, "-m", "app.get", url, "--category", a.category, "--subject", a.subject, "--action", a.action, "--kind", a.kind]
        subprocess.run(cmd, cwd=ROOT, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
EOF
PYTHONPATH=. python scripts/scout.py foot messi freekicks --limit 5