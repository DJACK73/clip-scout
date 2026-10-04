import json
import re
from google import genai
from google.genai import errors, types
from app.settings import settings
from app.profiler import build_query, excluded_terms, is_excluded
from app.exceptions import ScoutFailed
from app.logger import log

RETRYABLE_CODES: set[int] = {403, 429, 500, 503}
VIDEO_ID_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})"),
    re.compile(r"tiktok\.com/.*/video/(\d+)"),
]

class KeyRotator:
    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        self.index = 0

    def current(self) -> str:
        return self.keys[self.index]

    def rotate(self) -> None:
        self.index = (self.index + 1) % len(self.keys)

rotator = KeyRotator(settings.gemini_keys_list)

def _build_prompt(query: str, limit: int) -> str:
    excluded = ", ".join(excluded_terms())
    return (
        f"Recherche sur YouTube et TikTok des vidéos correspondant à: {query}. "
        f"Exclure tout contenu mentionnant: {excluded}. "
        f"Retourne UNIQUEMENT un tableau JSON de {limit} objets maximum, sans aucun texte avant ou après, "
        'au format [{"url": str, "title": str, "start_sec": int, "end_sec": int}]. '
        "start_sec et end_sec délimitent le passage exact de l'action, en secondes."
    )

def _generate(prompt: str) -> str:
    for _ in range(len(rotator.keys)):
        client = genai.Client(api_key=rotator.current())
        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            return response.text or ""
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES:
                raise ScoutFailed(f"Erreur API {e.code}: {e.message}") from e
            log(f"Clé #{rotator.index} rejetée ({e.code}): {str(e.message)[:300]}", "WARN")
            rotator.rotate()
    raise ScoutFailed("Toutes les clés épuisées")

def _parse(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ScoutFailed("Aucun tableau JSON dans la réponse")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ScoutFailed(f"JSON invalide: {e}") from e

def extract_video_id(url: str) -> str | None:
    for pattern in VIDEO_ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None

def apply_buffer(start: int, end: int) -> tuple[int, int]:
    buf = settings.time_clip_buffer_sec
    return max(0, start - buf), end + buf

def scout(category: str, subject: str, action: str, limit: int = 5) -> list[dict]:
    query = build_query(category, subject, action)
    log(f"Scout: {query}")
    results: list[dict] = []
    for item in _parse(_generate(_build_prompt(query, limit))):
        try:
            url, title = item["url"], item["title"]
            start, end = int(item["start_sec"]), int(item["end_sec"])
        except (KeyError, TypeError, ValueError):
            continue
        video_id = extract_video_id(url)
        if not video_id or is_excluded(title) or end <= start:
            continue
        start, end = apply_buffer(start, end)
        results.append({"video_id": video_id, "url": url, "title": title, "start_sec": start, "end_sec": end})
    return results
