import re
from collections import Counter
from app.ranker import rank
from app.database import norm_title, seen_titles, video_statuses

NOISE: set[str] = {"review", "reaction", "react", "reacts", "explained", "explanation", "debate", "theory", "theories", "news", "trailer", "podcast", "discussion", "recap", "breakdown", "analysis", "confirmed", "leak", "leaks", "ranking", "ranked", "réaction", "analyse", "débat", "explication"}
NOISE_PENALTY: int = 8
REFILL: set[str] = {"purged", "failed", "needs_confirm"}
HARD: set[str] = {"ok", "pending", "downloaded", "excluded_game"}
REJECTED: set[str] = {"rejected_inspect", "rejected_quality"}

def _demote(entries: list[dict]) -> list[dict]:
    out = []
    for e in entries:
        hits = len(NOISE & set(re.findall(r"\w+", e["title"].lower())))
        out.append({**e, "score": e["score"] - NOISE_PENALTY * hits})
    return sorted(out, key=lambda e: e["score"], reverse=True)

def find_candidates_ex(category: str, subject: str, action: str, limit: int = 5, kind: str = "raw", precision: str = "", free: bool = False) -> tuple[list[dict], Counter]:
    from app.search_ytdlp import search_ex
    raw, stats = search_ex(category, subject, action, limit * 4, kind, cap=limit * 8, precision=precision, free=free)
    hint = f"{precision} {action}".strip() if free else precision
    ranked = rank(raw, category, subject, action, kind, hint)
    if free:
        ranked = _demote(ranked)
    stats["rank_dropped"] = len(raw) - len(ranked)
    seen = seen_titles(category)
    new = 0
    for e in ranked:
        if norm_title(e["title"]) in seen and not e.get("duplicate"):
            e["duplicate"] = True
            new += 1
    stats["duplicate_title"] = new
    st = video_statuses([e["video_id"] for e in ranked])
    dups = [e for e in ranked if e.get("duplicate") or st.get(e["video_id"]) in HARD]
    dup_ids = {e["video_id"] for e in dups}
    fresh = [e for e in ranked if e["video_id"] not in st and e["video_id"] not in dup_ids]
    fill = [e for e in ranked if st.get(e["video_id"]) in REFILL and e["video_id"] not in dup_ids]
    stats["seen_rejected"] = len(ranked) - len(fresh) - len(fill) - len(dups)
    rej = [e for e in ranked if st.get(e["video_id"]) in REJECTED and e["video_id"] not in dup_ids]
    out = fresh[:limit]
    n_fresh = len(out)
    if len(out) < limit:
        out += fill[: limit - len(out)]
    n_fill = len(out) - n_fresh
    if len(out) < limit:
        out += [{**e, "duplicate": True} for e in dups[: limit - len(out)]]
    n_dup = len(out) - n_fresh - n_fill
    if len(out) < limit:
        out += [{**e, "rejected": True} for e in rej[: limit - len(out)]]
    stats["refilled"] = n_fill
    stats["shown_duplicates"] = n_dup
    stats["shown_rejected"] = len(out) - n_fresh - n_fill - n_dup
    return out, stats

def find_candidates(category: str, subject: str, action: str, limit: int = 5, kind: str = "raw") -> list[dict]:
    return [c for c in find_candidates_ex(category, subject, action, limit, kind)[0] if not c.get("duplicate") and not c.get("rejected")]
