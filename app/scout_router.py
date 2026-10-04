from collections import Counter
from app.settings import settings
from app.ranker import rank
from app.database import norm_title, seen_titles

def find_candidates_ex(category: str, subject: str, action: str, limit: int = 5, kind: str = "raw") -> tuple[list[dict], Counter]:
    if settings.search_backend == "gemini":
        from app.gemini_scout import scout
        return scout(category, subject, action, limit), Counter()
    from app.search_ytdlp import search_ex
    raw, stats = search_ex(category, subject, action, limit * 4, kind, cap=limit * 8)
    ranked = rank(raw, category, subject, action, kind)
    stats["rank_dropped"] = len(raw) - len(ranked)
    seen = seen_titles(category)
    before = len(ranked)
    ranked = [e for e in ranked if norm_title(e["title"]) not in seen]
    stats["duplicate_title"] = before - len(ranked)
    return ranked[:limit], stats

def find_candidates(category: str, subject: str, action: str, limit: int = 5, kind: str = "raw") -> list[dict]:
    return find_candidates_ex(category, subject, action, limit, kind)[0]
