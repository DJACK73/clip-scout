import re
import subprocess
import sys
from pathlib import Path
import streamlit as st
from app.database import all_downloads, init_db, job_row, ok_files, pending_ids, status_counts, status_reasons
from app.get import video_id
from app.profiler import load_rules
from app.scout_router import find_candidates_ex
from app.settings import settings
from app.paths import free_disk_gb
from app.slug import slug

CATEGORIES: list[str] = ["foot", "anime", "audio"]
CAT_LABELS: dict[str, str] = {"foot": "⚽ foot", "anime": "🎌 anime", "audio": "🎵 audio"}
KINDS: list[str] = ["raw", "pack", "edit"]
BASE_COLUMNS: list[str] = ["video_id", "status", "reason", "title", "category", "kind", "subject", "action", "fps", "bitrate", "channel", "file_path", "created_at"]
ACTIONS: dict[str, list[str]] = {k: v["actions"] for k, v in load_rules()["categories"].items()}
OTHER_ACTION: str = "✏️ Autre…"
SP_RECENT: str = "CAI%3D"

init_db()
st.set_page_config(page_title="clip-scout", layout="wide")
def _counts() -> dict[str, int]:
    return status_counts()

st.markdown("<style>[data-testid='stAppDeployButton']{display:none}</style>", unsafe_allow_html=True)
from app.menu_fr import translate_menu
translate_menu()
def _open_folder() -> None:
    win = subprocess.run(["wslpath", "-w", str(settings.base_storage_path)], capture_output=True, text=True).stdout.strip()
    subprocess.Popen(["explorer.exe", win])

def _pill(sel: str, color: str) -> str:
    return (
        f"{sel} button{{background:transparent;border:1px solid rgba(128,128,128,.28);border-left:3px solid {color};color:inherit;border-radius:6px;min-height:2rem;padding:0 .8rem;font-weight:500;font-size:.82rem;transition:border-color .15s,background .15s}}"
        f"{sel} button:hover{{border-color:{color};background:color-mix(in srgb,{color} 12%,transparent)}}"
        f"{sel} button p{{color:inherit;font-size:.82rem}}"
    )


