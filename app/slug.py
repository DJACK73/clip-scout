import re
import unicodedata

def slug(text: str, limit: int = 60) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:limit].strip("_")
    return s or "untitled"
