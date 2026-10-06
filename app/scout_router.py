import re
from collections import Counter
from app.ranker import rank
from app.database import norm_title, seen_titles

NOISE: set[str] = {"review", "reaction", "react", "reacts", "explained", "explanation", "debate", "theory", "theories", "news", "trailer", "podcast", "discussion", "recap", "breakdown", "analysis", "confirmed", "leak", "leaks", "ranking", "ranked", "réaction", "analyse", "débat", "explication"}
NOISE_PENALTY: int = 8

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
    before = len(ranked)
    ranked = [e for e in ranked if norm_title(e["title"]) not in seen]
    stats["duplicate_title"] = before - len(ranked)
    return ranked[:limit], stats

def find_candidates(category: str, subject: str, action: str, limit: int = 5, kind: str = "raw") -> list[dict]:
    return find_candidates_ex(category, subject, action, limit, kind)[0]