st.markdown(
    "<style>"
    "[data-testid='stMainBlockContainer']{padding-top:2.6rem;max-width:1120px}"
    "[data-testid='stMetric']{padding:.8rem 1.1rem;border-radius:14px}"
    "[data-testid='stMetricValue']{font-size:1.75rem;font-weight:600;letter-spacing:-.01em}"
    "[data-testid='stMetricLabel'] p{font-size:.8rem;opacity:.6}"
    "[data-baseweb='tab-list']{gap:.4rem}"
    "[data-baseweb='tab']{height:2.7rem;padding:0 1.1rem;outline:none!important;box-shadow:none!important}"
    "[data-baseweb='tab'] p{font-weight:600;font-size:.95rem}"
    "[data-testid='stWidgetLabel'] p{font-size:.8rem;font-weight:500;opacity:.7}"
    "[data-testid='stAlert']{border-radius:12px}"
    "[data-testid='stExpander']{border-radius:14px}"
    "[data-testid='stDataFrame']{border-radius:14px;overflow:hidden}"
    "[class*='st-key-card_']{border-radius:14px;padding:.3rem;transition:border-color .15s}"
    "[class*='st-key-card_']:hover{border-color:rgba(128,128,128,.55)}"
    "[class*='st-key-card_'] img{border-radius:10px}"
    ".st-key-s_go button,.st-key-u_go button{min-height:2.5rem;padding:0 1.8rem;font-weight:600;border-radius:10px}"
    ".cs-title{font-size:1.5rem;font-weight:700;letter-spacing:-.01em;line-height:1.25}"
    ".cs-sub{font-size:.8rem;opacity:.55;margin:.1rem 0 .8rem}"
    "[data-testid='stPopoverBody']{min-width:min(900px,92vw);max-width:92vw}"
    + _pill(".st-key-pop_guide", "#0ea5e9")
    + _pill(".st-key-pop_actions", "#f59e0b")
    + _pill(".st-key-open_dir", "#14b8a6")
    + "</style>",
    unsafe_allow_html=True,
)
_t, _g, _a, _o = st.columns([4, 1.3, 1.5, 2.2], vertical_alignment="center")
_t.markdown("<div class='cs-title'>🎬 clip-scout</div><div class='cs-sub'>Sourcing de rushs bruts · yt-dlp + FFprobe</div>", unsafe_allow_html=True)
_pg = _g.popover("ℹ️ Guide", key="pop_guide", width="stretch")
_pa = _a.popover("📖 Actions", key="pop_actions", width="stretch")
_o.button("📂 Ouvrir le dossier", key="open_dir", on_click=_open_folder, width="stretch")
with _pg:
    st.caption("**Étapes** : Chercher → Choisir → Télécharger. Un clip déjà téléchargé ou déjà rejeté n'est jamais retéléchargé (badge « doublon » / « rejeté »).")
    st.caption("**Sujet** : titre d'anime, joueur ou genre. Peut rester vide pour les actions foot (sauf big_matches et star_vs_stadium) et audio, et pour anime (fights_aura, rage_screams, sad_backstory) : recherche sur tous les sujets, rangement dans le dossier `multi`.")
    st.caption("**Précision** : mot libre ajouté à la requête (ex. un millésime ou deux noms de personnages).")
    st.caption("**Action** : le type de scène cherché, envoyé tel quel à YouTube. `✏️ Autre…` = action libre.")
    st.caption("**Formats foot spéciaux** : angle_goals = buts marqués depuis un angle très fermé, près de la ligne de but (façon Yamal) · rabona_goals = rabonas (frappe pied d'appui croisé derrière la jambe) · backheel_goals = buts du talon · nutmegs = petits ponts (ballon passé entre les jambes) · solo_goals = buts après un long dribble en solitaire · gk_goals = buts marqués par des gardiens. Ce sont des requêtes YouTube en anglais, pas des filtres : la pertinence dépend des titres, vérifie avant de télécharger.")
    st.caption("**Type raw** : scène brute, sources natives. **pack** : clips pour edits / scenepacks. **edit** : AMV et edits déjà montés. En pack et en edit, l'action est ignorée : seuls Sujet et Précision comptent.")
    st.caption("**Autorisation** : images/s (fps), débit (bitrate) ou hauteur sous le seuil de la catégorie demandent une confirmation avant téléchargement. Durée : anime 60-800 s (de 5 à 1200 s avec autorisation), foot jusqu'à 720 s, audio jusqu'à 600 s (musique : 60 s minimum) ; au-delà, écartée.")
    st.caption("**Audio seul** (catégorie audio, toutes actions) : télécharge uniquement la piste son en .m4a, sans image, bien plus léger qu'une vidéo. Les seuils vidéo (fps, hauteur, débit) sont ignorés, la durée reste contrôlée. Un titre déjà téléchargé en vidéo n'est pas retéléchargé (doublon) : supprime-le via le Nettoyage manuel ou choisis un autre titre.")
    st.caption("**Période** (foot, anime) : filtre YouTube « cette semaine » / « ce mois », classement par pertinence ; pas de tri par date ni de tri ascendant (pour une vidéo ancienne, mets un millésime en Précision). **Tri** (trending_music, phonk, sad_music, music_*) : Tendance semaine/mois = les plus vues sur la période, avec un minimum de vues pour écarter les titres confidentiels ; trending_music cherche des sons « slowed reverb edit » (ralentis avec écho) et phonk des sons « phonk edit », ceux utilisés dans les montages. Sans copyright (music_* seulement) = case Creative Commons de l'uploadeur, pas une garantie de licence. Destinations : music_anime, music_foot, music_both (croisement anime × foot) ; en Sans copyright, requêtes de remplacement (phonk / sport / générique) car la musique libre n'est pas spécifique à l'anime.")
with _pg:
    st.caption("**Thème** : menu ⋮ en haut à droite → Système (auto), Clair ou Sombre.")
