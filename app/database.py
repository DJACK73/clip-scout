import sqlite3
from pathlib import Path
from app.settings import settings

def get_connection() -> sqlite3.Connection:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            subject TEXT NOT NULL,
            action TEXT NOT NULL,
            source_url TEXT NOT NULL,
            file_path TEXT,
            fps REAL,
            bitrate INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(downloads)")}
    if "kind" not in cols:
        conn.execute("ALTER TABLE downloads ADD COLUMN kind TEXT NOT NULL DEFAULT 'raw'")
    if "reason" not in cols:
        conn.execute("ALTER TABLE downloads ADD COLUMN reason TEXT")
    conn.commit()
    conn.close()

def is_duplicate(video_id: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM downloads WHERE video_id = ? AND status != 'failed'", (video_id,)).fetchone()
    conn.close()
    return row is not None

def register_task(video_id: str, category: str, subject: str, action: str, source_url: str, kind: str = "raw") -> int:
    conn = get_connection()
    conn.execute("DELETE FROM downloads WHERE video_id = ? AND status = 'failed'", (video_id,))
    cur = conn.execute(
        "INSERT INTO downloads (video_id, category, subject, action, source_url, kind) VALUES (?, ?, ?, ?, ?, ?)",
        (video_id, category, subject, action, source_url, kind)
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id

def update_status(video_id: str, status: str, file_path: str | None = None, fps: float | None = None, bitrate: int | None = None, reason: str | None = None) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE downloads SET status = ?, file_path = COALESCE(?, file_path), fps = COALESCE(?, fps), bitrate = COALESCE(?, bitrate), reason = COALESCE(?, reason) WHERE video_id = ?",
        (status, file_path, fps, bitrate, reason, video_id),
    )
    conn.commit()
    conn.close()

def set_meta(video_id: str, title: str | None, channel: str | None) -> None:
    conn = get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(downloads)")}
    for c in ("title", "channel"):
        if c not in cols:
            conn.execute(f"ALTER TABLE downloads ADD COLUMN {c} TEXT")
    conn.execute("UPDATE downloads SET title = ?, channel = ? WHERE video_id = ?", (title, channel, video_id))
    conn.commit()
    conn.close()

def norm_title(title: str) -> str:
    import re
    return re.sub(r"\W+", " ", (title or "").lower()).strip()

def seen_titles(category: str) -> set[str]:
    conn = get_connection()
    rows = conn.execute("SELECT title FROM downloads WHERE category = ? AND status != 'failed' AND title IS NOT NULL", (category,)).fetchall()
    conn.close()
    return {norm_title(r[0]) for r in rows} - {""}
