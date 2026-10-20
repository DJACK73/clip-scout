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
    row = conn.execute("SELECT 1 FROM downloads WHERE video_id = ? AND status IN ('ok', 'pending', 'downloaded', 'excluded_game')", (video_id,)).fetchone()
    conn.close()
    return row is not None

def register_task(video_id: str, category: str, subject: str, action: str, source_url: str, kind: str = "raw") -> int:
    conn = get_connection()
    conn.execute("DELETE FROM downloads WHERE video_id = ? AND status NOT IN ('ok', 'pending', 'downloaded', 'excluded_game')", (video_id,))
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

def video_statuses(ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    conn = get_connection()
    marks = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT video_id, status FROM downloads WHERE video_id IN ({marks})", ids).fetchall()
    conn.close()
    return {r["video_id"]: r["status"] for r in rows}

def norm_title(title: str) -> str:
    import re
    return re.sub(r"\W+", " ", (title or "").lower()).strip()

def seen_titles(category: str) -> set[str]:
    conn = get_connection()
    rows = conn.execute("SELECT title FROM downloads WHERE category = ? AND status IN ('ok', 'pending', 'downloaded', 'excluded_game') AND title IS NOT NULL", (category,)).fetchall()
    conn.close()
    return {norm_title(r[0]) for r in rows} - {""}

def status_counts() -> dict[str, int]:
    conn = get_connection()
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM downloads GROUP BY status").fetchall()
    conn.close()
    return {r["status"]: r["n"] for r in rows}

def pending_ids() -> list[str]:
    conn = get_connection()
    rows = conn.execute("SELECT video_id FROM downloads WHERE status = 'pending'").fetchall()
    conn.close()
    return [r["video_id"] for r in rows]

def job_row(video_id: str) -> sqlite3.Row | None:
    conn = get_connection()
    row = conn.execute("SELECT status, reason FROM downloads WHERE video_id = ?", (video_id,)).fetchone()
    conn.close()
    return row

def ok_files(category: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT video_id, file_path FROM downloads WHERE category = ? AND status = 'ok' AND file_path IS NOT NULL", (category,)).fetchall()
    conn.close()
    return rows

def status_reasons() -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT video_id, status, reason FROM downloads").fetchall()
    conn.close()
    return rows

def all_downloads(newest_first: bool = True) -> list[dict]:
    order = "DESC" if newest_first else "ASC"
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM downloads ORDER BY created_at {order}, rowid {order}").fetchall()
    conn.close()
    return [dict(r) for r in rows]