_ACTION_HELP: dict[str, dict[str, str]] = {
    "foot": {
        "angle_goals": "buts à angle fermé", "rabona_goals": "rabonas", "backheel_goals": "buts du talon", "nutmegs": "petits ponts", "solo_goals": "buts en solitaire", "gk_goals": "buts de gardiens", "freekicks": "coups francs", "penalties": "penaltys", "celebrations": "célébrations de buts",
        "long_shots": "frappes de loin", "dribbles_skills": "dribbles et gestes techniques",
        "assists": "passes décisives", "general_comps": "compilations générales",
        "tiki_taka": "jeu de passes courtes", "bicycle_kicks": "retournés acrobatiques",
        "saves": "arrêts de gardien", "tackles": "tacles", "headers": "têtes",
        "counter_attacks": "contre-attaques", "hattricks": "triplés", "one_vs_one": "duels un contre un",
        "strength_duels": "duels physiques, force des joueurs", "best_moments": "meilleurs moments",
        "crazy_moments": "moments fous et insolites",
        "big_matches": "grandes rencontres et derbys entre deux clubs (sujet obligatoire : les deux equipes)",
        "star_vs_stadium": "un grand joueur qui fait taire ou applaudir un stade adverse (sujet obligatoire)",
    },
    "anime": {
        "fights_aura": "combats avec aura", "badass_walks": "marches et entrées classes",
        "rage_screams": "cris de rage", "sad_backstory": "passés tristes",
        "funny_chill": "scènes drôles et détente", "general_scenepacks": "lots de scènes variées à monter",
        "transformations": "transformations", "villain_moments": "moments de méchants",
        "plot_twists": "retournements de situation", "training_arcs": "arcs d'entraînement",
        "emotional_reunions": "retrouvailles émouvantes", "romance_moments": "moments romantiques",
    },
    "audio": {
        "trending_music": "musiques tendance (sons slowed reverb utilisés en edits)", "voicelines": "répliques de personnages",
        "sfx": "effets sonores", "phonk": "phonk (sons d'edits, style agressif)", "ambience": "ambiances",
        "transitions": "sons de transition", "meme_sounds": "sons de mèmes",
        "cinematic_hits": "impacts cinématiques", "music_anime": "musique pour anime (AMV)",
        "music_foot": "musique pour foot", "music_both": "musique pour anime et foot",
        "sad_music": "musique triste (sons slowed reverb d'edits tristes)",
    },
}
with _pa:
    for _col, _cat in zip(st.columns(3), CATEGORIES):
        _col.markdown(
            f"**{CAT_LABELS[_cat]}**\n\n"
            + "\n".join(f"- `{a}` : {_ACTION_HELP[_cat].get(a, '')}" for a in ACTIONS[_cat])
        )
    st.caption(
        "**Vocabulaire** : raw = brut (source native, non montée) · pack = lot de clips à monter · "
        "edit = vidéo déjà montée (AMV) · fps = images par seconde · bitrate = débit (kbps) · "
        "needs_confirm = à confirmer (autorisation requise) · doublon = déjà téléchargé · "
        "rejeté = refusé par les seuils de qualité · purged = supprimé par toi · failed = échec · "
        "multi = dossier sans sujet précis · slowed + reverb = musique ralentie avec écho · phonk = style de musique des edits sportifs et anime · Tendance = classement par nombre de vues sur la période."
    )
_c = _counts()
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Téléchargés", _c.get("ok", 0), border=True)
m2.metric("Rejetés", _c.get("rejected_inspect", 0) + _c.get("rejected_quality", 0), border=True)
m3.metric("Échecs", _c.get("failed", 0), border=True)
m4.metric("Supprimés", _c.get("purged", 0), border=True)
m5.metric("Disque libre", f"{free_disk_gb():.0f} Go", border=True)

from app.guard import pot_up
if not pot_up():
    st.warning("Serveur PO token arrêté : docker start bgutil-pot")
panel = st.container()
tab_search, tab_url, tab_db = st.tabs(["🔍 Recherche", "🔗 URL directe", "🗄️ Base"])

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
MAX_PAR = 3

def _alive(pid: int) -> bool:
    try:
        return b"app.get" in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False

def running_jobs() -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for f in LOGS.glob("*.pid"):
        try:
            pid = int(f.read_text().strip())
        except ValueError:
            f.unlink(missing_ok=True)
            continue
        if _alive(pid):
            out.append((f.stem, pid))
        else:
            f.unlink(missing_ok=True)
    return out

