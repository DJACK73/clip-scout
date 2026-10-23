from collections import Counter
from urllib.parse import quote_plus
import yt_dlp
from app.guard import build_ydl_opts, network_delay
from app.profiler import build_query, exclusion_reason, classify, load_rules
from app.database import is_duplicate
from app.logger import log
from app.ranker import relevant, precision_score

KEYWORD_LEVELS: tuple[int, ...] = (1, 0)
KIND_TERMS: dict[str, str] = {"raw": "", "pack": "clips for edits", "edit": "edit"}

def _fetch(query: str, count: int, sp: str | None = None) -> list[dict]:
    opts = {**build_ydl_opts(), "extract_flat": True, "skip_download": True}
    if sp:
        opts["playlistend"] = count
        target = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={sp}"
    else:
        target = f"ytsearch{count}:{query}"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
    return (info or {}).get("entries") or []

def _candidate(entry: dict) -> dict:
    video_id = entry["id"]
    return {
        "video_id": video_id,
        "url": entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        "title": entry.get("title") or "",
        "channel": entry.get("channel"),
        "duration": entry.get("duration"),
        "view_count": entry.get("view_count"),
        "start_sec": None,
        "end_sec": None,
    }

def _triage(raw: list[dict], category: str, subject: str, action: str, kind: str, music: bool = False) -> tuple[list[dict], Counter]:
    stats: Counter = Counter()
    kept: list[dict] = []
    for entry in raw:
        video_id = entry.get("id")
        title = entry.get("title") or ""
        if not video_id or len(video_id) != 11:
            stats["no_id"] += 1
            continue
        reason = exclusion_reason(title)
        if reason:
            stats[f"excluded:{reason[:24]}"] += 1
            continue
        ok = relevant(title, category, subject, action) if kind == "raw" else subject.lower() in title.lower()
        if not ok:
            stats["not_relevant"] += 1
            continue
        if music:
            if entry.get("duration") is None or len(video_id) != 11:
                stats["music_invalid"] += 1
                continue
        elif classify(title) != kind:
            stats["wrong_kind"] += 1
            continue
        cand = _candidate(entry)
        if is_duplicate(video_id):
            stats["duplicate"] += 1
            cand["duplicate"] = True
        stats["kept"] += 1
        kept.append(cand)
    return kept, stats

def search_ex(category: str, subject: str, action: str, limit: int = 10, kind: str = "raw", cap: int | None = None, precision: str = "", free: bool = False, sp: str | None = None) -> tuple[list[dict], Counter]:
    music = action in load_rules()["categories"].get(category, {}).get("action_query", {})
    total: Counter = Counter()
    carry: list[dict] = []
    for i, level in enumerate(KEYWORD_LEVELS if kind == "raw" and not free and not sp else (0,)):
        if i:
            network_delay()
        query = build_query(category, subject, action, level, precision, free) if kind == "raw" else " ".join(p for p in (subject, precision.strip(), KIND_TERMS[kind]) if p)
        cc_rules = load_rules()["categories"].get(category, {})
        if sp and sp == cc_rules.get("sp_modes", {}).get("cc") and cc_rules.get("cc_query", {}).get(action):
            query = " ".join(p for p in (subject, precision.strip(), cc_rules["cc_query"][action]) if p)
        raw = _fetch(query, limit * 3, sp)
        kept, stats = _triage(raw, category, subject, action, kind, music)
        if precision.strip():
            kept.sort(key=lambda c: -precision_score(c["title"], precision))
        total.update(stats)
        kept = kept[:cap or limit]
        log(f"Search '{query}': {len(raw)} bruts, {len(kept)} retenus, {dict(stats)}")
        if any(not c.get("duplicate") for c in kept):
            return kept, total
        carry = list({c["video_id"]: c for c in carry + kept}.values())
    return carry, total

def search(category: str, subject: str, action: str, limit: int = 10, kind: str = "raw") -> list[dict]:
    return search_ex(category, subject, action, limit, kind)[0]
