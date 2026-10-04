import subprocess
import sys
from pathlib import Path
import streamlit as st
from app.database import get_connection, init_db
from app.get import video_id
from app.profiler import load_rules
from app.scout_router import find_candidates_ex

CATEGORIES: list[str] = ["foot", "anime", "audio"]
KINDS: list[str] = ["raw", "pack", "edit"]
BASE_COLUMNS: list[str] = ["video_id", "status", "reason", "title", "category", "kind", "subject", "action", "fps", "bitrate", "channel", "file_path", "created_at"]
ACTIONS: dict[str, list[str]] = {k: v["actions"] for k, v in load_rules()["categories"].items()}

init_db()
st.set_page_config(page_title="clip-scout", layout="wide")
panel = st.container()
tab_url, tab_search, tab_db = st.tabs(["URL directe", "Recherche", "Base"])

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

with tab_url:
    url = st.text_input("URL")
    st.caption("URL directe : exclusions de mots-clés ignorées, seuils fps/kbps/hauteur appliqués au type raw.")
    cat = st.selectbox("Catégorie", CATEGORIES, key="u_cat")
    kind = st.selectbox("Type", KINDS, key="u_kind")
    if st.button("Télécharger", key="u_go", disabled=busy()) and url:
        try:
            vid = video_id(url)
            download({"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}"}, cat, "manual", "manual", kind)
        except SystemExit as exc:
            st.error(str(exc))

with tab_search:
    c1, c2, c3, c4, c5 = st.columns(5)
    s_cat = c1.selectbox("Catégorie", CATEGORIES, key="s_cat")
    subject = c2.text_input("Sujet")
    action = c3.selectbox("Action", ACTIONS[s_cat], key="s_action")
    s_kind = c4.selectbox("Type", KINDS, key="s_kind")
    limit = c5.number_input("Limite", 1, 20, 5)
    if st.button("Chercher") and subject and action:
        items, stats = find_candidates_ex(s_cat, subject, action, int(limit), s_kind)
        st.session_state["search"] = {"ctx": (s_cat, subject, action, s_kind), "items": items, "stats": dict(stats)}
    state = st.session_state.get("search", {"ctx": (s_cat, subject, action, s_kind), "items": [], "stats": {}})
    statuses = {r["video_id"]: r["status"] for r in get_connection().execute("select video_id, status from downloads")}
    ctx = state["ctx"]
    if state["stats"]:
        st.caption(" · ".join(f"{k}: {v}" for k, v in state["stats"].items()))
    for i, cand in enumerate(state["items"]):
        status = statuses.get(cand["video_id"])
        left, right = st.columns([5, 1])
        dur = cand.get("duration")
        left.write(f"{cand['title']} — {int(dur) if dur else '?'} s — {cand.get('channel')} — `{cand['video_id']}`" + (f" — **{status}**" if status else ""))
        blocked = busy() or (status is not None and status != "failed")
        if right.button("Télécharger", key=f"dl_{i}", disabled=blocked):
            download(cand, *ctx)

with tab_db:
    raw_rows = [dict(r) for r in get_connection().execute("select * from downloads order by rowid desc")]
    rows = [{k: r.get(k) for k in BASE_COLUMNS} for r in raw_rows]
    st.dataframe(rows, width="stretch")

with panel:
    st.fragment(render_job, run_every=5 if busy() else None)()