def cancel() -> None:
    import os
    import signal
    import time as _t
    from app.cleanup import purge_partials
    from app.database import update_status
    job = st.session_state.get("job")
    targets = running_jobs()
    for vid, pid in targets:
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            pass
        _t.sleep(1)
        n = purge_partials(vid)
        with (LOGS / f"{vid}.log").open("a") as fh:
            fh.write(f"cancel: {n} partiels purgés\n")
        update_status(vid, "failed", reason="annulé")
        (LOGS / f"{vid}.pid").unlink(missing_ok=True)

def busy() -> bool:
    job = st.session_state.get("job")
    if job and job["proc"].poll() is None:
        return True
    return bool(running_jobs())

def launch(candidate: dict, category: str, subject: str, action: str, kind: str, allow_low_fps: bool = False, audio_fmt: str = "") -> None:
    vid = candidate["video_id"]
    url = candidate.get("url") or f"https://www.youtube.com/watch?v={vid}"
    LOGS.mkdir(exist_ok=True)
    log = LOGS / f"{vid}.log"
    cmd = [sys.executable, "-m", "app.get", url, "--category", category, "--subject", subject, "--action", action, "--kind", kind]
    if allow_low_fps:
        cmd.append("--allow-low-fps")
    if category == "audio" and st.session_state.get("s_audio"):
        cmd.append("--audio-only")
    if audio_fmt:
        cmd += ["--audio-only", "--audio-fmt", audio_fmt]
    with log.open("w") as fh:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    (LOGS / f"{vid}.pid").write_text(str(proc.pid))
    st.session_state["job"] = {"proc": proc, "video_id": vid, "log": str(log), "args": (candidate, category, subject, action, kind)}

def render_job() -> None:
    import time as _t
    _q = st.session_state.get("queue")
    _n = 0
    while _q and len(running_jobs()) < MAX_PAR:
        if _n:
            _t.sleep(2)
        launch(*_q.pop(0))
        _n += 1
    job = st.session_state.get("job")
    for _v, _pid in running_jobs():
        if not job or _v != job["video_id"]:
            st.info(f"En cours : {_v}")
            _p = _progress(str(LOGS / f"{_v}.log"))
            st.progress((_p or 0) / 100, text=f"{_p:.0f} %" if _p is not None else "Téléchargement en cours…")
    if _q:
        st.caption(f"En attente : {len(_q)}")
    if not job:
        orphans = running_jobs()
        if orphans:
            st.info(f"En cours (reprise) : {orphans[0][0]}")
            if st.button("Annuler", key="cancel_orphan"):
                cancel()
                st.rerun()
        else:
            stale = pending_ids()
            if stale:
                st.warning("pending sans processus : " + ", ".join(stale))
                if st.button("Marquer failed", key="mark_failed"):
                    from app.database import update_status
                    for v in stale:
                        update_status(v, "failed", reason="orphelin")
                    st.rerun()
        return
    running = job["proc"].poll() is None
    row = job_row(job["video_id"])
    status = row["status"] if row else "inconnu"
    reason = (row["reason"] if row else "") or ""
    if running:
        st.info(f"En cours : {job['video_id']} — statut : {status}")
        pct = _progress(job["log"])
        st.progress((pct or 0) / 100, text=f"{pct:.0f} %" if pct is not None else "Téléchargement en cours…")
        if st.button("Tout annuler", key="cancel_job"):
            cancel()
            st.rerun()
        return
    if status == "ok":
        st.success(f"{job['video_id']} — statut : ok")
    else:
        st.warning(f"{job['video_id']} — statut : {status}" + (f" — {reason}" if reason else ""))
        if status == "needs_confirm" and job.get("args") and st.button("Autoriser et télécharger", key="allow_fps_job"):
            launch(*job["args"], allow_low_fps=True)
            st.rerun()
    st.code("\n".join(Path(job["log"]).read_text().strip().splitlines()[-3:]))
    if not job.get("done"):
        job["done"] = True
        st.rerun()

