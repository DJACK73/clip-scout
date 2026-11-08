import json

import streamlit.components.v1 as components

_MAP: dict[str, str] = {
    "System": "Système",
    "Light": "Clair",
    "Dark": "Sombre",
    "Rerun": "Relancer",
    "Auto rerun": "Relance auto",
    "Clear cache": "Vider le cache",
    "Print": "Imprimer",
    "Record screen": "Enregistrer l'écran",
    "Settings": "Paramètres",
    "Report a bug": "Signaler un bug",
    "Get help": "Aide",
    "About": "À propos",
}

_JS: str = """
const d = window.parent.document;
function tr(n) {
  if (n.nodeType === 3) {
    const p = n.parentElement;
    if (!p || p.closest('[data-testid="stMainBlockContainer"]')) return;
    const t = n.nodeValue.trim();
    if (M[t]) { n.nodeValue = n.nodeValue.replace(t, M[t]); return; }
    if (t.startsWith("Made with Streamlit")) n.nodeValue = n.nodeValue.replace("Made with Streamlit", "Fait avec Streamlit");
  } else if (n.nodeType === 1) {
    n.childNodes.forEach(tr);
  }
}
new MutationObserver(ms => ms.forEach(m => {
  m.addedNodes.forEach(tr);
  if (m.type === "characterData") tr(m.target);
})).observe(d.body, {childList: true, subtree: true, characterData: true});
tr(d.body);
"""


def translate_menu() -> None:
    components.html("<script>const M=" + json.dumps(_MAP, ensure_ascii=False) + ";" + _JS + "</script>", height=0)
