from google import genai
from google.genai import types, errors
from app.settings import settings

MODELS = [
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]
LABELS = {400: "CLÉ/REQUÊTE", 401: "CLÉ", 403: "CLÉ/ACCÈS", 404: "MODÈLE", 429: "QUOTA"}
GROUNDED = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

def call(client, model, config=None):
    try:
        r = client.models.generate_content(model=model, contents="Qui a gagné la dernière Ligue des champions ?", config=config)
        meta = r.candidates[0].grounding_metadata if r.candidates else None
        return "OK" + (f" grounded={bool(meta and meta.web_search_queries)}" if config else "")
    except errors.APIError as e:
        return f"{LABELS.get(e.code, 'AUTRE')} {e.code} {str(e.message)[:70]}"

for i, key in enumerate(settings.gemini_keys_list):
    client = genai.Client(api_key=key)
    print(f"clé{i} sans outil {settings.gemini_model}: {call(client, settings.gemini_model)}")
    for model in MODELS:
        print(f"clé{i} grounding {model}: {call(client, model, GROUNDED)}")
