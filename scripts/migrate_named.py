import shutil
from pathlib import Path
from app.database import get_connection, set_meta, update_status
from app.guard import network_delay
from app.inspector import fetch_info
from app.settings import settings
from app.slug import slug

conn = get_connection()
rows = conn.execute(
    "SELECT video_id, category, kind, subject, action, source_url, file_path FROM downloads WHERE status = 'ok' AND file_path IS NOT NULL"
).fetchall()
conn.close()

for r in rows:
    src = Path(r["file_path"])
    if not src.exists():
        print("absent", r["video_id"])
        continue
    info = fetch_info(r["source_url"])
    title = info.get("title") or r["video_id"]
    dest_dir = settings.base_storage_path / r["category"] / r["kind"] / slug(r["subject"]) / slug(r["action"])
    dest = dest_dir / f"{slug(title)}__{r['video_id']}{src.suffix}"
    set_meta(r["video_id"], title, info.get("channel") or info.get("uploader"))
    if src.resolve() != dest.resolve():
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        update_status(r["video_id"], "ok", file_path=str(dest))
    print("ok", dest)
    network_delay()
