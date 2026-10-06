import json
import re
from pathlib import Path
from app.settings import ROOT, settings

_RULES = ROOT / "config" / "rules.json"

def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))

_STOP = {"vs", "and", "et", "the", "of", "de", "le", "la", "les", "x"}

def precision_score(title: str, precision: str) -> int:
    return 3 * len((_tokens(precision) - _STOP) & _tokens(title))

def _category_rules(category: str) -> dict:
    return json.loads(_RULES.read_text())["categories"][category]

def score(entry: dict, category: str, subject: str, action: str, precision: str = "") -> int:
    rules = _category_rules(category)
    title = entry["title"].lower()
    total = 0
    subj = _tokens(subject)
    total += 3 * len(subj & _tokens(title))
    aliases = rules.get("action_aliases", {}).get(action, []) + [action.replace("_", " ")]
    if any(a in title for a in aliases):
        total += 4
    total += sum(1 for k in rules.get("forced_keywords", []) if k.lower() in title)
    total += precision_score(title, precision)
    return total

def _has_action(title: str, category: str, action: str) -> bool:
    aliases = _category_rules(category).get("action_aliases", {}).get(action)
    if not aliases:
        return True
    low = title.lower()
    return any(a.lower() in low for a in aliases)

def relevant(title: str, category: str, subject: str, action: str) -> bool:
    return bool(_tokens(subject) & _tokens(title)) and _has_action(title, category, action)

def rank(entries: list[dict], category: str, subject: str, action: str, kind: str = "raw", precision: str = "") -> list[dict]:
    out = []
    cap = None if kind == "pack" else _category_rules(category).get("max_duration_sec")
    min_dur = _category_rules(category).get("min_duration_sec", settings.min_video_duration_sec)
    for e in entries:
        dur = e.get("duration")
        if cap and dur is not None and dur > cap:
            continue
        if dur is not None and not min_dur <= dur <= settings.max_video_duration_sec:
            continue
        if not (relevant(e["title"], category, subject, action) if kind == "raw" else bool(_tokens(subject) & _tokens(e["title"]))):
            continue
        out.append({**e, "score": score(e, category, subject, action, precision)})
    seen: set[tuple[str, float | None]] = set()
    unique: list[dict] = []
    for e in sorted(out, key=lambda e: e["score"], reverse=True):
        key = (re.sub(r"\W+", " ", e["title"].lower()).strip(), e.get("duration"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique
