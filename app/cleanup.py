import argparse
import time
from pathlib import Path
from app.database import get_connection, update_status
from app.settings import settings

PARTIAL = {".part", ".ytdl", ".temp"}
GRACE_SEC = 600

def _registered() -> dict[str, str]:
    conn = get_connection()
    rows = conn.execute("SELECT video_id, file_path FROM downloads WHERE file_path IS NOT NULL AND status = 'ok'").fetchall()
    conn.close()
    return {str(Path(r["file_path"]).resolve()): r["video_id"] for r in rows}

def plan(older_than_days: int | None) -> list[tuple[Path, str | None]]:
    known = _registered()
    out: list[tuple[Path, str | None]] = []
    now = time.time()
    for p in Path(settings.base_storage_path).rglob("*"):
        if not p.is_file():
            continue
        if now - p.stat().st_mtime < GRACE_SEC:
            continue
        vid = known.get(str(p.resolve()))
        if p.suffix in PARTIAL or vid is None:
            out.append((p, None))
        elif older_than_days is not None and now - p.stat().st_mtime > older_than_days * 86400:
            out.append((p, vid))
    return out

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--older-than", type=int, default=None)
    a = ap.parse_args()
    items = plan(a.older_than)
    total = sum(p.stat().st_size for p, _ in items) // 1_000_000
    for p, vid in items:
        print(("PURGE " if vid else "ORPHAN ") + str(p))
        if a.apply:
            p.unlink(missing_ok=True)
            if vid:
                update_status(vid, "purged")
    print(f"{len(items)} fichiers, {total} Mo, {'supprimés' if a.apply else 'dry-run'}")

if __name__ == "__main__":
    main()

def purge_partials(video_id: str) -> int:
    n = 0
    for p in Path(settings.base_storage_path).rglob(f"*__{video_id}*"):
        if p.is_file() and p.suffix in PARTIAL:
            p.unlink(missing_ok=True)
            n += 1
    return n