def download(candidate: dict, category: str, subject: str, action: str, kind: str, allow_low_fps: bool = False) -> None:
    if busy():
        st.warning("Un téléchargement est déjà en cours")
        return
    launch(candidate, category, subject, action, kind, allow_low_fps)

def _progress(log: str) -> float | None:
    try:
        tail = Path(log).read_text(errors="ignore")[-2000:]
    except OSError:
        return None
    hits = re.findall(r"(\d{1,3}(?:\.\d+)?)%", tail)
    return min(float(hits[-1]), 100.0) if hits else None

def _category_files(cat: str) -> list[tuple[str, Path]]:
    root = Path(settings.base_storage_path).resolve()
    rows = ok_files(cat)
    out: list[tuple[str, Path]] = []
    for r in rows:
        p = Path(r["file_path"])
        if p.is_file() and root in p.resolve().parents:
            out.append((r["video_id"], p))
    return out

def _purge_category(cat: str) -> tuple[int, int]:
    from app.database import update_status
    files = _category_files(cat)
    size = 0
    for vid, p in files:
        size += p.stat().st_size
        p.unlink(missing_ok=True)
        update_status(vid, "purged")
    base = Path(settings.base_storage_path) / cat
    dirs = sorted((d for d in base.rglob("*") if d.is_dir()), key=lambda d: len(d.parts), reverse=True)
    for d in dirs:
        try:
            d.rmdir()
        except OSError:
            pass
    return len(files), size // 1_000_000

_STATUS_COLORS: dict[str, str] = {"ok": "green", "failed": "red", "rejected_inspect": "orange", "rejected_quality": "orange", "excluded_game": "gray", "pending": "blue", "needs_confirm": "violet"}

def _stepper(active: int) -> str:
    parts = []
    for i, name in enumerate(["Chercher", "Choisir", "Télécharger"]):
        if i < active:
            parts.append(f":green[✓ {name}]")
        elif i == active:
            parts.append(f":orange[● **{name}**]")
        else:
            parts.append(f":gray[{name}]")
    return " → ".join(parts)

def _fmt_dur(d: float | None) -> str:
    if not d:
        return "?"
    m, sec = divmod(int(d), 60)
    return f"{m}:{sec:02d}"

def _fmt_views(v: int | None) -> str:
    if not v:
        return ""
    return f" · {v / 1e6:.1f} M vues" if v >= 1_000_000 else f" · {v / 1e3:.0f} k vues" if v >= 1000 else f" · {v} vues"

_CAT_COLORS: dict[str, str] = {"foot": "#16a34a", "anime": "#e11d48", "audio": "#7c3aed"}
_KIND_COLORS: dict[str, str] = {"raw": "#2563eb", "pack": "#d97706", "edit": "#db2777"}


def _btn_css(sel: str, color: str) -> str:
    return (
        f"{sel} button{{background:transparent;border:1px solid rgba(128,128,128,.28);border-left:3px solid {color};color:inherit;border-radius:6px;min-height:2rem;padding:0 .8rem;font-weight:500;font-size:.82rem;transition:border-color .15s,background .15s}}"
        f"{sel} button:hover{{border-color:{color};background:color-mix(in srgb,{color} 12%,transparent)}}"
        f"{sel} button p{{color:inherit;font-size:.82rem}}"
        f"{sel} button[data-testid='stBaseButton-primary']{{background:{color};border-color:{color};color:#fff}}"
    )


def _solid(sel: str, color: str) -> str:
    return (
        f"{sel} button{{background:{color};border:1px solid {color};color:#fff;border-radius:6px;min-height:2.2rem;padding:0 1rem;font-weight:600}}"
        f"{sel} button:hover{{filter:brightness(1.15);border-color:{color};color:#fff}}"
        f"{sel} button p{{color:#fff;font-size:.9rem}}"
    )


def _pick(col, key: str, label: str, value: str, skey: str) -> None:
    col.button(
        label,
        key=key,
        type="primary" if st.session_state.get(skey) == value else "secondary",
        use_container_width=True,
        on_click=st.session_state.__setitem__,
        args=(skey, value),
    )


