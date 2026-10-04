from collections import Counter
import yt_dlp
from app.guard import build_ydl_opts, network_delay
from app.profiler import build_query, exclusion_reason, classify
from app.database import is_duplicate
from app.logger import log
from app.ranker import relevant

KEYWORD_LEVELS: tuple[int, ...] = (1, 0)
KIND_TERMS: dict[str, str] = {"raw": "", "pack": "clips for edits", "edit": "edit"}

def _fetch(query: str, count: int) -> list[dict]:
    opts = {**build_ydl_opts(), "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
    return (info or {}).get("entries") or []

def _candidate(entry: dict) -> dict:
    video_id = entry["id"]
    return {
        "video_id": video_id,
        "url": entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        "title": entry.get("title") or "",
        "channel": entry.get("channel"),
        "duration": entry.get("duration"),
        "start_sec": None,
        "end_sec": None,
    }

def _triage(raw: list[dict], category: str, subject: str, action: str, kind: str) -> tuple[list[dict], Counter]:
    stats: Counter = Counter()
    kept: list[dict] = []
    for entry in raw:
        video_id = entry.get("id")
        title = entry.get("title") or ""
        if not video_id:
            stats["no_id"] += 1
            continue
        reason = exclusion_reason(title)
        if reason:
            stats[f"excluded:{reason[:24]}"] += 1
            continue
        if is_duplicate(video_id):
            stats["duplicate"] += 1
            continue
        ok = relevant(title, category, subject, action) if kind == "raw" else subject.lower() in title.lower()
        if not ok:
            stats["not_relevant"] += 1
            continue
        if classify(title) != kind:
            stats["wrong_kind"] += 1
            continue
        stats["kept"] += 1
        kept.append(_candidate(entry))
    return kept, stats

def search_ex(category: str, subject: str, action: str, limit: int = 10, kind: str = "raw", cap: int | None = None) -> tuple[list[dict], Counter]:
    total: Counter = Counter()
    for i, level in enumerate(KEYWORD_LEVELS if kind == "raw" else (0,)):
        if i:
            network_delay()
        query = build_query(category, subject, action, level) if kind == "raw" else f"{subject} {KIND_TERMS[kind]}"
        raw = _fetch(query, limit * 3)
        kept, stats = _triage(raw, category, subject, action, kind)
        total.update(stats)
        kept = kept[:cap or limit]
        log(f"Search '{query}': {len(raw)} bruts, {len(kept)} retenus, {dict(stats)}")
        if kept:
            return kept, total
    return [], total

def search(category: str, subject: str, action: str, limit: int = 10, kind: str = "raw") -> list[dict]:
    return search_ex(category, subject, action, limit, kind)[0]
