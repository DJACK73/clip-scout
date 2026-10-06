import json
import re
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.json"

def load_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))

def validate(category: str, action: str, free: bool = False) -> None:
    categories = load_rules()["categories"]
    if category not in categories:
        raise ValueError(f"Catégorie inconnue: {category}")
    if not free and action not in categories[category]["actions"]:
        raise ValueError(f"Action inconnue pour {category}: {action}")

def build_query(category: str, subject: str, action: str, sample_size: int = 3, precision: str = "", free: bool = False) -> str:
    validate(category, action, free)
    rules = load_rules()["categories"][category]
    forced = [] if free else rules.get("action_forced_keywords", {}).get(action, rules["forced_keywords"])
    picked = forced[:sample_size]
    aliases = None if free else rules.get("action_aliases", {}).get(action)
    term = aliases[0] if aliases else action.replace('_', ' ')
    base = f"{subject} {precision.strip()}".strip()
    head = base if term.lower() == subject.lower() else f"{base} {term}"
    return f"{head} {' '.join(picked)}".strip()

def excluded_terms() -> list[str]:
    return load_rules().get("excluded_keywords", [])

def is_excluded(title: str) -> bool:
    if any(
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", title, re.IGNORECASE)
        for term in excluded_terms()
    ):
        return True
    return any(
        re.search(pat, title, re.IGNORECASE)
        for pat in load_rules().get("excluded_patterns", [])
    )



def _matches(title: str, terms: list[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(t)}(?!\w)", title, re.IGNORECASE) for t in terms)

def classify(title: str) -> str:
    kinds = load_rules().get("kind_keywords", {})
    if _matches(title, kinds.get("pack", [])):
        return "pack"
    if _matches(title, kinds.get("edit", [])):
        return "edit"
    return "raw"

def exclusion_reason(title: str) -> str | None:
    for term in excluded_terms():
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", title, re.IGNORECASE):
            return term
    for pat in load_rules().get("excluded_patterns", []):
        if re.search(pat, title, re.IGNORECASE):
            return pat
    return None