with tab_url:
    urls = st.text_area("URL ou nom (1 par ligne, max 4)", key="u_urls", height=110)
    u_fmt = st.radio("Format", ["Vidéo", "m4a", "mp3"], horizontal=True, key="u_fmt")
    st.caption("URL directe : exclusions de mots-clés ignorées, seuils fps/kbps/hauteur appliqués au type raw.")
    st.session_state.setdefault("u_cat", "foot")
    st.session_state.setdefault("u_kind", "raw")
    _uc = st.columns([1, 1, 1, 0.3, 1, 1, 1, 2.7])
    for _c, _k in zip(_uc[:3], CATEGORIES):
        _pick(_c, f"ucat_{_k}", CAT_LABELS[_k], _k, "u_cat")
    for _c, _k in zip(_uc[4:7], KINDS):
        _pick(_c, f"uknd_{_k}", _k, _k, "u_kind")
    cat = st.session_state["u_cat"]
    kind = st.session_state["u_kind"]
    st.markdown(
        "<style>"
        + "".join(_btn_css(f".st-key-ucat_{k}", _CAT_COLORS[k]) for k in CATEGORIES)
        + "".join(_btn_css(f".st-key-uknd_{k}", _KIND_COLORS[k]) for k in KINDS)
        + "</style>",
        unsafe_allow_html=True,
    )
    if st.button("Télécharger", key="u_go", disabled=bool(st.session_state.get("queue")) or len(running_jobs()) >= MAX_PAR) and urls.strip():
        from app.search_ytdlp import first_hit
        _fmt = {"Vidéo": "", "m4a": "m4a", "mp3": "mp3"}[u_fmt]
        _items, _seen = [], set()
        for _line in [x.strip() for x in urls.splitlines() if x.strip()][:4]:
            try:
                if _line.startswith("http"):
                    _vid = video_id(_line)
                    _cand = {"video_id": _vid, "url": f"https://www.youtube.com/watch?v={_vid}"}
                else:
                    _cand = first_hit(_line, bool(_fmt))
                    if not _cand:
                        st.error(f"introuvable : {_line}")
                        continue
            except (SystemExit, Exception) as exc:
                st.error(f"{_line} : {exc}")
                continue
            if _cand["video_id"] not in _seen:
                _seen.add(_cand["video_id"])
                _items.append((_cand, cat, "manual", "manual", kind, False, _fmt))
        if _items:
            st.session_state["queue"] = _items
            st.rerun()
    if cat == "audio" or u_fmt != "Vidéo":
        st.caption("⚠️ Musique : œuvres protégées par le droit d'auteur. Usage personnel uniquement, ne pas republier sans licence.")

