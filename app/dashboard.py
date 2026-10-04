import re
import subprocess
import sys
from pathlib import Path
import streamlit as st
from app.database import get_connection, init_db
from app.get import video_id
from app.profiler import load_rules
from app.scout_router import find_candidates_ex
from app.settings import settings

CATEGORIES: list[str] = ["foot", "anime", "audio"]
CAT_LABELS: dict[str, str] = {"foot": "⚽ foot", "anime": "🎌 anime", "audio": "🎵 audio"}
KINDS: list[str] = ["raw", "pack", "edit"]
BASE_COLUMNS: list[str] = ["video_id", "status", "reason", "title", "category", "kind", "subject", "action", "fps", "bitrate", "channel", "file_path", "created_at"]
ACTIONS: dict[str, list[str]] = {k: v["actions"] for k, v in load_rules()["categories"].items()}

init_db()
st.set_page_config(page_title="clip-scout", layout="wide")
def _counts() -> dict[str, int]:
    rows = get_connection().execute("select status, count(*) as n from downloads group by status").fetchall()
    return {r["status"]: r["n"] for r in rows}

st.title("🎬 clip-scout")
st.caption("Sourcing de rushs bruts · yt-dlp + FFprobe")
_c = _counts()
m1, m2, m3 = st.columns(3)
m1.metric("Téléchargés", _c.get("ok", 0))
m2.metric("Rejetés", _c.get("rejected_inspect", 0) + _c.get("rejected_quality", 0))
m3.metric("Échecs", _c.get("failed", 0))

def _open_folder() -> None:
    win = subprocess.run(["wslpath", "-w", str(settings.base_storage_path)], capture_output=True, text=True).stdout.strip()
    subprocess.Popen(["explorer.exe", win])

st.button("📂 Ouvrir le dossier des téléchargements", on_click=_open_folder)
panel = st.container()
tab_url, tab_search, tab_db = st.tabs(["🔗 URL directe", "🔍 Recherche", "🗄️ Base"])

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"

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
    targets = [(job["video_id"], job["proc"].pid)] if job and job["proc"].poll() is None else running_jobs()
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

def launch(candidate: dict, category: str, subject: str, action: str, kind: str) -> None:
    vid = candidate["video_id"]
    url = candidate.get("url") or f"https://www.youtube.com/watch?v={vid}"
    LOGS.mkdir(exist_ok=True)
    log = LOGS / f"{vid}.log"
    cmd = [sys.executable, "-m", "app.get", url, "--category", category, "--subject", subject, "--action", action, "--kind", kind]
    with log.open("w") as fh:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    (LOGS / f"{vid}.pid").write_text(str(proc.pid))
    st.session_state["job"] = {"proc": proc, "video_id": vid, "log": str(log)}

def render_job() -> None:
    job = st.session_state.get("job")
    if not job:
        orphans = running_jobs()
        if orphans:
            st.info(f"En cours (reprise) : {orphans[0][0]}")
            if st.button("Annuler", key="cancel_orphan"):
                cancel()
                st.rerun()
        else:
            stale = [r["video_id"] for r in get_connection().execute("select video_id from downloads where status = 'pending'")]
            if stale:
                st.warning("pending sans processus : " + ", ".join(stale))
                if st.button("Marquer failed", key="mark_failed"):
                    from app.database import update_status
                    for v in stale:
                        update_status(v, "failed", reason="orphelin")
                    st.rerun()
        return
    running = job["proc"].poll() is None
    row = get_connection().execute("select status, reason from downloads where video_id = ?", (job["video_id"],)).fetchone()
    status = row["status"] if row else "inconnu"
    reason = (row["reason"] if row else "") or ""
    if running:
        st.info(f"En cours : {job['video_id']} — statut : {status}")
        pct = _progress(job["log"])
        if pct is not None:
            st.progress(pct / 100, text=f"{pct:.0f} %")
        if st.button("Annuler", key="cancel_job"):
            cancel()
            st.rerun()
        return
    if status == "ok":
        st.success(f"{job['video_id']} — statut : ok")
    else:
        st.warning(f"{job['video_id']} — statut : {status}" + (f" — {reason}" if reason else ""))
    st.code("\n".join(Path(job["log"]).read_text().strip().splitlines()[-3:]))
    if not job.get("done"):
        job["done"] = True
        st.rerun()

def download(candidate: dict, category: str, subject: str, action: str, kind: str) -> None:
    if busy():
        st.warning("Un téléchargement est déjà en cours")
        return
    launch(candidate, category, subject, action, kind)

