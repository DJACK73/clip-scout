import re
import sys
from app.profiler import load_rules, excluded_terms, is_excluded

rules = load_rules()
bad: list[tuple] = []
for cat, c in rules["categories"].items():
    kws = list(c.get("forced_keywords", []))
    for v in c.get("action_forced_keywords", {}).values():
        kws += v
    for k in kws:
        if is_excluded(k):
            bad.append((cat, k))
        for t in excluded_terms():
            try:
                hit = re.search(t, k, re.IGNORECASE)
            except re.error:
                hit = None
            if hit:
                bad.append((cat, k, t))
print(bad or "ok")
sys.exit(1 if bad else 0)