with tab_search:
    step_slot = st.empty()
    st.session_state.setdefault("s_cat", "foot")
    st.session_state.setdefault("s_kind", "raw")
    _cols = st.columns([1, 1, 1, 0.3, 1, 1, 1, 2.7])
    for _c, _k in zip(_cols[:3], CATEGORIES):
        _pick(_c, f"cat_{_k}", CAT_LABELS[_k], _k, "s_cat")
    for _c, _k in zip(_cols[4:7], KINDS):
        _pick(_c, f"knd_{_k}", _k, _k, "s_kind")
    s_cat = st.session_state["s_cat"]
    s_kind = st.session_state["s_kind"]
    _acts = ACTIONS[s_cat] + [OTHER_ACTION]
    if st.session_state.get("s_action") not in _acts:
        st.session_state["s_action"] = _acts[0]
    st.markdown(
        "<style>"
        + "".join(_btn_css(f".st-key-cat_{k}", _CAT_COLORS[k]) for k in CATEGORIES)
        + "".join(_btn_css(f".st-key-knd_{k}", _KIND_COLORS[k]) for k in KINDS)
        + "</style>",
        unsafe_allow_html=True,
    )
    c2, c3, d1, d2, d4, _pad = st.columns([2, 2, 2, 2, 1, 3])
    precision = c3.text_input("Précision (optionnel)")
    choice = d1.selectbox("Action", _acts, key="s_action")
    free = choice == OTHER_ACTION
    custom = d2.text_input("Action libre", key="s_custom", disabled=not free)
    limit = d4.number_input("Limite", 1, 20, 5)
    if s_cat == "audio":
        _pad.checkbox("🎧 Audio seul (.m4a)", key="s_audio")
    _frules = load_rules()["categories"][s_cat]
    _opt = (not free) and s_kind == "raw" and choice in _frules.get("subject_optional", [])
    _sp_modes = _frules.get("sp_modes", {})
    _cc_ok = choice in _frules.get("action_query", {})
    _music = (not free) and choice in _frules.get("trend_actions", list(_frules.get("action_query", {})))
    _sort_opts = (["Standard", "Tendance semaine", "Tendance mois"] + (["Sans copyright"] if _cc_ok else [])) if _music else ["Pertinence"]
    _sort_key = {"Tendance semaine": "week", "Tendance mois": "month", "Sans copyright": "cc", "Plus récentes": "recent"}
    _periods = {"Tout": None, "Cette semaine": "EgIIAw%3D%3D", "Ce mois": "EgIIBA%3D%3D"}
    if _music:
        sort_label = st.segmented_control("Tri", _sort_opts, default=_sort_opts[0], key="s_sort_m_cc" if _cc_ok else "s_sort_m") or _sort_opts[0]
    else:
        sort_label = st.segmented_control("Période", list(_periods), default="Tout", key="s_period") or "Tout"
    _mode = _sort_key.get(sort_label)
    sp = (_sp_modes.get(_mode) if _mode else None) if _music else _periods[sort_label]
    if _mode == "cc":
        st.caption("Filtre Creative Commons de l'uploadeur : pas une garantie de licence.")
    _hint = ""
    subject = c2.text_input("Sujet" + (" (optionnel)" if _opt else ""), key="s_subject", placeholder=_hint)
    subj = subject.strip()
    action = custom.strip() if free else choice
    store_action = slug(action) if free else action
    if st.button("Chercher", key="s_go", type="primary", disabled=not ((subj or _opt) and action)):
        with st.spinner("Recherche en cours…"):
            items, stats = find_candidates_ex(s_cat, subj, action, int(limit), s_kind, precision.strip(), free, sp)
        st.session_state["search"] = {"ctx": (s_cat, subj or "multi", store_action, s_kind), "items": items, "stats": dict(stats), "limit": int(limit), "sort": sort_label}
    state = st.session_state.get("search", {"ctx": (s_cat, subject, action, s_kind), "items": [], "stats": {}})
    _rows = status_reasons()
    statuses = {r["video_id"]: r["status"] for r in _rows}
    reasons = {r["video_id"]: r["reason"] for r in _rows}
    ctx = state["ctx"]
    if state["stats"]:
        st.markdown(f"**{len(state['items'])}** affichés · limite {state.get('limit', '?')} · tri {state.get('sort', '—')}")
        _s = state["stats"]
        _d, _r, _f = _s.get("shown_duplicates", 0), _s.get("shown_rejected", 0), _s.get("refilled", 0)
        st.caption(f"{len(state['items']) - _d - _r - _f} neufs · {_f} complétés · {_d} doublons · {_r} rejetés")
        with st.expander("Détails du filtrage"):
            st.caption(" · ".join(f"{k}: {v}" for k, v in state["stats"].items() if v))
    if state["items"] and state.get("limit") not in (None, int(limit)):
        st.warning(f"Résultats obtenus avec la limite {state['limit']} (champ actuel : {int(limit)}) : relance Chercher.")
    if "search" in st.session_state and not state["items"]:
        st.info("Aucun candidat retenu : élargis le sujet ou change l'action.")
    for i, cand in enumerate(state["items"]):
        status = statuses.get(cand["video_id"])
        vid = cand["video_id"]
        need = status == "needs_confirm"
        dup = bool(cand.get("duplicate")) or status in ("ok", "pending", "downloaded", "excluded_game")
        rej = bool(cand.get("rejected")) or status in ("rejected_inspect", "rejected_quality")
        blocked = busy() or dup or rej
        with st.container(border=True, key=f"card_{i}"):
            img, body, act = st.columns([2, 6, 2], vertical_alignment="center")
            img.image(f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg", width=170)
            body.markdown(f"**{cand['title']}**")
            body.caption(f"{_fmt_dur(cand.get('duration'))}{_fmt_views(cand.get('view_count'))} · {cand.get('channel')} · score {cand.get('score', '?')} · `{vid}`")
            if dup:
                body.markdown(":orange-badge[doublon]" + (f" :gray-badge[{status}]" if status else " :gray-badge[titre déjà vu]"))
            elif rej:
                body.markdown(":red-badge[rejeté]")
                if reasons.get(vid):
                    body.caption(reasons[vid])
            elif status:
                body.markdown(f":{_STATUS_COLORS.get(status, 'gray')}-badge[{status}]")
                if need and reasons.get(vid):
                    body.caption(reasons[vid])
            act.link_button("Ouvrir", f"https://www.youtube.com/watch?v={vid}", width="stretch")
            if act.button("Déjà téléchargé" if dup else "Déjà rejeté" if rej else "Autoriser" if need else "Télécharger", key=f"dl_{i}", disabled=blocked, type="primary", width="stretch"):
                download(cand, *ctx, allow_low_fps=need)

with tab_db:
    order = st.segmented_control("Tri", ["Plus récents", "Plus anciens"], default="Plus récents", key="b_order") or "Plus récents"
    raw_rows = all_downloads(order == "Plus récents")
    rows = [{k: r.get(k) for k in BASE_COLUMNS} for r in raw_rows]
    labels = sorted({r["status"] for r in rows if r.get("status")})
    pick = st.pills("Statut", labels, selection_mode="multi", default=labels)
    q = st.text_input("Rechercher un titre", key="b_q").lower()
    view = [{**r, "lien": f"https://www.youtube.com/watch?v={r['video_id']}"} for r in rows if r["status"] in (pick or labels) and q in (r.get("title") or "").lower()]
    st.dataframe(view, width="stretch", hide_index=True, column_config={"lien": st.column_config.LinkColumn("Lien", display_text="Ouvrir")})
    st.caption(f"{len(view)} / {len(rows)} lignes")
    st.divider()
    msg = st.session_state.pop("purge_msg", None)
    if msg:
        st.success(msg)
    with st.expander("🧹 Nettoyage manuel (à faire à la fin)", expanded=bool(st.session_state.get("purge_ask"))):
        st.caption("Supprime les vidéos téléchargées (statut ok) d'une catégorie ; la ligne reste en base avec le statut purged.")
        st.markdown(
            "<style>"
            + "".join(_solid(f".st-key-purge_{k}", _CAT_COLORS[k]) for k in CATEGORIES)
            + _solid(".st-key-purge_yes", "#dc2626")
            + _solid(".st-key-purge_no", "#64748b")
            + "[class*='st-key-purge_'] button:disabled{opacity:.35}"
            + "</style>",
            unsafe_allow_html=True,
        )
        for col, pcat in zip(st.columns(3), CATEGORIES):
            pfiles = _category_files(pcat)
            pmb = sum(p.stat().st_size for _, p in pfiles) // 1_000_000
            col.metric(CAT_LABELS[pcat], f"{len(pfiles)} fichiers")
            col.caption(f"{pmb} Mo")
            if col.button(f"🗑️ Supprimer {pcat}", key=f"purge_{pcat}", disabled=not pfiles):
                st.session_state["purge_ask"] = pcat
        ask = st.session_state.get("purge_ask")
        if ask:
            afiles = _category_files(ask)
            st.warning(f"Supprimer définitivement {len(afiles)} vidéo(s) de {ask} ?")
            yes, no, _sp = st.columns([2, 2, 6])
            if yes.button("Confirmer la suppression", key="purge_yes", type="primary", width="stretch"):
                n, mb = _purge_category(ask)
                st.session_state.pop("purge_ask", None)
                st.session_state["purge_msg"] = f"{n} vidéo(s) supprimée(s) ({mb} Mo) — {ask}"
                st.rerun()
            if no.button("Annuler", key="purge_no", width="stretch"):
                st.session_state.pop("purge_ask", None)
                st.rerun()

with panel:
    st.fragment(render_job, run_every=5 if busy() else None)()
step_slot.markdown(_stepper(2 if busy() else 1 if state["items"] else 0))