def _progress(log: str) -> float | None:
    try:
        tail = Path(log).read_text(errors="ignore")[-2000:]
    except OSError:
        return None
    hits = re.findall(r"(\d{1,3}(?:\.\d+)?)%", tail)
    return min(float(hits[-1]), 100.0) if hits else None

_STATUS_COLORS: dict[str, str] = {"ok": "green", "failed": "red", "rejected_inspect": "orange", "rejected_quality": "orange", "excluded_game": "gray", "pending": "blue"}

def _fmt_dur(d: float | None) -> str:
    if not d:
        return "?"
    m, sec = divmod(int(d), 60)
    return f"{m}:{sec:02d}"

with tab_url:
    url = st.text_input("URL")
    st.caption("URL directe : exclusions de mots-clés ignorées, seuils fps/kbps/hauteur appliqués au type raw.")
    cat = st.selectbox("Catégorie", CATEGORIES, key="u_cat", format_func=CAT_LABELS.get)
    kind = st.selectbox("Type", KINDS, key="u_kind")
    if st.button("Télécharger", key="u_go", disabled=busy()) and url:
        try:
            vid = video_id(url)
            download({"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}"}, cat, "manual", "manual", kind)
        except SystemExit as exc:
            st.error(str(exc))

with tab_search:
    c1, c2, c3, c4, c5 = st.columns(5)
    s_cat = c1.selectbox("Catégorie", CATEGORIES, key="s_cat", format_func=CAT_LABELS.get)
    subject = c2.text_input("Sujet")
    action = c3.selectbox("Action", ACTIONS[s_cat], key="s_action")
    s_kind = c4.selectbox("Type", KINDS, key="s_kind")
    limit = c5.number_input("Limite", 1, 20, 5)
    if st.button("Chercher", type="primary") and subject and action:
        items, stats = find_candidates_ex(s_cat, subject, action, int(limit), s_kind)
        st.session_state["search"] = {"ctx": (s_cat, subject, action, s_kind), "items": items, "stats": dict(stats)}
    state = st.session_state.get("search", {"ctx": (s_cat, subject, action, s_kind), "items": [], "stats": {}})
    statuses = {r["video_id"]: r["status"] for r in get_connection().execute("select video_id, status from downloads")}
    ctx = state["ctx"]
    if state["stats"]:
        st.markdown(f"**{state['stats'].get('kept', 0)}** retenus")
        with st.expander("Détails du filtrage"):
            st.caption(" · ".join(f"{k}: {v}" for k, v in state["stats"].items() if v))
    if "search" in st.session_state and not state["items"]:
        st.info("Aucun candidat retenu : élargis le sujet ou change l'action.")
    for i, cand in enumerate(state["items"]):
        status = statuses.get(cand["video_id"])
        vid = cand["video_id"]
        blocked = busy() or (status is not None and status != "failed")
        with st.container(border=True):
            img, body, act = st.columns([2, 6, 2], vertical_alignment="center")
            img.image(f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg", width=170)
            body.markdown(f"**{cand['title']}**")
            body.caption(f"{_fmt_dur(cand.get('duration'))} · {cand.get('channel')} · `{vid}`")
            if status:
                body.markdown(f":{_STATUS_COLORS.get(status, 'gray')}-badge[{status}]")
            act.link_button("Ouvrir", f"https://www.youtube.com/watch?v={vid}", width="stretch")
            if act.button("Télécharger", key=f"dl_{i}", disabled=blocked, type="primary", width="stretch"):
                download(cand, *ctx)

with tab_db:
    raw_rows = [dict(r) for r in get_connection().execute("select * from downloads order by rowid desc")]
    rows = [{k: r.get(k) for k in BASE_COLUMNS} for r in raw_rows]
    labels = sorted({r["status"] for r in rows if r.get("status")})
    pick = st.pills("Statut", labels, selection_mode="multi", default=labels)
    q = st.text_input("Rechercher un titre", key="b_q").lower()
    view = [{**r, "lien": f"https://www.youtube.com/watch?v={r['video_id']}"} for r in rows if r["status"] in (pick or labels) and q in (r.get("title") or "").lower()]
    st.dataframe(view, width="stretch", hide_index=True, column_config={"lien": st.column_config.LinkColumn("Lien", display_text="Ouvrir")})
    st.caption(f"{len(view)} / {len(rows)} lignes")

with panel:
    st.fragment(render_job, run_every=5 if busy() else None)()
